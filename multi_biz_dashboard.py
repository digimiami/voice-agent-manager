#!/usr/bin/env python3
"""
Multi-Business Voice Agent Dashboard
=====================================
Each business client logs in and manages their own:
  - Leads (upload CSV, view, delete)
  - Call history & transcripts
  - Script & knowledge base
  - Campaign stats
  - Appointments
  
Run: python3 multi_biz_dashboard.py
Port: 8084
Login: Each business gets a unique link + passcode
"""

import os, sys, json, sqlite3, csv, io, hashlib, time
from datetime import datetime, date, timedelta
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, redirect, session, url_for
from functools import wraps
import secrets

DB_PATH = "/root/voice-agent-businesses.db"
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ── Landing Page ──

LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Agent Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        * { font-family: 'Inter', sans-serif; }
        body { background: #0a0a0f; }
        .gradient-text { background: linear-gradient(135deg, #c084fc, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .card { background: #12121a; border: 1px solid #252533; border-radius: 16px; padding: 24px; }
        .card:hover { border-color: #a855f7; }
        .btn-primary { background: linear-gradient(135deg, #a855f7, #ec4899); color: white; padding: 10px 20px; border-radius: 8px; font-weight: 600; border: none; cursor: pointer; transition: all 0.2s; }
        .btn-primary:hover { transform: scale(1.02); opacity: 0.9; }
        .btn-secondary { background: #1a1a26; color: #f1f1f5; padding: 8px 16px; border-radius: 8px; border: 1px solid #252533; cursor: pointer; }
        .btn-secondary:hover { border-color: #a855f7; }
        input, select { background: #1a1a26; border: 1px solid #252533; border-radius: 8px; padding: 10px 14px; color: #f1f1f5; outline: none; width: 100%; }
        input:focus { border-color: #a855f7; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 10px 12px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #7a7a8e; border-bottom: 1px solid #252533; }
        td { padding: 10px 12px; border-bottom: 1px solid #1a1a26; font-size: 13px; color: #b0b0c0; }
        tr:hover td { background: #1a1a26; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
        .badge-success { background: rgba(34,197,94,0.15); color: #4ade80; }
        .badge-warning { background: rgba(245,158,11,0.15); color: #fbbf24; }
        .badge-error { background: rgba(239,68,68,0.15); color: #ef4444; }
        .badge-info { background: rgba(168,85,247,0.15); color: #c084fc; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: #252533; border-radius: 2px; }
    </style>
</head>
<body class="text-[#f1f1f5] min-h-screen">
    <div class="max-w-6xl mx-auto p-4 sm:p-6">
        <!-- Header -->
        <div class="flex items-center justify-between mb-8">
            <div>
                <h1 class="text-2xl font-bold gradient-text">🤖 Voice Agent Hub</h1>
                <p class="text-[#7a7a8e] text-sm mt-1">Manage your AI voice campaigns</p>
            </div>
            {% if session.get('business_id') %}
            <div class="flex items-center gap-3">
                <span class="text-sm text-[#7a7a8e]">{{ biz_name }}</span>
                <a href="/logout" class="btn-secondary text-sm">Logout</a>
            </div>
            {% endif %}
        </div>

        {% if not session.get('business_id') %}
        <!-- Login -->
        <div class="max-w-md mx-auto mt-16">
            <div class="card text-center">
                <div class="text-4xl mb-4">🔐</div>
                <h2 class="text-xl font-bold mb-2">Business Login</h2>
                <p class="text-[#7a7a8e] text-sm mb-6">Enter your business ID to access your dashboard</p>
                <form method="POST" action="/login" class="space-y-4">
                    <input type="text" name="business_id" placeholder="Your Business ID" class="text-center" required>
                    <button type="submit" class="btn-primary w-full">Access Dashboard →</button>
                </form>
                {% if error %}
                <p class="text-red-400 text-sm mt-3">{{ error }}</p>
                {% endif %}
                <p class="text-[#5c5c70] text-xs mt-6">Don't have an ID? Contact your account manager.</p>
            </div>
        </div>
        {% else %}
        
        <!-- Dashboard Content -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div class="card text-center">
                <div class="text-2xl font-bold text-[#c084fc]">{{ stats.calls_made }}</div>
                <div class="text-xs text-[#7a7a8e] mt-1">Calls Made</div>
            </div>
            <div class="card text-center">
                <div class="text-2xl font-bold text-[#4ade80]">{{ stats.appointments }}</div>
                <div class="text-xs text-[#7a7a8e] mt-1">Appointments</div>
            </div>
            <div class="card text-center">
                <div class="text-2xl font-bold text-[#fbbf24]">{{ stats.leads_total }}</div>
                <div class="text-xs text-[#7a7a8e] mt-1">Leads</div>
            </div>
            <div class="card text-center">
                <div class="text-2xl font-bold text-[#f472b6]">${{ "%.2f"|format(stats.total_cost) }}</div>
                <div class="text-xs text-[#7a7a8e] mt-1">Total Spent</div>
            </div>
        </div>

        <!-- Tabs -->
        <div class="flex gap-2 mb-6 overflow-x-auto pb-2">
            <a href="?tab=overview" class="btn-secondary text-sm {% if tab == 'overview' %}border-[#a855f7]!{% endif %}">📊 Overview</a>
            <a href="?tab=leads" class="btn-secondary text-sm {% if tab == 'leads' %}border-[#a855f7]!{% endif %}">📋 Leads</a>
            <a href="?tab=history" class="btn-secondary text-sm {% if tab == 'history' %}border-[#a855f7]!{% endif %}">📞 Call History</a>
            <a href="?tab=settings" class="btn-secondary text-sm {% if tab == 'settings' %}border-[#a855f7]!{% endif %}">⚙️ Settings</a>
        </div>

        {% if tab == 'overview' %}
        <!-- Overview -->
        <div class="card mb-6">
            <h3 class="font-bold text-lg mb-2">📊 Campaign Overview</h3>
            <p class="text-[#7a7a8e] text-sm mb-4">Your {{ biz_info.industry }} voice agent is active.</p>
            <div class="grid grid-cols-2 gap-4 text-sm">
                <div><span class="text-[#7a7a8e]">Industry:</span> {{ biz_info.industry.title() }}</div>
                <div><span class="text-[#7a7a8e]">Status:</span> <span class="badge badge-success">Active</span></div>
                <div><span class="text-[#7a7a8e]">Phone:</span> {{ biz_info.vapi_phone_id[:8] }}... </div>
                <div><span class="text-[#7a7a8e]">Call Frequency:</span> Daily 9AM-5PM</div>
            </div>
        </div>

        <!-- Recent Calls -->
        {% if recent_calls %}
        <div class="card">
            <h3 class="font-bold mb-4">🕐 Recent Calls</h3>
            <table>
                <tr><th>Date</th><th>Number</th><th>Outcome</th><th>Cost</th><th>Details</th></tr>
                {% for call in recent_calls %}
                <tr>
                    <td>{{ call.created_at[:16] }}</td>
                    <td>{{ call.phone[-4:] }}</td>
                    <td>{% if call.appointment_booked %}<span class="badge badge-success">Booked</span>
                        {% elif call.outcome == 'voicemail' %}<span class="badge badge-warning">Voicemail</span>
                        {% elif call.outcome == 'customer-ended-call' %}<span class="badge badge-error">Hung up</span>
                        {% else %}<span class="badge badge-info">{{ call.outcome[:15] }}</span>{% endif %}
                    </td>
                    <td>${{ "%.2f"|format(call.cost or 0) }}</td>
                    <td class="max-w-[200px] truncate">{{ (call.transcript or '')[:80] }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% endif %}

        {% elif tab == 'leads' %}
        <!-- Leads -->
        <div class="card mb-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="font-bold text-lg">📋 Your Leads</h3>
                <button onclick="document.getElementById('csvUpload').click()" class="btn-primary text-sm">+ Upload CSV</button>
            </div>
            <input type="file" id="csvUpload" accept=".csv" class="hidden" onchange="uploadCSV(this)">
            <p class="text-[#7a7a8e] text-xs mb-4">CSV format: phone, name, business_name</p>
            
            {% if leads %}
            <table>
                <tr><th>Phone</th><th>Name</th><th>Business</th><th>Status</th><th>Last Called</th></tr>
                {% for lead in leads %}
                <tr>
                    <td>{{ lead.phone }}</td>
                    <td>{{ lead.name or '-' }}</td>
                    <td>{{ lead.business_name or '-' }}</td>
                    <td><span class="badge {% if lead.state == 'NEW' %}badge-info{% elif lead.state == 'CALLING' %}badge-warning{% elif lead.state == 'INTERESTED' %}badge-success{% else %}badge-error{% endif %}">{{ lead.state }}</span></td>
                    <td>{{ (lead.last_called_at or '-')[:10] }}</td>
                </tr>
                {% endfor %}
            </table>
            {% else %}
            <p class="text-center text-[#5c5c70] py-8">No leads yet. Upload a CSV to get started.</p>
            {% endif %}
        </div>

        {% elif tab == 'history' %}
        <!-- Call History -->
        <div class="card">
            <h3 class="font-bold text-lg mb-4">📞 Call Log</h3>
            {% if call_logs %}
            <div class="space-y-3">
                {% for log in call_logs %}
                <div class="bg-[#1a1a26] border border-[#252533] rounded-lg p-4">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-sm font-medium">{{ log.created_at[:16] }}</span>
                        <span class="text-xs text-[#7a7a8e]">${{ "%.2f"|format(log.cost or 0) }} · {{ log.duration or 0 }}s</span>
                    </div>
                    <p class="text-sm text-[#b0b0c0]">{{ (log.transcript or 'No transcript')[:200] }}</p>
                    {% if log.appointment_time %}
                    <div class="mt-2 badge badge-success">📅 {{ log.appointment_time }}</div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% else %}
            <p class="text-center text-[#5c5c70] py-8">No calls made yet.</p>
            {% endif %}
        </div>

        {% elif tab == 'settings' %}
        <!-- Settings -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="card">
                <h3 class="font-bold mb-4">🤖 Your Script</h3>
                <form method="POST" action="/update-script">
                    <label class="text-xs text-[#7a7a8e] block mb-2">System Prompt</label>
                    <textarea name="script" rows="6" class="w-full bg-[#1a1a26] border border-[#252533] rounded-lg p-3 text-sm text-[#f1f1f5]">{{ biz_info.script_template or '' }}</textarea>
                    <label class="text-xs text-[#7a7a8e] block mb-2 mt-4">Knowledge Base</label>
                    <textarea name="knowledge_base" rows="4" class="w-full bg-[#1a1a26] border border-[#252533] rounded-lg p-3 text-sm text-[#f1f1f5]">{{ biz_info.knowledge_base or '' }}</textarea>
                    <button type="submit" class="btn-primary text-sm mt-4">Save Changes</button>
                </form>
            </div>
            <div class="card">
                <h3 class="font-bold mb-4">⚙️ Campaign Settings</h3>
                <form method="POST" action="/update-settings">
                    <label class="text-xs text-[#7a7a8e] block mb-1">Call Window Start</label>
                    <input type="time" name="window_start" value="{{ biz_info.call_window_start or '09:00' }}" class="mb-3">
                    <label class="text-xs text-[#7a7a8e] block mb-1">Call Window End</label>
                    <input type="time" name="window_end" value="{{ biz_info.call_window_end or '17:00' }}" class="mb-3">
                    <label class="text-xs text-[#7a7a8e] block mb-1">Max Calls Per Day</label>
                    <input type="number" name="max_calls" value="{{ biz_info.max_calls_per_day or 20 }}" class="mb-4">
                    <button type="submit" class="btn-primary text-sm">Save Settings</button>
                </form>
                <hr class="border-[#252533] my-4">
                <h4 class="font-bold text-sm mb-2">🔗 Your Login</h4>
                <div class="bg-[#1a1a26] p-3 rounded-lg text-xs text-[#7a7a8e]">
                    <p>Business ID: <span class="text-[#c084fc]">{{ session.business_id }}</span></p>
                    <p class="mt-1">Login URL: <span class="text-[#4ade80]">{{ request.host_url }}login</span></p>
                </div>
            </div>
        </div>
        {% endif %}
        {% endif %}
    </div>
    
    <script>
    function uploadCSV(input) {
        const file = input.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append('csv', file);
        fetch('/upload-leads', { method: 'POST', body: formData })
            .then(r => r.json())
            .then(d => { alert(d.message); location.reload(); })
            .catch(e => alert('Error: ' + e));
    }
    </script>
</body>
</html>"""

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'business_id' not in session:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    tab = request.args.get('tab', 'overview')
    error = request.args.get('error', '')
    
    if 'business_id' in session:
        return dashboard(tab)
    
    return render_template_string(LANDING_HTML, session=session, error=error, tab=tab)

@app.route('/login', methods=['POST'])
def login():
    bid = request.form.get('business_id', '').strip()
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    
    if biz:
        session['business_id'] = bid
        session['biz_name'] = biz['name']
        return redirect('/')
    
    return redirect('/?error=Invalid Business ID. Please check and try again.')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/dashboard')
@login_required
def dashboard(tab=None):
    bid = session['business_id']
    if not tab:
        tab = request.args.get('tab', 'overview')
    
    db = get_db()
    c = db.cursor()
    
    c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    
    if not biz:
        session.clear()
        return redirect('/?error=Business not found')
    
    # Stats
    c.execute("SELECT COALESCE(SUM(calls_made),0) FROM campaigns WHERE business_id = ?", (bid,))
    calls_made = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(appointments_booked),0) FROM campaigns WHERE business_id = ?", (bid,))
    appointments = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ?", (bid,))
    leads_total = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(cost),0) FROM call_log WHERE business_id = ?", (bid,))
    total_cost = c.fetchone()[0]
    
    # Recent calls
    c.execute("""
        SELECT cl.*, l.phone, l.business_name 
        FROM call_log cl 
        LEFT JOIN leads l ON cl.lead_id = l.id
        WHERE cl.business_id = ? 
        ORDER BY cl.created_at DESC LIMIT 10
    """, (bid,))
    recent_calls = [dict(r) for r in c.fetchall()]
    
    # Call logs for history tab
    c.execute("""
        SELECT cl.*, l.phone, l.business_name, l.name as lead_name
        FROM call_log cl 
        LEFT JOIN leads l ON cl.lead_id = l.id
        WHERE cl.business_id = ? 
        ORDER BY cl.created_at DESC LIMIT 20
    """, (bid,))
    call_logs = [dict(r) for r in c.fetchall()]
    
    # Leads
    c.execute("SELECT * FROM leads WHERE business_id = ? ORDER BY state, created_at DESC LIMIT 50", (bid,))
    leads = [dict(r) for r in c.fetchall()]
    
    return render_template_string(LANDING_HTML,
        session=session, tab=tab, error='',
        stats={'calls_made': calls_made, 'appointments': appointments, 'leads_total': leads_total, 'total_cost': total_cost},
        biz_info=biz,
        recent_calls=recent_calls,
        call_logs=call_logs,
        leads=leads
    )

@app.route('/upload-leads', methods=['POST'])
@login_required
def upload_leads():
    bid = session['business_id']
    file = request.files.get('csv')
    
    if not file:
        return jsonify({'error': 'No file'}), 400
    
    db = get_db()
    c = db.cursor()
    count = 0
    
    stream = io.StringIO(file.stream.read().decode('utf-8'))
    reader = csv.DictReader(stream)
    
    for row in reader:
        phone = row.get('phone', row.get('Phone', row.get('number', ''))).strip()
        if not phone:
            continue
        lid = hashlib.md5((phone + bid + str(time.time())).encode()).hexdigest()[:12]
        c.execute("""
            INSERT OR IGNORE INTO leads (id, business_id, phone, name, business_name, state)
            VALUES (?, ?, ?, ?, ?, 'NEW')
        """, (lid, bid, phone, row.get('name', ''), row.get('business_name', '')))
        count += 1
    
    c.execute("UPDATE campaigns SET leads_imported = COALESCE(leads_imported,0) + ? WHERE business_id = ?", (count, bid))
    db.commit()
    
    return jsonify({'message': f'✅ {count} leads imported!'})

@app.route('/update-script', methods=['POST'])
@login_required
def update_script():
    bid = session['business_id']
    script = request.form.get('script', '')
    knowledge_base = request.form.get('knowledge_base', '')
    
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE businesses SET script_template = ?, knowledge_base = ? WHERE id = ?", (script, knowledge_base, bid))
    db.commit()
    
    return redirect('/?tab=settings')

@app.route('/update-settings', methods=['POST'])
@login_required
def update_settings():
    bid = session['business_id']
    
    db = get_db()
    c = db.cursor()
    c.execute("""
        UPDATE businesses SET 
            call_window_start = ?,
            call_window_end = ?,
            max_calls_per_day = ?
        WHERE id = ?
    """, (
        request.form.get('window_start', '09:00'),
        request.form.get('window_end', '17:00'),
        int(request.form.get('max_calls', 20)),
        bid
    ))
    db.commit()
    
    return redirect('/?tab=settings')

if __name__ == '__main__':
    print("🚀 Multi-Business Voice Agent Dashboard")
    print(f"📊 DB: {DB_PATH}")
    print("🌐 http://localhost:8084")
    app.run(host='0.0.0.0', port=8084, debug=True)
