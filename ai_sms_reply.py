"""
AI SMS Reply engine for Diazites — knowledge-base powered SMS assistant.

Flow: inbound SMS (sms-gate webhook) → business matched → if business.sms_ai_enabled:
  build conversation history → VAPI /chat (reuses the business's VAPI assistant,
  with an SMS-styled systemPrompt override) → parse BOOK| action → save appointment
  → send reply via sms-gate (logged to outgoing_sms for reply-matching).

Safety rails:
  - Never reply to opt-out keywords (STOP / UNSUBSCRIBE / CANCEL / END / QUIT)
  - Rate limit: skip if we replied to this sender within RATE_LIMIT_SECONDS
  - Only acts when the business has a VAPI assistant + sms_ai_enabled
  - BOOK| protocol: the assistant emits "BOOK|<day> <time>" on the LAST line when
    the customer has confirmed a specific time; engine saves the appointment and
    strips the protocol line before sending.
"""
import json
import os
import sqlite3
import threading
import time
import urllib.request

DB_PATH = "/root/voice-agent-businesses.db"
VAPI_BASE = "https://api.vapi.ai"
VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "d9486ec8-b862-460b-97ba-64bbb639f234")
RATE_LIMIT_SECONDS = 25
HISTORY_LIMIT = 8
OPT_OUT_KEYWORDS = ("STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "STOPALL")
HELP_KEYWORDS = ("HELP", "INFO")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_business(bid):
    conn = _get_db()
    row = conn.execute("SELECT * FROM businesses WHERE id = ?", (bid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def build_history(bid, sender, limit=HISTORY_LIMIT):
    """Merge recent incoming + outgoing messages for this sender into a role list."""
    conn = _get_db()
    inc = conn.execute(
        "SELECT body, received_at AS ts FROM incoming_sms "
        "WHERE business_id = ? AND sender = ? ORDER BY received_at DESC LIMIT ?",
        (bid, sender, limit)).fetchall()
    out = conn.execute(
        "SELECT body, sent_at AS ts FROM outgoing_sms "
        "WHERE business_id = ? AND phone = ? ORDER BY sent_at DESC LIMIT ?",
        (bid, sender, limit)).fetchall()
    conn.close()
    merged = [("user", dict(r)["body"], dict(r)["ts"]) for r in inc] + \
             [("assistant", dict(r)["body"], dict(r)["ts"]) for r in out]
    merged.sort(key=lambda x: x[2] or "")
    return [{"role": role, "content": body} for role, body, _ in merged[-limit:]]


def last_reply_seconds_ago(bid, sender):
    conn = _get_db()
    row = conn.execute(
        "SELECT sent_at FROM outgoing_sms WHERE business_id = ? AND phone = ? "
        "ORDER BY sent_at DESC LIMIT 1", (bid, sender)).fetchone()
    conn.close()
    if not row or not row["sent_at"]:
        return 9999
    try:
        from datetime import datetime
        ts = datetime.fromisoformat(row["sent_at"])
        return (datetime.now() - ts).total_seconds()
    except Exception:
        return 9999


def build_sms_prompt(biz):
    """SMS-styled system prompt grounded in the business KB + script."""
    name = biz.get("name") or "this business"
    kb = (biz.get("knowledge_base") or "").strip()
    script = (biz.get("script_template") or "").strip()
    industry = (biz.get("industry") or "general").strip()

    kb_block = f"\nKnowledge base:\n{kb}" if kb else ""
    script_block = f"\nRelevant business script/summary:\n{script[:800]}" if script else ""

    return (
        f"You are the SMS texting assistant for {name}, a {industry} business. "
        "Answer the customer's questions in TEXT MESSAGE style: 1-3 short sentences, "
        "friendly, no emojis unless natural, no markdown, no phone-script phrasing. "
        "Use ONLY the knowledge base below — never invent prices, hours, or services. "
        "If you don't know something, say you'll have the team follow up."
        f"{kb_block}{script_block}"
        "\n\nBooking protocol: if the customer wants to book, propose specific "
        "day+time options from the knowledge base. Once the customer CONFIRMS a "
        "specific day and time, end your reply with exactly one line: "
        'BOOK|<day> <time>  (e.g. BOOK|tomorrow at 3 PM). Then add a short confirmation '
        "sentence BEFORE that line. Do not output BOOK| in any other situation."
        "\n\nOpt-out: if the customer says STOP/UNSUBSCRIBE, reply just 'You are "
        "unsubscribed. Text HELP for help.' and nothing else."
    )


def call_vapi_chat(assistant_id, system_prompt, history, new_input):
    """Call VAPI /chat with the business assistant + SMS prompt override.
    Returns the assistant's reply text (or None)."""
    # Embed history so the stateless /chat endpoint has context
    if history:
        ctx = "\n".join(f"{m['role']}: {m['content']}" for m in history[-HISTORY_LIMIT:])
        system_prompt += f"\n\nConversation so far:\n{ctx}"
    payload = {
        "assistantId": assistant_id,
        "input": new_input,
        "assistantOverrides": {
            "model": {
                "provider": "xai",
                "model": "grok-4.3",
                "systemPrompt": system_prompt,
            }
        },
    }
    req = urllib.request.Request(
        f"{VAPI_BASE}/chat",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.0",  # Cloudflare blocks urllib's default UA (403)
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"❌ VAPI chat error: {e}")
        return None
    outputs = data.get("output") or data.get("outputs") or []
    for m in reversed(outputs):
        if m.get("role") == "assistant" and m.get("content"):
            return str(m["content"]).strip()
    return None


def save_appointment(biz_id, lead_id, sender, appointment_time, notes=""):
    """Insert a booked appointment + mark lead interested. Returns appt id or None."""
    import uuid
    try:
        conn = _get_db()
        appt_id = str(uuid.uuid4())[:12]
        conn.execute(
            """INSERT OR IGNORE INTO appointments
               (id, business_id, lead_id, call_log_id, prospect_name, phone, appointment_time, notes, status)
               VALUES (?, ?, ?, '', ?, ?, ?, ?, 'booked')""",
            (appt_id, biz_id, lead_id or "", "SMS Booking", sender, appointment_time, notes[:200]))
        if lead_id:
            conn.execute("UPDATE leads SET state='INTERESTED' WHERE id=? AND state NOT IN ('INTERESTED','BOOKED')",
                         (lead_id,))
        conn.commit()
        conn.close()
        print(f"✅ Appointment saved via SMS: {sender} @ {appointment_time}")
        return appt_id
    except Exception as e:
        print(f"❌ Appointment save failed: {e}")
        return None


def handle_inbound_sms(bid, sender, body, lead_id=None):
    """Main entry — called from the sms-gate webhook (background thread)."""
    try:
        if not bid or not sender or not body:
            return None
        biz = get_business(bid)
        if not biz or not biz.get("sms_ai_enabled"):
            return None
        if not biz.get("vapi_assistant_id"):
            print(f"⚠️ AI SMS: business {bid} has no VAPI assistant, skipping")
            return None

        up = (body or "").upper()
        if any(k in up for k in OPT_OUT_KEYWORDS):
            print(f"🚫 AI SMS: opt-out keyword from {sender}, no reply")
            return None

        if last_reply_seconds_ago(bid, sender) < RATE_LIMIT_SECONDS:
            print(f"⏳ AI SMS: rate-limited for {sender}, skipping")
            return None

        history = build_history(bid, sender)
        prompt = build_sms_prompt(biz)
        reply = call_vapi_chat(biz["vapi_assistant_id"], prompt, history, body)
        if not reply:
            print(f"❌ AI SMS: no reply from VAPI chat for {sender}")
            return None

        # Booking protocol: strip "BOOK|<time>" (own line OR mid-line) and save the appointment
        msg_text = reply
        book_line = None
        import re as _book_re
        m = _book_re.search(r'BOOK\|([A-Za-z0-9 ,:./-]+)', reply, _book_re.IGNORECASE)
        if m:
            book_line = m.group(1).strip()
            msg_text = _book_re.sub(r'BOOK\|[A-Za-z0-9 ,:./-]+', '', reply, flags=_book_re.IGNORECASE).strip()
            msg_text = msg_text.replace('  ', ' ').strip(' ,.;:-')
            print(f"📅 BOOK detected: {book_line}")

        if book_line:
            save_appointment(bid, lead_id, sender, book_line, notes=f"Booked via SMS AI. Original: {body[:100]}")

        # Send via sms-gate (logs to outgoing_sms → reply matching)
        import sys
        sys.path.insert(0, "/root/voice-agent-manager")
        from smsgate_sms import send_sms
        ok = send_sms(sender, msg_text, business_id=bid, lead_id=lead_id)
        print(f"🤖 AI SMS reply {'sent' if ok else 'FAILED'} to {sender}: {msg_text[:80]}")
        return msg_text if ok else None
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ AI SMS handler error: {e}")
        return None


def run_in_background(bid, sender, body, lead_id):
    t = threading.Thread(target=handle_inbound_sms, args=(bid, sender, body, lead_id), daemon=True)
    t.start()
