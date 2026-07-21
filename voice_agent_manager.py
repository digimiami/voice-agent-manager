#!/usr/bin/env python3
"""
AI Voice Agent Multi-Business Manager
======================================
Sell VAPI + Grok voice agents to different businesses.
Each business gets its own phone number, script, and campaign.

USAGE:
  ./voice_agent_manager.py add-business     # Add a new business
  ./voice_agent_manager.py list             # List all businesses  
  ./voice_agent_manager.py run <business>   # Run campaign for a business
  ./voice_agent_manager.py stats            # Show all stats
"""

import json, os, sys, sqlite3, time, random, hashlib
from datetime import datetime, timedelta

DB_PATH = "/root/voice-agent-businesses.db"
VAPI_API_KEY = "d9486ec8-b862-460b-97ba-64bbb639f234"
VAPI_BASE = "https://api.vapi.ai"

os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)

def init_db():
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS businesses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            industry TEXT,
            phone_number TEXT,
            vapi_assistant_id TEXT,
            vapi_phone_id TEXT,
            script_template TEXT,
            knowledge_base TEXT,
            timezone TEXT DEFAULT 'America/New_York',
            call_window_start TEXT DEFAULT '09:00',
            call_window_end TEXT DEFAULT '17:00',
            max_calls_per_day INTEGER DEFAULT 20,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            status TEXT DEFAULT 'idle',
            calls_made INTEGER DEFAULT 0,
            appointments_booked INTEGER DEFAULT 0,
            total_cost REAL DEFAULT 0,
            leads_imported INTEGER DEFAULT 0,
            started_at TIMESTAMP,
            last_run_at TIMESTAMP,
            FOREIGN KEY(business_id) REFERENCES businesses(id)
        );
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            phone TEXT,
            name TEXT,
            business_name TEXT,
            state TEXT DEFAULT 'NEW',
            retry_count INTEGER DEFAULT 0,
            last_called_at TIMESTAMP,
            next_call_at TIMESTAMP,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(business_id) REFERENCES businesses(id)
        );
        CREATE TABLE IF NOT EXISTS call_log (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            lead_id TEXT,
            vapi_call_id TEXT,
            duration INTEGER,
            cost REAL,
            outcome TEXT,
            appointment_time TEXT,
            transcript TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(business_id) REFERENCES businesses(id)
        );
    """)
    db.commit()
    return db

# ── INDUSTRY PRESETS ──

INDUSTRY_PRESETS = {
    "dentist": {
        "script": "You are Dr. {name}'s assistant from {company}. You're calling because we noticed {prospect_business} might benefit from our new patient reminder and booking system. Goal: book a 10-min call to explain how we reduce no-shows by 40%.",
        "kb": "Dental practices: common procedures (cleaning, fillings, crowns, implants). Office hours typically 8am-5pm. Insurance accepted.",
        "benefit": "reduce no-shows and fill cancelled slots"
    },
    "plumber": {
        "script": "You are {name} from {company}. You help local plumbing businesses get more emergency and scheduled service calls without paying for ads. Goal: book a 10-min discovery call.",
        "kb": "Plumbing services: emergency repairs, drain cleaning, water heater installation, pipe repair. 24/7 emergency service available.",
        "benefit": "never miss an emergency call again"
    },
    "roofer": {
        "script": "You are {name} from {company}. You help roofing companies capture more leads from storm season and insurance claims. Goal: book a 10-min call to show how.",
        "kb": "Roofing: shingle repair, metal roofing, flat roofs, storm damage, insurance claims. Seasonal peaks after storms.",
        "benefit": "capture storm season leads 24/7"
    },
    "hvac": {
        "script": "You are {name} from {company}. You help HVAC businesses handle after-hours emergency calls and schedule maintenance bookings automatically. Goal: book a 10-min call.",
        "kb": "HVAC: AC repair, heating repair, furnace maintenance, duct cleaning. Peak seasons summer and winter.",
        "benefit": "answer emergency calls at 2 AM"
    },
    "lawyer": {
        "script": "You are {name}, a legal intake specialist from {company}. You help law firms qualify leads and book consultations without hiring extra receptionists. Goal: book a 15-min strategy call.",
        "kb": "Legal services: personal injury, family law, criminal defense, business law. Intake and consultation booking.",
        "benefit": "qualify leads before they call elsewhere"
    },
    "real estate agent": {
        "script": "You are {name} from {company}. You help real estate agents capture buyer and seller leads 24/7 when they're on Zillow or Realtor.com. Goal: book a 10-min call.",
        "kb": "Real estate: buyer representation, seller listing, property valuation, open houses. MLS access.",
        "benefit": "capture leads while you sleep"
    },
    "auto mechanic": {
        "script": "You are {name} from {company}. You help auto repair shops book more service appointments and handle after-hours calls. Goal: book a 10-min call.",
        "kb": "Auto repair: oil changes, brake repair, engine diagnostics, tire replacement, AC service.",
        "benefit": "book appointments overnight"
    },
    "cleaning service": {
        "script": "You are {name} from {company}. You help cleaning businesses get more recurring clients without spending on ads. Goal: book a 10-min call.",
        "kb": "Cleaning: residential cleaning, office cleaning, move-in/move-out, deep cleaning, recurring weekly/monthly.",
        "benefit": "automate your booking pipeline"
    },
    "pest control": {
        "script": "You are {name} from {company}. You help pest control companies respond to emergency calls and book quarterly inspections automatically. Goal: book a 10-min call.",
        "kb": "Pest control: termites, rodents, roaches, bed bugs, ants. Quarterly treatment plans. Emergency service.",
        "benefit": "respond to pest emergencies instantly"
    },
    "landscaper": {
        "script": "You are {name} from {company}. You help landscaping businesses book recurring maintenance and estimate appointments without the phone tag. Goal: book a 10-min call.",
        "kb": "Landscaping: lawn mowing, tree trimming, garden design, irrigation, snow removal, seasonal cleanup.",
        "benefit": "book estimates while you're on the job"
    }
}

SCRIPTS_DIR = "/root/voice-agent-scripts"
os.makedirs(SCRIPTS_DIR, exist_ok=True)

def generate_id():
    return hashlib.md5(str(time.time()).encode()).hexdigest()[:12]

def add_business():
    db = init_db()
    
    print("\n━━━ ADD NEW BUSINESS ━━━")
    name = input("Business name: ").strip()
    
    print("\nAvailable industries:")
    for i, ind in enumerate(INDUSTRY_PRESETS.keys(), 1):
        print(f"  {i}. {ind.title()}")
    print("  0. Custom")
    
    choice = input(f"\nSelect industry (1-{len(INDUSTRY_PRESETS)} or 0): ").strip()
    try:
        idx = int(choice)
        if 1 <= idx <= len(INDUSTRY_PRESETS):
            industry = list(INDUSTRY_PRESETS.keys())[idx-1]
            preset = INDUSTRY_PRESETS[industry]
            script = preset["script"]
            kb = preset["kb"]
        else:
            industry = input("Custom industry: ").strip()
            script = input("Script template: ").strip()
            kb = input("Knowledge base: ").strip()
    except:
        industry = "custom"
        script = input("Script template: ").strip()
        kb = input("Knowledge base: ").strip()
    
    phone = input("Their phone number (for calls to them): ").strip()
    
    bid = generate_id()
    
    c = db.cursor()
    c.execute("""
        INSERT INTO businesses (id, name, industry, phone_number, script_template, knowledge_base)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (bid, name, industry, phone, script, kb))
    
    # Create campaign
    cid = generate_id()
    c.execute("""
        INSERT INTO campaigns (id, business_id, status)
        VALUES (?, ?, 'ready')
    """, (cid, bid))
    
    db.commit()
    
    print(f"\n✅ Business added: {name}")
    print(f"   ID: {bid}")
    print(f"   Industry: {industry}")
    print(f"   Campaign ID: {cid}")
    
    # Save script to file
    script_file = f"{SCRIPTS_DIR}/{bid}_script.txt"
    with open(script_file, 'w') as f:
        f.write(f"System Prompt:\n{script}\n\nKnowledge Base:\n{kb}")
    print(f"   Script saved: {script_file}")
    
    print(f"\nNext step: Run 'python3 voice_agent_manager.py setup-vapi {bid}' to create VAPI assistant")
    return bid

def setup_vapi_assistant(business_id):
    """Creates a VAPI assistant + phone number for a business."""
    import urllib.request
    
    db = init_db()
    c = db.cursor()
    c.execute("SELECT * FROM businesses WHERE id = ?", (business_id,))
    biz = c.fetchone()
    if not biz:
        print(f"❌ Business not found: {business_id}")
        return
    
    biz_dict = dict(zip([d[0] for d in c.description], biz))
    name = biz_dict['name']
    industry = biz_dict['industry']
    script = biz_dict['script_template']
    kb = biz_dict['knowledge_base']
    
    print(f"\n━━━ Setting up VAPI for: {name} ━━━")
    
    # Read script file
    script_file = f"{SCRIPTS_DIR}/{business_id}_script.txt"
    full_script = f"{script}\n\nKnowledge Base Context:\n{kb}\n\nKeep responses under 30 seconds. If prospect asks for email or calendar, say a team member will handle it."
    
    # Create VAPI assistant
    print("  Creating VAPI assistant...")
    
    import subprocess
    result = subprocess.run([
        "curl", "-s", "-X", "POST", f"{VAPI_BASE}/assistant",
        "-H", f"Authorization: Bearer {VAPI_API_KEY}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({
            "name": f"{name} Voice Agent",
            "model": {
                "provider": "xai",
                "model": "grok-4.3",
                "temperature": 0.3,
                "maxTokens": 300,
                "systemPrompt": full_script
            },
            "voice": {
                "provider": "11labs",
                "voiceId": "burt"
            },
            "firstMessage": f"Hi, this is {name}'s assistant from AI Workers. We help {industry} businesses never miss a call. Do you have a moment?",
            "firstMessageMode": "assistant-speaks-first",
            "silenceTimeoutSeconds": 10,
            "maxDurationSeconds": 300,
            "backgroundSound": "off"
        })
    ], capture_output=True, text=True)
    
    try:
        assistant = json.loads(result.stdout)
        assistant_id = assistant.get('id')
        if not assistant_id:
            print(f"❌ Failed: {assistant.get('message', result.stdout[:200])}")
            return
    except:
        print(f"❌ API error: {result.stdout[:300]}")
        return
    
    print(f"  ✅ Assistant created: {assistant_id}")
    
    # Update business with VAPI assistant ID
    c.execute("UPDATE businesses SET vapi_assistant_id = ? WHERE id = ?", (assistant_id, business_id))
    db.commit()
    
    print(f"\n✅ VAPI setup complete for {name}!")
    print(f"   Assistant ID: {assistant_id}")
    print(f"   To assign a phone number, run:")
    print(f"   python3 voice_agent_manager.py assign-phone {business_id}")

def import_leads_csv(business_id, csv_path):
    """Import leads from CSV for a business campaign."""
    import csv
    
    db = init_db()
    c = db.cursor()
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            phone = row.get('phone', row.get('Phone', row.get('number', row.get('Number', '')))).strip()
            if not phone:
                continue
            
            name = row.get('name', row.get('Name', row.get('business_name', '')))
            biz_name = row.get('business', row.get('Business', ''))
            
            lid = generate_id()
            c.execute("""
                INSERT INTO leads (id, business_id, phone, name, business_name, state)
                VALUES (?, ?, ?, ?, ?, 'NEW')
            """, (lid, business_id, phone, name, biz_name))
            count += 1
        
        # Update campaign lead count
        c.execute("UPDATE campaigns SET leads_imported = ? WHERE business_id = ?", (count, business_id))
        db.commit()
        
        print(f"✅ Imported {count} leads for business {business_id}")

def run_campaign(business_id, max_calls=10):
    """Run a calling campaign for a business."""
    import urllib.request
    
    db = init_db()
    c = db.cursor()
    
    c.execute("SELECT * FROM businesses WHERE id = ?", (business_id,))
    biz = c.fetchone()
    if not biz:
        print(f"❌ Business not found: {business_id}")
        return
    
    biz_dict = dict(zip([d[0] for d in c.description], biz))
    assistant_id = biz_dict.get('vapi_assistant_id')
    phone_id = biz_dict.get('vapi_phone_id')
    name = biz_dict['name']
    
    if not assistant_id:
        print(f"❌ No VAPI assistant set up. Run setup-vapi first.")
        return
    
    if not phone_id:
        print(f"❌ No phone number assigned. Run assign-phone first.")
        return
    
    # Get leads to call
    c.execute("""
        SELECT * FROM leads 
        WHERE business_id = ? AND state = 'NEW'
        LIMIT ?
    """, (business_id, max_calls))
    leads = c.fetchall()
    
    if not leads:
        print(f"No leads to call for {name}")
        return
    
    print(f"\n━━━ Running Campaign: {name} ━━━")
    print(f"Leads to call: {len(leads)}")
    
    calls_made = 0
    appointments = 0
    
    for lead_row in leads:
        lead = dict(zip([d[0] for d in c.description], lead_row))
        phone = lead['phone']
        
        print(f"\n  📞 Calling {lead.get('business_name', lead.get('name', phone))}...")
        
        # Make VAPI call with business-specific overrides
        result = subprocess.run([
            "curl", "-s", "-X", "POST", f"{VAPI_BASE}/call",
            "-H", f"Authorization: Bearer {VAPI_API_KEY}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({
                "assistantId": assistant_id,
                "phoneNumberId": phone_id,
                "customer": {"number": phone},
                "assistantOverrides": {
                    "variableValues": {
                        "business_name": name,
                        "industry": biz_dict.get('industry', ''),
                        "prospect_business": lead.get('business_name', 'your business')
                    }
                }
            })
        ], capture_output=True, text=True)
        
        try:
            call_data = json.loads(result.stdout)
            call_id = call_data.get('id')
            print(f"     Call ID: {call_id}")
        except:
            print(f"     ❌ Failed: {result.stdout[:100]}")
            continue
        
        # Update lead state
        c.execute("UPDATE leads SET state = 'CALLING', last_called_at = datetime('now') WHERE id = ?", (lead['id'],))
        db.commit()
        calls_made += 1
        
        # Update campaign stats
        c.execute("""
            UPDATE campaigns SET calls_made = calls_made + 1, last_run_at = datetime('now')
            WHERE business_id = ?
        """, (business_id,))
        db.commit()
        
        # Wait between calls
        if calls_made < len(leads):
            delay = 90 + random.randint(0, 60)
            print(f"     Waiting {delay}s...")
            time.sleep(delay)
    
    print(f"\n✅ Campaign complete for {name}")
    print(f"   Calls made: {calls_made}")
    print(f"   Appointments: {appointments}")
    
    # Update campaign status
    c.execute("UPDATE campaigns SET status = 'idle' WHERE business_id = ?", (business_id,))
    db.commit()

def list_businesses():
    db = init_db()
    c = db.cursor()
    c.execute("""
        SELECT b.*, c.calls_made, c.appointments_booked, c.total_cost, c.status
        FROM businesses b
        LEFT JOIN campaigns c ON b.id = c.business_id
        ORDER BY b.created_at DESC
    """)
    rows = c.fetchall()
    
    if not rows:
        print("No businesses configured yet.")
        return
    
    print(f"\n━━━ BUSINESSES ({len(rows)}) ━━━")
    print(f"{'ID':<14} {'NAME':<20} {'INDUSTRY':<18} {'CALLS':<6} {'APPTS':<5} {'SPENT':<8} {'STATUS':<10}")
    print("-"*85)
    
    for row in rows:
        d = dict(zip([d[0] for d in c.description], row))
        cost = d.get('total_cost', 0) or 0
        print(f"{d['id']:<14} {d['name']:<20} {(d.get('industry','') or ''):<18} {d.get('calls_made',0):<6} {d.get('appointments_booked',0):<5} ${cost:<5.2f} {d.get('status','idle'):<10}")

def show_stats():
    db = init_db()
    c = db.cursor()
    
    print("\n━━━ OVERALL STATS ━━━")
    
    c.execute("SELECT COUNT(*) FROM businesses")
    biz_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM leads")
    lead_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM call_log")
    call_count = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(cost),0) FROM call_log")
    total_cost = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(appointments_booked),0) FROM campaigns")
    total_appts = c.fetchone()[0]
    
    print(f"  Businesses:      {biz_count}")
    print(f"  Total Leads:     {lead_count}")
    print(f"  Calls Made:      {call_count}")
    print(f"  Appointments:    {total_appts}")
    print(f"  Total Cost:      ${total_cost:.2f}")

def assign_phone(business_id, phone_id=None):
    """Assign a VAPI phone number to a business."""
    db = init_db()
    c = db.cursor()
    
    c.execute("SELECT * FROM businesses WHERE id = ?", (business_id,))
    biz = c.fetchone()
    if not biz:
        print(f"❌ Business not found: {business_id}")
        return
    
    biz_dict = dict(zip([d[0] for d in c.description], biz))
    
    if not phone_id:
        # List available phones
        result = subprocess.run([
            "curl", "-s", f"{VAPI_BASE}/phone-number",
            "-H", f"Authorization: Bearer {VAPI_API_KEY}"
        ], capture_output=True, text=True)
        
        try:
            phones = json.loads(result.stdout)
            if isinstance(phones, dict):
                phones = phones.get('data', [])
            
            print("\nAvailable phone numbers:")
            for i, p in enumerate(phones, 1):
                num = p.get('number', p.get('phoneNumber', '?'))
                pid = p.get('id', '?')
                print(f"  {i}. {num} (ID: {pid})")
            print("  0. Buy a new number")
            
            choice = input("\nSelect number: ").strip()
            try:
                idx = int(choice)
                if idx == 0:
                    print("To buy a new number: visit https://dashboard.vapi.ai/phone-numbers")
                    return
                phone_id = phones[idx-1]['id']
            except:
                print("Invalid selection")
                return
        except:
            print(f"Error listing phones: {result.stdout[:200]}")
            return
    
    c.execute("UPDATE businesses SET vapi_phone_id = ? WHERE id = ?", (phone_id, business_id))
    db.commit()
    print(f"✅ Phone assigned to {biz_dict['name']}")

# ── CLI ──

if __name__ == "__main__":
    import subprocess
    
    init_db()
    
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "add-business":
        add_business()
    elif cmd == "list":
        list_businesses()
    elif cmd == "stats":
        show_stats()
    elif cmd == "setup-vapi":
        if len(sys.argv) < 3:
            print("Usage: voice_agent_manager.py setup-vapi <business_id>")
            sys.exit(1)
        setup_vapi_assistant(sys.argv[2])
    elif cmd == "assign-phone":
        if len(sys.argv) < 3:
            print("Usage: voice_agent_manager.py assign-phone <business_id> [phone_id]")
            sys.exit(1)
        assign_phone(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "import-leads":
        if len(sys.argv) < 4:
            print("Usage: voice_agent_manager.py import-leads <business_id> <csv_path>")
            sys.exit(1)
        import_leads_csv(sys.argv[2], sys.argv[3])
    elif cmd == "run":
        if len(sys.argv) < 3:
            print("Usage: voice_agent_manager.py run <business_id> [max_calls]")
            sys.exit(1)
        max_c = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        run_campaign(sys.argv[2], max_c)
    elif cmd == "industries":
        print("\n━━━ AVAILABLE INDUSTRIES ━━━")
        for i, (ind, preset) in enumerate(INDUSTRY_PRESETS.items(), 1):
            print(f"\n  {i}. {ind.title()}")
            print(f"     Benefit: {preset['benefit']}")
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
