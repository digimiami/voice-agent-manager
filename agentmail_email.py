#!/usr/bin/env python3
"""
AgentMail Email Integration for Diazites
=========================================
Send appointment confirmation emails with .ics calendar invites
via AgentMail API (diazites@agentmail.to).

Usage:
    from agentmail_email import send_appointment_confirmation
    send_appointment_confirmation(
        to="client@email.com",
        prospect_name="John",
        business_name="Diaz Plumbing",
        appointment_time="2026-07-25T10:00:00",
        business_phone="+1385XXXXXXX"
    )
"""

import json, base64, uuid, os
import urllib.request
from datetime import datetime, timedelta

# ── Config ──
API_KEY = "am_us_c5cf4cf40b8b25b09546e54890bb4d570a00d3a93cd9f09cfa762b6f7f139c90"
INBOX = "diazites@agentmail.to"
API_BASE = "https://api.agentmail.to"

def generate_ics(appointment_time_str, business_name, prospect_name, duration_min=30):
    """Generate .ics calendar file content."""
    try:
        dt = datetime.fromisoformat(appointment_time_str.replace('Z', '+00:00'))
    except:
        dt = datetime.now() + timedelta(days=1)
    
    end_dt = dt + timedelta(minutes=duration_min)
    uid = str(uuid.uuid4())
    
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Diazites//VoiceAgent//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{dt.strftime('%Y%m%dT%H%M%S')}
DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}
SUMMARY:Appointment with {business_name}
DESCRIPTION:Your appointment with {business_name} has been confirmed.\\n\\nProspect: {prospect_name}\\nDuration: {duration_min} minutes\\nType: Phone consultation
LOCATION:Phone Call
STATUS:CONFIRMED
SEQUENCE:0
BEGIN:VALARM
TRIGGER:-PT15M
ACTION:DISPLAY
DESCRIPTION:Reminder: Appointment with {business_name} in 15 minutes
END:VALARM
END:VEVENT
END:VCALENDAR"""
    return ics


def send_agentmail(to, subject, text, html=None, attachments=None):
    """Send email via AgentMail API."""
    payload = {
        "to": to,
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html
    if attachments:
        payload["attachments"] = attachments
    
    url = f"{API_BASE}/v0/inboxes/{INBOX.replace('@', '%40')}/messages/send"
    data = json.dumps(payload).encode()
    
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0"
    })
    
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        return result.get("message_id"), result.get("thread_id")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ AgentMail HTTP {e.code}: {body}")
        raise
    except Exception as e:
        print(f"❌ AgentMail error: {e}")
        raise


def send_appointment_confirmation(to, prospect_name, business_name, 
                                   appointment_time, business_phone="",
                                   duration_min=30, cc=None):
    """Send appointment confirmation email with .ics calendar invite."""
    
    # Parse appointment time for display
    try:
        dt = datetime.fromisoformat(appointment_time.replace('Z', '+00:00'))
        date_str = dt.strftime("%A, %B %d, %Y")
        time_str = dt.strftime("%I:%M %p").lstrip("0")
    except:
        date_str = appointment_time
        time_str = ""
    
    # Generate .ics attachment
    ics_content = generate_ics(appointment_time, business_name, prospect_name, duration_min)
    ics_b64 = base64.b64encode(ics_content.encode()).decode()
    
    attachments = [{
        "filename": f"appointment_{business_name.replace(' ', '_')}.ics",
        "content_type": "text/calendar; method=REQUEST",
        "content": ics_b64
    }]
    
    # HTML email body
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:20px">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">

<!-- Header -->
<tr><td style="background:linear-gradient(135deg,#7c3aed,#ec4899);padding:30px;border-radius:16px 16px 0 0;text-align:center">
<h1 style="color:#fff;margin:0;font-size:24px">✅ Appointment Confirmed</h1>
<p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:15px">{business_name}</p>
</td></tr>

<!-- Body -->
<tr><td style="background:#fff;padding:30px;border-radius:0 0 16px 16px">
<p style="color:#374151;font-size:16px;margin:0 0 20px">Hi <strong>{prospect_name}</strong>,</p>
<p style="color:#6b7280;font-size:15px;line-height:1.6;margin:0 0 24px">
Your appointment with <strong>{business_name}</strong> has been confirmed. Here are the details:
</p>

<!-- Details Card -->
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fd;border-radius:12px;padding:20px;margin-bottom:24px">
<tr><td>
<table width="100%">
<tr><td style="padding:6px 0"><span style="color:#6b7280;font-size:13px">📅 Date</span></td>
<td style="text-align:right;color:#374151;font-size:14px;font-weight:600">{date_str}</td></tr>
<tr><td style="padding:6px 0"><span style="color:#6b7280;font-size:13px">⏰ Time</span></td>
<td style="text-align:right;color:#374151;font-size:14px;font-weight:600">{time_str}</td></tr>
<tr><td style="padding:6px 0"><span style="color:#6b7280;font-size:13px">⏱ Duration</span></td>
<td style="text-align:right;color:#374151;font-size:14px;font-weight:600">{duration_min} minutes</td></tr>
<tr><td style="padding:6px 0"><span style="color:#6b7280;font-size:13px">📞 Type</span></td>
<td style="text-align:right;color:#374151;font-size:14px;font-weight:600">Phone Call</td></tr>
{"<tr><td style='padding:6px 0'><span style='color:#6b7280;font-size:13px'>📱 Contact</span></td><td style='text-align:right;color:#374151;font-size:14px;font-weight:600'>" + business_phone + "</td></tr>" if business_phone else ""}
</table>
</td></tr>
</table>

<!-- Calendar Button -->
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding-bottom:20px">
<p style="color:#6b7280;font-size:13px;margin:0 0 8px">
📎 A calendar invite (.ics) is attached to this email — click to add to your calendar
</p>
</td></tr>
</table>

<p style="color:#6b7280;font-size:14px;line-height:1.6;margin:0 0 24px;border-top:1px solid #e5e7eb;padding-top:20px">
<strong>Need to reschedule?</strong><br>
Reply to this email or call us and we'll be happy to help.
</p>

<p style="color:#374151;font-size:14px;margin:0">
Best regards,<br>
<strong>{business_name} Team</strong><br>
<span style="color:#9ca3af;font-size:12px">Powered by Diazites AI Voice Agents</span>
</p>
</td></tr>

<!-- Footer -->
<tr><td style="text-align:center;padding:16px;color:#9ca3af;font-size:11px">
<p style="margin:0">This is an automated confirmation from your Diazites AI voice agent.</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
    
    # Plain text fallback
    text = f"""✅ Appointment Confirmed - {business_name}

Hi {prospect_name},

Your appointment with {business_name} has been confirmed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Date:  {date_str}
⏰ Time:  {time_str}
⏱ Duration: {duration_min} minutes
📞 Type: Phone Call
{f"📱 Contact: {business_phone}" if business_phone else ""}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A calendar invite (.ics) is included as an attachment — open it to add to your calendar.

Need to reschedule? Reply to this email or call us.

Best regards,
{business_name} Team
Powered by Diazites AI Voice Agents"""
    
    # Send
    msg_id, thread_id = send_agentmail(
        to=to,
        subject=f"✅ Appointment Confirmed - {business_name}",
        text=text,
        html=html,
        attachments=attachments
    )
    
    print(f"📧 Confirmation sent to {to} via AgentMail")
    print(f"   Message ID: {msg_id}")
    print(f"   Thread ID: {thread_id}")
    return msg_id, thread_id


def send_business_welcome(to, biz_name, bid):
    """Send welcome credentials via AgentMail."""
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:20px">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">
<tr><td style="background:linear-gradient(135deg,#7c3aed,#ec4899);padding:30px;border-radius:16px 16px 0 0;text-align:center">
<h1 style="color:#fff;margin:0;font-size:24px">🎉 Welcome to Diazites!</h1>
<p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:15px">Your AI Voice Agent is Ready</p>
</td></tr>
<tr><td style="background:#fff;padding:30px;border-radius:0 0 16px 16px">
<p style="color:#374151;font-size:16px;margin:0 0 20px">Hi <strong>{biz_name}</strong> Team,</p>
<p style="color:#6b7280;font-size:15px;line-height:1.6;margin:0 0 24px">
Your AI voice agent has been created and is ready to start booking appointments!
</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fd;border-radius:12px;padding:20px;margin-bottom:24px">
<tr><td style="padding:6px 0"><span style="color:#6b7280;font-size:13px">🔐 Business ID</span></td>
<td style="text-align:right;color:#374151;font-size:14px;font-weight:600">{bid}</td></tr>
<tr><td style="padding:6px 0"><span style="color:#6b7280;font-size:13px">🌐 Dashboard</span></td>
<td style="text-align:right;color:#7c3aed;font-size:14px;font-weight:600"><a href="https://diazites.online" style="color:#7c3aed">diazites.online</a></td></tr>
</table>
<ol style="color:#6b7280;font-size:14px;line-height:1.8;margin:0 0 20px;padding-left:20px">
<li>Go to <a href="https://diazites.online" style="color:#7c3aed">diazites.online</a></li>
<li>Enter your Business ID: <strong>{bid}</strong></li>
<li>Click "Access Dashboard"</li>
<li>Upload your leads</li>
<li>Start your campaign!</li>
</ol>
<p style="color:#6b7280;font-size:14px;margin:0">Need help? Contact your account manager.</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""
    
    text = f"""🎉 Welcome to Diazites!

Hi {biz_name} Team,

Your AI voice agent has been created and is ready to start booking appointments!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 Business ID: {bid}
🌐 Dashboard: https://diazites.online
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to https://diazites.online
2. Enter your Business ID: {bid}
3. Click "Access Dashboard"
4. Upload your leads
5. Start your campaign!

Need help? Contact your account manager."""

    msg_id, thread_id = send_agentmail(
        to=to,
        subject=f"🎉 Welcome to Diazites - Your {biz_name} Dashboard",
        text=text,
        html=html
    )
    print(f"📧 Welcome email sent to {to} for {biz_name}")
    return msg_id, thread_id


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        msg_id, thread_id = send_appointment_confirmation(
            to="digimiami@gmail.com",
            prospect_name="John Doe",
            business_name="Diaz Plumbing Services",
            appointment_time=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            business_phone="+13855551234"
        )
        print(f"✅ Test complete: {msg_id}")
    else:
        print("Usage: python3 agentmail_email.py test")
