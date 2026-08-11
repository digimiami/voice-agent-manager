"""
Appointment reminder sender — scans booked appointments and texts the customer
via sms-gate ~12 hours before their appointment, ONLY during the business's
business hours (call_window_start → call_window_end, in the business timezone).
Also sends an EMAIL reminder (AgentMail) when the customer gave an email.

Rules:
  * Only businesses with sms_reminders=1 get reminders.
  * A reminder fires 12h before the appointment, but never outside business
    hours: if the 12h mark falls before open, it fires at open; if it falls
    after close, it fires at close (same day).
  * Each appointment is reminded once (reminder_sent_at column).
  * Supports NLP times ("tomorrow at 3 PM"), ISO times ("2026-08-10 at 2:30 PM"),
    and raw ISO ("2026-08-10T14:00:00" — what the AI booking tool sends).
  * force=True (dashboard "Send Reminders Now"): send to EVERY upcoming booked
    appointment immediately, ignoring the 12h window and business hours.

Run every 30 min from cron. Prints a summary (delivered by the no_agent cron).
"""
import datetime
import re
import sqlite3
import sys
import time
from zoneinfo import ZoneInfo

sys.path.insert(0, "/root/voice-agent-manager")

DB = "/root/voice-agent-businesses.db"
LEAD_HOURS = 12          # send ~12h before the appointment
WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
RELATIVE_TOKENS = ("today", "tonight", "tomorrow") + tuple(WEEKDAYS.keys())


def parse_appointment_time(text, now):
    """Parse 'tomorrow at 3 PM', 'friday at 10am', '2026-08-10 at 2:30 PM',
    '2026-08-10T14:00:00' -> datetime (tz-aware)."""
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
        # ISO time right after the date: "2026-08-09T13:20:20" or "2026-08-09 13:20" (t is lowercased!)
        tm = re.search(r'[t ](\d{1,2}):(\d{2})', t)
        if tm:
            hour = int(tm.group(1))
            if hour > 23:
                return None
            return datetime.datetime.combine(day, datetime.time(hour, int(tm.group(2))), tzinfo=now.tzinfo)
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


def normalize_appointment_time(raw, tz_name="America/New_York"):
    """Resolve a relative/NLP appointment time ('tomorrow at 3 PM', 'friday at 10am')
    to an absolute 'YYYY-MM-DD at H:MM AM' string so it never drifts with time.
    Returns the original raw string if it can't be resolved."""
    if not raw:
        return raw
    try:
        tz = ZoneInfo(tz_name or "America/New_York")
    except Exception:
        tz = ZoneInfo("America/New_York")
    now = datetime.datetime.now(tz)
    dt = parse_appointment_time(raw, now)
    if not dt:
        return raw
    hour12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{dt.date().isoformat()} at {hour12}:{dt.minute:02d} {ampm}"


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
    sent, skipped = run_reminders()
    for s in sent:
        print(f"📅 Reminder sent: {s[1]} @ {s[2]} (biz {s[3]})")
    if sent:
        print(f"📅 Appointment reminders sent: {len(sent)}")


def run_reminders(business_id=None, force=False):
    """Scan due appointments and send reminders (SMS + email).

    Returns (sent, skipped) where sent is a list of
    (id, phone, appointment_time, biz_name, sms_flag, email_flag) tuples.
    Optionally restrict to a single business (used by the dashboard's
    "Send Reminders Now" button, which passes force=True).

    force=True: send to EVERY upcoming booked appointment immediately,
    ignoring the 12h window and business hours.
    force=False (cron): only fire inside the 12h window clamped to business hours.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    from smsgate_sms import send_sms

    # ensure per-appointment reminder tracking + email column exist
    cols = [r[1] for r in conn.execute("PRAGMA table_info(appointments)")]
    if "reminder_sent_at" not in cols:
        conn.execute("ALTER TABLE appointments ADD COLUMN reminder_sent_at TEXT DEFAULT NULL")
        conn.commit()
    if "email" not in cols:
        conn.execute("ALTER TABLE appointments ADD COLUMN email TEXT DEFAULT ''")
        conn.commit()

    if business_id:
        rows = conn.execute(
            "SELECT a.id, a.business_id, a.phone, a.email, a.prospect_name, a.appointment_time, "
            "       a.created_at, "
            "       b.name AS biz_name, b.timezone, b.call_window_start, b.call_window_end, "
            "       b.business_address, b.phone_number AS biz_phone "
            "FROM appointments a JOIN businesses b ON a.business_id = b.id "
            "WHERE a.status='booked' AND b.sms_reminders=1 AND a.business_id=? "
            "AND (a.reminder_sent_at IS NULL OR a.reminder_sent_at = '')",
            (business_id,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT a.id, a.business_id, a.phone, a.email, a.prospect_name, a.appointment_time, "
            "       a.created_at, "
            "       b.name AS biz_name, b.timezone, b.call_window_start, b.call_window_end, "
            "       b.business_address, b.phone_number AS biz_phone "
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

        # Staleness guard: relative times ("tomorrow", "friday", ...) resolve against
        # TODAY — a booking from weeks ago must not re-fire as if booked for this week.
        raw_l = (r["appointment_time"] or "").lower()
        if not re.search(r"\d{4}-\d{1,2}-\d{1,2}", raw_l) and r["created_at"]:
            rel = [t for t in RELATIVE_TOKENS if t in raw_l]
            if rel:
                try:
                    created = datetime.datetime.fromisoformat(
                        str(r["created_at"]).replace("Z", "+00:00"))
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=now.tzinfo)
                    else:
                        created = created.astimezone(now.tzinfo)
                    max_days = 2 if any(t in ("today", "tonight", "tomorrow")
                                        for t in rel) else 8
                    if (appt_dt.date() - created.date()).days > max_days:
                        skipped.append((r["id"], "stale"))
                        continue
                except Exception:
                    pass

        if appt_dt <= now:
            continue  # already past

        open_t, close_t = business_hours(r)
        if not force:
            send_at = scheduled_send_time(appt_dt, open_t, close_t)
            if send_at > appt_dt:
                send_at = appt_dt  # safety: never later than the appointment itself
            if now < send_at:
                continue  # not yet time — wait for the next tick

        name = r["prospect_name"] or "there"
        biz_name = r["biz_name"] or "us"
        addr = r["business_address"] or ""
        biz_phone = r["biz_phone"] or ""
        # Pretty "Saturday, August 15 at 2:00 PM" display
        try:
            from datetime import datetime as _dt
            _d = _dt.fromisoformat(str(r["appointment_time"]).replace("Z", "+00:00"))
            when = f"{_d.strftime('%A, %B %d')} at {_d.strftime('%I:%M %p').lstrip('0')}"
        except Exception:
            when = r["appointment_time"]

        sms_body = (f"Hi {name}! ⏰ Reminder: your test drive at {biz_name} is "
                    f"{when}. 📍 {biz_name}: {addr} | 📞 {biz_phone}. "
                    "Reply CONFIRM to keep it or CANCEL to reschedule.")
        delivered_sms = False
        # sms-gate intermittently 401s on /messages — retry up to 3x (known quirk)
        for _attempt in range(3):
            try:
                if send_sms(r["phone"], sms_body, business_id=r["business_id"]):
                    delivered_sms = True
                    break
            except Exception as _e:
                skipped.append((r["id"], f"sms-exc:{str(_e)[:24]}"))
            time.sleep(2)

        # Email reminder (best-effort — never blocks the SMS path)
        delivered_email = False
        if r["email"]:
            try:
                import agentmail_email
                subject = f"⏰ Reminder: Your Test Drive at {biz_name} is {when}"
                html = (f"<div style='font-family:-apple-system,sans-serif;padding:20px'>"
                        f"<h2 style='margin:0 0 12px'>⏰ Appointment Reminder</h2>"
                        f"<p>Hi <strong>{name}</strong>,</p>"
                        f"<p>Just a reminder that your test drive at <strong>{biz_name}</strong> "
                        f"is <strong>{when}</strong>.</p>"
                        f"<table cellpadding='6' style='background:#f8f9fd;border-radius:10px;margin:16px 0'>"
                        f"<tr><td style='color:#6b7280'>📍 Address</td><td style='font-weight:600'>{addr}</td></tr>"
                        f"<tr><td style='color:#6b7280'>📞 Phone</td><td style='font-weight:600'>{biz_phone}</td></tr>"
                        f"</table>"
                        f"<p style='color:#6b7280'>Reply to this email or call {biz_phone} to reschedule.</p>"
                        f"<p style='color:#9ca3af;font-size:12px'>— {biz_name}</p></div>")
                _mid, _tid = agentmail_email.send_agentmail(r["email"], subject, "", html=html)
                delivered_email = bool(_mid)
            except Exception:
                pass

        if delivered_sms or delivered_email:
            conn.execute("UPDATE appointments SET reminder_sent_at=? WHERE id=?",
                         (now_utc.isoformat(), r["id"]))
            conn.commit()
            sent.append((r["id"], r["phone"], r["appointment_time"], r["biz_name"],
                         "sms" if delivered_sms else "", "email" if delivered_email else ""))
        else:
            skipped.append((r["id"], "send-failed"))

    conn.close()
    return sent, skipped


if __name__ == "__main__":
    main()
