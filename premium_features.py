#!/usr/bin/env python3
"""
Premium Features: Analytics, Stripe, Calendar, SMS, Voice Cloning
Integrated with the Voice Agent SaaS dashboard.
"""

import json, sqlite3, os, uuid, hashlib, tempfile, time
from datetime import datetime, timedelta

DB_PATH = "/root/voice-agent-businesses.db"

# ═══════════════════════════════════════════════
# 1. ANALYTICS
# ═══════════════════════════════════════════════

def get_analytics(business_id, days=30):
    """Return analytics data for a business."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Calls over time (daily)
    c.execute("""
        SELECT date(created_at) as day, COUNT(*) as calls,
               SUM(CASE WHEN outcome='appointment_booked' THEN 1 ELSE 0 END) as bookings,
               SUM(cost) as cost
        FROM call_log WHERE business_id = ? AND created_at >= ?
        GROUP BY date(created_at) ORDER BY day
    """, (business_id, since))
    daily = [dict(r) for r in c.fetchall()]
    
    # Conversion rate
    c.execute("SELECT COUNT(*) FROM call_log WHERE business_id = ?", (business_id,))
    total_calls = c.fetchone()[0] or 1
    c.execute("SELECT COUNT(*) FROM call_log WHERE business_id = ? AND outcome='appointment_booked'", (business_id,))
    total_bookings = c.fetchone()[0]
    conv_rate = (total_bookings / total_calls * 100) if total_calls else 0
    
    # Outcomes breakdown
    c.execute("""
        SELECT outcome, COUNT(*) as count FROM call_log 
        WHERE business_id = ? GROUP BY outcome ORDER BY count DESC
    """, (business_id,))
    outcomes = [dict(r) for r in c.fetchall()]
    
    # Best calling times (hour of day)
    c.execute("""
        SELECT CAST(strftime('%H', created_at) AS INTEGER) as hour, COUNT(*) as calls,
               SUM(CASE WHEN outcome='appointment_booked' THEN 1 ELSE 0 END) as bookings
        FROM call_log WHERE business_id = ?
        GROUP BY hour ORDER BY calls DESC
    """, (business_id,))
    hour_perf = [dict(r) for r in c.fetchall()]
    
    # Top performing leads
    c.execute("""
        SELECT l.name, l.phone, COUNT(cl.id) as calls, 
               SUM(CASE WHEN cl.outcome='appointment_booked' THEN 1 ELSE 0 END) as bookings
        FROM call_log cl JOIN leads l ON cl.lead_id = l.id
        WHERE cl.business_id = ? AND cl.lead_id IS NOT NULL
        GROUP BY cl.lead_id ORDER BY bookings DESC LIMIT 10
    """, (business_id,))
    top_leads = [dict(r) for r in c.fetchall()]
    
    # Cost analysis
    c.execute("SELECT COALESCE(SUM(cost),0) FROM call_log WHERE business_id = ?", (business_id,))
    total_cost = c.fetchone()[0]
    cost_per_booking = total_cost / total_bookings if total_bookings else 0
    
    db.close()
    
    return {
        'daily': daily,
        'total_calls': total_calls,
        'total_bookings': total_bookings,
        'conv_rate': round(conv_rate, 1),
        'outcomes': outcomes,
        'hour_perf': hour_perf,
        'top_leads': top_leads,
        'total_cost': round(total_cost, 2),
        'cost_per_booking': round(cost_per_booking, 2),
    }

# ═══════════════════════════════════════════════
# 2. STRIPE BILLING
# ═══════════════════════════════════════════════

STRIPE_CONFIG_PATH = "/root/voice-agent-manager/stripe_config.json"

def load_stripe_config():
    try:
        with open(STRIPE_CONFIG_PATH) as f:
            return json.load(f)
    except:
        return {'secret_key': '', 'publishable_key': '', 'enabled': False, 'webhook_secret': ''}

def save_stripe_config(config):
    with open(STRIPE_CONFIG_PATH, 'w') as f:
        json.dump(config, f)

def create_stripe_checkout(business_id, plan_name, price_cents, email, success_url, cancel_url):
    """Create a Stripe checkout session."""
    cfg = load_stripe_config()
    if not cfg.get('enabled') or not cfg.get('secret_key'):
        return None
    
    import stripe
    stripe.api_key = cfg['secret_key']
    
    try:
        session = stripe.checkout.Session.create(
            customer_email=email,
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Voice Agent - {plan_name} Plan',
                        'description': f'AI voice agent for outbound and inbound calls',
                    },
                    'unit_amount': price_cents,
                    'recurring': {'interval': 'month'},
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={'business_id': business_id, 'plan': plan_name}
        )
        return session.url
    except Exception as e:
        print(f"❌ Stripe error: {e}")
        return None

def handle_stripe_webhook(payload, sig_header):
    """Verify and process Stripe webhook events."""
    cfg = load_stripe_config()
    if not cfg.get('webhook_secret'):
        return None
    
    import stripe
    stripe.api_key = cfg['secret_key']
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, cfg['webhook_secret'])
    except:
        return None
    
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        bid = session.get('metadata', {}).get('business_id')
        if bid:
            db = sqlite3.connect(DB_PATH)
            c = db.cursor()
            c.execute("UPDATE businesses SET subscription_status='active', stripe_subscription_id=? WHERE id=?",
                (session.get('subscription', ''), bid))
            db.commit()
            db.close()
            return {'business_id': bid, 'status': 'active'}
    
    return None

# ═══════════════════════════════════════════════
# 3. GOOGLE CALENDAR SYNC
# ═══════════════════════════════════════════════

def generate_google_calendar_url(summary, description, start_dt_str, duration_min=30):
    """Generate a Google Calendar quick-add URL (no OAuth needed)."""
    try:
        dt = datetime.fromisoformat(start_dt_str.replace('Z', '+00:00').split('.')[0])
    except:
        dt = datetime.now() + timedelta(days=1)
    
    end_dt = dt + timedelta(minutes=duration_min)
    
    import urllib.parse
    params = urllib.parse.urlencode({
        'action': 'TEMPLATE',
        'text': summary,
        'dates': f"{dt.strftime('%Y%m%dT%H%M%S')}/{end_dt.strftime('%Y%m%dT%H%M%S')}",
        'details': description,
        'location': 'Phone Call',
    })
    return f"https://calendar.google.com/calendar/render?{params}"

# ═══════════════════════════════════════════════
# 4. SMS FOLLOW-UP (webhook integration)
# ═══════════════════════════════════════════════

def send_sms_followup(business_id, lead_phone, prospect_name, outcome):
    """Send SMS based on call outcome and business settings."""
    if not lead_phone:
        return False
    
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("SELECT sms_after_call, sms_reminders, sms_missed, name FROM businesses WHERE id=?", (business_id,))
    biz = c.fetchone()
    if not biz:
        db.close()
        return False
    
    sms_after, sms_remind, sms_missed, biz_name = biz
    
    should_send = False
    msg = ""
    
    if outcome == 'appointment_booked' and sms_after == '1':
        should_send = True
        msg = f"Thanks for booking with {biz_name}! We'll confirm your appointment time soon. Reply STOP to opt out."
    elif outcome in ('customer-ended-call', 'customer-didnt-answer') and sms_missed == '1':
        should_send = True
        msg = f"Hi! We missed your call at {biz_name}. Want us to call you back? Reply YES and we'll ring you right away."
    elif outcome == 'appointment_booked' and sms_remind == '1':
        should_send = True  # Reminder SMS handled separately
    
    db.close()
    
    if should_send and msg:
        cfg_path = "/root/voice-agent-manager/twilio_config.json"
        try:
            with open(cfg_path) as f:
                cfg = json.load(f)
        except:
            return False
        
        if cfg.get('enabled') and cfg.get('account_sid') and cfg.get('auth_token'):
            try:
                from twilio.rest import Client
                client = Client(cfg['account_sid'], cfg['auth_token'])
                client.messages.create(
                    body=msg,
                    from_=cfg['from_number'],
                    to=lead_phone
                )
                print(f"📱 SMS sent to {lead_phone[-4:]}")
                return True
            except Exception as e:
                print(f"❌ SMS failed: {e}")
    
    return False

# ═══════════════════════════════════════════════
# 5. VOICE CLONING (11labs)
# ═══════════════════════════════════════════════

def clone_voice_from_file(audio_path, voice_name, business_id):
    """
    Upload audio to 11labs and create a cloned voice via VAPI.
    Returns the voice ID if successful.
    """
    if not os.path.exists(audio_path):
        return None
    
    try:
        # Step 1: Upload to 11labs via their API
        import requests
        from pathlib import Path
        
        # Get 11labs API key from VAPI's config (or use env)
        xi_api_key = os.environ.get('ELEVENLABS_API_KEY', '')
        if not xi_api_key:
            return None
        
        audio_file = Path(audio_path)
        
        # Upload to 11labs
        r = requests.post(
            f"https://api.elevenlabs.io/v1/voices/add",
            headers={"xi-api-key": xi_api_key},
            files={"files": (audio_file.name, open(audio_path, 'rb'), 'audio/mpeg')},
            data={"name": f"{voice_name} - {business_id[:8]}", "description": f"Cloned voice for {business_id}"}
        )
        
        if r.status_code == 200:
            voice_id = r.json().get('voice_id')
            print(f"🎤 Voice cloned! 11labs ID: {voice_id}")
            return voice_id
        else:
            print(f"❌ 11labs error: {r.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ Clone failed: {e}")
        return None

# ═══════════════════════════════════════════════
# ANALYTICS CHART DATA (JSON endpoint)
# ═══════════════════════════════════════════════

def get_chart_data(business_id):
    """Return chart-ready JSON data."""
    analytics = get_analytics(business_id)
    
    # Format for Chart.js
    chart_data = {
        'labels': [d['day'][5:] for d in analytics['daily']],
        'calls': [d['calls'] for d in analytics['daily']],
        'bookings': [d['bookings'] for d in analytics['daily']],
        'costs': [float(d['cost']) for d in analytics['daily']],
        'conv_rate': analytics['conv_rate'],
        'total_calls': analytics['total_calls'],
        'total_bookings': analytics['total_bookings'],
        'total_cost': analytics['total_cost'],
        'cost_per_booking': analytics['cost_per_booking'],
    }
    
    # Hour performance (best times)
    hours_data = [0]*24
    hours_bookings = [0]*24
    for h in analytics['hour_perf']:
        hours_data[h['hour']] = h['calls']
        hours_bookings[h['hour']] = h['bookings']
    
    chart_data['hours'] = hours_data
    chart_data['hours_bookings'] = hours_bookings
    chart_data['hour_labels'] = [f"{h}:00" for h in range(24)]
    
    return chart_data
