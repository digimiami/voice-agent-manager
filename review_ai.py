"""
Review AI — find local businesses with unanswered Google reviews and call them
with a pitch for an AI review-response service (default $99/mo).

Pipeline:
  1. scrape_prospects()   — Playwright Google Maps search → review_prospects rows
                            (name, phone, rating, review_count, place_url)
  2. count_unanswered()   — best-effort per-place count of reviews with NO
                            "Response from the owner" (real number for the pitch)
  3. ensure_assistant()   — creates the Vapi outbound assistant (xai grok-4.3,
                            mark voice) if not present
  4. run_calls()          — background thread: Vapi outbound calls via curl
  5. sync_call_outcomes() — polls Vapi for ended calls, maps to status
  6. send_sample_sms()    — texts the free sample review response (sms-gate)

All state lives in the shared DB (review_prospects, review_ai_calls,
review_ai_settings). Used by the admin panel (admin_panel.py, port 8086).
"""
import asyncio
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
import uuid
from datetime import datetime

DB_PATH = "/root/voice-agent-businesses.db"
VAPI_BASE = "https://api.vapi.ai"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

DEFAULT_SCRIPT = """You are calling the owner of a local business to talk about their Google reviews. Be warm, brief, and completely human — never mention being AI, a bot, or software.

Opening line — say it naturally, using the customer's business name:
"Hi! This is a quick call — I noticed {business_name} has {unanswered} on Google. I run a service that writes personalized responses to every review and posts them with your approval. It's just {pricing} a month."

If they ask what it is:
- We write authentic, on-brand replies to every Google review — positive and negative.
- You approve each response before it's posted. Nothing goes live without your OK.
- We handle posting too, so you never have to think about it.

Offer (important): "Want me to send you a free sample response for your latest review? No commitment at all."
- If they say YES: thank them warmly, confirm you'll text it over right away, and confirm their number is {phone}.
- If they say no or not interested: be friendly, thank them for their time, and hang up. Do NOT push, argue, or call back pressure.

Keep the entire call under 2 minutes. End politely every time."""

DEFAULT_WEBSITE_SCRIPT = """You are calling the owner of a local business that does NOT have a website. Be warm, brief, and completely human — never mention being AI, a bot, or software.

Opening line — say it naturally, using the customer's business name:
"Hi! Quick call — I noticed {business_name} doesn't have a website yet. I build websites for local businesses — mobile-friendly, fast, with your services, hours, contact info and your Google reviews on it — and it's {website_pricing}. Would you like a free preview of what your site would look like?"

If they ask what it includes:
- Modern mobile-first design that works great on phones (most customers search from their phone).
- Your services, hours, contact info, map, directions, and a link to your Google reviews.
- Hosting, maintenance, and updates handled — you don't have to do anything.
- They own the site and everything in it.

Offer (important): "Want me to send you a free preview of what your website would look like? No commitment."
- If they say YES: thank them warmly, confirm their number is {phone}, and tell them the preview is coming.
- If they say no or not interested: be friendly, thank them for their time, and hang up. Do NOT push, argue, or pressure.

Keep the entire call under 2 minutes. End politely every time."""

DEFAULT_SETTINGS = {
    "city": "Miami",
    "state": "FL",
    "categories": "dentist,plumber,auto repair,hair salon,chiropractor,electrician,roofing contractor,law firm",
    "max_per_category": "15",
    "pricing": "$99/mo",
    "script": DEFAULT_SCRIPT,
    "service": "reviews",
    "website_pricing": "$499",
    "website_script": DEFAULT_WEBSITE_SCRIPT,
    "voice_id": "mark",
    "enabled": "1",
    "max_calls_per_run": "5",
    "delay_seconds": "90",
    "assistant_id": "",
    "phone_number_id": "9031d73a-85e4-437e-af27-f6b877a2c039",
    "webhook_url": "https://diazites.online/api/v1/vapi-webhook",
}

_stop_flag = threading.Event()
_running = {"scrape": False, "calls": False, "count": False}
_run_log = []


# ─────────────────────────── DB ───────────────────────────

def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_tables():
    db = _db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS review_prospects (
        id TEXT PRIMARY KEY,
        business_name TEXT, phone TEXT, category TEXT, address TEXT,
        rating REAL, review_count INTEGER, unanswered_count INTEGER,
        place_url TEXT, website TEXT, city TEXT, state TEXT,
        status TEXT DEFAULT 'new',
        last_call_id TEXT, last_outcome TEXT, last_call_at TEXT,
        sample_sent_at TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS review_ai_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prospect_id TEXT, call_id TEXT, status TEXT,
        cost REAL, duration INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS review_ai_settings (
        key TEXT PRIMARY KEY, value TEXT
    );
    """)
    # guarded migration: website column on older DBs
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info(review_prospects)")]
        if "website" not in cols:
            db.execute("ALTER TABLE review_prospects ADD COLUMN website TEXT")
    except Exception:
        pass
    db.commit()
    db.close()


def get_settings():
    init_tables()
    db = _db()
    rows = db.execute("SELECT key, value FROM review_ai_settings").fetchall()
    db.close()
    s = dict(DEFAULT_SETTINGS)
    for r in rows:
        s[r["key"]] = r["value"]
    return s


def save_settings(updates):
    init_tables()
    db = _db()
    for k, v in updates.items():
        if k in DEFAULT_SETTINGS:
            db.execute("INSERT OR REPLACE INTO review_ai_settings (key, value) VALUES (?, ?)",
                       (k, str(v)))
    db.commit()
    db.close()


def vapi_key():
    for path in ("/root/voice-agent-manager/.env", "/root/.env"):
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("VAPI_API_KEY="):
                        return line.split("=", 1)[1].strip()
        except Exception:
            pass
    return os.environ.get("VAPI_API_KEY", "")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    _run_log.append(line)
    _run_log[:] = _run_log[-200:]
    print(line, flush=True)


def running_state():
    return dict(_running)


def recent_log(n=25):
    return _run_log[-n:]


# ─────────────────── Vapi API (curl — bypasses Cloudflare) ───────────────────

def _vapi(method, path, payload=None):
    key = vapi_key()
    if not key:
        return {"error": "VAPI_API_KEY not set"}
    cmd = ["curl", "-s", "--max-time", "30", "-X", method,
           f"{VAPI_BASE}{path}",
           "-H", f"Authorization: Bearer {key}",
           "-H", "Content-Type: application/json",
           "-H", f"User-Agent: {UA}"]
    if payload is not None:
        cmd += ["-d", json.dumps(payload)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
        return json.loads(proc.stdout or "{}")
    except Exception as e:
        return {"error": str(e)}


def ensure_assistant():
    """Create the Review AI assistant if missing. Returns (id, created)."""
    s = get_settings()
    if s.get("assistant_id"):
        # verify it still exists
        d = _vapi("GET", f"/assistant/{s['assistant_id']}")
        if not d.get("error"):
            return s["assistant_id"], False
        save_settings({"assistant_id": ""})
    system_prompt = ("You are calling local business owners about their Google reviews. "
                     "Personalize with the business name and the number of unanswered reviews. "
                     "Be warm and brief. The pitch:\n\n" + s.get("script", DEFAULT_SCRIPT))
    payload = {
        "name": "Review AI — Google Review Responses",
        "firstMessageMode": "assistant-speaks-first",
        "model": {
            "provider": "xai",
            "model": "grok-4.3",
            "maxTokens": 300,
            "temperature": 0.3,
            "systemPrompt": system_prompt,
        },
        "voice": {
            "provider": "11labs",
            "model": "eleven_v3",
            "voiceId": s.get("voice_id", "mark"),
            "stability": 0.4,
            "similarityBoost": 0.85,
            "style": 0.1,
            "useSpeakerBoost": True,
            "speed": 0.97,
        },
        "transcriber": {"provider": "openai", "model": "gpt-4o-transcribe"},
        "serverUrl": s.get("webhook_url", ""),
        "serverMessages": ["end-of-call-report"],
    }
    d = _vapi("POST", "/assistant", payload)
    if d.get("id"):
        save_settings({"assistant_id": d["id"]})
        log(f"🤖 Review AI assistant created: {d['id']}")
        return d["id"], True
    log(f"❌ Assistant creation failed: {str(d)[:200]}")
    return None, False


# ─────────────────── Personalization ───────────────────

def unanswered_text(prospect):
    n = prospect.get("unanswered_count")
    if n is not None:
        return f"{n} unanswered reviews"
    rc = prospect.get("review_count") or 0
    if rc:
        return f"{rc} reviews, several unanswered"
    return "unanswered reviews"


def personalize(prospect, script):
    s = get_settings()
    return (script
            .replace("{business_name}", str(prospect.get("business_name") or "your business"))
            .replace("{unanswered}", unanswered_text(prospect))
            .replace("{pricing}", str(s.get("pricing", "$99/mo")))
            .replace("{website_pricing}", str(s.get("website_pricing", "$499")))
            .replace("{phone}", str(prospect.get("phone") or "")))


def active_script():
    """Script + pricing for the currently selected service mode."""
    s = get_settings()
    if s.get("service") == "website":
        return s.get("website_script") or DEFAULT_WEBSITE_SCRIPT
    return s.get("script") or DEFAULT_SCRIPT


# ─────────────────── Scraper (Playwright) ───────────────────

class ReviewScraper:
    CATEGORIES = {
        "dentist": "dentist", "plumber": "plumber", "electrician": "electrician",
        "auto repair": "auto+repair+shop", "hair salon": "hair+salon",
        "chiropractor": "chiropractor", "roofing contractor": "roofing+contractor",
        "law firm": "law+firm", "accountant": "accountant", "veterinarian": "veterinarian",
        "pet groomer": "pet+groomer", "barber shop": "barber+shop", "gym": "gym",
        "restaurant": "restaurant", "nail salon": "nail+salon", "real estate agent": "real+estate+agent",
        "general contractor": "general+contractor", "insurance agent": "insurance+agent",
        "massage therapist": "massage+therapist", "day spa": "spa", "optician": "optician",
        "pharmacy": "pharmacy", "car dealership": "car+dealership",
    }

    def __init__(self, headless=True):
        self.headless = headless
        self.browser = None
        self.page = None

    async def _init(self):
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage", "--disable-gpu"])
        ctx = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080}, locale="en-US",
            timezone_id="America/New_York", user_agent=UA,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})
        await ctx.add_cookies([
            {"name": "CONSENT", "value": "YES+US.en+V12", "domain": ".google.com", "path": "/"},
            {"name": "SOCS", "value": "CAISHAgBEhJnd3NfMjAyNjA1MjQtMF9SQzEaAmVuIAEaBggAWEAgWg",
             "domain": ".google.com", "path": "/"},
        ])
        self.page = await ctx.new_page()

    async def _close(self):
        try:
            await self.browser.close()
            await self._pw.stop()
        except Exception:
            pass

    async def _dismiss_cookies(self):
        for sel in ('button[aria-label*="Accept"]', 'button[aria-label*="accept"]',
                    'button:has-text("Accept all")', 'form[action*="consent"] button:first-of-type',
                    'div[role="dialog"] button:first-of-type'):
            try:
                btn = await self.page.query_selector(sel)
                if btn:
                    await btn.click()
                    await asyncio.sleep(1)
                    return
            except Exception:
                pass

    async def _scroll_feed(self, selector, max_count, max_scrolls=25):
        try:
            await self.page.wait_for_selector(selector, timeout=8000)
        except Exception:
            return 0
        prev, stalled = 0, 0
        for _ in range(max_scrolls):
            try:
                await self.page.evaluate(
                    "document.querySelector('div[role=\"feed\"]')?.scrollTo(0, 999999)")
            except Exception:
                pass
            await asyncio.sleep(1.2)
            items = await self.page.query_selector_all('a[href*="/maps/place/"]')
            if len(items) >= max_count:
                return len(items)
            if len(items) == prev:
                stalled += 1
                if stalled >= 3:
                    break
            else:
                stalled = 0
            prev = len(items)
        return len(await self.page.query_selector_all('a[href*="/maps/place/"]'))

    async def search(self, city, state, categories, max_per):
        found = []
        for cat in categories:
            if _stop_flag.is_set():
                break
            q = self.CATEGORIES.get(cat, cat.replace(" ", "+"))
            url = f"https://www.google.com/maps/search/{q}+in+{city}+{state}?hl=en"
            log(f"🔍 Searching: {cat} in {city}, {state}")
            await self.page.goto(url, timeout=45000)
            await asyncio.sleep(3)
            await self._dismiss_cookies()
            count = await self._scroll_feed('div[role="feed"]', max_per)
            links = await self.page.query_selector_all('a[href*="/maps/place/"]')
            hrefs = []
            for link in links:
                try:
                    href = await link.get_attribute("href") or ""
                    if href:
                        hrefs.append(href.split("?")[0])
                except Exception:
                    pass
            seen = set()
            processed = 0
            for place_url in hrefs:
                if processed >= max_per:
                    break
                try:
                    if not place_url or place_url in seen:
                        continue
                    seen.add(place_url)
                    # navigate straight to the place page — deterministic extraction
                    await self.page.goto(place_url + "?hl=en", timeout=45000)
                    await asyncio.sleep(2.2)
                    await self._dismiss_cookies()
                    body = await self.page.inner_text("body")
                    name = ""
                    h1 = await self.page.query_selector("h1")
                    if h1:
                        name = (await h1.inner_text()).strip()
                    if not name:
                        for sel in ("div.NrDZNb", "div.qBF1Pd.fontHeadlineSmall"):
                            el = await self.page.query_selector(sel)
                            if el:
                                name = (await el.inner_text()).strip()
                                break
                    phone = ""
                    pid_el = await self.page.query_selector('[data-item-id^="phone:tel:"]')
                    if pid_el:
                        phone = ((await pid_el.get_attribute("data-item-id")) or "") \
                            .replace("phone:tel:", "").strip()
                    if not phone:
                        tel = await self.page.query_selector_all('a[href^="tel:"]')
                        if tel:
                            phone = (await tel[0].get_attribute("href") or "").replace("tel:", "").strip()
                    if not phone:
                        m = re.search(r"\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", body)
                        if m:
                            phone = m.group(0).strip()
                    rating = ""
                    rev_count = 0
                    rm = re.search(r"(\d[,.]\d)\s*\(([\d.,]+)\)", body)
                    if rm:
                        rating = rm.group(1).replace(",", ".")
                        rev_count = int(rm.group(2).replace(",", "").replace(".", ""))
                    address = ""
                    addr = await self.page.query_selector('[data-item-id="address"]')
                    if addr:
                        address = (await addr.inner_text()).strip()
                    website = ""
                    web_els = await self.page.query_selector_all(
                        'a[data-tooltip*="Open website"], a[data-tooltip*="Website"], '
                        'a[data-tooltip*="Webseite"], a[data-tooltip*="Webseite öffnen"], '
                        'a[aria-label*="Website"], a[aria-label*="Webseite"]')
                    for el in web_els:
                        href = await el.get_attribute("href") or ""
                        if "google" not in href.lower() and "maps" not in href.lower():
                            website = href
                            break
                    if not website:
                        # fallback: any external http link visible in the info panel
                        ext = await self.page.query_selector_all(
                            'div[data-attrid="website"] a, a[jsname*="website"], '
                            'button[data-tooltip*="site"] + a[href^="http"]')
                        for el in ext:
                            href = await el.get_attribute("href") or ""
                            if "google" not in href.lower() and "maps" not in href.lower():
                                website = href
                                break
                    processed += 1
                    if name and phone:
                        found.append({
                            "business_name": name[:120], "phone": _clean_phone(phone),
                            "category": cat, "address": address[:180],
                            "rating": rating or None,
                            "review_count": rev_count or None,
                            "place_url": place_url or "", "website": website,
                            "city": city, "state": state,
                        })
                        log(f"  ✅ {name[:34]} | {_clean_phone(phone)} | ⭐{rating or '?'} ({rev_count or '?'}) | 🌐{'yes' if website else 'NO'}")
                    else:
                        log(f"  ⚠️ skipped: name={name[:20]!r} phone={phone[:16]!r}")
                except Exception as e:
                    log(f"  ⚠️ extract error: {str(e)[:60]}")
            await asyncio.sleep(1)
        return found

    async def count_unanswered(self, place_url):
        """Count visible reviews WITHOUT an owner response (best effort)."""
        if not place_url:
            return None
        try:
            await self.page.goto(place_url + ("&" if "?" in place_url else "?") + "hl=en", timeout=45000)
            await asyncio.sleep(2.5)
            await self._dismiss_cookies()
            # open the Reviews tab if present
            clicked = False
            for sel in ('button[aria-label*="reviews"]', 'button[aria-label*="Reviews"]',
                        'button[aria-label*="Bewertungen"]', 'button[aria-label*="Bewertung"]',
                        'button:has-text("reviews")', 'button:has-text("Reviews")',
                        'button:has-text("Bewertungen")'):
                try:
                    el = await self.page.query_selector(sel)
                    if el:
                        await el.click()
                        clicked = True
                        break
                except Exception:
                    pass
            await asyncio.sleep(2)
            # scroll the review feed a few times
            for _ in range(5):
                try:
                    await self.page.evaluate(
                        "document.querySelectorAll('div[role=\"feed\"]')[0]?.scrollTo(0, 999999)")
                except Exception:
                    pass
                await asyncio.sleep(1.2)
            cards = await self.page.query_selector_all('div.jftiEf, div[data-review-id]')
            if not cards:
                return None
            answered = 0
            for card in cards[:60]:
                try:
                    txt = (await card.inner_text()) or ""
                    if ("Response from the owner" in txt or "Response from owner" in txt
                            or "Antwort des Inhabers" in txt):
                        answered += 1
                except Exception:
                    pass
            total = min(len(cards), 60)
            unanswered = total - answered
            log(f"  🔢 {total} reviews visible, {unanswered} unanswered")
            return unanswered
        except Exception as e:
            log(f"  ⚠️ review count error: {str(e)[:60]}")
            return None


def _clean_phone(p):
    digits = re.sub(r"\D", "", p)
    if digits.startswith("1") and len(digits) == 11:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    return p


def scrape_prospects(city=None, state=None, categories=None, max_per=None):
    """Run the scraper in a background thread. Updates review_prospects."""
    def worker():
        if _running["scrape"]:
            return
        _running["scrape"] = True
        _stop_flag.clear()
        s = get_settings()
        cty = city or s["city"]
        st = state or s["state"]
        cats = [c.strip() for c in (categories or s["categories"]).split(",") if c.strip()]
        maxp = int(max_per or s["max_per_category"] or 15)
        try:
            async def _run():
                sc = ReviewScraper(headless=True)
                await sc._init()
                try:
                    return await sc.search(cty, st, cats, maxp)
                finally:
                    await sc._close()
            found = asyncio.run(_run())
            db = _db()
            added = 0
            for f in found:
                exists = db.execute("SELECT id FROM review_prospects WHERE phone=?", (f["phone"],)).fetchone()
                if exists:
                    db.execute("UPDATE review_prospects SET review_count=?, rating=?, place_url=?, website=? WHERE id=?",
                               (f["review_count"], f["rating"], f["place_url"], f.get("website") or "", exists["id"]))
                    continue
                db.execute(
                    "INSERT INTO review_prospects (id, business_name, phone, category, address, "
                    "rating, review_count, place_url, website, city, state, status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?, 'new')",
                    ("rp_" + uuid.uuid4().hex[:10], f["business_name"], f["phone"], f["category"],
                     f["address"], f["rating"], f["review_count"], f["place_url"],
                     f.get("website") or "", f["city"], f["state"]))
                added += 1
            db.commit()
            db.close()
            log(f"📦 Scrape done: {len(found)} found, {added} new prospects")
        except Exception as e:
            log(f"❌ Scrape error: {str(e)[:200]}")
        finally:
            _running["scrape"] = False
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return True


def count_unanswered_all(limit=100):
    """Background: count unanswered reviews for prospects that have a place_url."""
    def worker():
        if _running["count"]:
            return
        _running["count"] = True
        _stop_flag.clear()
        try:
            db = _db()
            rows = db.execute(
                "SELECT id, place_url FROM review_prospects "
                "WHERE place_url != '' AND unanswered_count IS NULL "
                "ORDER BY created_at LIMIT ?", (int(limit),)).fetchall()
            db.close()
            log(f"🔢 Counting unanswered for {len(rows)} prospects…")
            async def _run():
                sc = ReviewScraper(headless=True)
                await sc._init()
                try:
                    done = 0
                    for r in rows:
                        if _stop_flag.is_set():
                            break
                        n = await sc.count_unanswered(r["place_url"])
                        if n is not None:
                            db = _db()
                            db.execute("UPDATE review_prospects SET unanswered_count=? WHERE id=?",
                                       (n, r["id"]))
                            db.commit()
                            db.close()
                        done += 1
                        await asyncio.sleep(1.0)
                    return done
                finally:
                    await sc._close()
            done = asyncio.run(_run())
            log(f"🔢 Unanswered counting done ({done} checked)")
        except Exception as e:
            log(f"❌ Count error: {str(e)[:200]}")
        finally:
            _running["count"] = False
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return True


# ─────────────────── Calls ───────────────────

def run_calls(max_calls=None, delay=None):
    """Background: place Vapi outbound calls to 'new' prospects."""
    def worker():
        if _running["calls"]:
            return
        _running["calls"] = True
        _stop_flag.clear()
        s = get_settings()
        maxc = int(max_calls or s["max_calls_per_run"] or 5)
        wait = int(delay or s["delay_seconds"] or 90)
        aid, _ = ensure_assistant()
        if not aid:
            log("❌ No assistant — cannot call")
            _running["calls"] = False
            return
        phone_id = s["phone_number_id"]
        service = s.get("service", "reviews")
        # website mode: only call businesses with NO website
        if service == "website":
            rows = _db().execute(
                "SELECT * FROM review_prospects WHERE status='new' AND "
                "(website IS NULL OR website='') ORDER BY created_at LIMIT ?",
                (maxc,)).fetchall()
        else:
            rows = _db().execute(
                "SELECT * FROM review_prospects WHERE status='new' ORDER BY created_at LIMIT ?",
                (maxc,)).fetchall()
        log(f"📞 Placing up to {len(rows)} calls ({service} mode, assistant {aid[:8]}…, phone {phone_id[:8]}…)")
        placed = 0
        for r in rows:
            if _stop_flag.is_set():
                log("⏹ Stopped by user")
                break
            script = personalize(dict(r), active_script())
            # personalize the system prompt on the fly per prospect
            d = _vapi("POST", "/call", {
                "assistantId": aid,
                "phoneNumberId": phone_id,
                "customer": {"number": r["phone"], "name": (r["business_name"] or "")[:40]},
                "assistantOverrides": {"model": {
                    "provider": "xai", "model": "grok-4.3",
                    "maxTokens": 300, "temperature": 0.3,
                    "systemPrompt": script,
                }},
            })
            if d.get("id"):
                db = _db()
                db.execute(
                    "UPDATE review_prospects SET status='called', last_call_id=?, last_call_at=datetime('now') "
                    "WHERE id=?", (d["id"], r["id"]))
                db.execute("INSERT INTO review_ai_calls (prospect_id, call_id, status) VALUES (?,?, 'placed')",
                           (r["id"], d["id"]))
                db.commit()
                db.close()
                log(f"  ✅ {r['business_name'][:35]} → call {d['id'][:8]}…")
                placed += 1
            else:
                log(f"  ❌ {r['business_name'][:35]}: {str(d)[:120]}")
            if placed < maxc:
                time.sleep(wait)
        log(f"📞 Run complete: {placed} calls placed")
        _running["calls"] = False
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return True


def sync_call_outcomes():
    """Poll Vapi for outcomes of calls placed but not yet resolved."""
    db = _db()
    rows = db.execute(
        "SELECT p.id, p.business_name, p.last_call_id FROM review_prospects p "
        "WHERE p.status='called' AND p.last_call_id != '' AND "
        "(p.last_outcome IS NULL OR p.last_outcome='')").fetchall()
    updated = 0
    for r in rows:
        d = _vapi("GET", f"/call/{r['last_call_id']}")
        if d.get("error"):
            continue
        ended = d.get("endedReason") or ""
        dur = d.get("durationMinutes") or 0
        cost = d.get("cost") or 0
        analysis = d.get("analysis") or {}
        summary = (analysis.get("summary") or "")[:400]
        transcript = " ".join([m.get("message", "") for m in (d.get("messages") or [])])[:800]
        text = (summary + " " + transcript).lower()
        if ended in ("customer-ended-call", "assistant-ended-call"):
            if any(w in text for w in ("interested", "yes, send", "send me", "sounds good", "sign me up", "that works")):
                status = "interested"
            elif any(w in text for w in ("not interested", "no thanks", "no thank you", "don't need", "not for me", "stop calling")):
                status = "not_interested"
            else:
                status = "called"
        elif ended in ("no-answer", "voicemail", "user-busy", "user-cancelled"):
            status = "no_answer"
        else:
            status = "called"
        db.execute("UPDATE review_prospects SET status=?, last_outcome=? WHERE id=?",
                   (status, ended, r["id"]))
        db.execute("UPDATE review_ai_calls SET status=?, cost=?, duration=? WHERE call_id=?",
                   (status, cost, int(dur * 60), r["last_call_id"]))
        updated += 1
        log(f"  📊 {r['business_name'][:30]}: {ended} → {status}")
    db.commit()
    db.close()
    log(f"📊 Synced {updated} call outcome(s)")
    return updated


def send_sample_sms(prospect_id):
    """Send the free sample review response via sms-gate."""
    db = _db()
    row = db.execute("SELECT * FROM review_prospects WHERE id=?", (prospect_id,)).fetchone()
    if not row:
        return {"success": False, "message": "Prospect not found"}
    try:
        from smsgate_sms import send_sms
        s = get_settings()
        biz = row["business_name"] or "your business"
        if s.get("service") == "website":
            body = (f"Hi! Here's the free website preview for {biz} — a mobile-friendly one-pager with "
                    f"your services, hours, contact info and Google reviews, ready in 48 hours. "
                    f"Full site is {s.get('website_pricing', '$499')} — you own it. "
                    f"Want me to start on yours?")
        else:
            body = (f"Hi! Here's the free sample review response we'd post for {biz}: "
                    f"“Thank you for your feedback! We really appreciate you taking the time to share "
                    f"your experience — it helps us keep improving every day. 🙌 — The {biz} Team” "
                    f"If you like it, we can handle all your reviews for {s.get('pricing', '$99/mo')} — "
                    f"you approve everything before it's posted.")
        ok = send_sms(row["phone"], body)
        if ok:
            db.execute("UPDATE review_prospects SET sample_sent_at=datetime('now') WHERE id=?", (prospect_id,))
            db.commit()
        db.close()
        return {"success": bool(ok), "message": "✅ Sample SMS sent" if ok else "❌ SMS send failed"}
    except Exception as e:
        db.close()
        return {"success": False, "message": f"❌ {str(e)[:120]}"}


def stop_all():
    _stop_flag.set()
    return True


# ─────────────────── Admin data ───────────────────

def tab_data():
    init_tables()
    db = _db()
    prospects = [dict(r) for r in db.execute(
        "SELECT * FROM review_prospects ORDER BY created_at DESC LIMIT 200").fetchall()]
    stats = {
        "total": db.execute("SELECT COUNT(*) FROM review_prospects").fetchone()[0],
        "new": db.execute("SELECT COUNT(*) FROM review_prospects WHERE status='new'").fetchone()[0],
        "called": db.execute("SELECT COUNT(*) FROM review_prospects WHERE status='called'").fetchone()[0],
        "interested": db.execute("SELECT COUNT(*) FROM review_prospects WHERE status='interested'").fetchone()[0],
        "no_answer": db.execute("SELECT COUNT(*) FROM review_prospects WHERE status='no_answer'").fetchone()[0],
        "no_website": db.execute("SELECT COUNT(*) FROM review_prospects WHERE website IS NULL OR website=''").fetchone()[0],
    }
    calls = [dict(r) for r in db.execute(
        "SELECT rc.*, p.business_name FROM review_ai_calls rc "
        "LEFT JOIN review_prospects p ON rc.prospect_id = p.id "
        "ORDER BY rc.id DESC LIMIT 30").fetchall()]
    db.close()
    return {
        "ra_settings": get_settings(),
        "ra_prospects": prospects,
        "ra_stats": stats,
        "ra_calls": calls,
        "ra_running": running_state(),
        "ra_log": recent_log(),
    }
