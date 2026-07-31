"""
Appointment reminder sender — scans booked appointments whose human-readable
time ("tomorrow at 3 PM", "friday at 10am") falls within the reminder window
(12–36h ahead), and texts the customer via sms-gate. Only businesses with
sms_reminders=1. Prints a summary (delivered by the no_agent cron).
"""
import datetime
import re
import sqlite3
import sys

sys.path.insert(0, "/root/voice-agent-manager")

DB = "/root/voice-agent-businesses.db"
MIN_HOURS = 12
MAX_HOURS = 36
WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}


def parse_appointment_time(text, now):
    """Parse 'tomorrow at 3 PM', 'friday at 10am', 'today at 5pm' -> datetime."""
    if not text:
        return None
    t = text.lower().strip()
    m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', t)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    ampm = m.group(3)
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    base = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if "tomorrow" in t:
        return base + datetime.timedelta(days=1)
    if "today" in t:
        return base
    for name, idx in WEEKDAYS.items():
        if name in t:
            days_ahead = (idx - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # next week, not today
            return base + datetime.timedelta(days=days_ahead)
    return None


def main():
    now = datetime.datetime.now()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    from smsgate_sms import send_sms

    # ensure per-appointment reminder tracking exists
    cols = [r[1] for r in conn.execute("PRAGMA table_info(appointments)")]
    if "reminder_sent_at" not in cols:
        conn.execute("ALTER TABLE appointments ADD COLUMN reminder_sent_at TEXT DEFAULT NULL")
        conn.commit()

    rows = conn.execute(
        "SELECT a.id, a.business_id, a.phone, a.prospect_name, a.appointment_time, b.name AS biz_name "
        "FROM appointments a JOIN businesses b ON a.business_id = b.id "
        "WHERE a.status='booked' AND b.sms_reminders=1 "
        "AND (a.reminder_sent_at IS NULL OR a.reminder_sent_at = '')").fetchall()

    sent = []
    skipped = []
    for r in rows:
        appt_dt = parse_appointment_time(r["appointment_time"], now)
        if not appt_dt:
            skipped.append((r["id"], "unparseable"))
            continue
        hours = (appt_dt - now).total_seconds() / 3600
        if not (MIN_HOURS <= hours <= MAX_HOURS):
            continue
        body = (f"Hi {r['prospect_name'] or 'there'}! Reminder: your appointment with "
                f"{r['biz_name'] or 'us'} is {r['appointment_time']}. "
                "Reply CONFIRM to keep it or CANCEL to reschedule.")
        try:
            ok = send_sms(r["phone"], body, business_id=r["business_id"])
            if ok:
                conn.execute("UPDATE appointments SET reminder_sent_at=? WHERE id=?",
                             (datetime.datetime.utcnow().isoformat(), r["id"]))
                conn.commit()
                sent.append((r["id"], r["appointment_time"]))
                print(f"📅 Reminder sent: {r['phone']} @ {r['appointment_time']}")
            else:
                skipped.append((r["id"], "send-failed"))
        except Exception as e:
            skipped.append((r["id"], str(e)[:40]))

    conn.close()
    if sent:
        print(f"📅 Appointment reminders sent: {len(sent)}")


if __name__ == "__main__":
    main()
