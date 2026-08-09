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
import datetime
import json
import os
import re
import sqlite3
import threading
import time
import urllib.request

DB_PATH = "/root/voice-agent-businesses.db"
VAPI_BASE = "https://api.vapi.ai"
VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "d9486ec8-b862-460b-97ba-64bbb639f234")
RATE_LIMIT_SECONDS = 25
HISTORY_LIMIT = 8
OPT_OUT_KEYWORDS = ("STOP", "UNSUBSCRIBE", "STOPALL", "UNSUB")
HELP_KEYWORDS = ("HELP", "INFO")
DEDUP_SECONDS = 60

# In-memory processed-message cache: {(bid, sender, body) -> epoch}. Guards against
# sms-gate webhook redeliveries of the SAME message. Unlike a reply-rate limit this
# never blocks a real human texting a fast conversation.
_processed_lock = threading.Lock()
_processed = {}


def _mark_processed(bid, sender, body):
    """True if this exact message was already handled within DEDUP_SECONDS."""
    global _processed
    key = (bid, sender, body)
    now = time.time()
    with _processed_lock:
        if _processed.get(key, 0) > now - DEDUP_SECONDS:
            return False
        _processed[key] = now
        # prune old entries
        cutoff = now - 300
        for k in [k for k, v in _processed.items() if v < cutoff]:
            del _processed[k]
        return True


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


def build_sms_prompt(biz, current_appt=None):
    """SMS-styled system prompt grounded in the business KB + script.
    current_appt: dict from appointments (or None) so the AI knows what to
    cancel/reschedule."""
    name = biz.get("name") or "this business"
    kb = (biz.get("knowledge_base") or "").strip()
    script = (biz.get("script_template") or "").strip()
    industry = (biz.get("industry") or "general").strip()

    # Append uploaded documents (menus / inventories / URLs) to the KB
    try:
        _conn = sqlite3.connect(DB_PATH)
        _conn.row_factory = sqlite3.Row
        _docs = _conn.execute(
            "SELECT name, content FROM kb_documents WHERE business_id=? ORDER BY created_at",
            (biz.get("id"),)).fetchall()
        _conn.close()
        _blocks = [f"📄 {d['name']}:\n{d['content']}" for d in _docs]
        if _blocks:
            kb = (kb + "\n\n[DOCUMENTS — the business's official documents (menu, inventory, catalog). "
                  "If anything conflicts with the knowledge base, the DOCUMENTS are the source of truth. "
                  "Use them to answer customer questions.]\n" + "\n\n".join(_blocks)).strip()[:60000]
    except Exception:
        pass

    kb_block = f"\nKnowledge base:\n{kb}" if kb else ""
    script_block = f"\nRelevant business script/summary:\n{script[:800]}" if script else ""
    appt_block = ""
    if current_appt and current_appt.get("appointment_time"):
        appt_block = (
            f"\n\nThis customer's CURRENT appointment: {current_appt['appointment_time']} "
            f"(status: {current_appt.get('status')}). Only cancel/reschedule THIS one."
        )

    return (
        f"You are the SMS texting assistant for {name}, a {industry} business. "
        "Answer the customer's questions in TEXT MESSAGE style: 1-3 short sentences, "
        "friendly, no emojis unless natural, no markdown, no phone-script phrasing. "
        "Use ONLY the knowledge base below — never invent prices, hours, or services. "
        "If you don't know something, say you'll have the team follow up. "
        "LANGUAGE: always reply in the SAME LANGUAGE the customer writes in "
        "(English, Spanish, Portuguese, French, etc.). If they write Spanish, reply in Spanish."
        f"{kb_block}{script_block}{appt_block}"
        "\n\nProtocols (these control the system — NEVER show the protocol text to the customer, "
        "always write a normal confirmation sentence too):"
        "\n- BOOK: if the customer wants a NEW appointment and CONFIRMS a specific day+time, "
        "end your reply with exactly: BOOK|<day> <time>  (e.g. BOOK|tomorrow at 3 PM)"
        "\n- CANCEL: if the customer asks to CANCEL their appointment, end your reply with exactly: CANCEL|"
        "\n- MOVE: if the customer wants to RESCHEDULE and agrees on a new day+time, "
        "end your reply with exactly: MOVE|<day> <time>"
        "\n- CALLME: if the customer asks to be CALLED BACK or wants to talk to a person "
        "on the phone, end your reply with exactly: CALLME|"
        "\nOnly emit one protocol per reply. Do not output any protocol in any other situation."
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
        # Resolve relative times ("tomorrow at 3 PM") to absolute ISO-ish strings
        # right now, so the reminder engine never re-interprets them weeks later.
        try:
            from appointment_reminder import normalize_appointment_time
            tz_name = "America/New_York"
            conn_tz = _get_db()
            try:
                row = conn_tz.execute(
                    "SELECT timezone FROM businesses WHERE id=?", (biz_id,)).fetchone()
                if row and row[0]:
                    tz_name = row[0]
            except Exception:
                pass
            conn_tz.close()
            appointment_time = normalize_appointment_time(appointment_time, tz_name) or appointment_time
        except Exception as e:
            print(f"⚠️ normalize_appointment_time failed: {e}")
        conn = _get_db()
        appt_id = str(uuid.uuid4())[:12]
        conn.execute(
            """INSERT OR IGNORE INTO appointments
               (id, business_id, lead_id, call_log_id, prospect_name, phone, appointment_time, notes, status, source)
               VALUES (?, ?, ?, '', ?, ?, ?, ?, 'booked', 'ai')""",
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


def find_current_appointment(biz_id, phone):
    """Most recent booked appointment for this phone."""
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM appointments WHERE business_id=? AND phone=? AND status='booked' "
        "ORDER BY created_at DESC LIMIT 1", (biz_id, phone)).fetchone()
    conn.close()
    return dict(row) if row else None


def cancel_appointment(appt_id):
    conn = _get_db()
    conn.execute("UPDATE appointments SET status='cancelled' WHERE id=?", (appt_id,))
    conn.commit()
    conn.close()
    print(f"🚫 Appointment cancelled: {appt_id}")


def move_appointment(appt_id, new_time):
    conn = _get_db()
    conn.execute("UPDATE appointments SET appointment_time=? WHERE id=?", (new_time, appt_id))
    conn.commit()
    conn.close()
    print(f"🔄 Appointment moved: {appt_id} -> {new_time}")


def trigger_call_back(biz, phone):
    """Place a VAPI call from the business to the customer (SMS 'call me back')."""
    if not phone.startswith("+"):
        phone = "+" + phone
    payload = {
        "assistantId": biz.get("vapi_assistant_id"),
        "phoneNumberId": biz.get("vapi_phone_id"),
        "customer": {"number": phone},
        "assistantOverrides": {
            "variableValues": {
                "business_name": biz.get("name") or "",
                "industry": biz.get("industry") or "",
            }
        },
    }
    req = urllib.request.Request(
        f"{VAPI_BASE}/call",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        cid = data.get("id")
        print(f"📞 Callback call placed: {cid} -> {phone}")
        if cid:
            # Log the call so the webhook can match business_id (reply routing)
            # and fall back to the lead's name in confirmations.
            try:
                import sqlite3 as _cl_db
                import uuid as _cl_uid
                _c = _cl_db.connect("/root/voice-agent-businesses.db")
                _lead = _c.execute(
                    "SELECT id, name FROM leads WHERE phone=? AND business_id=? "
                    "ORDER BY created_at DESC LIMIT 1", (phone, biz.get("id"))).fetchone()
                _c.execute(
                    "INSERT INTO call_log (id, vapi_call_id, business_id, lead_id, status, outcome, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    ("cl_" + _cl_uid.uuid4().hex[:10], cid, biz.get("id"),
                     _lead[0] if _lead else "", "in-progress", "called",
                     datetime.datetime.utcnow().isoformat()))
                _c.commit()
                _c.close()
                print(f"📝 callback call_log row created (lead: {_lead[1] if _lead else 'unknown'})")
            except Exception as _le:
                print(f"⚠️ callback call_log insert failed: {_le}")
        return cid
    except Exception as e:
        print(f"❌ Callback call failed: {e}")
        return None


def _normalize_phone(p):
    """Strip +, spaces, dashes, parens for comparison."""
    if not p:
        return ""
    return re.sub(r"[^0-9]", "", str(p))


def _is_twilio_number(number):
    """True if this number is a Twilio-owned line we can send SMS from."""
    if not number:
        return False
    try:
        import json as _j, os as _os
        # Check the business's Twilio config
        cfg_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'twilio_config.json')
        if _os.path.exists(cfg_path):
            cfg = _j.load(open(cfg_path))
            if cfg.get('from_number') and _normalize_phone(cfg['from_number']) == _normalize_phone(number):
                return bool(cfg.get('account_sid') and cfg.get('auth_token'))
        # Also check env creds
        return bool(_os.environ.get("TWILIO_ACCOUNT_SID") and _os.environ.get("TWILIO_AUTH_TOKEN"))
    except Exception:
        return False


def _send_via_twilio(from_number, to_number, body, biz, lead_id):
    """Send an SMS via Twilio from a specific owned number. Logs to outgoing_sms."""
    import base64 as _b64
    import urllib.parse as _up
    import urllib.request as _ur
    import urllib.error as _ue
    import json as _j
    import os as _os
    import time as _t

    try:
        env_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '.env')
        if _os.path.exists(env_path):
            for line in open(env_path):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    _os.environ.setdefault(k.strip(), v.strip())
        sid = _os.environ.get("TWILIO_ACCOUNT_SID")
        tok = _os.environ.get("TWILIO_AUTH_TOKEN")
        if not sid or not tok:
            # Fall back to twilio_config.json
            cfg = _j.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'twilio_config.json')))
            sid, tok = cfg.get('account_sid'), cfg.get('auth_token')
        if not sid or not tok:
            print("⚠️ Twilio not configured, skipping Twilio send")
            return False
        auth = _b64.b64encode(f"{sid}:{tok}".encode()).decode()
        data = _up.urlencode({
            "From": from_number, "To": to_number, "Body": body,
        }).encode()
        req = _ur.Request(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data=data, method="POST",
            headers={"Authorization": "Basic " + auth, "User-Agent": "curl/8.0"})
        resp = _ur.urlopen(req, timeout=30)
        result = _j.loads(resp.read().decode())
        mid = result.get("sid", "")
        print(f"✅ Twilio SMS sent to {to_number} from {from_number} — SID: {mid}")
        # Log to outgoing_sms for reply-matching
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute(
                "INSERT INTO outgoing_sms (id, business_id, lead_id, phone, body, message_id, sent_at) VALUES (?,?,?,?,?,?,?)",
                (mid, biz.get("id") if biz else None, lead_id, to_number, body, mid,
                 datetime.now().isoformat()))
            db.commit()
            db.close()
        except Exception as _le:
            print(f"⚠️ outgoing log failed: {_le}")
        return True
    except Exception as e:
        print(f"❌ Twilio send error: {e}")
        return False


def handle_inbound_sms(bid, sender, body, lead_id=None, to_number=None):
    """Main entry — called from the sms-gate webhook (background thread).
    to_number = the number the customer texted (used to reply from the same line)."""
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
        # Word-boundary opt-out: bare STOP/UNSUBSCRIBE — NOT "cancel my appointment"
        if any(re.search(rf"\b{k}\b", up) for k in OPT_OUT_KEYWORDS):
            print(f"🚫 AI SMS: opt-out keyword from {sender}, no reply")
            return None

        # Dedup: skip only webhook REDELIVERIES of the same message (not fast human replies)
        if not _mark_processed(bid, sender, body):
            print(f"🔄 AI SMS: duplicate delivery of same message from {sender}, skipping")
            return None

        history = build_history(bid, sender)
        current_appt = find_current_appointment(bid, sender)
        prompt = build_sms_prompt(biz, current_appt)
        reply = call_vapi_chat(biz["vapi_assistant_id"], prompt, history, body)
        if not reply:
            print(f"❌ AI SMS: no reply from VAPI chat for {sender}")
            return None

        # ── Protocol parsing: BOOK| / MOVE| / CANCEL| (own line OR mid-line) ──
        import re as _proto_re
        msg_text = _proto_re.sub(
            r'(BOOK|MOVE|CANCEL|CALLME)\|[A-Za-z0-9 ,:./-]*', '', reply, flags=_proto_re.IGNORECASE)
        msg_text = msg_text.replace('  ', ' ').strip(' ,.;:-') or reply

        m_book = _proto_re.search(r'BOOK\|([A-Za-z0-9 ,:./-]+)', reply, _proto_re.IGNORECASE)
        m_move = _proto_re.search(r'MOVE\|([A-Za-z0-9 ,:./-]+)', reply, _proto_re.IGNORECASE)
        m_cancel = _proto_re.search(r'CANCEL\|', reply, _proto_re.IGNORECASE)
        m_callme = _proto_re.search(r'CALLME\|', reply, _proto_re.IGNORECASE)

        if m_book:
            book_line = m_book.group(1).strip()
            print(f"📅 BOOK detected: {book_line}")
            save_appointment(bid, lead_id, sender, book_line,
                             notes=f"Booked via SMS AI. Original: {body[:100]}")
        elif m_move:
            move_line = m_move.group(1).strip()
            print(f"🔄 MOVE detected: {move_line}")
            if current_appt:
                move_appointment(current_appt["id"], move_line)
            else:
                print("⚠️ MOVE requested but no current appointment found")
        elif m_cancel:
            print("🚫 CANCEL detected")
            if current_appt:
                cancel_appointment(current_appt["id"])
            else:
                print("⚠️ CANCEL requested but no current appointment found")
        elif m_callme:
            print("📞 CALLME detected — placing callback call")
            trigger_call_back(biz, sender)

        # Send reply via sms-gate.app (PRIMARY — Twilio fails with 30034 on
        # this number since VAPI's account isn't A2P-registered; sms-gate
        # delivers reliably to real US phones via the SIM).
        import sys
        sys.path.insert(0, "/root/voice-agent-manager")
        from smsgate_sms import send_sms
        ok = send_sms(sender, msg_text, business_id=bid, lead_id=lead_id)
        if ok:
            print(f"🤖 AI SMS reply sent (sms-gate) to {sender}: {msg_text[:80]}")
        else:
            # Last-resort fallback: Twilio (same number as inbound when possible)
            if to_number and _is_twilio_number(to_number):
                ok = _send_via_twilio(to_number, sender, msg_text, biz, lead_id)
                if ok:
                    print(f"🤖 AI SMS reply sent (Twilio fallback, from {to_number}) to {sender}: {msg_text[:80]}")
            if not ok:
                print(f"❌ AI SMS reply FAILED to {sender}")
        return msg_text if ok else None
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ AI SMS handler error: {e}")
        return None


def run_in_background(bid, sender, body, lead_id, to_number=None):
    t = threading.Thread(target=handle_inbound_sms, args=(bid, sender, body, lead_id, to_number), daemon=True)
    t.start()
