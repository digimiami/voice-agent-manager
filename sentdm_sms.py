"""
Sent.dm compatibility shim — now routes through sms-gate.app.
All existing imports of sentdm_sms (send_sms, send_welcome_sms) now
send via sms-gate.app device gateway (SMSGATE_* credentials in .env).
Kept as a fallback: if sms-gate.app is not configured, falls back to Sent.dm.
"""
import os

# Sent.dm fallback key (used only if sms-gate.app is NOT configured)
SENT_API_KEY = os.environ.get("SENT_API_KEY", "af92a016-9230-44de-849d-8fb042c2d475")
SENT_URL = "https://api.sent.dm/v3/messages"

import smsgate_sms


def send_sms(to_phone, message, business_id=None, lead_id=None):
    """Send SMS — primary: sms-gate.app, fallback: Sent.dm."""
    if smsgate_sms.is_configured():
        return smsgate_sms.send_sms(to_phone, message, business_id, lead_id)
    return _sentdm_fallback(to_phone, message)


def send_welcome_sms(phone, name, bid, host_url):
    """Send welcome SMS with Business ID."""
    msg = f"🎉 Welcome to Diazites, {name}! ✅ Your User ID: {bid}. Login at {host_url}. 3-day free trial started!"
    return send_sms(phone, msg, business_id=bid)


def _sentdm_fallback(to_phone, message):
    """Original Sent.dm implementation (fallback)."""
    if not to_phone or not message:
        print("❌ send_sms: missing phone or message")
        return False
    cleaned = ''.join(c for c in to_phone if c.isdigit() or c == '+')
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned

    payload = {
        "to": [cleaned],
        "channel": ["sms"],
        "text": message
    }
    try:
        import requests
        resp = requests.post(
            SENT_URL,
            headers={"x-api-key": SENT_API_KEY},
            json=payload,
            timeout=15
        )
        if resp.status_code == 202:
            data = resp.json()
            if data.get('success'):
                msg_id = data['data']['recipients'][0]['message_id']
                print(f"✅ SMS queued to {cleaned} — ID: {msg_id}")
                return True
        print(f"❌ SMS failed ({resp.status_code}): {resp.json()}")
        return False
    except Exception as e:
        print(f"❌ SMS error: {e}")
        return False
