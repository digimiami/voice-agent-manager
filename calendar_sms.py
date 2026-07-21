#!/usr/bin/env python3
"""
Calendar Sync + SMS Follow-ups for the Voice Agent SaaS.
Adds to the existing dashboard.

Features:
- Calendar: ICS generation, appointment view, auto-reminders
- SMS: Follow-ups after calls, appointment reminders
"""

import json, sqlite3, uuid, os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DB_PATH = "/root/voice-agent-businesses.db"

# ── CALENDAR ──

def generate_ics(appointment_time_str, business_name, prospect_name, duration_min=30):
    """Generate an .ics calendar file content for an appointment."""
    try:
        dt = datetime.fromisoformat(appointment_time_str.replace('Z', '+00:00'))
    except:
        dt = datetime.now() + timedelta(days=1)
    
    end_dt = dt + timedelta(minutes=duration_min)
    
    uid = str(uuid.uuid4())
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//VoiceAgent//Calendar//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{dt.strftime('%Y%m%dT%H%M%S')}
DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}
SUMMARY:Appointment with {prospect_name} - {business_name}
DESCRIPTION:Booked via AI Voice Agent\\n\\nBusiness: {business_name}\\nProspect: {prospect_name}
LOCATION:Phone Call
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""
    return ics

def get_upcoming_appointments(business_id, days=30):
    """Get upcoming appointments from call_log."""
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("""
        SELECT cl.*, l.name as prospect_name, l.phone
        FROM call_log cl
        LEFT JOIN leads l ON cl.lead_id = l.id
        WHERE cl.business_id = ? AND cl.appointment_booked = 1
          AND cl.appointment_time != ''
        ORDER BY cl.appointment_time ASC
        LIMIT 20
    """, (business_id,))
    rows = [dict(r) for r in c.fetchall()]
    db.close()
    return rows

# ── SMS ──

def load_twilio_config():
    """Load Twilio config from JSON file."""
    cfg_path = '/root/voice-agent-manager/twilio_config.json'
    try:
        with open(cfg_path) as f:
            return json.load(f)
    except:
        return {'account_sid': '', 'auth_token': '', 'from_number': '', 'enabled': False}

def save_twilio_config(config):
    """Save Twilio config."""
    cfg_path = '/root/voice-agent-manager/twilio_config.json'
    with open(cfg_path, 'w') as f:
        json.dump(config, f)

def send_sms(to_number, message):
    """Send SMS via Twilio."""
    cfg = load_twilio_config()
    if not cfg.get('enabled') or not cfg.get('account_sid') or not cfg.get('auth_token'):
        print("📵 SMS not configured")
        return False
    
    try:
        from twilio.rest import Client
        client = Client(cfg['account_sid'], cfg['auth_token'])
        msg = client.messages.create(
            body=message,
            from_=cfg['from_number'],
            to=to_number
        )
        print(f"📱 SMS sent to {to_number[-4:]}: {msg.sid}")
        return True
    except Exception as e:
        print(f"❌ SMS failed: {e}")
        return False

# SMS Templates
SMS_TEMPLATES = {
    'after_call': "Hi {prospect_name}, thanks for your time! Here's a link to book directly: {booking_link}",
    'missed_call': "Hi! We missed your call at {business_name}. Reply BOOK to schedule a quick call or call us back at {business_phone}",
    'appointment_reminder': "Reminder: You have an appointment with {business_name} on {appointment_time}. Reply CONFIRM or call {business_phone} to reschedule.",
    'thank_you': "Thanks for booking with {business_name}! We look forward to speaking with you on {appointment_time}.",
}

def send_appointment_sms(phone, prospect_name, appointment_time, business_name, template_key='thank_you'):
    """Send an appointment-related SMS."""
    if not phone: return False
    tmpl = SMS_TEMPLATES.get(template_key, SMS_TEMPLATES['thank_you'])
    msg = tmpl.format(
        prospect_name=prospect_name or 'there',
        business_name=business_name,
        appointment_time=appointment_time,
        business_phone='',
        booking_link=''
    )
    return send_sms(phone, msg)
