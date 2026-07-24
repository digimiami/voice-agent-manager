"""Sent.dm SMS sender for Diazites."""
import requests

SENT_API_KEY = "af92a016-9230-44de-849d-8fb042c2d475"
SENT_URL = "https://api.sent.dm/v3/messages"


def send_sms(to_phone, message):
    """Send an SMS via Sent.dm API."""
    if not to_phone or not message:
        print("❌ send_sms: missing phone or message")
        return False
    
    # Clean phone number — ensure E.164 format
    cleaned = ''.join(c for c in to_phone if c.isdigit() or c == '+')
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    
    payload = {
        "to": [cleaned],
        "channel": ["sms"],
        "text": message
    }
    
    try:
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


def send_welcome_sms(phone, name, bid, host_url):
    """Send welcome SMS with Business ID."""
    msg = f"🎉 Welcome to Diazites, {name}! ✅ Your Business ID: {bid}. Login at {host_url}. 3-day free trial started!"
    return send_sms(phone, msg)
