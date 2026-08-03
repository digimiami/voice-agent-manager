"""
Appointment reminder sender — scans booked appointments and texts the customer
via sms-gate ~12 hours before their appointment, ONLY during the business's
business hours (call_window_start → call_window_end, in the business timezone).

Rules:
  * Only businesses with sms_reminders=1 get reminders.
  * A reminder fires 12h before the appointment, but never outside business
    hours: if the 12h mark falls before open, it fires at open; if it falls
    after close, it fires at close (same day).
  * Each appointment is reminded once (reminder_sent_at column).
  * Supports NLP times ("tomorrow at 3 PM") and ISO times ("2026-08-10 at 2:30 PM").

Run every 30 min from cron. Prints a summary (delivered by the no_agent cron).
"""
import datetime
import re
import sqlite3
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, "/root/voice-agent-manager")

DB = "/root/voice-agent-businesses.db"
LEAD_HOURS = 12          # send ~12h before the appointment
WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}


def parse_appointment_time(text, now):
    """Parse 'tomorrow at 3 PM', 'friday at 10am', '2026-08-10 at 2:30 PM' -> datetime (tz-aware)."""
    if not text:
        return None
    t = text.lower().strip()
    base_now = now.replace(second=0, microsecond=0)
    day = None

    # ISO date: 2026-08-10
    im = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', t)
    if im:
        try:
            day = datetime.date(int(im.group(1)), int(im.group(2)), int(im.group(3)))
        except ValueError:
            return None
        base_now = datetime.datetime.combine(day, datetime.time(0, 0), tzinfo=now.tzinfo)
    elif "tomorrow" in t:
        day = (now + datetime.timedelta(days=1)).date()
    elif "today" in t or "tonight" in t:
        day = now.date()
    else:
        for name, idx in WEEKDAYS.items():
            if name in t:
                days_ahead = (idx - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7  # next week, not today
                day = (now + datetime.timedelta(days=days_ahead)).date()
                break
        if day is None:
            return None

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
    return datetime.datetime.combine(day, datetime.time(hour, minute), tzinfo=now.tzinfo)


def business_hours(biz):
    """Return (open_time, close_time) as datetime.time from a businesses row."""
    try:
        open_t = datetime.time.fromisoformat((biz["call_window_start"] or "09:00")[:5])
    except ValueError:
        open_t = datetime.time(9, 0)
    try:
        close_t = datetime.time.fromisoformat((biz["call_window_end"] or "17:00")[:5])
    except ValueError:
        close_t = datetime.time(17, 0)
    return open_t, close_t


def scheduled_send_time(appt_dt, open_t, close_t):
    """12h before the appointment, clamped into the business hours of that day."""
    candidate = appt_dt - datetime.timedelta(hours=LEAD_HOURS)
    open_dt = datetime.datetime.combine(candidate.date(), open_t, tzinfo=appt_dt.tzinfo)
    close_dt = datetime.datetime.combine(candidate.date(), close_t, tzinfo=appt_dt.tzinfo)
    if candidate < open_dt:
        return open_dt
    if candidate > close_dt:
        return close_dt
    return candidate


def main():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    from smsgate_sms import send_sms

    # ensure per-appointment reminder tracking exists
    cols = [r[1] for r in conn.execute("PRAGMA table_info(appointments)")]
    if "reminder_sent_at" not in cols:
        conn.execute("ALTER TABLE appointments ADD COLUMN reminder_sent_at TEXT DEFAULT NULL")
        conn.commit()

    rows = conn.execute(
        "SELECT a.id, a.business_id, a.phone, a.prospect_name, a.appointment_time, "
        "       b.name AS biz_name, b.timezone, b.call_window_start, b.call_window_end "
        "FROM appointments a JOIN businesses b ON a.business_id = b.id "
        "WHERE a.status='booked' AND b.sms_reminders=1 "
        "AND (a.reminder_sent_at IS NULL OR a.reminder_sent_at = '')").fetchall()

    sent = []
    skipped = []
    for r in rows:
        try:
            tz = ZoneInfo(r["timezone"] or "America/New_York")
        except Exception:
            tz = ZoneInfo("America/New_York")
        now = now_utc.astimezone(tz)

        appt_dt = parse_appointment_time(r["appointment_time"], now)
        if not appt_dt:
            skipped.append((r["id"], "unparseable"))
            continue
        if appt_dt <= now:
            continue  # already past

        open_t, close_t = business_hours(r)
        send_at = scheduled_send_time(appt_dt, open_t, close_t)
        if send_at > appt_dt:
            send_at = appt_dt  # safety: never later than the appointment itself

        if now < send_at:
            continue  # not yet time — wait for the next tick

        body = (f"Hi {r['prospect_name'] or 'there'}! Reminder: your appointment with "
                f"{r['biz_name'] or 'us'} is {r['appointment_time']}. "
                "Reply CONFIRM to keep it or CANCEL to reschedule.")
        try:
            ok = send_sms(r["phone"], body, business_id=r["business_id"])
            if ok:
                conn.execute("UPDATE appointments SET reminder_sent_at=? WHERE id=?",
                             (now_utc.isoformat(), r["id"]))
                conn.commit()
                sent.append((r["id"], r["appointment_time"]))
                print(f"📅 Reminder sent: {r['phone']} @ {r['appointment_time']} (biz {r['biz_name']})")
            else:
                skipped.append((r["id"], "send-failed"))
        except Exception as e:
            skipped.append((r["id"], str(e)[:40]))

    conn.close()
    if sent:
        print(f"📅 Appointment reminders sent: {len(sent)}")


if __name__ == "__main__":
    main()
