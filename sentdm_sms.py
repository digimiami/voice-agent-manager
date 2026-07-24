"""Sent.dm SMS sender for Diazites."""
import requests

SENT_API_KEY = "af92a016-9230-44de-849d-8fb042c2d475"
SENT_URL = "https://api.sent.dm/v3/messages"


def send_sms(to_phone, message):
    """Send an SMS via Sent.dm API."""
    if not to_phone or not message:
        print("❌ send_sms: missing phone or message")
        return False
    
    # Clean phone number — remove non-digits
    cleaned = ''.join(c for c in to_phone if c.isdigit() or c == '+')
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    
    payload = {
        "to": [cleaned],
        "channel": ["sms"],
        "template": {
            "name": "generic_message",
            "parameters": {"1": message}
        }
    }
    
    try:
        resp = requests.post(
            SENT_URL,
            headers={"x-api-key": SENT_API_KEY},
            json=payload,
            timeout=15
        )
        data = resp.json()
        if resp.status_code in (200, 201):
            print(f"✅ SMS sent to {cleaned}: {data}")
            return True
        else:
            print(f"❌ SMS failed ({resp.status_code}): {data}")
            return False
    except Exception as e:
        print(f"❌ SMS error: {e}")
        return False


def send_welcome_sms(phone, name, bid, host_url):
    """Send welcome SMS with Business ID."""
    msg = f"Welcome to Diazites, {name}! Your Business ID: {bid}. Login at {host_url}. 3-day free trial started!"
    return send_sms(phone, msg)
