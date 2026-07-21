#!/usr/bin/env python3
"""
Helper module for buying Twilio numbers and registering with Vapi.
"""
import json, subprocess, urllib.request, urllib.parse

DB_PATH = "/root/voice-agent-businesses.db"
VAPI_BASE = "https://api.vapi.ai"
VAPI_API_KEY = "49e91b8a-21d2-458c-a586-d6368289e5a6"

def load_twilio_config():
    try:
        with open('/root/voice-agent-manager/twilio_config.json') as f:
            return json.load(f)
    except:
        return {}

def twilio_api_get(path):
    """Call Twilio REST API GET."""
    tc = load_twilio_config()
    sid = tc.get('account_sid', '')
    token = tc.get('auth_token', '')
    if not sid or not token:
        return None, "Twilio not configured"
    import base64
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/{path}",
        headers={"Authorization": f"Basic {auth}"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        try:
            msg = json.loads(err).get('message', err[:200])
        except:
            msg = err[:200]
        return None, msg
    except Exception as e:
        return None, str(e)

def twilio_api_post(path, data):
    """Call Twilio REST API POST."""
    tc = load_twilio_config()
    sid = tc.get('account_sid', '')
    token = tc.get('auth_token', '')
    if not sid or not token:
        return None, "Twilio not configured"
    import base64
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    payload = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/{path}",
        data=payload,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        try:
            msg = json.loads(err).get('message', err[:200])
        except:
            msg = err[:200]
        return None, msg
    except Exception as e:
        return None, str(e)

def search_available_numbers(area_code=None, contains=None, limit=10):
    """Search for available local numbers on Twilio."""
    path = "AvailablePhoneNumbers/US/Local.json"
    params = []
    if area_code:
        params.append(f"AreaCode={area_code}")
    if contains:
        params.append(f"Contains={contains}")
    params.append(f"Limit={limit}")
    if params:
        path += "?" + "&".join(params)
    
    result, error = twilio_api_get(path)
    if error:
        return None, error
    nums = result.get('available_phone_numbers', [])
    if not nums:
        return None, "No numbers available in that area code"
    return nums, None

def buy_twilio_number(phone_number, voice_url=None):
    """Purchase a phone number from Twilio."""
    data = {
        "PhoneNumber": phone_number,
        "Voice": "true",
        "SmsEnabled": "true",
        "StatusCallback": "https://diazites.online/api/vapi/webhook"
    }
    if voice_url:
        data["VoiceUrl"] = voice_url
    
    result, error = twilio_api_post("IncomingPhoneNumbers.json", data)
    if error:
        return None, error
    return result, None

def register_with_vapi(phone_number, assistant_id):
    """Register an already-purchased Twilio number with Vapi."""
    tc = load_twilio_config()
    sid = tc.get('account_sid', '')
    token = tc.get('auth_token', '')
    
    payload = {
        "provider": "twilio",
        "number": phone_number,
        "assistantId": assistant_id,
        "twilioAccountSid": sid,
        "twilioAuthToken": token
    }
    
    result = subprocess.run([
        "curl", "-s", "-X", "POST", f"{VAPI_BASE}/phone-number",
        "-H", f"Authorization: Bearer {VAPI_API_KEY}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload)
    ], capture_output=True, text=True, timeout=30)
    
    try:
        data = json.loads(result.stdout)
        if data.get('id'):
            return data, None
        msg = data.get('message', str(data))
        if isinstance(msg, list):
            msg = '; '.join(msg)
        return None, msg
    except Exception as e:
        return None, str(e) or result.stdout[:200]

def buy_and_assign_number(assistant_id, area_code=None):
    """
    Full flow: search → buy → register → return phone data.
    Returns (phone_id, phone_number, error_message).
    """
    # Step 1: Search Twilio for available numbers
    nums, error = search_available_numbers(area_code, limit=1)
    if error:
        # Try without area code
        nums, error = search_available_numbers(None, limit=1)
        if error:
            return None, None, f"Twilio search failed: {error}"
    
    phone_to_buy = nums[0]['phone_number']
    
    # Step 2: Buy from Twilio
    twilio_result, error = buy_twilio_number(phone_to_buy)
    if error:
        return None, None, f"Twilio purchase failed: {error}"
    
    bought_number = twilio_result.get('phone_number', phone_to_buy)
    
    # Step 3: Configure Twilio voice URL to point to Vapi
    # The number was just bought - set its Voice URL to Vapi's SIP endpoint
    # We'll configure this on the Vapi side instead
    
    # Step 4: Register with Vapi
    vapi_data, error = register_with_vapi(bought_number, assistant_id)
    if error:
        return None, bought_number, f"Bought {bought_number} from Twilio but Vapi registration failed: {error}"
    
    return vapi_data['id'], bought_number, None
