#!/usr/bin/env python3
"""
Owner alerts — email (diazites.ai@gmail.com) + SMS (+17867846192) whenever a
new business signs up or a payment is made. Import from any Diazites service
(multi_biz_dashboard_v2, admin_panel, agent_api).

Usage:
    from owner_alerts import notify_owner
    notify_owner('signup', name='Joe Plumber', email='joe@x.com',
                 plan='pro', business_id='abc123', industry='plumber')
    notify_owner('payment', name='Joe Plumber', amount=197.0, plan='pro',
                 business_id='abc123', email='joe@x.com', source='checkout')

Fire-and-forget: each alert runs in a daemon thread, never blocks webhooks.
"""
import threading

ALERT_EMAIL = "diazites.ai@gmail.com"
ALERT_SMS = "+17867846192"


def _fmt_amount(amount):
    try:
        return f"${float(amount):,.2f}"
    except Exception:
        return f"${amount}"


def _build_text(kind, info):
    if kind == 'signup':
        return (
            f"🆕 NEW BUSINESS SIGNUP\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏢 {info.get('name', '?')}\n"
            f"📧 {info.get('email', '—')}\n"
            f"📱 {info.get('phone', '—')}\n"
            f"📦 Plan: {info.get('plan', '?')}\n"
            f"🏷 Industry: {info.get('industry', '?')}\n"
            f"🆔 {info.get('business_id', '?')}\n"
            f"📍 {info.get('source', 'website')}"
        )
    if kind == 'payment':
        return (
            f"💰 PAYMENT RECEIVED\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🏢 {info.get('name', info.get('email', '?'))}\n"
            f"💵 {_fmt_amount(info.get('amount'))}\n"
            f"📦 Plan: {info.get('plan', info.get('source', '?') or '?')}\n"
            f"📧 {info.get('email', '—')}\n"
            f"🆔 {info.get('business_id', '?')}\n"
            f"📍 {info.get('source', 'stripe')}"
        )
    return f"{kind.upper()}: {info}"


def _worker(kind, info):
    try:
        from agentmail_email import send_agentmail
        from smsgate_sms import send_sms

        subject = "🆕 New Signup" if kind == 'signup' else "💰 Payment Received"
        text = _build_text(kind, info)

        # Email alert (AgentMail — aiworkers@agentmail.to, the working Diazites inbox)
        try:
            send_agentmail(ALERT_EMAIL, subject, text)
            print(f"📧 Owner alert email sent ({kind})")
        except Exception as e:
            print(f"⚠️ Owner alert EMAIL failed ({kind}): {e}")

        # SMS alert (sms-gate, priority=100 high so it's never queued low)
        try:
            send_sms(ALERT_SMS, subject + "\n" + text, business_id=info.get('business_id'))
            print(f"📱 Owner alert SMS sent ({kind})")
        except Exception as e:
            print(f"⚠️ Owner alert SMS failed ({kind}): {e}")
    except Exception as e:
        print(f"⚠️ Owner alert error ({kind}): {e}")


def notify_owner(kind, **info):
    """Fire-and-forget alert to the owner (email + SMS)."""
    threading.Thread(target=_worker, args=(kind, info), daemon=True).start()


if __name__ == "__main__":
    import sys
    print("Testing owner alerts...")
    notify_owner('signup', name='Test Biz', email='test@example.com',
                 phone='+15551234567', plan='pro', business_id='test123',
                 industry='general', source='manual-test')
    print("Queued. Check sms-gate status / inbox shortly.")
