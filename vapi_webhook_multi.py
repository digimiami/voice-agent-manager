#!/usr/bin/env python3
"""
Multi-Business VAPI Webhook Server
===================================
Receives VAPI call completion events and logs them to the correct business.
Maps assistant_id → business_id, updates call_log, leads, and campaign stats.

Run: python3 vapi_webhook_multi.py
Port: 8087
Webhook URL: https://<tunnel>/api/vapi/webhook
"""

import json, logging, sqlite3, time
from datetime import datetime
from flask import Flask, request, jsonify

DB_PATH = "/root/voice-agent-businesses.db"
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

def get_business_id_by_assistant(assistant_id):
    """Map VAPI assistant ID back to business ID."""
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("SELECT id, name FROM businesses WHERE vapi_assistant_id = ?", (assistant_id,))
    row = c.fetchone()
    db.close()
    return row if row else (None, None)

def get_lead_id_by_phone(business_id, phone):
    """Find lead by phone number for a business."""
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("SELECT id FROM leads WHERE business_id = ? AND phone = ? LIMIT 1", (business_id, phone))
    row = c.fetchone()
    db.close()
    return row[0] if row else None

def process_end_of_call(msg):
    """Process end-of-call report from VAPI."""
    call = msg.get("call", {})
    assistant_id = call.get("assistantId") or msg.get("assistantId") or ""
    customer = call.get("customer", {}) or {}
    phone = customer.get("number", "") or call.get("customerNumber", "")
    
    bid, biz_name = get_business_id_by_assistant(assistant_id)
    if not bid:
        log.warning(f"No business found for assistant: {assistant_id}")
        return False
    
    analysis = call.get("analysis", {}) or {}
    structured = analysis.get("structuredData", {}) or {}
    summary = analysis.get("summary", "")
    
    # Get recording URL - use authenticated endpoint
    # Direct recordingUrl now requires API auth, use proxy endpoint instead
    call_id = call.get('id', '')
    recording_url = f"/api/call/{call_id}/recording" if call_id else ""
    
    cost = call.get("cost", 0) or 0
    duration = call.get("duration", 0) or 0
    ended_reason = call.get("endedReason", "unknown")
    
    # Fallback: check msg top-level for cost/duration if call doesn't have it
    if not cost and "cost" in msg:
        cost = msg.get("cost", 0) or 0
    if not duration and "durationSeconds" in msg:
        duration = msg.get("durationSeconds", 0) or 0
    if ended_reason == "unknown" and "endedReason" in msg:
        ended_reason = msg.get("endedReason", "unknown")
    
    # Extract appointment info
    appointment_booked = structured.get("appointment_booked", False)
    appointment_time = structured.get("appointment_time", "")
    interested = structured.get("interested", False)
    
    # Set lead outcome - handle both webhook and API response formats
    if appointment_booked:
        outcome = "appointment_booked"
    elif interested:
        outcome = "interested"
    elif ended_reason and ended_reason != "unknown":
        outcome = ended_reason
    else:
        # Check assistant's analysis for outcome
        assistant_analysis = call.get("analysis", {}) or {}
        if isinstance(assistant_analysis, dict):
            success_eval = assistant_analysis.get("successEvaluation", "")
            if success_eval:
                outcome = f"AI: {success_eval[:30]}"
            else:
                outcome = ended_reason or call.get("status", "completed")
        else:
            outcome = ended_reason or "completed"
    
    messages = call.get("messages", msg.get("messages", []))
    transcript = " ".join([m.get("message", "") for m in messages if m.get("role") in ("assistant", "user")])[:500]
    
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    
    # Find lead
    lead_id = get_lead_id_by_phone(bid, phone)
    lead_name = ""
    if lead_id:
        c2 = sqlite3.connect(DB_PATH)
        c2.row_factory = sqlite3.Row
        r = c2.execute("SELECT name FROM leads WHERE id = ?", (lead_id,)).fetchone()
        lead_name = r['name'] if r else ""
        c2.close()
    
    call_id = call.get("id", "") or msg.get("id", "")
    
    # Insert call log with recording
    c.execute("""
        INSERT OR REPLACE INTO call_log 
        (id, business_id, lead_id, vapi_call_id, duration, cost, outcome, 
         appointment_time, transcript, recording_url, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        call_id or f"call_{int(time.time())}",
        bid, lead_id, call_id, int(duration), float(cost),
        outcome, appointment_time, transcript[:500], recording_url or ""
    ))
    
    # Update lead state
    if lead_id:
        new_state = "APPOINTMENT" if appointment_booked else "INTERESTED" if interested else "CALLED"
        c.execute("UPDATE leads SET state = ?, retry_count = COALESCE(retry_count,0) + 1, last_called_at = datetime('now') WHERE id = ?",
            (new_state, lead_id))
    
    # Update campaign stats
    if appointment_booked:
        c.execute("UPDATE campaigns SET appointments_booked = COALESCE(appointments_booked,0) + 1, total_cost = COALESCE(total_cost,0) + ? WHERE business_id = ?",
            (cost, bid))
    
    db.commit()
    db.close()
    
    log.info(f"✅ Logged call for {biz_name}: {outcome} (${cost:.2f})")
    log.info(f"   Phone: {phone[-4:]}")
    if appointment_booked:
        log.info(f"   📅 Appointment: {appointment_time}")
    if summary:
        log.info(f"   Summary: {summary[:100]}")
    
    # Send SMS follow-up
    try:
        from premium_features import send_sms_followup
        send_sms_followup(bid, phone, lead_name, outcome)
    except Exception as e:
        log.warning(f"SMS follow-up skipped: {e}")
    
    # Smart follow-up sequence
    try:
        from premium_features2 import trigger_followup
        trigger_followup(bid, lead_id, phone, lead_name, outcome)
    except Exception as e:
        log.warning(f"Sequence follow-up skipped: {e}")
    
    return True

@app.route("/api/vapi/webhook", methods=["POST"])
def handle_webhook():
    payload = request.get_json(silent=True) or {}
    msg = payload.get("message", payload)
    event_type = msg.get("type", "unknown")
    
    log.info(f"Webhook received: {event_type}")
    
    if event_type == "end-of-call-report":
        try:
            processed = process_end_of_call(msg)
            return jsonify({"status": "ok" if processed else "unmatched"}), 200
        except Exception as e:
            log.error(f"Error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    return jsonify({"status": "ignored"}), 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "db": DB_PATH})

if __name__ == "__main__":
    print(f"🔄 Multi-Business VAPI Webhook Server")
    print(f"📊 DB: {DB_PATH}")
    print(f"🌐 http://localhost:8087/api/vapi/webhook")
    app.run(host="0.0.0.0", port=8087, debug=False)
