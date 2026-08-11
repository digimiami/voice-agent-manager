"""
sms-gate.app SMS sender/receiver for Diazites.
Replaces Sent.dm. Credentials loaded from env/.env — NEVER hardcoded.

API (https://docs.sms-gate.app/):
  POST /3rdparty/v1/auth/token   — Basic auth (username:password) -> JWT access token
  POST /3rdparty/v1/messages     — Send SMS (Bearer token)
  GET  /3rdparty/v1/inbox        — Fetch incoming SMS
  GET  /3rdparty/v1/messages     — Message status
  POST /3rdparty/v1/webhooks     — Register webhook (sms:received, sms:delivered...)
"""
import json, os, time, threading, sqlite3
from datetime import datetime

import requests

# ── Config from env/.env ──
def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

DB_PATH = os.environ.get("VOICE_AGENT_DB", "/root/voice-agent-businesses.db")

BASE_URL = "https://api.sms-gate.app"
USERNAME = os.environ.get("SMSGATE_USERNAME", "E4BDEN")
PASSWORD = os.environ.get("SMSGATE_PASSWORD", "")
DEVICE_ID = os.environ.get("SMSGATE_DEVICE_ID", "Z-F8pJXPGR2G0_0JAFoeh")

_token_cache = {"token": None, "expires_at": 0}
_token_lock = threading.Lock()

# Scopes needed for all operations
_SCOPES = ["messages:send", "messages:list", "messages:read", "inbox:list",
           "inbox:refresh", "devices:list", "webhooks:list", "webhooks:write",
           "webhooks:delete", "logs:read"]


def is_configured():
    """True if password is set."""
    return bool(PASSWORD)


def get_access_token(force=False):
    """Get (and cache) a JWT access token via Basic auth."""
    if not PASSWORD:
        raise RuntimeError("SMSGATE_PASSWORD not set in .env")
    with _token_lock:
        now = time.time()
        if not force and _token_cache["token"] and _token_cache["expires_at"] > now + 60:
            return _token_cache["token"]

        resp = requests.post(
            f"{BASE_URL}/3rdparty/v1/auth/token",
            auth=(USERNAME, PASSWORD),
            json={"scopes": _SCOPES, "ttl": 3600},
            timeout=20
        )
        if resp.status_code != 201:
            raise RuntimeError(f"Token request failed ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        token = data.get("access_token", "")
        expires_at = data.get("expires_at", "")
        try:
            exp_ts = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
        except:
            exp_ts = now + 3000
        _token_cache["token"] = token
        _token_cache["expires_at"] = exp_ts
        return token


def _headers():
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }


def _clean_phone(to_phone):
    """Normalize to E.164. US/CA 10-digit numbers get +1 prefix."""
    cleaned = ''.join(c for c in str(to_phone) if c.isdigit() or c == '+')
    if not cleaned:
        return ''
    if not cleaned.startswith('+'):
        digits = ''.join(c for c in cleaned if c.isdigit())
        if len(digits) == 10:
            cleaned = '+1' + digits  # US/CA
        else:
            cleaned = '+' + digits
    return cleaned


def send_sms(to_phone, message, business_id=None, lead_id=None, priority=100):
    """Send an SMS via sms-gate.app. Returns True on success (202).
    business_id/lead_id are logged so inbound replies can be matched back.
    priority: High (100-127) bypasses rate limits/delays — verified 2026-08-02
    that priority=0 gets STUCK on the flapping C25_Ultra (device rate-limits
    same/low-priority messages), while priority>=100 sends in seconds.
    All Diazites AI SMS are time-sensitive customer replies -> high priority."""
    if not to_phone or not message:
        print("❌ send_sms: missing phone or message")
        return False
    if not is_configured():
        print("❌ sms-gate.app not configured (SMSGATE_PASSWORD missing)")
        return False

    # Clean phone — E.164 with leading +
    cleaned = _clean_phone(to_phone)

    payload = {
        "phoneNumbers": [cleaned],
        "textMessage": {"text": message},
        "deviceId": DEVICE_ID,
        "priority": priority,
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/3rdparty/v1/messages",
            headers=_headers(),
            json=payload,
            timeout=20
        )
        if resp.status_code == 202:
            data = resp.json()
            mid = data.get("id", "?")
            print(f"✅ SMS queued to {cleaned} — ID: {mid}")
            # Log outgoing SMS for reply-matching
            _log_outgoing(cleaned, message, business_id, lead_id, mid)
            return True
        print(f"❌ SMS failed ({resp.status_code}): {resp.text[:300]}")
        return False
    except Exception as e:
        print(f"❌ SMS error: {e}")
        return False


def _log_outgoing(phone, body, business_id, lead_id, message_id):
    """Record an outgoing SMS so inbound replies can be routed to the right business."""
    try:
        db = sqlite3.connect(DB_PATH)
        c = db.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS outgoing_sms (
                id TEXT PRIMARY KEY,
                business_id TEXT,
                lead_id TEXT,
                phone TEXT,
                body TEXT,
                message_id TEXT,
                sent_at TEXT
            )
        """)
        c.execute(
            "INSERT INTO outgoing_sms (id, business_id, lead_id, phone, body, message_id, sent_at) VALUES (?,?,?,?,?,?,?)",
            (str(message_id) or str(time.time()), business_id, lead_id, phone, body, message_id,
             datetime.now().isoformat())
        )
        db.commit()
        db.close()
    except Exception as e:
        print(f"⚠️ outgoing log failed: {e}")


def send_welcome_sms(phone, name, bid, host_url):
    """Send welcome SMS with Business ID."""
    msg = f"🎉 Welcome to Diazites, {name}! ✅ Your Business ID: {bid}. Login at {host_url}. 3-day free trial started!"
    return send_sms(phone, msg)


def fetch_inbox(limit=50, offset=0):
    """Fetch incoming SMS messages. Returns list of dicts."""
    try:
        resp = requests.get(
            f"{BASE_URL}/3rdparty/v1/inbox",
            headers=_headers(),
            params={"limit": limit, "offset": offset},
            timeout=20
        )
        if resp.status_code == 200:
            data = resp.json()
            # JSON:API style — {data: [...]}
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            if isinstance(data, list):
                return data
        print(f"❌ Inbox fetch failed ({resp.status_code}): {resp.text[:300]}")
        return []
    except Exception as e:
        print(f"❌ Inbox error: {e}")
        return []


def get_message_status(message_id):
    """Check delivery state of a sent message."""
    try:
        resp = requests.get(
            f"{BASE_URL}/3rdparty/v1/messages/{message_id}",
            headers=_headers(),
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def list_webhooks():
    """List registered webhooks."""
    try:
        resp = requests.get(f"{BASE_URL}/3rdparty/v1/webhooks", headers=_headers(), timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", data) if isinstance(data, dict) else data
        return []
    except Exception:
        return []


def register_webhook(url, event="sms:received"):
    """Register a webhook for incoming SMS (or other events)."""
    payload = {
        "event": event,
        "url": url,
        "deviceId": DEVICE_ID,
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/3rdparty/v1/webhooks",
            headers=_headers(),
            json=payload,
            timeout=15
        )
        if resp.status_code in (200, 201):
            print(f"✅ Webhook registered: {event} -> {url}")
            return True
        print(f"❌ Webhook failed ({resp.status_code}): {resp.text[:300]}")
        return False
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return False


if __name__ == "__main__":
    print(f"Configured: {is_configured()}")
    if is_configured():
        try:
            t = get_access_token(force=True)
            print(f"✅ Token acquired: {t[:20]}...")
            devs = requests.get(f"{BASE_URL}/3rdparty/v1/devices", headers=_headers(), timeout=15)
            print(f"Devices ({devs.status_code}): {devs.text[:300]}")
        except Exception as e:
            print(f"❌ {e}")
