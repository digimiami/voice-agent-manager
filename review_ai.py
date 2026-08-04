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
"Hi! This is a quick call — I noticed {business_name} has {unanswered} on Google. I run a service that writes personalized responses to every review and posts them with your approval. It's just {pricing}."

If they ask what it is:
- We write authentic, on-brand replies to every Google review — positive and negative.
- You approve each response before it's posted. Nothing goes live without your OK.
- We handle posting too, so you never have to think about it.

Offer (important): "Want me to send you a free sample response for your latest review? No commitment at all."
- If they say YES: thank them warmly, ask for the best email to send the sample to, repeat the email back to confirm, and confirm their number is {phone}.
- If they say no or not interested: be friendly, thank them for their time, and hang up. Do NOT push, argue, or call back pressure.
- STAY ON TOPIC: talk ONLY about responding to their Google reviews. Never mention websites, web design, or any other service.

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
- If they say YES: thank them warmly, ask for the best email to send the preview to, repeat the email back to confirm, and confirm their number is {phone}.
- If they say no or not interested: be friendly, thank them for their time, and hang up. Do NOT push, argue, or pressure.
- STAY ON TOPIC: talk ONLY about building their website. Never mention reviews, review responses, or any other service.

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
    # ── Post-call funnel: demo, signup form & payment ──
    "payment_link": "https://buy.stripe.com/14AcN598d3I6gmO0hl67S04",
    "price_id": "price_1U0jNCGaNMCjVFzm1sFJ48O0",
    "signup_url": "https://diazites.online/review-service",
    "service_name": "Review Response Service",
    # Website-service funnel (separate links — never mix services)
    "website_payment_link": "https://buy.stripe.com/cNi3cv3NT3I62vYc0367S05",
    "website_price_id": "price_1U0jeeGaNMCjVFzmD82Psu2Z",
    "website_signup_url": "https://diazites.online/website-service",
    "website_service_name": "Website Builder Service",
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
    CREATE TABLE IF NOT EXISTS review_service_leads (
        id TEXT PRIMARY KEY,
        prospect_id TEXT,
        business_name TEXT, contact_name TEXT,
        email TEXT, phone TEXT,
        service TEXT DEFAULT 'reviews',
        status TEXT DEFAULT 'new',
        stripe_customer TEXT, stripe_subscription TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # guarded migration: website column on older DBs
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info(review_prospects)")]
        if "website" not in cols:
            db.execute("ALTER TABLE review_prospects ADD COLUMN website TEXT")
        if "email" not in cols:
            db.execute("ALTER TABLE review_prospects ADD COLUMN email TEXT")
        if "service" not in cols:
            db.execute("ALTER TABLE review_prospects ADD COLUMN service TEXT")
    except Exception:
        pass
    try:
        lcols = [r[1] for r in db.execute("PRAGMA table_info(review_service_leads)")]
        if "service" not in lcols:
            db.execute("ALTER TABLE review_service_leads ADD COLUMN service TEXT DEFAULT 'reviews'")
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
                    "UPDATE review_prospects SET status='called', service=?, last_call_id=?, last_call_at=datetime('now') "
                    "WHERE id=?", (service, d["id"], r["id"]))
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
        # ── Capture email the agent asked for (from summary/transcript) ──
        email_captured = _extract_email(text)
        if email_captured:
            db.execute("UPDATE review_prospects SET email=? WHERE id=? AND (email IS NULL OR email='')",
                       (email_captured, r["id"]))
        db.execute("UPDATE review_prospects SET status=?, last_outcome=? WHERE id=?",
                   (status, ended, r["id"]))
        db.execute("UPDATE review_ai_calls SET status=?, cost=?, duration=? WHERE call_id=?",
                   (status, cost, int(dur * 60), r["last_call_id"]))
        updated += 1
        log(f"  📊 {r['business_name'][:30]}: {ended} → {status}{f' 📧 {email_captured}' if email_captured else ''}")
        # ── Auto-send demo + signup landing page on first 'interested' ──
        if status == 'interested' and not r["sample_sent_at"]:
            try:
                res = send_sample_sms(r["id"])
                log(f"  📤 Auto-package → {r['business_name'][:30]}: {res.get('message', 'sent')}")
                if email_captured:
                    lead = {"business_name": r["business_name"], "contact_name": r["business_name"],
                            "email": email_captured, "phone": r["phone"],
                            "service": r["service"] or s.get("service", "reviews")}
                    ok = send_package_email(lead)
                    log(f"  📧 Auto-email → {r['business_name'][:30]}: {'sent' if ok else 'FAILED'}")
            except Exception as e:
                log(f"  ❌ Auto-package failed: {e}")
    db.commit()
    db.close()
    log(f"📊 Synced {updated} call outcome(s)")
    return updated


def _extract_email(text):
    """Find the first email address the agent captured during the call."""
    import re as _re
    m = _re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text or "")
    return m.group(0).lower() if m else None


def _service_of(prospect):
    """Service of the call that created this prospect (never mixes)."""
    svc = ""
    try:
        svc = prospect.get("service") or ""
    except AttributeError:
        try:
            svc = prospect["service"] or ""
        except Exception:
            svc = ""
    if svc not in ("reviews", "website"):
        svc = get_settings().get("service", "reviews")
        if svc != "website":
            svc = "reviews"
    return svc


def send_sample_sms(prospect_id):
    """Send demo + the service's signup landing page via sms-gate (no raw Stripe links)."""
    db = _db()
    row = db.execute("SELECT * FROM review_prospects WHERE id=?", (prospect_id,)).fetchone()
    if not row:
        return {"success": False, "message": "Prospect not found"}
    try:
        from smsgate_sms import send_sms
        s = get_settings()
        biz = row["business_name"] or "your business"
        svc = _service_of(row)
        if svc == "website":
            signup = s.get("website_signup_url", "https://diazites.online/website-service")
            body = (f"Hi! Here's your free website preview for {biz} — a mobile-friendly one-pager with "
                    f"your services, hours, contact info and Google reviews, ready in 48 hours. "
                    f"Full site is {s.get('website_pricing', '$499')} — you own it. "
                    f"Sign up here to start yours: {signup}")
        else:
            signup = s.get("signup_url", "https://diazites.online/review-service")
            body = (f"Hi! Here's the free sample review response we'd post for {biz}: "
                    f"“Thank you for your feedback! We really appreciate you taking the time to share "
                    f"your experience — it helps us keep improving every day. 🙌 — The {biz} Team” "
                    f"If you like it, we can handle all your reviews for {s.get('pricing', '$99/mo')} — "
                    f"you approve everything before it's posted. "
                    f"Sign up here: {signup}")
        ok = send_sms(row["phone"], body)
        if ok:
            db.execute("UPDATE review_prospects SET sample_sent_at=datetime('now') WHERE id=?", (prospect_id,))
            db.commit()
        db.close()
        return {"success": bool(ok), "message": f"✅ Package SMS sent ({svc} mode, demo + signup page)" if ok else "❌ SMS send failed"}
    except Exception as e:
        db.close()
        return {"success": False, "message": f"❌ {str(e)[:120]}"}


def send_email_via_agentmail(to, subject, body):
    """AgentMail email (no admin_panel import — avoids circular deps)."""
    import os as _os, json as _json, urllib.request
    key = _os.environ.get("AGENTMAIL_API_KEY", "")
    if not key:
        for _p in ("/root/.env", "/root/voice-agent-manager/.env"):
            try:
                with open(_p) as _f:
                    for _line in _f:
                        _line = _line.strip()
                        if _line.startswith("AGENTMAIL_API_KEY="):
                            key = _line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                continue
            if key:
                break
    if not key:
        return False
    try:
        payload = {"to": to, "subject": subject, "text": body}
        req = urllib.request.Request(
            "https://api.agentmail.to/v0/inboxes/aiworkers@agentmail.to/messages/send",
            data=_json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                     "User-Agent": "DiazitesReviewAI/1.0"},
            method="POST")
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as e:
        log(f"⚠️ Email failed: {e}")
        return False


def send_package_email(lead, checkout_url=None):
    """Send demo + the service's signup landing page to a lead's email (AgentMail)."""
    s = get_settings()
    biz = lead.get("business_name") or "your business"
    svc = (lead.get("service") or s.get("service", "reviews"))
    svc = svc if svc == "website" else "reviews"
    if svc == "website":
        signup = s.get("website_signup_url", "https://diazites.online/website-service")
        subject = f"Your free website preview for {biz}"
        body = (
            f"Hi {lead.get('contact_name') or 'there'},\n\n"
            f"Thanks for your interest! Here's what your free website preview will include for {biz}:\n\n"
            f"--------------------------------------------------\n"
            f"• Modern mobile-first design that works great on phones\n"
            f"• Your services, hours, contact info, map & directions\n"
            f"• A link to your Google reviews\n"
            f"• Hosting, maintenance & updates — handled by us\n"
            f"• You own the site and everything in it\n"
            f"--------------------------------------------------\n\n"
            f"Your preview will be ready in 48 hours. To get started, sign up here:\n"
            f"👉 {signup}\n\n"
            f"Full site is {s.get('website_pricing', '$499')} — one-time, you own it.\n\n"
            f"Questions? Just reply to this email.\n"
            f"— The {s.get('website_service_name', 'Diazites')} Team"
        )
    else:
        signup = s.get("signup_url", "https://diazites.online/review-service")
        subject = f"Your free sample review response for {biz}"
        body = (
            f"Hi {lead.get('contact_name') or 'there'},\n\n"
            f"Thanks for your interest! Here's the free sample response we'd post for {biz}:\n\n"
            f"--------------------------------------------------\n"
            f"“Thank you for your feedback! We really appreciate you taking the time to share your "
            f"experience — it helps us keep improving every day. 🙌 — The {biz} Team”\n"
            f"--------------------------------------------------\n\n"
            f"We write personalized replies to EVERY Google review — positive and negative — in your "
            f"brand's voice, and post them with your approval. No bots, no templates off the shelf.\n\n"
            f"👉 Start here (2-minute signup): {signup}\n\n"
            f"It's {s.get('pricing', '$99/mo')} — cancel anytime.\n\n"
            f"Questions? Just reply to this email.\n"
            f"— The {s.get('service_name', 'Diazites')} Team"
        )
    return send_email_via_agentmail(lead.get("email", ""), subject, body)


def create_lead_checkout(lead_id, email, service="reviews"):
    """Per-lead checkout: $99/mo subscription (reviews) or $499 one-time (website)."""
    try:
        import json as _json
        cfg = _json.load(open("/root/voice-agent-manager/stripe_config.json"))
        import stripe
        stripe.api_key = cfg["secret_key"]
        s = get_settings()
        if service == "website":
            mode, price, success = "payment", s.get("website_price_id", "price_1U0jeeGaNMCjVFzmD82Psu2Z"), "https://diazites.online/website-service?thankyou=1"
        else:
            mode, price, success = "subscription", s.get("price_id", "price_1U0jNCGaNMCjVFzm1sFJ48O0"), "https://diazites.online/review-service?thankyou=1"
        sd = stripe.checkout.Session.create(
            mode=mode,
            line_items=[{"price": price, "quantity": 1}],
            client_reference_id=f"review-lead-{lead_id}",
            customer_email=email or None,
            success_url=success,
            cancel_url="https://diazites.online/" + ("website-service" if service == "website" else "review-service"))
        return sd.url
    except Exception as e:
        return None


def add_lead(prospect_id=None, business_name="", contact_name="", email="", phone="", service="reviews"):
    """Insert a service lead, linking it to a prospect by phone when possible."""
    import uuid
    db = _db()
    pid = prospect_id
    if not pid and phone:
        row = db.execute("SELECT id FROM review_prospects WHERE phone=? ORDER BY created_at DESC LIMIT 1", (phone,)).fetchone()
        if row:
            pid = row["id"]
            db.execute("UPDATE review_prospects SET email=?, service=? WHERE id=?",
                       (email, service, pid))
    lid = "lead-" + str(uuid.uuid4())[:10]
    db.execute("""INSERT INTO review_service_leads (id, prospect_id, business_name, contact_name, email, phone, service)
                  VALUES (?,?,?,?,?,?,?)""", (lid, pid, business_name, contact_name, email, phone, service))
    db.commit()
    db.close()
    return lid


# ─────────────────── Public service page (diazites.online/review-service) ───────────────────

def service_page_html(thankyou=False, error=False, service="reviews"):
    """Public landing page for the requested service (signup + payment live on the page)."""
    if service == "website":
        return _website_service_page(thankyou, error)
    return _review_service_page(thankyou, error)


def _website_service_page(thankyou=False, error=False):
    """Website Builder service page — $499 one-time, signup + payment."""
    s = get_settings()
    pay_link = s.get("website_payment_link", "https://buy.stripe.com/cNi3cv3NT3I62vYc0367S05")
    thankyou_html = f'''<div class="card" style="border-color:rgba(74,222,128,0.35);background:linear-gradient(135deg,#052e16,#0a0f1e);margin-bottom:24px">
      <div style="font-size:40px;text-align:center;margin-bottom:8px">✅</div>
      <h2 style="text-align:center;font-size:18px;font-weight:800;color:#4ade80;margin-bottom:6px">You're signed up!</h2>
      <p style="font-size:13px;color:#94a3b8;text-align:center;line-height:1.6">Your free website preview is on its way to your inbox.<br>Want to lock in your site now? <a href="{pay_link}" style="color:#c084fc;font-weight:700">Pay $499 — you own it →</a></p>
    </div>''' if thankyou else ''
    error_html = f'''<div class="card" style="border-color:rgba(239,68,68,0.4);margin-bottom:24px">
      <p style="font-size:13px;color:#f87171;text-align:center">Please fill all fields with a valid email & phone.</p></div>''' if error else ''
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
<title>Website Builder — $499 One-Time | Diazites</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a12;color:#f1f1f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.5}}
.wrap{{max-width:720px;margin:0 auto;padding:20px 16px 40px}}
.badge{{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.5px;padding:6px 14px;border-radius:999px;background:linear-gradient(135deg,rgba(56,189,248,.15),rgba(168,85,247,.15));border:1px solid rgba(56,189,248,.35);color:#38bdf8;margin-bottom:14px}}
h1{{font-size:28px;line-height:1.25;margin-bottom:12px}}
.sub{{color:#94a3b8;font-size:14px;margin-bottom:20px;line-height:1.6}}
.btn{{display:block;width:100%;text-align:center;padding:16px;border-radius:12px;font-weight:800;font-size:16px;text-decoration:none;color:#fff;background:linear-gradient(135deg,#38bdf8,#a855f7);border:none;cursor:pointer}}
.card{{background:#0e0e16;border:1px solid #1e1e2e;border-radius:16px;padding:20px;margin-bottom:16px}}
h2{{font-size:18px;margin-bottom:12px}}
.step{{display:flex;gap:12px;margin-bottom:14px;align-items:flex-start}}
.step .n{{min-width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#38bdf8,#a855f7);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800}}
.step p{{font-size:13px;color:#94a3b8}}
.step b{{color:#e2e8f0}}
.mock{{background:#0a0a12;border:1px solid #1a1a24;border-radius:12px;padding:16px;margin-bottom:10px}}
.mock .bar{{height:10px;width:140px;background:#1e1e2e;border-radius:5px;margin-bottom:12px}}
.mock .row{{display:flex;gap:8px;margin-bottom:8px}}
.mock .row i{{flex:1;height:34px;border-radius:8px;background:#14141f}}
.mock .row i.hi{{background:linear-gradient(135deg,rgba(56,189,248,.25),rgba(168,85,247,.25))}}
.mock .dots{{display:flex;gap:6px;margin-bottom:12px}}
.mock .dots span{{width:8px;height:8px;border-radius:50%;background:#1e1e2e}}
label{{display:block;font-size:11px;font-weight:700;letter-spacing:.4px;color:#64748b;text-transform:uppercase;margin:12px 0 5px}}
input{{width:100%;padding:12px 14px;border-radius:10px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:15px;outline:none}}
input:focus{{border-color:#38bdf8}}
.faq details{{margin-bottom:10px}}
.faq summary{{font-size:13px;font-weight:700;cursor:pointer;color:#e2e8f0}}
.faq p{{font-size:12px;color:#94a3b8;margin-top:6px}}
.price{{text-align:center;padding:24px}}
.price .amt{{font-size:44px;font-weight:900;color:#38bdf8}}
.price .per{{font-size:12px;color:#64748b}}
.foot{{text-align:center;font-size:11px;color:#475569;margin-top:24px}}
@media(min-width:640px){{h1{{font-size:36px}}}}
</style></head><body><div class="wrap">
  <div style="text-align:center;margin-bottom:20px">
    <span class="badge">🌐 WEBSITE BUILDER — LOCAL BUSINESS SITES</span>
    <h1>Your business deserves a website customers find on Google.</h1>
    <p class="sub">A modern, mobile-first site with your services, hours, contact info and Google reviews — built in 48 hours. Hosting, maintenance and updates handled. <b>$499 one-time, you own it.</b></p>
    <a class="btn" href="{pay_link}">Get My Website — $499 →</a>
    <p style="font-size:11px;color:#64748b;margin-top:8px">🔒 Secure Stripe checkout · Free preview first · No monthly fees</p>
  </div>

  {thankyou_html}
  {error_html}

  <div class="card">
    <h2>⚡ How it works</h2>
    <div class="step"><div class="n">1</div><p><b>Free preview first</b> — we send you a mockup of your site before you pay a cent.</p></div>
    <div class="step"><div class="n">2</div><p><b>We build it</b> — mobile-first, fast, with your services, hours, map and reviews.</p></div>
    <div class="step"><div class="n">3</div><p><b>You own it</b> — hosting, updates and maintenance on us. Done.</p></div>
  </div>

  <div class="card">
    <h2>🎨 What your site looks like</h2>
    <div class="mock"><div class="bar"></div><div class="dots"><span></span><span></span><span></span></div>
      <div class="row"><i class="hi"></i></div>
      <div class="row"><i></i><i></i><i></i></div>
      <div class="row"><i></i><i></i></div></div>
    <p style="font-size:12px;color:#64748b">Mobile-first design that loads fast and makes customers call you.</p>
  </div>

  <div class="card" style="border-color:rgba(56,189,248,.4)">
    <h2>📝 Sign up — get your free preview in 48 hours</h2>
    <form method="POST" action="/website-service/signup">
      <label>Business name</label><input name="business_name" required placeholder="e.g. Miami Plumbers LLC">
      <label>Your name</label><input name="contact_name" required placeholder="e.g. Jorge Rivera">
      <label>Email (we send your preview here)</label><input type="email" name="email" required placeholder="you@business.com">
      <label>Phone</label><input type="tel" name="phone" required placeholder="(305) 555-0123">
      <button class="btn" type="submit" style="margin-top:18px">Send Me My Free Preview →</button>
    </form>
    <p style="font-size:11px;color:#64748b;text-align:center;margin-top:10px">No spam. Preview is free — you only pay if you love it.</p>
  </div>

  <div class="card price">
    <h2>Simple pricing</h2>
    <div class="amt">$499<span style="font-size:16px;color:#64748b"> once</span></div>
    <p style="font-size:13px;color:#94a3b8;margin:8px 0 14px">Free preview · 48h delivery · hosting & updates included · you own it</p>
    <a class="btn" href="{pay_link}">Get My Website →</a>
  </div>

  <div class="card faq">
    <h2>Questions? Answered.</h2>
    <details><summary>Is the preview really free?</summary><p>Yes. We build a mockup of your site first. You only pay $499 if you approve it.</p></details>
    <details><summary>Who owns the website?</summary><p>You do. 100%. Domain, content, everything.</p></details>
    <details><summary>Do I need to do anything after?</summary><p>No. Hosting, updates and maintenance are handled by us.</p></details>
    <details><summary>Will it work on phones?</summary><p>It's built mobile-first — most of your customers will find you on their phone.</p></details>
  </div>

  <div class="foot">Diazites · Website Builder Service · support@diazites.online</div>
</div></body></html>'''


def _review_service_page(thankyou=False, error=False):
    """Standalone mobile-first service page: demo → signup → $99/mo payment."""
    s = get_settings()
    pay_link = s.get("payment_link", "https://buy.stripe.com/14AcN598d3I6gmO0hl67S04")
    thankyou_html = f'''<div class="card" style="border-color:rgba(74,222,128,0.35);background:linear-gradient(135deg,#052e16,#0a0f1e);margin-bottom:24px">
      <div style="font-size:40px;text-align:center;margin-bottom:8px">✅</div>
      <h2 style="text-align:center;font-size:18px;font-weight:800;color:#4ade80;margin-bottom:6px">You're signed up!</h2>
      <p style="font-size:13px;color:#94a3b8;text-align:center;line-height:1.6">Your free sample review response is on its way to your inbox.<br>Want to get started right now? <a href="{pay_link}" style="color:#c084fc;font-weight:700">Start your subscription →</a></p>
    </div>''' if thankyou else ''
    error_html = f'''<div class="card" style="border-color:rgba(239,68,68,0.4);margin-bottom:24px">
      <p style="font-size:13px;color:#f87171;text-align:center">Please fill all fields with a valid email & phone.</p></div>''' if error else ''
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
<title>Google Review Response Service — $99/mo | Diazites</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a12;color:#f1f1f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.5}}
.wrap{{max-width:720px;margin:0 auto;padding:20px 16px 40px}}
.badge{{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.5px;padding:6px 14px;border-radius:999px;background:linear-gradient(135deg,rgba(168,85,247,.15),rgba(236,72,153,.15));border:1px solid rgba(168,85,247,.35);color:#c084fc;margin-bottom:14px}}
h1{{font-size:28px;line-height:1.25;margin-bottom:12px}}
.sub{{color:#94a3b8;font-size:14px;margin-bottom:20px;line-height:1.6}}
.btn{{display:block;width:100%;text-align:center;padding:16px;border-radius:12px;font-weight:800;font-size:16px;text-decoration:none;color:#fff;background:linear-gradient(135deg,#a855f7,#ec4899);border:none;cursor:pointer}}
.card{{background:#0e0e16;border:1px solid #1e1e2e;border-radius:16px;padding:20px;margin-bottom:16px}}
h2{{font-size:18px;margin-bottom:12px}}
.step{{display:flex;gap:12px;margin-bottom:14px;align-items:flex-start}}
.step .n{{min-width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#a855f7,#ec4899);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800}}
.step p{{font-size:13px;color:#94a3b8}}
.step b{{color:#e2e8f0}}
.demo{{background:#0a0a12;border:1px solid #1a1a24;border-radius:12px;padding:14px;margin-bottom:10px}}
.demo .rev{{font-size:13px;color:#d0d0e0;margin-bottom:8px}}
.demo .stars{{color:#fbbf24;font-size:11px;margin-bottom:4px}}
.demo .who{{font-size:11px;color:#64748b;margin-bottom:8px}}
.demo .reply{{font-size:12px;color:#c084fc;background:rgba(168,85,247,.08);border-left:2px solid #a855f7;padding:10px 12px;border-radius:0 8px 8px 0}}
label{{display:block;font-size:11px;font-weight:700;letter-spacing:.4px;color:#64748b;text-transform:uppercase;margin:12px 0 5px}}
input{{width:100%;padding:12px 14px;border-radius:10px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:15px;outline:none}}
input:focus{{border-color:#a855f7}}
.faq details{{margin-bottom:10px}}
.faq summary{{font-size:13px;font-weight:700;cursor:pointer;color:#e2e8f0}}
.faq p{{font-size:12px;color:#94a3b8;margin-top:6px}}
.price{{text-align:center;padding:24px}}
.price .amt{{font-size:44px;font-weight:900;color:#c084fc}}
.price .per{{font-size:12px;color:#64748b}}
.foot{{text-align:center;font-size:11px;color:#475569;margin-top:24px}}
@media(min-width:640px){{h1{{font-size:36px}}}}
</style></head><body><div class="wrap">
  <div style="text-align:center;margin-bottom:20px">
    <span class="badge">⭐ GOOGLE REVIEW RESPONSE SERVICE</span>
    <h1>Never leave another Google review unanswered.</h1>
    <p class="sub">We write personalized, on-brand replies to <b>every</b> Google review — positive and negative — and post them with your approval. More responses = better ranking = more customers. <b>$99/mo, cancel anytime.</b></p>
    <a class="btn" href="{pay_link}">Start Now — $99/mo →</a>
    <p style="font-size:11px;color:#64748b;margin-top:8px">🔒 Secure Stripe checkout · Cancel anytime · 14-day guarantee</p>
  </div>

  {thankyou_html}
  {error_html}

  <div class="card">
    <h2>⚡ How it works</h2>
    <div class="step"><div class="n">1</div><p><b>We connect</b> to your Google Business Profile and read your reviews.</p></div>
    <div class="step"><div class="n">2</div><p><b>We draft responses</b> in your brand's voice — warm for fans, professional for critics.</p></div>
    <div class="step"><div class="n">3</div><p><b>You approve</b> (or edit) in one tap. We post. You look responsive 24/7.</p></div>
  </div>

  <div class="card">
    <h2>🎁 A real sample — this is what we'd write for you</h2>
    <div class="demo"><div class="stars">★★★★★</div><div class="who">Maria G. · 2 days ago</div>
      <div class="rev">"Best service in Miami! Called at 9am, they were here by noon. Super professional."</div>
      <div class="reply">"Thank you, Maria! We're so glad we could help — our team works hard to be fast and professional every single time. We appreciate you! 🙌"</div></div>
    <div class="demo"><div class="stars">★★☆☆☆</div><div class="who">Tom R. · 1 week ago</div>
      <div class="rev">"Had to wait a bit longer than expected for the estimate."</div>
      <div class="reply">"Hi Tom, thank you for the honest feedback — we're sorry about the wait. We've adjusted our scheduling so estimates go out same-day. We'd love the chance to make it right!"</div></div>
  </div>

  <div class="card" style="border-color:rgba(168,85,247,.4)">
    <h2>📝 2-minute signup — get your free sample today</h2>
    <form method="POST" action="/review-service/signup">
      <label>Business name</label><input name="business_name" required placeholder="e.g. Miami Plumbers LLC">
      <label>Your name</label><input name="contact_name" required placeholder="e.g. Jorge Rivera">
      <label>Email (we send your sample here)</label><input type="email" name="email" required placeholder="you@business.com">
      <label>Phone</label><input type="tel" name="phone" required placeholder="(305) 555-0123">
      <button class="btn" type="submit" style="margin-top:18px">Send Me My Free Sample →</button>
    </form>
    <p style="font-size:11px;color:#64748b;text-align:center;margin-top:10px">No spam. We only write review replies — ever.</p>
  </div>

  <div class="card price">
    <h2>Simple pricing</h2>
    <div class="amt">$99<span style="font-size:16px;color:#64748b">/mo</span></div>
    <p style="font-size:13px;color:#94a3b8;margin:8px 0 14px">Unlimited reviews · your voice · approve before posting · cancel anytime</p>
    <a class="btn" href="{pay_link}">Start Now →</a>
  </div>

  <div class="card faq">
    <h2>Questions? Answered.</h2>
    <details><summary>Do I need to give you my Google login?</summary><p>No. You add us as a manager on your Business Profile (2 minutes) — you stay in control.</p></details>
    <details><summary>Will responses sound like me?</summary><p>We build a voice profile from your business — you approve or edit every single reply before it goes live.</p></details>
    <details><summary>Does responding to reviews actually help?</summary><p>Yes — businesses that respond get 35% more 5-star reviews (BrightLocal) and rank higher in local search. It's the cheapest marketing you can buy.</p></details>
    <details><summary>Can I cancel?</summary><p>Anytime, in one click. No contracts, no calls.</p></details>
  </div>

  <div class="foot">Diazites · Google Review Response Service · support@diazites.online</div>
</div></body></html>'''


def signup_lead(form, service="reviews"):
    """Process a service-page signup form. Returns (ok: bool, lead_id: str|None)."""
    biz = (form.get("business_name") or "").strip()
    contact = (form.get("contact_name") or "").strip()
    email = (form.get("email") or "").strip()
    phone = (form.get("phone") or "").strip()
    if not biz or not contact or "@" not in email or len(phone) < 7:
        return False, None
    svc = service if service == "website" else "reviews"
    lid = add_lead(business_name=biz, contact_name=contact, email=email, phone=phone, service=svc)
    lead = {"business_name": biz, "contact_name": contact, "email": email, "phone": phone, "service": svc}
    checkout = create_lead_checkout(lid, email, service=svc)
    send_package_email(lead, checkout_url=checkout)
    try:
        from smsgate_sms import send_sms
        s = get_settings()
        signup_url = s.get("website_signup_url" if svc == "website" else "signup_url", "")
        send_sms(phone, f"Hi {contact}! We got your signup for {biz} — your free {'website preview' if svc == 'website' else 'sample review response'} is on its way to {email}. Sign up / pay here: {signup_url}")
    except Exception:
        pass
    return True, lid


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
    leads = [dict(r) for r in db.execute(
        "SELECT * FROM review_service_leads ORDER BY created_at DESC LIMIT 15").fetchall()]
    db.close()
    return {
        "ra_settings": get_settings(),
        "ra_prospects": prospects,
        "ra_stats": stats,
        "ra_calls": calls,
        "ra_leads": leads,
        "ra_running": running_state(),
        "ra_log": recent_log(),
    }
