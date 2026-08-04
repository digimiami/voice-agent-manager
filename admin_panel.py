#!/usr/bin/env python3
"""
# Diazites Admin Panel
=============================
Admin dashboard to manage all business clients:
  - Create/Edit/Delete businesses
  - Generate Business IDs & login URLs
  - Manage subscriptions & billing
  - Track payments & usage per client
  - View all client activity
  - Set pricing tiers

Admin login: http://localhost:8086/admin
Password:    from .env (ADMIN_PASSWORD)
"""

import os, sys, json, sqlite3, csv, io, hashlib, time, threading, subprocess, uuid, urllib.request, urllib.error
from datetime import datetime, date, timedelta
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, redirect, session, url_for, flash, send_file
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix

# Import Agent API module
from agent_api import agent_api, init_api_keys_table, generate_api_key, validate_api_key
from agent_api import api_key_required
from diazites_prompt import build_diazites_prompt

DB_PATH = "/root/voice-agent-businesses.db"

# ── Load VAPI key from env (DO NOT hardcode in source) ──
VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
if not VAPI_API_KEY:
    try:
        with open("/root/voice-agent-manager/.env") as f:
            for line in f:
                line = line.strip()
                if line.startswith("VAPI_API_KEY="):
                    VAPI_API_KEY = line.split("=", 1)[1]
                    break
    except:
        pass
VAPI_BASE = "https://api.vapi.ai"

# ── Load admin password from env (DO NOT hardcode in source) ──
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
if not ADMIN_PASSWORD:
    try:
        with open("/root/voice-agent-manager/.env") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ADMIN_PASSWORD="):
                    ADMIN_PASSWORD = line.split("=", 1)[1]
                    break
    except:
        pass
if not ADMIN_PASSWORD:
    print("⚠️  ADMIN_PASSWORD not set in env/.env — admin login will be BLOCKED")

app = Flask(__name__)
app.secret_key = "admin-secret-key-hermes-2026"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
# Trust X-Forwarded-Proto from nginx so cookie Secure flag works behind reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True

# Register Agent API blueprint
app.register_blueprint(agent_api)
init_api_keys_table()

# Ensure first API key exists for admin use
try:
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("SELECT COUNT(*) FROM agent_api_keys")
    if c.fetchone()[0] == 0:
        key_id, raw_key, _ = generate_api_key(
            name="Default Admin Key",
            description="Auto-generated admin API key",
            permissions="read,write,admin",
            created_by="system"
        )
        print(f"🔑 Default API key generated: {raw_key}")
    db.close()
except Exception as e:
    print(f"⚠️ Could not create default API key: {e}")

# Load persisted pricing tiers from file (if any)
try:
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pricing_tiers.json')
    if os.path.exists(cfg_path):
        import json as _j
        with open(cfg_path) as _f:
            saved = _j.load(_f)
        if saved:
            PRICING_TIERS.update(saved)
            print(f"✅ Loaded {len(saved)} pricing tiers from file")
except Exception as e:
    print(f"⚠️ Could not load pricing tiers: {e}")

# ── INDUSTRY PRESETS ──

INDUSTRY_PRESETS = {
    "dentist": "Reduce no-shows with automated booking",
    "plumber": "Never miss emergency calls",
    "roofer": "Capture storm season leads",
    "hvac": "Handle after-hours emergencies",
    "lawyer": "Qualify leads automatically",
    "real_estate": "Capture buyer/seller leads 24/7",
    "auto_mechanic": "Book service appointments overnight",
    "cleaning": "Recurring client pipeline automation",
    "pest_control": "Emergency response automation",
    "landscaper": "Book estimates while on the job",
    "general": "General business lead generation"
}

PRICING_TIERS = {
    "starter": {"name": "Starter", "price": 97, "calls_included": 500, "minutes_limit": 250, "features": "1 AI agent, 1 number, 500 calls/mo, 250 min, booking, email support"},
    "pro": {"name": "Professional", "price": 197, "calls_included": 2000, "minutes_limit": 1000, "features": "2 AI agents, 2 numbers, 2K calls/mo, 1000 min, campaigns, SMS, calendar"},
    "premium": {"name": "Premium", "price": 297, "calls_included": 5000, "minutes_limit": 2500, "features": "3 AI agents, 3 numbers, 5K calls/mo, 2500 min, forwarding, priority support"},
    "enterprise": {"name": "Enterprise", "price": 497, "calls_included": 15000, "minutes_limit": 7500, "features": "5 AI agents, 5 numbers, 15K calls/mo, 7500 min, white-label, API"},
    "custom": {"name": "Custom", "price": 997, "calls_included": 0, "minutes_limit": 0, "features": "Fully customizable package"}
}

ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diazites Admin</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        * { font-family: 'Inter', sans-serif; }
        body { background: #050508; }
        .card { background: #0d0d14; border: 1px solid #1a1a28; border-radius: 12px; padding: 20px; }
        .card-hover:hover { border-color: #6366f1; }
        .btn-primary { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 8px 16px; border-radius: 8px; font-weight: 600; border: none; cursor: pointer; transition: all 0.2s; font-size: 13px; }
        .btn-primary:hover { transform: scale(1.02); opacity: 0.9; }
        .btn-success { background: linear-gradient(135deg, #22c55e, #16a34a); color: white; padding: 8px 16px; border-radius: 8px; font-weight: 600; border: none; cursor: pointer; font-size: 13px; }
        .btn-danger { background: linear-gradient(135deg, #ef4444, #dc2626); color: white; padding: 8px 16px; border-radius: 8px; font-weight: 600; border: none; cursor: pointer; font-size: 13px; }
        .btn-secondary { background: #1a1a28; color: #e2e8f0; padding: 8px 16px; border-radius: 8px; border: 1px solid #1a1a28; cursor: pointer; font-size: 13px; transition: all 0.2s; }
        .btn-secondary:hover { border-color: #6366f1; }
        input, select, textarea { background: #1a1a28; border: 1px solid #1a1a28; border-radius: 8px; padding: 10px 14px; color: #e2e8f0; outline: none; width: 100%; font-size: 13px; }
        input:focus, select:focus { border-color: #6366f1; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 10px 12px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; border-bottom: 1px solid #1a1a28; font-weight: 600; }
        td { padding: 10px 12px; border-bottom: 1px solid #0d0d14; font-size: 13px; color: #94a3b8; }
        tr:hover td { background: #0d0d14; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 10px; font-weight: 600; }
        .badge-active { background: rgba(34,197,94,0.15); color: #4ade80; }
        .badge-inactive { background: rgba(113,113,122,0.15); color: #a1a1aa; }
        .badge-pro { background: rgba(99,102,241,0.15); color: #818cf8; }
        .badge-overdue { background: rgba(239,68,68,0.15); color: #ef4444; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: #1a1a28; border-radius: 2px; }
        .gradient-text { background: linear-gradient(135deg, #6366f1, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 100; display: none; align-items: center; justify-content: center; padding: 20px; }
        .modal-overlay.show { display: flex; }
        .modal { background: #0d0d14; border: 1px solid #1a1a28; border-radius: 16px; padding: 24px; max-width: 600px; width: 100%; max-height: 85vh; overflow-y: auto; }
        .stat-box { background: #0d0d14; border: 1px solid #1a1a28; border-radius: 12px; padding: 16px; text-align: center; }
        .sidebar { width: 230px; min-height: 100vh; background: #0d0d14; border-right: 1px solid #1a1a28; padding: 20px 14px; position: sticky; top: 0; height: 100vh; overflow-y: auto; }
        .sidebar-item { display: flex; align-items: center; gap: 10px; padding: 7px 10px; border-radius: 8px; cursor: pointer; font-size: 13px; color: #64748b; transition: all 0.15s; text-decoration: none; white-space: nowrap; }
        .sidebar-item:hover { background: #1a1a28; color: #e2e8f0; }
        .sidebar-item.active { background: linear-gradient(135deg, rgba(99,102,241,0.18), rgba(139,92,246,0.12)); color: #a5b4fc; border-left: 2px solid #6366f1; }
        .sidebar-section { font-size: 10px; font-weight: 700; letter-spacing: 1.2px; color: #475569; text-transform: uppercase; padding: 16px 10px 6px; }
        .menu-search { position: relative; margin: 14px 4px 4px; }
        .menu-search i { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); font-size: 12px; color: #475569; pointer-events: none; }
        .menu-search input { padding: 8px 10px 8px 32px; font-size: 12px; border-radius: 8px; }
        .menu-badge { margin-left: auto; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 9999px; letter-spacing: 0.5px; animation: pulse-badge 2s infinite; }
        @keyframes pulse-badge { 0%,100% { opacity: 1; } 50% { opacity: 0.55; } }
        .hamburger { display: none; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 10px; background: #1a1a28; border: 1px solid #1a1a28; color: #e2e8f0; cursor: pointer; font-size: 15px; }
        .drawer-backdrop { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 90; }
        .drawer-backdrop.show { display: block; }
        .drawer { position: fixed; top: 0; left: 0; bottom: 0; width: 264px; max-width: 84vw; background: #0d0d14; border-right: 1px solid #1a1a28; z-index: 95; transform: translateX(-100%); transition: transform 0.25s ease; overflow-y: auto; padding: 20px 14px; }
        .drawer.show { transform: translateX(0); }
        @media (max-width: 767px) {
            .hamburger { display: inline-flex; }
            .hamburger:active { border-color: #6366f1; }
        }
    </style>
</head>
<body class="text-[#e2e8f0] min-h-screen flex">
    {% if session.get('admin_logged_in') %}
    {% macro admin_menu() %}
    <div class="menu-search">
        <i class="fas fa-search"></i>
        <input type="text" class="menu-filter" placeholder="Search tabs… (e.g. sms, review, mrr)" autocomplete="off">
    </div>
    {% set groups = [
        ('Overview', [
            ('dashboard', 'gauge', 'Dashboard'),
            ('analytics', 'chart-bar', 'Analytics'),
            ('mrr', 'chart-line', 'MRR'),
            ('scoreboard', 'medal', 'Scoreboard'),
            ('health', 'heartbeat', 'Health')
        ]),
        ('Customers & Billing', [
            ('businesses', 'building', 'Businesses'),
            ('create', 'plus-circle', 'New Business'),
            ('subscriptions', 'credit-card', 'Subscriptions'),
            ('billing', 'file-invoice-dollar', 'Billing'),
            ('stripe', 'cc-stripe', 'Stripe'),
            ('coupons', 'ticket-alt', 'Coupons'),
            ('trials', 'hourglass-half', 'Trials'),
            ('usage', 'gauge-high', 'Usage'),
            ('affiliates', 'hand-holding-usd', 'Affiliates')
        ]),
        ('Communication', [
            ('sms', 'message', 'SMS'),
            ('email', 'envelope', 'Email Config'),
            ('inbox', 'inbox', 'Inbox'),
            ('broadcast', 'bullhorn', 'Broadcast'),
            ('transcripts', 'file-alt', 'Transcripts'),
            ('calendar', 'calendar-alt', 'Calendar')
        ]),
        ('Growth & Automation', [
            ('campaigns', 'rocket', 'Campaigns'),
            ('chatbot', 'robot', 'Chatbot'),
            ('industries', 'industry', 'Industries'),
            ('abtest', 'vials', 'A/B Tests')
        ]),
        ('System', [
            ('vapi', 'phone-volume', 'VAPI Config'),
            ('costs', 'dollar-sign', 'Costs'),
            ('audit', 'history', 'Audit Log'),
            ('security', 'shield-alt', 'Security'),
            ('backup', 'database', 'Backup')
        ]),
        ('AI Tools', [
            ('agent-tars', 'robot', 'Agent TARS'),
            ('agent-api', 'key', 'Agent API'),
            ('reviews-ai', 'star', 'Review AI')
        ])
    ] %}
    {% for gname, items in groups %}
    <div class="sidebar-section">{{ gname }}</div>
    {% for key, icon, label in items %}
    <a href="?tab={{ key }}" class="sidebar-item {% if tab == key %}active{% endif %}" data-label="{{ label|lower }}">
        <i class="fas fa-{{ icon }} w-4 text-center"></i><span>{{ label }}</span>
        {% if key == 'reviews-ai' %}<span class="menu-badge">NEW</span>{% endif %}
    </a>
    {% endfor %}
    {% endfor %}
    {% endmacro %}
    <!-- DESKTOP SIDEBAR -->
    <div class="sidebar hidden md:block">
        <div class="flex items-center gap-2 mb-2 px-1">
            <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-[#6366f1] to-[#8b5cf6] flex items-center justify-center text-white font-bold text-sm">A</div>
            <div>
                <div class="font-bold text-sm">Diazites</div>
                <div class="text-xs text-[#64748b]">SaaS Panel</div>
            </div>
        </div>
        <div class="flex-1 overflow-y-auto pr-1">
            {{ admin_menu() }}
        </div>
        <div class="pt-4 mt-2 border-t border-[#1a1a28]">
            <a href="/admin/logout" class="sidebar-item flex items-center gap-2 text-red-400">
                <i class="fas fa-sign-out-alt w-4 text-center"></i> Logout
            </a>
        </div>
    </div>

    <!-- MOBILE DRAWER MENU -->
    <div class="drawer-backdrop" id="drawerBackdrop"></div>
    <nav class="drawer" id="mobileDrawer">
        <div class="flex items-center justify-between mb-3 px-1">
            <div class="flex items-center gap-2">
                <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-[#6366f1] to-[#8b5cf6] flex items-center justify-center text-white font-bold text-xs">A</div>
                <span class="font-bold text-sm">Diazites</span>
            </div>
            <button class="hamburger" id="drawerClose" aria-label="Close menu"><i class="fas fa-times"></i></button>
        </div>
        {{ admin_menu() }}
        <div class="pt-4 mt-2 border-t border-[#1a1a28]">
            <a href="/admin/logout" class="sidebar-item flex items-center gap-2 text-red-400">
                <i class="fas fa-sign-out-alt w-4 text-center"></i> Logout
            </a>
        </div>
    </nav>

    <!-- MAIN -->
    <div class="flex-1 p-4 sm:p-6 overflow-x-hidden">
        <!-- Mobile header -->
        <div class="flex items-center justify-between md:hidden mb-4">
            <div class="flex items-center gap-3">
                <button class="hamburger" id="hamburgerBtn" aria-label="Open menu"><i class="fas fa-bars"></i></button>
                <div class="font-bold gradient-text">Diazites</div>
            </div>
            <a href="/admin/logout" class="text-xs text-red-400"><i class="fas fa-sign-out-alt mr-1"></i>Logout</a>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
        {% for category, message in messages %}
        <div class="fixed bottom-4 right-4 z-50 px-4 py-2 rounded-lg text-sm font-medium {% if category == 'success' %}bg-green-600{% else %}bg-red-600{% endif %} animate-bounce">{{ message | safe }}</div>
        {% endfor %}
        {% endif %}
        {% endwith %}

        <!-- TAB: DASHBOARD -->
        {% if tab == 'dashboard' %}
        <h2 class="text-xl font-bold mb-6">📊 Admin Dashboard</h2>
        
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <div class="stat-box"><div class="text-2xl font-bold text-[#818cf8]">{{ stats.total_businesses }}</div><div class="text-xs text-[#64748b] mt-1">Businesses</div></div>
            <div class="stat-box"><div class="text-2xl font-bold text-[#4ade80]">{{ stats.active_campaigns }}</div><div class="text-xs text-[#64748b] mt-1">Active Campaigns</div></div>
            <div class="stat-box"><div class="text-2xl font-bold text-[#fbbf24]">{{ stats.total_leads }}</div><div class="text-xs text-[#64748b] mt-1">Total Leads</div></div>
            <div class="stat-box"><div class="text-2xl font-bold text-[#f472b6]">${{ "%.0f"|format(stats.total_revenue) }}</div><div class="text-xs text-[#64748b] mt-1">Est. Monthly Revenue</div></div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <div class="card">
                <h3 class="font-bold mb-3">📈 Monthly Revenue</h3>
                <div class="space-y-3">
                    {% for tier, count in stats.tier_breakdown.items() %}
                    <div class="flex items-center justify-between text-sm">
                        <span class="text-[#64748b]">{{ tier.title() }}</span>
                        <span><span class="font-semibold text-[#e2e8f0]">{{ count }}</span> clients</span>
                    </div>
                    <div class="h-2 bg-[#1a1a28] rounded-full overflow-hidden">
                        <div class="h-full bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] rounded-full" style="width:{% if stats.total_businesses > 0 %}{{ (count / stats.total_businesses * 100)|round }}{% else %}0{% endif %}%"></div>
                    </div>
                    {% endfor %}
                </div>
                <div class="mt-4 pt-3 border-t border-[#1a1a28] flex justify-between text-sm">
                    <span class="text-[#64748b]">Total MRR</span>
                    <span class="font-bold text-[#4ade80]">${{ "%.0f"|format(stats.total_revenue) }}</span>
                </div>
            </div>
            <div class="card">
                <h3 class="font-bold mb-3">🕐 Recent Activity</h3>
                {% if recent_activity %}
                <div class="space-y-2">
                    {% for act in recent_activity %}
                    <div class="flex items-center gap-2 text-xs text-[#94a3b8]">
                        <span class="text-[#64748b]">{{ act.created_at[:16] }}</span>
                        <span class="text-[#818cf8]">{{ act.name }}</span>
                        <span>{{ act.phone or '' }}</span>
                        <span class="text-[#64748b]">${{ "%.2f"|format(act.cost or 0) }}</span>
                    </div>
                    {% endfor %}
                </div>
                {% else %}
                <p class="text-[#64748b] text-sm">No activity yet.</p>
                {% endif %}
            </div>
        </div>

        <!-- TAB: BUSINESSES -->
        {% elif tab == 'businesses' %}
        <div class="flex items-center justify-between mb-6">
            <h2 class="text-xl font-bold">🏪 Clients & Agents ({{ businesses|length }})</h2>
            <a href="?tab=create" class="btn-primary text-xs"><i class="fas fa-plus mr-1"></i> New Business</a>
        </div>

        <style>
        .agent-card { background:#0d0d14; border:1px solid #1a1a28; border-radius:12px; padding:20px; transition:border-color .2s }
        .agent-card:hover { border-color:#6366f1; }
        .meter-bar { height:8px; border-radius:4px; background:#1a1a28; overflow:hidden; }
        .meter-fill { height:100%; border-radius:4px; transition:width .5s; }
        .kb-box { background:#0a0a12; border:1px solid #1a1a28; border-radius:8px; padding:10px; font-size:12px; color:#7a7a8e; max-height:60px; overflow:hidden; line-height:1.4; }
        .feature-badge { display:inline-flex; align-items:center; gap:4px; font-size:11px; padding:3px 8px; border-radius:6px; background:#1a1a28; color:#cbd5e1; margin:2px; }
        .feature-badge.active { background:#22c55e15; border:1px solid #22c55e30; color:#4ade80; }
        </style>

        <div class="grid gap-4">
            {% for biz in businesses %}
            {% set plan_key = biz.plan or 'starter' %}
            {% set tier = tiers.get(plan_key, tiers['starter']) %}
            {% set used_min = (biz.total_duration or 0) // 60 %}
            {% set limit_min = tier.minutes_limit or 250 %}
            {% set pct = (used_min / limit_min * 100)|round|int if limit_min > 0 else 0 %}
            {% set kb = biz.agent_prompt or biz.knowledge_base or '' %}
            {% set features = tier.features.split(', ') %}
            {% set agent_count = {'starter':'1','pro':'2','premium':'3','enterprise':'5','custom':'?'}.get(plan_key, '1') %}

            <div class="agent-card">
                <!-- Row 1: Header -->
                <div class="flex items-start justify-between mb-3">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-600/30 to-pink-600/30 flex items-center justify-center text-lg">{{ biz.name[:1]|upper }}</div>
                        <div>
                            <div class="font-semibold text-[#e2e8f0]">{{ biz.name }} <span class="text-xs text-[#64748b] font-normal">· {{ biz.industry or 'General' }}</span></div>
                            <div class="text-xs text-[#64748b] mt-0.5 flex items-center gap-2">
                                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold" style="background:#a855f722;color:#c084fc">{{ tier.name }}</span>
                                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px]" style="background:#22c55e15;color:#4ade80">🧠 {{ agent_count }} Agent{% if agent_count != '1' %}s{% endif %}</span>
                                <span class="{% if biz.status == 'active' %}text-[#4ade80]{% else %}text-red-400{% endif %}">● {{ biz.status or 'active' }}</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <a href="/admin/business/{{ biz.id }}" class="btn-secondary text-xs py-1.5 px-3"><i class="fas fa-eye mr-1"></i>View</a>
                        <a href="/admin/business/{{ biz.id }}/resend-credentials" class="btn-secondary text-xs py-1.5 px-3" onclick="return confirm('Resend credentials to {{ biz.name }}?')"><i class="fas fa-envelope"></i></a>
                        <form method="POST" action="/admin/business/delete/{{ biz.id }}" style="display:inline" onsubmit="return confirm('Delete business and all data?')">
                            <button class="text-red-400 text-xs py-1.5 px-3 border border-red-800 rounded-lg hover:bg-red-900/20"><i class="fas fa-trash"></i></button>
                        </form>
                    </div>
                </div>

                <!-- Row 2: Knowledge Base / Agent Prompt -->
                <div class="mb-3">
                    <div class="flex items-center justify-between mb-1">
                        <span class="text-xs text-[#64748b] font-semibold">📝 Knowledge Base / Agent Prompt</span>
                        <a href="/admin/business/{{ biz.id }}" class="text-[10px] text-[#818cf8] hover:underline">Edit →</a>
                    </div>
                    <div class="kb-box">{% if kb %}{{ kb[:200] }}{% if kb|length > 200 %}...{% endif %}{% else %}<span class="text-[#5c5c70] italic">No custom knowledge base configured. Using default script.</span>{% endif %}</div>
                </div>

                <!-- Row 3: Minutes Meter + Buy More -->
                <div class="grid grid-cols-3 gap-4 mb-3">
                    <div class="col-span-2">
                        <div class="flex items-center justify-between mb-1">
                            <span class="text-xs text-[#64748b] font-semibold">⏱ Call Minutes Used</span>
                            <span class="text-xs font-mono">{{ used_min }} / {{ limit_min }} min</span>
                        </div>
                        <div class="meter-bar">
                            <div class="meter-fill {% if pct < 60 %}bg-gradient-to-r from-[#22c55e] to-[#4ade80]{% elif pct < 85 %}bg-gradient-to-r from-[#f59e0b] to-[#fbbf24]{% else %}bg-gradient-to-r from-[#ef4444] to-[#f87171]{% endif %}" style="width:{{ pct }}%"></div>
                        </div>
                        <div class="flex items-center justify-between mt-1">
                            <span class="text-[10px] text-[#5c5c70]">{{ limit_min - used_min }} min remaining</span>
                            <span class="text-[10px] text-[#5c5c70]">{{ pct }}% used</span>
                        </div>
                    </div>
                    <div class="flex flex-col justify-center items-center border border-dashed border-[#1a1a28] rounded-lg p-3">
                        <span class="text-xs text-[#818cf8] font-semibold mb-1">+ Buy Minutes</span>
                        <div class="flex gap-1">
                            <button onclick="buyMinutes('{{ biz.id }}','500')" class="text-[10px] px-2 py-1 rounded bg-[#1a1a28] hover:bg-[#252533] text-[#cbd5e1]">500</button>
                            <button onclick="buyMinutes('{{ biz.id }}','1000')" class="text-[10px] px-2 py-1 rounded bg-[#1a1a28] hover:bg-[#252533] text-[#cbd5e1]">1K</button>
                            <button onclick="buyMinutes('{{ biz.id }}','5000')" class="text-[10px] px-2 py-1 rounded bg-[#6366f1] text-white hover:bg-[#818cf8]">5K</button>
                        </div>
                    </div>
                </div>

                <!-- Row 4: Plan Features -->
                <div class="flex flex-wrap gap-1">
                    <span class="feature-badge active">🤖 {{ agent_count }} AI Agent{% if agent_count != '1' %}s{% endif %}</span>
                    {% if plan_key == 'starter' or plan_key == 'pro' or plan_key == 'premium' or plan_key == 'enterprise' %}
                    <span class="feature-badge active">📞 1 Number{% if plan_key != 'starter' %} +{% endif %}</span>
                    {% endif %}
                    {% if plan_key == 'pro' or plan_key == 'premium' or plan_key == 'enterprise' %}
                    <span class="feature-badge active">📱 SMS Reminders</span>
                    <span class="feature-badge active">📅 Calendar Booking</span>
                    <span class="feature-badge active">📊 Campaigns</span>
                    <span class="feature-badge active">⭐ Priority Support</span>
                    {% endif %}
                    {% if plan_key == 'premium' or plan_key == 'enterprise' %}
                    <span class="feature-badge active">🔄 Call Forwarding</span>
                    <span class="feature-badge active">🏢 3+ Numbers</span>
                    {% endif %}
                    {% if plan_key == 'enterprise' %}
                    <span class="feature-badge active">🔌 API Access</span>
                    <span class="feature-badge active">🏷️ White-Label</span>
                    <span class="feature-badge active">👤 Dedicated Manager</span>
                    {% endif %}
                    {% if plan_key == 'custom' %}
                    <span class="feature-badge active">⚙️ Custom Config</span>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>

        <script>
        function buyMinutes(bizId, amount) {
            if (!confirm('Add ' + amount + ' extra minutes to ' + bizId + '?')) return;
            fetch('/admin/api/add-minutes', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({business_id: bizId, minutes: parseInt(amount)})
            }).then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.success) { alert('✅ ' + amount + ' minutes added!'); location.reload(); }
                else { alert('❌ ' + (d.error || 'Failed')); }
            }).catch(function(err) { alert('❌ ' + err.message); });
        }
        </script>

        <!-- TAB: CREATE BUSINESS -->
        {% elif tab == 'create' %}
        <h2 class="text-xl font-bold mb-6">➕ Create New Business</h2>
        
        <div class="max-w-2xl card">
            <form method="POST" action="/admin/create-business" class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Business Name *</label>
                        <input type="text" name="name" placeholder="e.g. Mario's Plumbing" required>
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Contact Email</label>
                        <input type="email" name="email" placeholder="mario@example.com">
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Industry</label>
                        <select name="industry">
                            {% for ind, desc in industries.items() %}
                            <option value="{{ ind }}">{{ ind.replace('_',' ').title() }} — {{ desc[:30] }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Subscription Package</label>
                        <select name="plan" onchange="toggleCustom()">
                            {% for key, tier in tiers.items() %}
                            <option value="{{ key }}">{{ tier.name }} — ${{ tier.price }}/mo ({{ tier.calls_included }} calls)</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>

                <!-- CUSTOM PACKAGE FIELDS (shown when Custom selected) -->
                <div id="customPackage" style="display:none" class="p-4 bg-[#0a0a12] border border-[#6366f1]/30 rounded-lg space-y-4">
                    <p class="text-xs font-semibold text-[#818cf8]">✏️ Custom Package Configuration</p>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="text-xs text-[#64748b] block mb-1">Monthly Price ($)</label>
                            <input type="number" name="monthly_price" value="0" min="0" step="10">
                        </div>
                        <div>
                            <label class="text-xs text-[#64748b] block mb-1">Calls Included / Month</label>
                            <input type="number" name="calls_included" value="1000" min="0" step="100">
                        </div>
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Features Description</label>
                        <input type="text" name="features_desc" value="Custom package" placeholder="e.g. AI agent, 3 numbers, 5K calls, priority support">
                    </div>
                    <div class="grid grid-cols-3 gap-4">
                        <div>
                            <label class="text-xs text-[#64748b] block mb-1">🧠 Max Tokens</label>
                            <input type="number" name="max_tokens" value="200" min="50" max="1000" step="10">
                        </div>
                        <div>
                            <label class="text-xs text-[#64748b] block mb-1">⚡ Voice Speed</label>
                            <input type="number" name="voice_speed" value="1.0" min="0.5" max="2.0" step="0.05">
                        </div>
                        <div>
                            <label class="text-xs text-[#64748b] block mb-1">📞 Concurrency</label>
                            <input type="number" name="concurrency" value="5" min="1" max="50">
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Phone (for AI to call)</label>
                        <input type="text" name="phone_number" placeholder="+123****7890">
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Monthly Price ($)</label>
                        <input type="number" name="monthly_price" value="599" placeholder="599">
                    </div>
                </div>

                <script>
                function toggleCustom(){
                    var sel = document.querySelector('select[name=plan]');
                    document.getElementById('customPackage').style.display = sel.value === 'custom' ? 'block' : 'none';
                }
                </script>

                <div>
                    <label class="text-xs text-[#64748b] block mb-1">Script Template</label>
                    <textarea name="script_template" rows="3">{{ default_script }}</textarea>
                </div>

                <button type="submit" class="btn-primary"><i class="fas fa-magic mr-1"></i> Create Business</button>
            </form>
        </div>

        <!-- TAB: SUBSCRIPTIONS -->
        {% elif tab == 'subscriptions' %}
        <h2 class="text-xl font-bold mb-6">📋 Subscriptions & Plan Manager</h2>

        <!-- Plan Cards with Edit -->
        <div class="grid grid-cols-1 lg:grid-cols-5 gap-3 mb-6">
            {% for key, tier in tiers.items() %}
            <div class="card card-hover p-4 {% if key == 'pro' %}border-[#6366f1]/50{% endif %}">
                <div class="flex items-center justify-between mb-2">
                    <div class="text-xs text-[#64748b] uppercase tracking-wider font-semibold">{{ tier.name }}</div>
                    <button onclick="editTier('{{ key }}')" class="text-[#818cf8] hover:text-[#a855f7] text-xs"><i class="fas fa-edit"></i></button>
                </div>
                <div class="text-2xl font-bold text-[#e2e8f0]">${{ tier.price }}<span class="text-sm text-[#64748b]">/mo</span></div>
                <div class="text-xs text-[#64748b] mt-1">{{ tier.features }}</div>
                <div class="mt-2 space-y-1 text-xs">
                    <div class="text-[#4ade80]">{{ tier.calls_included }} calls</div>
                    <div class="text-[#fbbf24]">{{ tier.minutes_limit }} min limit</div>
                </div>
                <div class="mt-2 text-[#7a7a8e] text-xs"><span class="font-semibold text-[#e2e8f0]">{{ sub_counts[key] or 0 }}</span> clients</div>
            </div>
            {% endfor %}
        </div>

        <!-- Edit Tier Modal -->
        <div id="tierModal" class="hidden fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm" onclick="if(event.target===this)closeTierModal()">
        <div class="card max-w-md w-full mx-4" onclick="event.stopPropagation()">
            <h3 class="font-bold mb-4">✏️ Edit Plan</h3>
            <form id="tierForm" class="space-y-3">
                <input type="hidden" id="tierKey">
                <div>
                    <label class="text-xs text-[#64748b] block mb-1">Plan Name</label>
                    <input type="text" id="tierName" class="w-full bg-[#12121a] border border-[#252533] rounded-lg px-3 py-2 text-sm">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Price ($/mo)</label>
                        <input type="number" id="tierPrice" class="w-full bg-[#12121a] border border-[#252533] rounded-lg px-3 py-2 text-sm">
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Calls Included</label>
                        <input type="number" id="tierCalls" class="w-full bg-[#12121a] border border-[#252533] rounded-lg px-3 py-2 text-sm">
                    </div>
                </div>
                <div>
                    <label class="text-xs text-[#64748b] block mb-1">Minutes Limit</label>
                    <input type="number" id="tierMinutes" class="w-full bg-[#12121a] border border-[#252533] rounded-lg px-3 py-2 text-sm">
                </div>
                <div>
                    <label class="text-xs text-[#64748b] block mb-1">Features (comma separated)</label>
                    <input type="text" id="tierFeatures" class="w-full bg-[#12121a] border border-[#252533] rounded-lg px-3 py-2 text-sm">
                </div>
                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="saveTier()" class="btn-primary flex-1">💾 Save Plan</button>
                    <button type="button" onclick="closeTierModal()" class="btn-primary flex-1 !bg-[#1a1a28] !bg-none" style="background:#1a1a28">Cancel</button>
                </div>
            </form>
        </div>
        </div>

        <!-- Clients by Plan with minutes & upgrade -->
        <div class="card">
            <div class="flex items-center justify-between mb-3">
                <h3 class="font-bold">👥 Clients by Plan</h3>
                <span class="text-xs text-[#64748b]">{{ businesses|length }} clients</span>
            </div>
            <div class="overflow-x-auto">
            <table>
                <tr><th>Business</th><th>Plan</th><th>Price</th><th>Calls</th><th>Minutes</th><th>% Calls</th><th>% Minutes</th><th>Action</th></tr>
                {% for biz in businesses %}
                {% set plan = biz.plan or 'starter' %}
                {% set tier = tiers[plan] if plan in tiers else tiers['starter'] %}
                {% set calls_made = biz.calls_made|int or 0 %}
                {% set total_seconds = biz.total_duration|int or 0 %}
                {% set total_minutes = (total_seconds / 60)|round(1) %}
                {% set call_pct = ((calls_made / tier.calls_included) * 100)|round if tier.calls_included > 0 else 0 %}
                {% set min_pct = ((total_minutes / tier.minutes_limit) * 100)|round if tier.minutes_limit > 0 else 0 %}
                {% set over_limit = call_pct > 100 or min_pct > 100 %}
                <tr class="{% if over_limit %}bg-red-500/5{% endif %}">
                    <td class="font-semibold text-sm">{{ biz.name }}</td>
                    <td>
                        <select onchange="changePlan('{{ biz.id }}', this.value)" class="text-xs bg-[#12121a] border border-[#252533] rounded px-2 py-1">
                            {% for k, t in tiers.items() %}
                            <option value="{{ k }}" {% if k == plan %}selected{% endif %}>{{ t.name }}</option>
                            {% endfor %}
                        </select>
                    </td>
                    <td>${{ "%.0f"|format(biz.monthly_price|int or tier.price) }}</td>
                    <td class="text-xs">{{ calls_made }}/{{ tier.calls_included }}</td>
                    <td class="text-xs">{{ total_minutes }}/{{ tier.minutes_limit }}m</td>
                    <td>
                        <div class="flex items-center gap-2">
                            <div class="h-1.5 w-16 bg-[#1a1a28] rounded-full overflow-hidden">
                                <div class="h-full rounded-full {% if call_pct > 100 %}bg-red-500{% else %}bg-gradient-to-r from-[#6366f1] to-[#8b5cf6]{% endif %}" style="width:{{ [call_pct, 100]|min|float }}%"></div>
                            </div>
                            <span class="text-xs {% if call_pct > 100 %}text-red-400{% else %}text-[#94a3b8]{% endif %}">{{ "%.0f"|format(call_pct) }}%</span>
                        </div>
                    </td>
                    <td>
                        <div class="flex items-center gap-2">
                            <div class="h-1.5 w-16 bg-[#1a1a28] rounded-full overflow-hidden">
                                <div class="h-full rounded-full {% if min_pct > 100 %}bg-red-500{% else %}bg-gradient-to-r from-[#fbbf24] to-[#f59e0b]{% endif %}" style="width:{{ [min_pct, 100]|min|float }}%"></div>
                            </div>
                            <span class="text-xs {% if min_pct > 100 %}text-red-400{% else %}text-[#94a3b8]{% endif %}">{{ "%.0f"|format(min_pct) }}%</span>
                        </div>
                    </td>
                    <td>
                        {% if over_limit %}
                        <span class="badge badge-error text-xs">⚠️ Over limit</span>
                        {% else %}
                        <span class="badge badge-active text-xs">OK</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </table>
            </div>
        </div>

        <!-- Tier Editor JS -->
        <script>
        function editTier(key) {
            var tiers = {{ tiers|tojson|safe }};
            var t = tiers[key];
            document.getElementById('tierKey').value = key;
            document.getElementById('tierName').value = t.name;
            document.getElementById('tierPrice').value = t.price;
            document.getElementById('tierCalls').value = t.calls_included;
            document.getElementById('tierMinutes').value = t.minutes_limit || 0;
            document.getElementById('tierFeatures').value = t.features;
            document.getElementById('tierModal').classList.remove('hidden');
        }
        function closeTierModal() {
            document.getElementById('tierModal').classList.add('hidden');
        }
        function saveTier() {
            var key = document.getElementById('tierKey').value;
            var data = {
                name: document.getElementById('tierName').value,
                price: parseInt(document.getElementById('tierPrice').value) || 0,
                calls_included: parseInt(document.getElementById('tierCalls').value) || 0,
                minutes_limit: parseInt(document.getElementById('tierMinutes').value) || 0,
                features: document.getElementById('tierFeatures').value
            };
            fetch('/admin/api/update-tier', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({key: key, tier: data})
            }).then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.success) {
                    closeTierModal();
                    location.reload();
                } else {
                    alert('Error: ' + (d.error || 'Failed to save'));
                }
            });
        }
        function changePlan(bizId, plan) {
            if (!confirm('Change this business to ' + plan + ' plan?')) return;
            fetch('/admin/api/change-plan', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({business_id: bizId, plan: plan})
            }).then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.success) {
                    location.reload();
                } else {
                    alert('Error: ' + (d.error || 'Failed'));
                }
            });
        }
        </script>

        {% elif tab == 'billing' %}
        <h2 class="text-xl font-bold mb-6">💰 Billing Overview</h2>
        
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
            <div class="card">
                <div class="text-xs text-[#64748b] uppercase">Monthly Recurring Revenue</div>
                <div class="text-3xl font-bold text-[#4ade80] mt-2">${{ "%.0f"|format(stats.total_revenue) }}</div>
                <div class="text-xs text-[#64748b] mt-1">{{ stats.total_businesses }} clients</div>
            </div>
            <div class="card">
                <div class="text-xs text-[#64748b] uppercase">Avg Revenue Per Client</div>
                <div class="text-3xl font-bold text-[#818cf8] mt-2">${{ "%.0f"|format(stats.total_revenue / stats.total_businesses) if stats.total_businesses > 0 else '0' }}</div>
                <div class="text-xs text-[#64748b] mt-1">ARPC</div>
            </div>
            <div class="card">
                <div class="text-xs text-[#64748b] uppercase">Total AI Cost (est.)</div>
                <div class="text-3xl font-bold text-[#f472b6] mt-2">${{ "%.0f"|format(stats.total_ai_cost) }}</div>
                <div class="text-xs text-[#64748b] mt-1">{{ "%.1f"|format(stats.total_ai_cost / stats.total_revenue * 100) if stats.total_revenue > 0 else '0' }}% of revenue</div>
            </div>
        </div>

        <div class="card">
            <h3 class="font-bold mb-3">Billable Clients</h3>
            <table>
                <tr><th>Business</th><th>Plan</th><th>Monthly</th><th>Calls</th><th>AI Cost</th><th>Profit</th><th>Margin</th></tr>
                {% for biz in businesses %}
                {% set plan = biz.plan or 'starter' %}
                {% set tier = tiers[plan] if plan in tiers else tiers['starter'] %}
                {% set price = (biz.monthly_price|int) if biz.monthly_price else tier.price %}
                {% set ai_cost = (biz.calls_made or 0) * 0.05 %}
                {% set profit = price - ai_cost %}
                {% set margin = (profit / price * 100)|round if price > 0 else 0 %}
                <tr>
                    <td>{{ biz.name }}</td>
                    <td>{{ tier.name }}</td>
                    <td class="text-[#4ade80]">${{ "%.0f"|format(price) }}</td>
                    <td>{{ biz.calls_made or 0 }}</td>
                    <td class="text-[#f472b6]">${{ "%.2f"|format(ai_cost) }}</td>
                    <td class="text-[#4ade80]">${{ "%.0f"|format(profit) }}</td>
                    <td class="text-[#4ade80]">{{ margin }}%</td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <!-- TAB: VAPI CONFIG -->
        {% elif tab == 'vapi' %}
        <h2 class="text-xl font-bold mb-6">📞 VAPI Configuration</h2>
        
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="card">
                <h3 class="font-bold mb-3">Available Phone Numbers</h3>
                <div class="space-y-2">
                    {% for num in vapi_numbers %}
                    <div class="flex items-center justify-between bg-[#1a1a28] rounded-lg p-3">
                        <div>
                            <div class="font-medium text-sm">{{ num.number }}</div>
                            <div class="text-xs text-[#64748b]">{{ num.name }}</div>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="badge badge-active text-xs">Available</span>
                            <span class="text-xs text-[#64748b]">{{ num.provider }}</span>
                        </div>
                    </div>
                    {% else %}
                    <p class="text-[#64748b] text-sm">No numbers found</p>
                    {% endfor %}
                </div>
            </div>
            <div class="card">
                <h3 class="font-bold mb-3">API Configuration</h3>
                <div class="space-y-2 text-sm">
                    <div class="flex justify-between"><span class="text-[#64748b]">VAPI API Key</span><span class="font-mono text-xs">••••••••{{ VAPI_API_KEY[-4:] }}</span></div>
                    <div class="flex justify-between"><span class="text-[#64748b]">Assistants Created</span><span>{{ vapi_assistant_count }}</span></div>
                    <div class="flex justify-between"><span class="text-[#64748b]">Numbers Available</span><span>{{ vapi_numbers|length }}</span></div>
                </div>
                <hr class="border-[#1a1a28] my-4">
                <h3 class="font-bold mb-3">📱 Twilio Credentials</h3>
                <form method="POST" action="/admin/update-twilio" class="space-y-3">
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Account SID</label>
                        <input type="text" name="account_sid" value="{{ twilio_config.account_sid or '' }}" placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx">
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Auth Token</label>
                        <input type="password" name="auth_token" value="{{ twilio_config.auth_token or '' }}" placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx">
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">From Number</label>
                        <input type="text" name="from_number" value="{{ twilio_config.from_number or '' }}" placeholder="+123****7890">
                    </div>
                    <button type="submit" class="btn-primary text-xs"><i class="fas fa-save mr-1"></i> Save Twilio Config</button>
                </form>
                <hr class="border-[#1a1a28] my-4">
                <p class="text-xs text-[#64748b]">Configure in VAPI dashboard for additional numbers and settings.</p>
                <a href="https://dashboard.vapi.ai" target="_blank" class="btn-secondary text-xs mt-3 inline-block"><i class="fas fa-external-link-alt mr-1"></i> Open VAPI Dashboard</a>
            </div>
        </div>

        <!-- TAB: CHATBOT SETTINGS -->
        {% elif tab == 'chatbot' %}
        <h2 class="text-xl font-bold mb-6">🤖 Chatbot Configuration</h2>
        <p class="text-sm text-[#64748b] mb-6">Configure the AI chatbot on your landing page. Visitors can ask questions about pricing, features, and setup.</p>
        
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="card">
                <h3 class="font-bold mb-4">AI Provider</h3>
                <form method="POST" action="/admin/update-chatbot" class="space-y-4">
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Provider</label>
                        <select name="chatbot_provider">
                            <option value="xai" {% if chatbot_provider == 'xai' %}selected{% endif %}>xAI (Grok) — Recommended</option>
                            <option value="deepseek" {% if chatbot_provider == 'deepseek' %}selected{% endif %}>DeepSeek</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Model</label>
                        <input type="text" name="chatbot_model" value="{{ chatbot_model or '' }}" placeholder="Leave blank for default (grok-4-mini / deepseek-chat)">
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">API Key</label>
                        <input type="password" name="chatbot_api_key" value="{{ chatbot_api_key or '' }}" placeholder="sk-...">
                        <p class="text-[10px] text-[#475569] mt-1">Uses XAI_API_KEY from env as fallback</p>
                    </div>
                    <button type="submit" class="btn-primary"><i class="fas fa-save mr-1"></i> Save Chatbot Settings</button>
                </form>
            </div>
            <div class="card">
                <h3 class="font-bold mb-4">💬 Preview</h3>
                <div class="bg-[#1a1a28] rounded-lg p-4 mb-4">
                    <p class="text-xs text-[#64748b] mb-2">Chatbot will answer questions like:</p>
                    <div class="space-y-2">
                        <div class="bg-[#0d0d14] rounded-lg p-2 text-xs">💬 "How much does it cost?"</div>
                        <div class="bg-[#0d0d14] rounded-lg p-2 text-xs">💬 "What features do you offer?"</div>
                        <div class="bg-[#0d0d14] rounded-lg p-2 text-xs">💬 "Can I try it for free?"</div>
                    </div>
                </div>
                <div class="text-xs text-[#64748b]">
                    <p><strong>Current Provider:</strong> {{ chatbot_provider or 'xAI' }}</p>
                    <p><strong>Model:</strong> {{ chatbot_model or 'Default' }}</p>
                    <p><strong>API Key Set:</strong> {% if chatbot_api_key %}✅ Yes{% else %}❌ No (using env fallback){% endif %}</p>
                </div>
            </div>
        </div>

        <!-- TAB: INDUSTRIES -->
        {% elif tab == 'industries' %}
        <div class="flex items-center justify-between mb-6">
            <h2 class="text-xl font-bold">🏭 Industry Presets</h2>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {% for ind, desc in industries.items() %}
            <div class="card card-hover">
                <div class="font-semibold text-sm">{{ ind.replace('_',' ').title() }}</div>
                <div class="text-xs text-[#64748b] mt-1">{{ desc }}</div>
                <div class="mt-2 text-xs text-[#818cf8]">{{ businesses|selectattr('industry','equalto',ind)|list|length }} clients</div>
            </div>
            {% endfor %}
        </div>

        <!-- TAB: EMAIL CONFIG -->
        {% elif tab == 'email' %}
        <h2 class="text-xl font-bold mb-6">📧 Email Configuration</h2>
        <div class="max-w-xl card mb-6">
            <h3 class="font-bold mb-3">SMTP Settings</h3>
            <p class="text-xs text-[#64748b] mb-4">Configure email to send Business IDs to new clients automatically.</p>
            <form method="POST" action="/admin/update-email-config">
                <label class="text-xs text-[#64748b] block mb-1">SMTP Server</label>
                <input type="text" name="smtp_host" value="{{ smtp_config.host or '' }}" placeholder="smtp.gmail.com" class="mb-3">
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">SMTP Port</label>
                        <input type="number" name="smtp_port" value="{{ smtp_config.port or '587' }}" class="mb-3">
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Use TLS</label>
                        <select name="smtp_tls" class="mb-3">
                            <option value="1" {% if smtp_config.tls != '0' %}selected{% endif %}>Yes</option>
                            <option value="0" {% if smtp_config.tls == '0' %}selected{% endif %}>No</option>
                        </select>
                    </div>
                </div>
                <label class="text-xs text-[#64748b] block mb-1">Email Address</label>
                <input type="email" name="smtp_email" value="{{ smtp_config.email or '' }}" placeholder="you@gmail.com" class="mb-3">
                <label class="text-xs text-[#64748b] block mb-1">Password / App Password</label>
                <input type="password" name="smtp_password" value="{{ smtp_config.password or '' }}" placeholder="App password" class="mb-4">
                <button type="submit" class="btn-primary text-sm"><i class="fas fa-save mr-1"></i> Save SMTP</button>
            </form>
        </div>
        <div class="max-w-xl card">
            <h3 class="font-bold mb-3">📨 Test Email</h3>
            <p class="text-xs text-[#64748b] mb-3">Send a test email to verify configuration.</p>
            <form method="POST" action="/admin/test-email">
                <label class="text-xs text-[#64748b] block mb-1">Send To</label>
                <input type="email" name="test_to" placeholder="client@example.com" required class="mb-3">
                <button type="submit" class="btn-secondary text-sm"><i class="fas fa-paper-plane mr-1"></i> Send Test</button>
            </form>
        </div>

        <!-- TAB: SMS CONFIG -->
        {% elif tab == 'sms' %}
        <h2 class="text-xl font-bold mb-6">📱 SMS Settings</h2>
        <div class="max-w-xl card mb-6">
            <h3 class="font-bold mb-3">Twilio SMS Settings</h3>
            <p class="text-xs text-[#64748b] mb-4">Configure SMS for auto follow-ups after calls and appointment reminders.</p>
            <form method="POST" action="/admin/update-twilio">
                <label class="flex items-center gap-2 mb-3">
                    <input type="checkbox" name="sms_enabled" value="1" {% if twilio_config.enabled %}checked{% endif %} class="w-auto accent-[#6366f1]">
                    <span class="text-sm">Enable SMS Follow-ups</span>
                </label>
                <label class="text-xs text-[#64748b] block mb-1">Twilio Account SID</label>
                <input type="text" name="account_sid" value="{{ twilio_config.account_sid or '' }}" placeholder="AC..." class="mb-3 font-mono text-xs">
                <label class="text-xs text-[#64748b] block mb-1">Twilio Auth Token</label>
                <input type="password" name="auth_token" value="{{ twilio_config.auth_token or '' }}" placeholder="********" class="mb-3 font-mono text-xs">
                <label class="text-xs text-[#64748b] block mb-1">Twilio From Number</label>
                <input type="text" name="from_number" value="{{ twilio_config.from_number or '' }}" placeholder="+17861234567" class="mb-4">
                <button type="submit" class="btn-primary text-sm"><i class="fas fa-save mr-1"></i> Save SMS Config</button>
            </form>
        </div>

        <!-- BULK SMS SENDER (admin only) -->
        <div class="max-w-2xl card mb-6 mt-6">
            <h3 class="font-bold mb-3">📢 Bulk SMS Sender <span class="text-[10px] text-[#fbbf24] bg-yellow-500/10 px-2 py-0.5 rounded-full ml-1">ADMIN ONLY</span></h3>
            <p class="text-xs text-[#64748b] mb-4">Send one message to many numbers: all leads, one business's leads, business owners, an uploaded list, or numbers you paste in. Sent via sms-gate.app.</p>

            <form method="POST" action="/admin/bulk-sms" enctype="multipart/form-data" id="bulkSmsForm">
                <label class="text-xs text-[#64748b] block mb-1">📝 Message <span class="text-[10px]">(use <code>{name}</code> and <code>{business}</code> for personalization)</span></label>
                <textarea name="message" id="bulkMessage" rows="3" placeholder="Hi {name}, this is a message from Diazites..." class="mb-1" required></textarea>
                <div class="flex justify-between items-center mb-3">
                    <div class="flex gap-1 flex-wrap">
                        <button type="button" onclick="insertVar('{name}')" class="btn-secondary text-[10px] px-2 py-1" style="padding:2px 8px">+{name}</button>
                        <button type="button" onclick="insertVar('{business}')" class="btn-secondary text-[10px] px-2 py-1" style="padding:2px 8px">+{business}</button>
                    </div>
                    <span id="charCount" class="text-[10px] text-[#64748b]">0 chars · 0 SMS</span>
                </div>

                <label class="text-xs text-[#64748b] block mb-1">🎯 Recipients</label>
                <select name="target" id="bulkTarget" class="mb-3" onchange="toggleBulkTarget()">
                    <option value="all">🌎 All leads (every business)</option>
                    <option value="business">🏢 A specific business's leads</option>
                    <option value="owners">👤 All business owners (dashboard users)</option>
                    <option value="paste">⌨️ Type / paste phone numbers</option>
                    <option value="upload">📄 Upload a phone number list (CSV/txt)</option>
                </select>

                <div id="bulkBusinessRow" style="display:none" class="mb-3">
                    <label class="text-xs text-[#64748b] block mb-1">🏢 Business</label>
                    <select name="business_id" id="bulkBusinessId" class="mb-1">
                        {% for b in businesses %}
                        <option value="{{ b.id }}">{{ b.name }} ({{ b.id[:8] }})</option>
                        {% endfor %}
                    </select>
                </div>

                <div id="bulkPasteRow" style="display:none" class="mb-3">
                    <label class="text-xs text-[#64748b] block mb-1">⌨️ Phone numbers <span class="text-[10px]">(one per line, or CSV: phone,name)</span></label>
                    <textarea name="pasted_numbers" id="bulkPasted" rows="4" placeholder="7867846192
+17865551234
(786) 555-1234, John" class="mb-1"></textarea>
                </div>

                <div id="bulkUploadRow" style="display:none" class="mb-3">
                    <label class="text-xs text-[#64748b] block mb-1">📄 Phone list file</label>
                    <input type="file" name="phone_file" id="bulkFile" accept=".csv,.txt" class="mb-1">
                    <p class="text-xs text-[#5c5c70]">One number per line, or CSV: phone,name. Formats: 7867846192, +17867846192, (786) 784-6192</p>
                </div>

                <div class="flex items-center gap-3 mb-4">
                    <button type="button" onclick="previewBulk()" class="btn-secondary text-sm"><i class="fas fa-eye mr-1"></i> Preview Count</button>
                    <span id="previewResult" class="text-xs text-[#64748b]"></span>
                </div>

                <button type="submit" class="btn-primary text-sm" id="bulkSendBtn" onclick="return confirmBulkSend()"><i class="fas fa-paper-plane mr-1"></i> Send Bulk SMS</button>
            </form>
        </div>

        <script>
        function toggleBulkTarget() {
            var t = document.getElementById('bulkTarget').value;
            document.getElementById('bulkBusinessRow').style.display = t === 'business' ? 'block' : 'none';
            document.getElementById('bulkPasteRow').style.display = t === 'paste' ? 'block' : 'none';
            document.getElementById('bulkUploadRow').style.display = t === 'upload' ? 'block' : 'none';
            document.getElementById('previewResult').textContent = '';
        }
        function insertVar(v) {
            var ta = document.getElementById('bulkMessage');
            ta.value += v;
            updateCharCount();
            ta.focus();
        }
        function updateCharCount() {
            var len = document.getElementById('bulkMessage').value.length;
            var segs = Math.max(1, Math.ceil(len / 160));
            document.getElementById('charCount').textContent = len + ' chars · ' + segs + ' SMS' + (segs > 1 ? ' (multi-part)' : '');
        }
        document.getElementById('bulkMessage').addEventListener('input', updateCharCount);
        function previewBulk() {
            var fd = new FormData(document.getElementById('bulkSmsForm'));
            var span = document.getElementById('previewResult');
            span.textContent = '⏳ Counting...';
            fetch('/admin/bulk-sms-preview', { method: 'POST', body: fd })
                .then(function(r){ return r.json(); })
                .then(function(d){
                    var s = d.sample && d.sample.length ? ' · e.g. ' + d.sample.join(', ') : '';
                    span.textContent = '👥 ' + d.count + ' recipients will receive this SMS' + s;
                })
                .catch(function(){ span.textContent = '❌ Preview failed'; });
        }
        function confirmBulkSend() {
            var msg = document.getElementById('bulkMessage').value.trim();
            if (!msg) { alert('Type a message first'); return false; }
            return confirm('Send this SMS to the selected recipients?');
        }
        </script>


        <!-- ADMIN REPLY CENTER -->
        <div class="max-w-3xl card mt-6">
            <h3 class="font-bold mb-3">📥 Reply Center <span class="text-[10px] text-[#fbbf24] bg-yellow-500/10 px-2 py-0.5 rounded-full ml-1">ADMIN ONLY</span></h3>
            <p class="text-xs text-[#64748b] mb-4">Every incoming reply across all businesses, plus everything sent. Reply to any number from here — auto-refreshes every 20s.</p>
            <div class="flex items-center gap-2 mb-3">
                <button onclick="refreshAdminInbox()" class="btn-secondary text-xs" style="padding:4px 12px">🔄 Refresh</button>
                <input type="text" id="adminInboxSearch" placeholder="🔍 Search number or message..." class="text-xs max-w-xs" oninput="renderAdminInbox()" style="padding:6px 10px">
                <span id="adminInboxStatus" class="text-xs text-[#64748b]"></span>
            </div>
            <div id="adminInboxCard">
                <div class="text-center py-8 text-[#64748b] text-sm">Loading replies...</div>
            </div>
        </div>

        <!-- Admin reply modal -->
        <div class="modal-overlay" id="adminReplyModal">
            <div class="modal">
                <div class="flex items-center justify-between mb-3">
                    <h4 class="font-bold text-sm" id="adminReplyTitle">↩️ Reply</h4>
                    <button onclick="closeAdminReply()" class="text-[#64748b] hover:text-white" style="background:none;border:none;cursor:pointer;font-size:16px">✕</button>
                </div>
                <label class="text-xs text-[#64748b] block mb-1">📱 To</label>
                <input type="text" id="adminReplyTo" class="mb-3 font-mono text-xs" readonly>
                <label class="text-xs text-[#64748b] block mb-1">🏢 Business</label>
                <input type="text" id="adminReplyBiz" class="mb-3 text-xs" readonly>
                <label class="text-xs text-[#64748b] block mb-1">💬 Message</label>
                <textarea id="adminReplyBody" rows="3" class="mb-3" placeholder="Type your reply..."></textarea>
                <div class="flex items-center gap-2 justify-end">
                    <span id="adminReplyStatus" class="text-xs"></span>
                    <button onclick="sendAdminReply()" class="btn-primary text-sm"><i class="fas fa-paper-plane mr-1"></i> Send Reply</button>
                </div>
            </div>
        </div>

        <script>
        var adminInbox = [];
        function refreshAdminInbox() {
            fetch('/admin/sms-inbox').then(function(r){ return r.json(); }).then(function(d){
                adminInbox = d.messages || [];
                renderAdminInbox();
            }).catch(function(){
                document.getElementById('adminInboxCard').innerHTML = '<div class="text-center py-6 text-red-400 text-sm">Failed to load replies</div>';
            });
        }
        function renderAdminInbox() {
            var card = document.getElementById('adminInboxCard');
            var status = document.getElementById('adminInboxStatus');
            var q = (document.getElementById('adminInboxSearch').value || '').toLowerCase();
            var msgs = adminInbox;
            if (q) msgs = msgs.filter(function(m){ return (m.number + ' ' + m.body + ' ' + m.biz).toLowerCase().indexOf(q) !== -1; });
            if (!msgs.length) {
                card.innerHTML = '<div class="text-center py-8 text-[#64748b] text-sm">📭 No SMS yet. Send a bulk campaign and replies will appear here.</div>';
                if (status) status.textContent = '0 messages';
                return;
            }
            var html = '<div style="overflow-x:auto"><table class="w-full text-sm"><thead><tr><th>Dir</th><th>Number</th><th>Message</th><th>Business</th><th>Time</th><th></th></tr></thead><tbody>';
            msgs.forEach(function(m){
                var time = (m.time || '').replace('T', ' ').slice(0, 16);
                var badge = m.direction === 'IN'
                    ? '<span class="badge badge-active">IN</span>'
                    : '<span class="badge badge-inactive">OUT</span>';
                html += '<tr>' +
                    '<td>' + badge + '</td>' +
                    '<td class="font-mono text-xs">' + (m.number || '-') + '</td>' +
                    '<td class="max-w-sm" style="word-break:break-word">' + (m.body || '') + '</td>' +
                    '<td class="text-xs">' + (m.biz || '—') + '</td>' +
                    '<td class="text-xs text-[#64748b]">' + time + '</td>' +
                    '<td><button onclick="openAdminReply(\'' + m.number.replace(/'/g, "\\'") + '\',\'' + (m.biz || '').replace(/'/g, "\\'") + '\')" class="btn-primary text-xs" style="padding:4px 10px">↩️ Reply</button></td>' +
                    '</tr>';
            });
            html += '</tbody></table></div>';
            card.innerHTML = html;
            if (status) status.textContent = msgs.length + ' messages';
        }
        function openAdminReply(number, biz) {
            document.getElementById('adminReplyTo').value = number;
            document.getElementById('adminReplyBiz').value = biz || '';
            document.getElementById('adminReplyBody').value = '';
            document.getElementById('adminReplyStatus').textContent = '';
            document.getElementById('adminReplyModal').classList.add('show');
            document.getElementById('adminReplyBody').focus();
        }
        function closeAdminReply() {
            document.getElementById('adminReplyModal').classList.remove('show');
        }
        function sendAdminReply() {
            var to = document.getElementById('adminReplyTo').value.trim();
            var body = document.getElementById('adminReplyBody').value.trim();
            var status = document.getElementById('adminReplyStatus');
            if (!to || !body) { status.textContent = '⚠️ Number + message required'; status.style.color = '#fbbf24'; return; }
            status.textContent = '⏳ Sending...'; status.style.color = '#818cf8';
            var fd = new FormData();
            fd.append('to', to);
            fd.append('message', body);
            fetch('/admin/sms-reply', { method: 'POST', body: fd })
                .then(function(r){ return r.json(); })
                .then(function(d){
                    if (d.success) {
                        status.textContent = '✅ Sent!'; status.style.color = '#4ade80';
                        setTimeout(closeAdminReply, 700);
                        setTimeout(refreshAdminInbox, 1000);
                    } else {
                        status.textContent = '❌ ' + (d.error || 'Failed'); status.style.color = '#f87171';
                    }
                })
                .catch(function(){ status.textContent = '❌ Network error'; status.style.color = '#f87171'; });
        }
        // Auto-refresh reply center while on the SMS tab
        var adminInboxTimer = setInterval(function(){
            if (document.querySelector('a[href="?tab=sms"]') && document.querySelector('a[href="?tab=sms"]').classList.contains('active')) {
                refreshAdminInbox();
            }
        }, 20000);
        setTimeout(refreshAdminInbox, 500);
        </script>

        <!-- TAB: STRIPE -->
        {% elif tab == 'stripe' %}
        <h2 class="text-xl font-bold mb-6">💳 Stripe Payment Settings</h2>
        <div class="max-w-xl card mb-6">
            <h3 class="font-bold mb-3">API Keys</h3>
            <p class="text-xs text-[#64748b] mb-4">Configure Stripe to auto-bill clients monthly.</p>
            <form method="POST" action="/admin/update-stripe">
                <label class="flex items-center gap-2 mb-3">
                    <input type="checkbox" name="stripe_enabled" value="1" {% if stripe_config.enabled %}checked{% endif %} class="w-auto accent-[#6366f1]">
                    <span class="text-sm">Enable Stripe Payments</span>
                </label>
                <label class="text-xs text-[#64748b] block mb-1">Secret Key</label>
                <input type="password" name="secret_key" value="{{ stripe_config.secret_key or '' }}" placeholder="sk_live_..." class="mb-3 font-mono text-xs">
                <label class="text-xs text-[#64748b] block mb-1">Publishable Key</label>
                <input type="text" name="publishable_key" value="{{ stripe_config.publishable_key or '' }}" placeholder="pk_live_..." class="mb-3 font-mono text-xs">
                <label class="text-xs text-[#64748b] block mb-1">Webhook Secret</label>
                <input type="password" name="webhook_secret" value="{{ stripe_config.webhook_secret or '' }}" placeholder="whsec_..." class="mb-4 font-mono text-xs">
                <button type="submit" class="btn-primary text-sm"><i class="fas fa-save mr-1"></i> Save Stripe Config</button>
            </form>
        </div>
        <div class="max-w-xl card">
            <h3 class="font-bold mb-3">🔗 Webhook URL</h3>
            <p class="text-xs text-[#64748b] mb-2">Configure this URL in your Stripe dashboard → Webhooks:</p>
            <div class="bg-[#1a1a28] rounded-lg p-3 font-mono text-xs text-[#818cf8] break-all">
                {{ request.host_url }}stripe-webhook
            </div>
            <p class="text-xs text-[#5c5c70] mt-2">Events: <code>checkout.session.completed</code></p>
        </div>
        {% elif tab == 'analytics' %}
        <h2 class="text-xl font-bold mb-6">📊 Analytics & Console</h2>
        <div class="max-w-xl card mb-6">
            <h3 class="font-bold mb-3">Google Analytics & Search Console</h3>
            <p class="text-xs text-[#64748b] mb-4">Injects Google Analytics (GA4) + Search Console verification into diazites.online (landing page & client dashboard).</p>
            <form method="POST" action="/admin/update-ga-config">
                <label class="text-xs text-[#64748b] block mb-1">Google Analytics ID (GA4)</label>
                <input type="text" name="ga_id" value="{{ ga_config.ga_id or '' }}" placeholder="G-XXXXXXXXXX" class="mb-3 font-mono text-xs">
                <p class="text-[10px] text-[#5c5c70] mb-3">Get this from <a href="https://analytics.google.com" target="_blank" class="text-[#38bdf8]">Google Analytics</a> &rarr; Admin &rarr; Data Streams</p>
                <label class="text-xs text-[#64748b] block mb-1">Search Console Verification Key</label>
                <input type="text" name="sc_key" value="{{ ga_config.sc_key or '' }}" placeholder="Paste the google-site-verification content value" class="mb-3 font-mono text-xs">
                <p class="text-[10px] text-[#5c5c70] mb-3">Get this from <a href="https://search.google.com/search-console" target="_blank" class="text-[#38bdf8]">Search Console</a> &rarr; Settings &rarr; Ownership verification &rarr; HTML tag</p>
                <button type="submit" class="btn-primary text-sm"><i class="fas fa-save mr-1"></i> Save Analytics Config</button>
            </form>
        </div>
        {% elif tab == 'campaigns' %}
        <h2 class="text-xl font-bold mb-6">📞 Outbound Campaigns</h2>
        
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Start a campaign -->
            <div class="card">
                <h3 class="font-bold mb-3">🚀 Start Campaign</h3>
                <p class="text-xs text-[#64748b] mb-4">Select a business and add leads, then start the campaign.</p>
                <form method="POST" action="/admin/campaign/start" class="space-y-3">
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Business</label>
                        <select name="business_id" class="text-sm" required>
                            <option value="">— Select —</option>
                            {% for biz in businesses %}
                            <option value="{{ biz.id }}">{{ biz.name }} ({{ biz.plan or 'starter' }}{% if biz.vapi_phone_id %} 📞{% endif %})</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Phone Numbers (one per line) <span class="text-[#5c5c70]">— or leave empty to use existing leads</span></label>
                        <textarea name="leads" rows="5" class="font-mono text-xs" placeholder="+13051234567&#10;+19541234567&#10;+17861234567"></textarea>
                    </div>
                    <button type="submit" class="btn-primary text-sm" onclick="return confirm('Start campaign for selected business?')"><i class="fas fa-play mr-1"></i> Start Campaign</button>
                </form>
            </div>
            
            <!-- Running campaigns -->
            <div class="card">
                <h3 class="font-bold mb-3">🔄 Running Campaigns</h3>
                <div id="campaignsList" class="space-y-3">
                    {% set has_running = false %}
                    {% for biz in businesses %}
                    {% if biz.campaign_status == 'running' %}
                    {% set has_running = true %}
                    <div class="p-3 bg-[#1a1a28] rounded-lg border border-green-800">
                        <div class="flex items-center justify-between mb-2">
                            <div>
                                <span class="font-semibold text-sm">{{ biz.name }}</span>
                                <span class="text-xs text-green-400 ml-2"><span class="w-2 h-2 bg-green-400 rounded-full inline-block animate-pulse mr-1"></span>Running</span>
                            </div>
                            <form method="POST" action="/admin/campaign/stop/{{ biz.id }}" style="display:inline">
                                <button class="btn-danger text-xs py-1 px-2"><i class="fas fa-stop mr-1"></i> Stop</button>
                            </form>
                        </div>
                        <div class="grid grid-cols-3 gap-2 text-xs text-[#94a3b8]">
                            <div>Calls: <span class="text-white font-semibold">{{ biz.calls_made or 0 }}</span></div>
                            <div>Appts: <span class="text-green-400 font-semibold">{{ biz.appointments_booked or 0 }}</span></div>
                            <div>Leads: <span class="text-white font-semibold">{{ biz.leads_count or biz.leads_imported or 0 }}</span></div>
                        </div>
                    </div>
                    {% endif %}
                    {% endfor %}
                    {% if not has_running %}
                    <p class="text-[#64748b] text-sm">No campaigns running.</p>
                    {% endif %}
                </div>
            </div>
        </div>

        <!-- Search & Add Leads -->
        <div class="card mt-6">
            <h3 class="font-bold mb-3">🔍 Search & Add Leads</h3>
            <p class="text-xs text-[#64748b] mb-3">Search your existing leads database, or search on <strong>Google Maps</strong> / <strong>Yelp</strong> in your browser and paste the numbers below.</p>
            <div class="flex gap-3 mb-3">
                <select id="leadSearchBizId" class="text-sm flex-1">
                    <option value="">— Target Business —</option>
                    {% for biz in businesses %}
                    <option value="{{ biz.id }}">{{ biz.name }}</option>
                    {% endfor %}
                </select>
                <input type="text" id="leadSearchQuery" class="text-sm flex-[2]" placeholder="e.g. plumbers in Miami FL" onkeydown="if(event.key==='Enter')searchBusinessLeads()">
                <button id="leadSearchBtn" onclick="searchBusinessLeads()" class="btn-primary text-sm whitespace-nowrap"><i class="fas fa-search mr-1"></i> Search</button>
            </div>
            <div id="leadSearchResults" class="min-h-[40px]">
                <p class="text-[#5c5c70] text-xs">Searches your database. To find new leads, <strong>search Google Maps or Yelp</strong> in your browser, then paste numbers below:</p>
                <div class="mt-2">
                    <textarea id="manualLeadsInput" rows="3" class="text-xs font-mono" placeholder="+13051234567&#10;John: +19541234567&#10;John,Acme Plumbing: +17861234567"></textarea>
                    <button onclick="addManualLeads()" class="btn-primary text-xs mt-2"><i class="fas fa-plus mr-1"></i> Add to Selected Business</button>
                    <span id="manualAddStatus" class="text-xs ml-2"></span>
                </div>
            </div>
        </div>

        <!-- All campaign statuses -->
        <div class="card mt-6">
            <h3 class="font-bold mb-3">📋 All Campaign Status</h3>
            <div class="overflow-x-auto">
            <table>
                <tr><th>Business</th><th>Status</th><th>Calls</th><th>Appts</th><th>Cost</th><th>Actions</th></tr>
                {% for biz in businesses %}
                {% if biz.campaign_status %}
                <tr>
                    <td class="font-semibold text-[#e2e8f0]">{{ biz.name }}</td>
                    <td>
                        {% if biz.campaign_status == 'running' %}
                        <span class="badge badge-active">▶ Running</span>
                        {% elif biz.campaign_status == 'stopped' %}
                        <span class="badge badge-inactive">⏹ Stopped</span>
                        {% else %}
                        <span class="badge badge-inactive">💤 {{ biz.campaign_status|title }}</span>
                        {% endif %}
                    </td>
                    <td>{{ biz.calls_made or 0 }}</td>
                    <td class="text-green-400">{{ biz.appointments_booked or 0 }}</td>
                    <td class="text-[#f472b6]">${{ "%.2f"|format(biz.total_cost or 0) }}</td>
                    <td class="flex gap-2">
                        {% if biz.campaign_status == 'running' %}
                        <form method="POST" action="/admin/campaign/stop/{{ biz.id }}" style="display:inline">
                            <button class="btn-danger text-xs py-1 px-2"><i class="fas fa-stop mr-1"></i> Stop</button>
                        </form>
                        {% else %}
                        <form method="POST" action="/admin/campaign/start/{{ biz.id }}" style="display:inline">
                            <button class="btn-primary text-xs py-1 px-2"><i class="fas fa-play mr-1"></i> Start</button>
                        </form>
                        {% endif %}
                        <a href="/admin/campaign/leads/{{ biz.id }}" class="btn-secondary text-xs py-1 px-2" onclick="return loadLeadsModal('{{ biz.id }}','{{ biz.name }}')"><i class="fas fa-users mr-1"></i> Leads</a>
                    </td>
                </tr>
                {% endif %}
                {% endfor %}
            </table>
            </div>
        </div>

        <!-- Add Leads Modal -->
        <div id="leadsModal" class="modal-overlay" onclick="if(event.target===this)this.classList.remove('show')">
            <div class="modal">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="font-bold">📱 Add Leads — <span id="leadsBizName"></span></h3>
                    <button onclick="document.getElementById('leadsModal').classList.remove('show')" class="text-[#5c5c70] hover:text-white text-lg">&times;</button>
                </div>
                <form id="leadsForm" method="POST" class="space-y-3">
                    <input type="hidden" name="business_id" id="leadsBizId">
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Phone Numbers (one per line)</label>
                        <textarea name="leads" rows="8" class="font-mono text-xs" placeholder="+13051234567&#10;Name: +19541234567&#10;Name, Business: +17861234567"></textarea>
                    </div>
                    <div class="flex gap-2">
                        <button type="submit" class="btn-primary text-sm"><i class="fas fa-plus mr-1"></i> Add Leads</button>
                        <button type="button" onclick="document.getElementById('leadsModal').classList.remove('show')" class="btn-secondary text-sm">Cancel</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
        function loadLeadsModal(bizId, bizName) {
            document.getElementById('leadsBizName').textContent = bizName;
            document.getElementById('leadsBizId').value = bizId;
            document.getElementById('leadsForm').action = '/admin/campaign/add-leads/' + bizId;
            document.getElementById('leadsModal').classList.add('show');
            return false;
        }
        
        // ── Search & Add Leads ──
        function searchBusinessLeads() {
            const query = document.getElementById('leadSearchQuery').value.trim();
            const bizId = document.getElementById('leadSearchBizId').value;
            if (!query) { alert('Enter a search query'); return; }
            if (!bizId) { alert('Select a target business'); return; }
            
            const btn = document.getElementById('leadSearchBtn');
            const results = document.getElementById('leadSearchResults');
            btn.disabled = true; btn.innerHTML = '<i class=\"fas fa-spinner fa-spin mr-1\"></i> Searching...';
            results.innerHTML = '';
            
            fetch('/admin/api/search-leads?q=' + encodeURIComponent(query))
                .then(function(r) { return r.json(); })
                .then(function(d) {
                    btn.disabled = false; btn.innerHTML = '<i class=\"fas fa-search mr-1\"></i> Search';
                    if (!d.results || d.results.length === 0) {
                        results.innerHTML = '<p class="text-[#64748b] text-sm">' + (d.note || 'No businesses found.') + '</p>';
                        return;
                    }
                    var html = '<div class=\"space-y-2 max-h-80 overflow-y-auto\">';
                    d.results.forEach(function(r, i) {
                        var phone = r.phone || '';
                        var name = r.name || 'Unknown';
                        var addr = r.address || '';
                        html += '<div class=\"flex items-center justify-between p-2 bg-[#1a1a28] rounded-lg text-xs\">' +
                            '<div class=\"flex-1 min-w-0\">' +
                            '<div class=\"font-semibold text-[#e2e8f0] truncate\">' + name + '</div>' +
                            '<div class=\"text-[#64748b] truncate\">' + (phone ? phone + ' &middot; ' : '') + addr + '</div>' +
                            '</div>' +
                            '<button onclick=\"addSearchLead(\\'' + bizId + '\\', \\'' + phone.replace(/'/g, '') + '\\', \\'' + name.replace(/'/g, '') + '\\')\" class=\"btn-primary text-xs py-1 px-2 ml-2\" ' + (phone ? '' : 'disabled') + '>' + (phone ? 'Add' : 'No phone') + '</button>' +
                            '</div>';
                    });
                    html += '</div>';
                    results.innerHTML = html;
                })
                .catch(function(err) {
                    btn.disabled = false; btn.innerHTML = '<i class=\"fas fa-search mr-1\"></i> Search';
                    results.innerHTML = '<p class=\"text-red-400 text-xs\">Error: ' + err.message + '</p>';
                });
        }
        
        function addSearchLead(bizId, phone, name) {
            if (!phone) return;
            var form = new FormData();
            form.append('business_id', bizId);
            form.append('leads', name + ': ' + phone);
            form.append('redirect', 'false');
            
            fetch('/admin/campaign/add-leads/' + bizId, { method: 'POST', body: form })
                .then(function(r) { return r.json(); })
                .then(function(d) {
                    if (d.success) {
                        var el = event.target;
                        el.textContent = '✅ Added';
                        el.classList.remove('btn-primary');
                        el.classList.add('btn-success');
                        el.disabled = true;
                    } else {
                        alert('Error: ' + (d.message || 'Failed to add'));
                    }
                })
                .catch(function(err) { alert('Error: ' + err.message); });
        }
        
        function addManualLeads() {
            var input = document.getElementById('manualLeadsInput');
            var bizId = document.getElementById('leadSearchBizId').value;
            var status = document.getElementById('manualAddStatus');
            var text = input.value.trim();
            
            if (!text) { alert('Paste some phone numbers first.'); return; }
            if (!bizId) { alert('Select a target business first.'); return; }
            
            status.textContent = '⏳ Adding...';
            var form = new FormData();
            form.append('business_id', bizId);
            form.append('leads', text);
            form.append('redirect', 'false');
            
            fetch('/admin/campaign/add-leads/' + bizId, { method: 'POST', body: form })
                .then(function(r) { return r.json(); })
                .then(function(d) {
                    if (d.success) {
                        status.textContent = '✅ ' + d.message || 'Added!';
                        input.value = '';
                    } else {
                        status.textContent = '❌ ' + (d.message || 'Failed');
                    }
                })
                .catch(function(err) {
                    status.textContent = '❌ Error: ' + err.message;
                });
        }
        </script>
        {% elif tab == 'agent-tars' %}
        <h2 class="text-xl font-bold mb-6">🤖 Agent TARS</h2>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="card">
                <h3 class="font-bold mb-3">🔧 AI Agent Console</h3>
                <p class="text-xs text-[#64748b] mb-4">Agent TARS is a multimodal AI agent that can control browsers, check sites, and automate tasks. Run headless commands here.</p>
                <form method="POST" action="/admin/agent-tars-run" class="space-y-3">
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Task for TARS</label>
                        <textarea name="task" rows="4" class="font-mono text-xs" placeholder="e.g. Go to diazites.online/manage/admin?tab=businesses, list the businesses and their call stats...">{{ last_task or '' }}</textarea>
                    </div>
                    <div class="flex gap-3">
                        <button type="submit" class="btn-primary text-sm"><i class="fas fa-play mr-1"></i> Run Task</button>
                        <a href="/admin/agent-tars-status" class="btn-secondary text-sm"><i class="fas fa-server mr-1"></i> Server Status</a>
                    </div>
                </form>
                {% if tars_result %}
                <hr class="border-[#1a1a28] my-4">
                <h4 class="font-bold text-sm mb-2">📋 Result</h4>
                <div class="bg-[#0a0a12] border border-[#1a1a28] rounded-lg p-3 font-mono text-xs text-[#cbd5e1] whitespace-pre-wrap max-h-96 overflow-y-auto">{{ tars_result }}</div>
                {% elif tars_status and tars_status.status == 'processing' %}
                <hr class="border-[#1a1a28] my-4">
                <div class="flex items-center gap-3 text-sm text-yellow-400">
                    <span class="w-3 h-3 rounded-full bg-yellow-400 animate-pulse"></span>
                    ⏳ TARS is processing your task... (started {{ tars_status.time }})
                </div>
                <p class="text-xs text-[#64748b] mt-2">Auto-refreshing...</p>
                <script>setTimeout(function(){ location.reload(); }, 5000);</script>
                {% endif %}
            </div>
            <div class="card">
                <h3 class="font-bold mb-3">⚡ Quick Tasks</h3>
                <div class="space-y-2">
                    <form method="POST" action="/admin/agent-tars-run">
                        <input type="hidden" name="task" value="Go to diazites.online/manage/admin?tab=businesses. List all businesses, their names, how many leads each has, and campaign status. Report in a clean summary.">
                        <button class="w-full text-left p-2 rounded-lg bg-[#1a1a28] hover:bg-[#252533] text-xs transition"><i class="fas fa-list mr-2 text-[#818cf8]"></i> Check All Business Status</button>
                    </form>
                    <form method="POST" action="/admin/agent-tars-run">
                        <input type="hidden" name="task" value="Go to diazites.online/?tab=overview (business dashboard). Read the current campaign status, recent activity, and setup status. Is everything working properly? Report any issues.">
                        <button class="w-full text-left p-2 rounded-lg bg-[#1a1a28] hover:bg-[#252533] text-xs transition"><i class="fas fa-activity mr-2 text-[#4ade80]"></i> Monitor Active Campaign</button>
                    </form>
                    <form method="POST" action="/admin/agent-tars-run">
                        <input type="hidden" name="task" value="Go to diazites.online/manage/admin?tab=businesses. Check which businesses have vapi_assistant_id set and which have vapi_phone_id. List any that are missing either one.">
                        <button class="w-full text-left p-2 rounded-lg bg-[#1a1a28] hover:bg-[#252533] text-xs transition"><i class="fas fa-exclamation-triangle mr-2 text-[#fbbf24]"></i> Find Missing Setup</button>
                    </form>
                    <form method="POST" action="/admin/agent-tars-run">
                        <input type="hidden" name="task" value="Go to the VAPI dashboard at https://dashboard.vapi.ai. Check total used minutes and any billing alerts.">
                        <button class="w-full text-left p-2 rounded-lg bg-[#1a1a28] hover:bg-[#252533] text-xs transition"><i class="fas fa-chart-line mr-2 text-[#f472b6]"></i> VAPI Usage Report</button>
                    </form>
                    <form method="POST" action="/admin/agent-tars-run">
                        <input type="hidden" name="task" value="Summarize the current state of the Diazites system: check diazites.online for signup page, diazites.online/manage/admin for admin panel. Report if both are accessible.">
                        <button class="w-full text-left p-2 rounded-lg bg-[#1a1a28] hover:bg-[#252533] text-xs transition"><i class="fas fa-heartbeat mr-2 text-[#60a5fa]"></i> System Health Check</button>
                    </form>
                </div>
                <hr class="border-[#1a1a28] my-4">
                <h3 class="font-bold mb-2">💡 What TARS Can Do</h3>
                <ul class="text-xs space-y-1 text-[#94a3b8]">
                    <li>✅ Browse any website and report back visually</li>
                    <li>✅ Fill forms, click buttons, navigate pages</li>
                    <li>✅ Check your admin panel remotely</li>
                    <li>✅ Monitor campaign health automatically</li>
                    <li>✅ Cross-reference data across multiple tabs</li>
                    <li>✅ Export findings as reports</li>
                </ul>
            </div>
        </div>
        {% elif tab == 'agent-api' %}
        <h2 class="text-xl font-bold mb-6">🔑 Agent API — Connect AI Agents</h2>
        <p class="text-sm text-[#64748b] mb-6">Generate API keys so AI agents can connect to the Diazites system, manage accounts, run campaigns, and generate reports programmatically.</p>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <!-- Generate Key -->
            <div class="card">
                <h3 class="font-bold mb-3">✨ Generate New API Key</h3>
                <p class="text-xs text-[#64748b] mb-4">Create a key for an AI agent with specific permissions.</p>
                <form id="apiKeyForm" class="space-y-3" onsubmit="return false;">
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Key Name *</label>
                        <input type="text" id="keyName" placeholder="e.g. Auto-Agent TARS" required>
                    </div>
                    <div>
                        <label class="text-xs text-[#64748b] block mb-1">Description</label>
                        <input type="text" id="keyDesc" placeholder="For automated campaign management">
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="text-xs text-[#64748b] block mb-1">Permissions</label>
                            <select id="keyPerms" class="text-xs">
                                <option value="read">Read Only</option>
                                <option value="read,write" selected>Read + Write</option>
                                <option value="read,write,admin">Full Admin</option>
                            </select>
                        </div>
                        <div>
                            <label class="text-xs text-[#64748b] block mb-1">Expires In</label>
                            <select id="keyExpiry" class="text-xs">
                                <option value="30">30 days</option>
                                <option value="90">90 days</option>
                                <option value="365" selected>1 year</option>
                                <option value="0">Never</option>
                            </select>
                        </div>
                    </div>
                    <button type="button" onclick="generateApiKey()" class="btn-primary text-sm w-full"><i class="fas fa-key mr-1"></i> Generate Key</button>
                </form>
                <!-- Error display -->
                <div id="generateKeyError" class="mt-3 hidden">
                    <div class="bg-red-900/30 border border-red-700/40 rounded-lg p-3 text-sm text-red-300">
                        <span id="generateKeyErrorText"></span>
                    </div>
                </div>
                <!-- Generated key display -->
                <div id="newKeyResult" class="mt-4 hidden">
                    <div class="bg-[#0a0a12] border border-[#22c55e]/30 rounded-lg p-4">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-green-400">✅ Key generated!</span>
                        </div>
                        <div class="bg-[#1a1a28] rounded-lg p-3 font-mono text-xs text-[#fbbf24] break-all select-all" id="newKeyValue">loading...</div>
                        <p class="text-xs text-red-400 mt-2">⚠️ Copy this key now — it won't be shown again!</p>
                        <button onclick="copyKey()" class="btn-secondary text-xs mt-2"><i class="fas fa-copy mr-1"></i> Copy to Clipboard</button>
                    </div>
                </div>
            </div>

            <!-- Active Keys -->
            <div class="card">
                <h3 class="font-bold mb-3">🔐 Active API Keys</h3>
                <div id="apiKeysList">
                    <p class="text-[#64748b] text-sm"><i class="fas fa-spinner fa-spin mr-2"></i>Loading keys...</p>
                </div>
            </div>
        </div>

        <!-- API Documentation -->
        <div class="card mb-6">
            <h3 class="font-bold mb-3">📖 API Documentation</h3>
            <p class="text-xs text-[#64748b] mb-4">Base URL: <code class="bg-[#1a1a28] px-2 py-0.5 rounded text-[#818cf8]">https://diazites.online/api/v1</code></p>
            <p class="text-xs text-[#64748b] mb-4">Authenticate with: <code class="bg-[#1a1a28] px-2 py-0.5 rounded text-[#fbbf24]">Authorization: Bearer &lt;your_api_key&gt;</code></p>
            
            <div class="overflow-x-auto">
                <table>
                    <tr><th class="w-20">Method</th><th>Endpoint</th><th>Description</th></tr>
                    <tr><td><span class="badge badge-active text-xs">GET</span></td><td class="font-mono text-xs">/api/v1/health</td><td>Health check (no auth)</td></tr>
                    <tr><td><span class="badge badge-active text-xs">GET</span></td><td class="font-mono text-xs">/api/v1/businesses</td><td>List all businesses</td></tr>
                    <tr><td><span class="text-xs text-yellow-400">POST</span></td><td class="font-mono text-xs">/api/v1/businesses</td><td>Create a business</td></tr>
                    <tr><td><span class="badge badge-active text-xs">GET</span></td><td class="font-mono text-xs">/api/v1/businesses/&lt;id&gt;</td><td>Get business details</td></tr>
                    <tr><td><span class="text-xs text-blue-400">PUT</span></td><td class="font-mono text-xs">/api/v1/businesses/&lt;id&gt;</td><td>Update a business</td></tr>
                    <tr><td><span class="text-xs text-red-400">DEL</span></td><td class="font-mono text-xs">/api/v1/businesses/&lt;id&gt;</td><td>Delete business (admin only)</td></tr>
                    <tr><td><span class="badge badge-active text-xs">GET</span></td><td class="font-mono text-xs">/api/v1/leads?business_id=X</td><td>List leads (filterable)</td></tr>
                    <tr><td><span class="text-xs text-yellow-400">POST</span></td><td class="font-mono text-xs">/api/v1/leads</td><td>Add leads to a business</td></tr>
                    <tr><td><span class="badge badge-active text-xs">GET</span></td><td class="font-mono text-xs">/api/v1/reports/overview</td><td>System overview report</td></tr>
                    <tr><td><span class="badge badge-active text-xs">GET</span></td><td class="font-mono text-xs">/api/v1/reports/billing</td><td>Billing report (per-client)</td></tr>
                    <tr><td><span class="badge badge-active text-xs">GET</span></td><td class="font-mono text-xs">/api/v1/reports/calls</td><td>Call log report</td></tr>
                    <tr><td><span class="text-xs text-yellow-400">POST</span></td><td class="font-mono text-xs">/api/v1/campaigns/&lt;bid&gt;/start</td><td>Start a campaign</td></tr>
                    <tr><td><span class="text-xs text-yellow-400">POST</span></td><td class="font-mono text-xs">/api/v1/campaigns/&lt;bid&gt;/stop</td><td>Stop a campaign</td></tr>
                    <tr><td><span class="badge badge-active text-xs">GET</span></td><td class="font-mono text-xs">/api/v1/campaigns/status</td><td>All campaign statuses</td></tr>
                    <tr><td><span class="badge badge-active text-xs">GET</span></td><td class="font-mono text-xs">/api/v1/settings</td><td>System settings (industries, tiers)</td></tr>
                    <tr><td><span class="badge badge-active text-xs">GET</span></td><td class="font-mono text-xs">/api/v1/export/businesses</td><td>Export businesses as CSV</td></tr>
                </table>
            </div>
        </div>

        <!-- API Test Console -->
        <div class="card mb-6">
            <h3 class="font-bold mb-3">🧪 API Test Console</h3>
            <p class="text-xs text-[#64748b] mb-4">Paste an API key and test endpoints directly.</p>
            <form id="apiTestForm" class="space-y-3" onsubmit="return testApiEndpoint(event)">
                <div class="grid grid-cols-3 gap-3">
                    <select id="testMethod" class="text-xs">
                        <option value="GET">GET</option>
                        <option value="POST">POST</option>
                        <option value="PUT">PUT</option>
                        <option value="DELETE">DELETE</option>
                    </select>
                    <input type="text" id="testEndpoint" class="text-xs font-mono col-span-2" placeholder="/api/v1/health" value="/api/v1/health">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <input type="text" id="testKey" class="text-xs font-mono" placeholder="API Key (dz_...)">
                    <input type="text" id="testBody" class="text-xs font-mono" placeholder="JSON body (for POST/PUT)">
                </div>
                <button type="submit" class="btn-primary text-sm"><i class="fas fa-play mr-1"></i> Send Request</button>
            </form>
            <div id="testResult" class="mt-4 hidden">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-bold">Response</span>
                    <span id="testStatus" class="text-xs px-2 py-0.5 rounded"></span>
                </div>
                <pre id="testResponse" class="bg-[#0a0a12] border border-[#1a1a28] rounded-lg p-3 text-xs font-mono text-[#cbd5e1] max-h-64 overflow-y-auto whitespace-pre-wrap"></pre>
            </div>
        </div>

        <div class="card">
            <h3 class="font-bold mb-3">🤖 Example: Auto-Agent Script</h3>
            <p class="text-xs text-[#64748b] mb-3">Use this curl command to connect any AI agent to the Diazites API:</p>
            <div class="bg-[#0a0a12] border border-[#1a1a28] rounded-lg p-4 font-mono text-xs text-[#cbd5e1] whitespace-pre-wrap">
# 1. Check system health
curl -s https://diazites.online/api/v1/health | jq .

# 2. List all businesses
curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  https://diazites.online/api/v1/businesses | jq .

# 3. Get overview report
curl -s -H "Authorization: Bearer YOUR_API_KEY" \
  https://diazites.online/api/v1/reports/overview | jq .

# 4. Create a new business
curl -s -X POST -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Joe Plumbing","industry":"plumber","plan":"pro","email":"joe@example.com"}' \
  https://diazites.online/api/v1/businesses | jq .

# 5. Add leads
curl -s -X POST -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"business_id":"BUSINESS_ID","leads":["+13055550100","+17865550101"]}' \
  https://diazites.online/api/v1/leads | jq .

# 6. Start campaign
curl -s -X POST -H "Authorization: Bearer YOUR_API_KEY" \
  https://diazites.online/api/v1/campaigns/BUSINESS_ID/start | jq .
            </div>
        </div>

        <script>
        // ── Load API Keys ──
        function loadApiKeys() {
            fetch('/api/v1/auth/keys', {credentials: 'same-origin'})
            .then(function(r) { 
                if (!r.ok) throw new Error('Auth failed — ensure you are logged in as admin');
                return r.json(); 
            })
            .then(function(d) {
                var html = '';
                if (!d.keys || d.keys.length === 0) {
                    html = '<p class="text-[#64748b] text-sm">No API keys yet. Generate one above.</p>';
                } else {
                    html = '<div class="space-y-2">';
                    d.keys.forEach(function(k) {
                        var status = k.active ? '<span class="text-green-400">● Active</span>' : '<span class="text-red-400">● Revoked</span>';
                        var perms = (k.permissions || '').replace(/,/g, ' / ').toUpperCase();
                        var lastUsed = k.last_used_at ? k.last_used_at.slice(0, 10) : 'Never';
                        html += '<div class="bg-[#1a1a28] rounded-lg p-3 text-xs flex items-center justify-between">' +
                            '<div class="flex-1">' +
                            '<div class="font-semibold text-[#e2e8f0]">' + k.name + ' <span class="text-[#64748b] font-normal">' + status + '</span></div>' +
                            '<div class="text-[#64748b] mt-0.5">' + perms + ' · Last: ' + lastUsed + '</div>' +
                            '<div class="text-[#5c5c70] font-mono text-[10px]">' + k.id + '</div>' +
                            '</div>' +
                            (k.active ? 
                            '<div class="flex items-center gap-1">' +
                            '<button data-key-id="' + k.id + '" onclick="revokeKey(this.dataset.keyId)" class="text-red-400 hover:text-red-300 text-xs py-1 px-2 border border-red-800 rounded"><i class="fas fa-ban mr-1"></i>Revoke</button>' +
                            '<button data-key-id="' + k.id + '" onclick="deleteKeyPermanent(this.dataset.keyId)" class="text-red-400 hover:text-red-300 text-xs py-1 px-2 border border-red-800 rounded ml-1"><i class="fas fa-times mr-1"></i>Delete</button>' +
                            '</div>' :
                            '<button data-key-id="' + k.id + '" onclick="reactivateKey(this.dataset.keyId)" class="text-green-400 hover:text-green-300 text-xs py-1 px-2 border border-green-800 rounded"><i class="fas fa-undo mr-1"></i>Reactivate</button>'
                            ) +
                            '</div>';
                    });
                    html += '</div>';
                }
                document.getElementById('apiKeysList').innerHTML = html;
            })
            .catch(function(err) {
                document.getElementById('apiKeysList').innerHTML = '<p class="text-red-400 text-xs">❌ ' + err.message + '</p>';
            });
        }

        // ── Generate API Key ──
        function generateApiKey() {
            // Hide previous error and result
            document.getElementById('generateKeyError').classList.add('hidden');
            document.getElementById('newKeyResult').classList.add('hidden');
            var name = document.getElementById('keyName').value.trim();
            if (!name) {
                showGenerateError('Key name is required');
                return false;
            }
            var btn = document.querySelector('#apiKeyForm button');
            btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Generating...';

            fetch('/api/v1/auth/generate', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name: name,
                    description: document.getElementById('keyDesc').value.trim(),
                    permissions: document.getElementById('keyPerms').value,
                    expires_in_days: parseInt(document.getElementById('keyExpiry').value)
                })
            })
            .then(function(r) {
                if (!r.ok) {
                    return r.json().then(function(errData) {
                        throw new Error(errData.error || 'Request failed (HTTP ' + r.status + ')');
                    });
                }
                return r.json();
            })
            .then(function(d) {
                btn.disabled = false; btn.innerHTML = '<i class="fas fa-key mr-1"></i> Generate Key';
                if (d.success) {
                    document.getElementById('newKeyValue').textContent = d.api_key;
                    document.getElementById('newKeyResult').classList.remove('hidden');
                    document.getElementById('keyName').value = '';
                    document.getElementById('keyDesc').value = '';
                    loadApiKeys();
                } else {
                    showGenerateError(d.error || 'Failed to generate key');
                }
            })
            .catch(function(err) {
                btn.disabled = false; btn.innerHTML = '<i class="fas fa-key mr-1"></i> Generate Key';
                showGenerateError(err.message || 'Connection error — are you logged in?');
            });
            return false;
        }

        function showGenerateError(msg) {
            document.getElementById('generateKeyErrorText').textContent = '❌ ' + msg;
            document.getElementById('generateKeyError').classList.remove('hidden');
            // Auto-hide after 10s
            setTimeout(function() {
                document.getElementById('generateKeyError').classList.add('hidden');
            }, 10000);
        }

        // ── Revoke Key ──
        function revokeKey(keyId) {
            if (!confirm('Revoke this API key? Agents using it will lose access immediately.')) return;
            fetch('/api/v1/auth/keys/' + keyId, {method: 'DELETE', credentials: 'same-origin'})
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.success) loadApiKeys();
                else alert('Error: ' + (d.error || 'Failed to revoke'));
            })
            .catch(function(err) { alert('Error: ' + err.message); });
        }

        // ── Reactivate Key ──
        function reactivateKey(keyId) {
            if (!confirm('Reactivate this API key?')) return;
            fetch('/api/v1/auth/keys/' + keyId + '?reactivate=true', {method: 'POST', credentials: 'same-origin'})
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.success) loadApiKeys();
                else alert('Error: ' + (d.error || 'Failed to reactivate'));
            })
            .catch(function(err) { alert('Error: ' + err.message); });
        }

        // ── Permanent Delete Key ──
        function deleteKeyPermanent(keyId) {
            if (!confirm('⚠️ PERMANENTLY DELETE this API key? This cannot be undone!')) return;
            if (!confirm('Are you sure? Agents using this key will lose access.')) return;
            fetch('/api/v1/auth/keys/' + keyId + '/delete', {method: 'DELETE', credentials: 'same-origin'})
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.success) { alert('🗑️ Key permanently deleted.'); loadApiKeys(); }
                else alert('Error: ' + (d.error || 'Failed to delete'));
            })
            .catch(function(err) { alert('Error: ' + err.message); });
        }

        // ── Copy Key ──
        function copyKey() {
            var key = document.getElementById('newKeyValue');
            navigator.clipboard.writeText(key.textContent).then(function() {
                var btn = event.target;
                var orig = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check mr-1"></i> Copied!';
                setTimeout(function() { btn.innerHTML = orig; }, 2000);
            });
        }

        // ── Test Console ──
        function testApiEndpoint(e) {
            e.preventDefault();
            var method = document.getElementById('testMethod').value;
            var endpoint = document.getElementById('testEndpoint').value.trim();
            var key = document.getElementById('testKey').value.trim();
            var body = document.getElementById('testBody').value.trim();

            if (!endpoint.startsWith('/')) endpoint = '/' + endpoint;
            var url = window.location.origin + endpoint;
            var headers = {'Content-Type': 'application/json'};
            if (key) headers['Authorization'] = 'Bearer ' + key;

            var opts = {method: method, headers: headers};
            if ((method === 'POST' || method === 'PUT') && body) {
                try { JSON.parse(body); opts.body = body; }
                catch(e) { alert('Invalid JSON body'); return; }
            }

            document.getElementById('testResult').classList.remove('hidden');
            document.getElementById('testResponse').textContent = '⏳ Sending request...';
            document.getElementById('testStatus').textContent = '';

            fetch(url, opts)
                .then(function(r) {
                    document.getElementById('testStatus').textContent = r.status + ' ' + r.statusText;
                    document.getElementById('testStatus').className = 'text-xs px-2 py-0.5 rounded ' + (r.ok ? 'bg-green-800 text-green-300' : 'bg-red-800 text-red-300');
                    return r.text();
                })
                .then(function(text) {
                    try {
                        var formatted = JSON.stringify(JSON.parse(text), null, 2);
                        document.getElementById('testResponse').textContent = formatted;
                    } catch(e) {
                        document.getElementById('testResponse').textContent = text;
                    }
                })
                .catch(function(err) {
                    document.getElementById('testResponse').textContent = '❌ Error: ' + err.message;
                    document.getElementById('testStatus').textContent = 'Failed';
                    document.getElementById('testStatus').className = 'text-xs px-2 py-0.5 rounded bg-red-800 text-red-300';
                });
            return false;
        }

        // ── Init ──
        document.addEventListener('DOMContentLoaded', function() {
            loadApiKeys();
        });
        </script>
        {% elif tab == 'affiliates' %}
        <h2 class="text-xl font-bold mb-6">💸 Affiliates — Commission Tracking</h2>
        <p class="text-sm text-[#64748b] mb-6">Sales people earn a flat commission per business signup through their affiliate link. Mark signups as <b>paid</b> when you send the money.</p>
        <div class="card mb-6">
            <h3 class="font-bold mb-4">👥 Affiliates ({{ affiliates|length }})</h3>
            <table class="w-full text-sm">
                <tr class="text-left text-[#64748b]"><th>Name</th><th>Code</th><th>Email</th><th>Rate</th><th>Status</th><th>Created</th><th>Actions</th></tr>
                {% for a in affiliates %}
                <tr class="border-t border-[#1a1a2e]">
                    <td class="py-2">{{ a.name }}</td>
                    <td><code>{{ a.code }}</code></td>
                    <td>{{ a.email }}</td>
                    <td>
                        <form method="POST" action="/admin/affiliates/rate" class="flex items-center gap-1" style="display:inline-flex">
                            <input type="hidden" name="affiliate_id" value="{{ a.id }}">
                            <input type="number" name="rate" value="{{ a.commission_per_signup }}" min="0" step="5" style="width:70px;padding:4px 6px;font-size:12px" class="input">
                            <button class="btn-primary text-xs" style="padding:4px 10px">Set</button>
                        </form>
                    </td>
                    <td><span class="badge {{ 'badge-green' if a.status=='active' else 'badge-red' }}">{{ a.status }}</span></td>
                    <td class="text-xs text-[#64748b]">{{ (a.created_at or '')[:10] }}</td>
                    <td>
                        <form method="POST" action="/admin/affiliates/toggle" style="display:inline">
                            <input type="hidden" name="affiliate_id" value="{{ a.id }}">
                            <button class="btn-secondary text-xs" style="padding:4px 10px">{{ '⏸ Disable' if a.status=='active' else '▶ Enable' }}</button>
                        </form>
                        <form method="POST" action="/admin/affiliates/mark-all-paid" style="display:inline">
                            <input type="hidden" name="affiliate_id" value="{{ a.id }}">
                            <button class="btn-secondary text-xs" style="padding:4px 10px" title="Mark all pending commissions paid">✅ All Paid</button>
                        </form>
                        <form method="POST" action="/admin/affiliates/delete" style="display:inline" onsubmit="return confirm('Delete {{ a.name }} and ALL their events/payouts? This cannot be undone.')">
                            <input type="hidden" name="affiliate_id" value="{{ a.id }}">
                            <button class="btn-secondary text-xs" style="padding:4px 10px;color:#f87171" title="Delete affiliate + all data">🗑️ Delete</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>
        <div class="card mb-6">
            <h3 class="font-bold mb-4">💰 Payout Requests ({{ affiliate_payouts|length }})</h3>
            <table class="w-full text-sm">
                <tr class="text-left text-[#64748b]"><th>Affiliate</th><th>Amount</th><th>Status</th><th>Requested</th><th>Paid</th><th></th></tr>
                {% for p in affiliate_payouts %}
                <tr class="border-t border-[#1a1a2e]">
                    <td class="py-2">{{ p.affiliate_name or '—' }}</td>
                    <td><b>${{ '%.0f' % (p.amount or 0) }}</b></td>
                    <td><span class="badge {{ 'badge-green' if p.status=='paid' else 'badge-yellow' }}">{{ p.status }}</span></td>
                    <td class="text-xs text-[#64748b]">{{ (p.created_at or '')[:16] }}</td>
                    <td class="text-xs text-[#64748b]">{{ (p.paid_at or '—')[:16] }}</td>
                    <td>
                        {% if p.status=='pending' %}
                        <form method="POST" action="/admin/affiliates/payout-pay" style="display:inline">
                            <input type="hidden" name="payout_id" value="{{ p.id }}">
                            <button class="btn-primary text-xs" style="padding:4px 10px">💸 Settle ${{ '%.0f' % (p.amount or 0) }}</button>
                        </form>
                        {% endif %}
                        <form method="POST" action="/admin/affiliates/delete-payout" style="display:inline" onsubmit="return confirm('Delete this payout request?')">
                            <input type="hidden" name="payout_id" value="{{ p.id }}">
                            <button class="btn-secondary text-xs" style="padding:4px 10px;color:#f87171">🗑️</button>
                        </form>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="6" class="text-[#64748b] py-2">No payout requests yet.</td></tr>
                {% endfor %}
            </table>
        </div>
        <div class="card">
            <h3 class="font-bold mb-4">📊 Commission Events ({{ affiliate_events|length }})</h3>
            <table class="w-full text-sm">
                <tr class="text-left text-[#64748b]"><th>Affiliate</th><th>Type</th><th>Business</th><th>Commission</th><th>Status</th><th>Date</th><th></th></tr>
                {% for e in affiliate_events %}
                <tr class="border-t border-[#1a1a2e]">
                    <td class="py-2">{{ e.affiliate_name or '—' }}</td>
                    <td>{{ '🚀' if e.event_type=='signup' else '👆' }} {{ e.event_type }}</td>
                    <td>{{ e.business_name or '—' }}</td>
                    <td>${{ '%.0f' % (e.commission or 0) }}</td>
                    <td><span class="badge {{ 'badge-green' if e.status=='paid' else 'badge-yellow' }}">{{ e.status }}</span></td>
                    <td class="text-xs text-[#64748b]">{{ (e.created_at or '')[:16] }}</td>
                    <td>
                        {% if e.event_type=='signup' and e.status=='pending' %}
                        <form method="POST" action="/admin/affiliates/pay" style="display:inline">
                            <input type="hidden" name="event_id" value="{{ e.id }}">
                            <button class="btn-primary text-xs" style="padding:4px 10px">💰 Mark Paid</button>
                        </form>
                        {% endif %}
                        <form method="POST" action="/admin/affiliates/delete-event" style="display:inline" onsubmit="return confirm('Delete this event?')">
                            <input type="hidden" name="event_id" value="{{ e.id }}">
                            <button class="btn-secondary text-xs" style="padding:4px 10px;color:#f87171">🗑️</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% elif tab == 'calendar' %}
        <h2 class="text-xl font-bold mb-6">📅 All Appointments</h2>

        <!-- Calendar Sync info -->
        <div class="max-w-2xl card mb-6">
            <h3 class="font-bold mb-3">📅 Calendar Sync</h3>
            <p class="text-xs text-[#64748b] mb-3">When an appointment is booked via AI, clients can download an .ics calendar file.</p>
            <div class="bg-[#1a1a28] rounded-lg p-3 text-sm">
                <div class="flex items-center gap-2">
                    <span class="text-[#4ade80]">✅</span>
                    <span>ICS calendar files are auto-generated for every booked appointment</span>
                </div>
            </div>
            <p class="text-xs text-[#5c5c70] mt-3">No additional setup needed — works automatically.</p>
        </div>

        <!-- Stats -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <div class="stat-box"><div class="text-2xl font-bold text-[#818cf8]">{{ all_appointments|length }}</div><div class="text-xs text-[#64748b] mt-1">Total Appointments</div></div>
            <div class="stat-box"><div class="text-2xl font-bold text-[#4ade80]">{{ all_appointments|selectattr('status','equalto','booked')|list|length }}</div><div class="text-xs text-[#64748b] mt-1">Booked</div></div>
            <div class="stat-box"><div class="text-2xl font-bold text-[#fbbf24]">{{ all_appointments|selectattr('status','equalto','completed')|list|length }}</div><div class="text-xs text-[#64748b] mt-1">Completed</div></div>
            <div class="stat-box"><div class="text-2xl font-bold text-[#f472b6]">{{ all_appointments|selectattr('status','equalto','cancelled')|list|length }}</div><div class="text-xs text-[#64748b] mt-1">Cancelled</div></div>
        </div>

        <!-- Business filter -->
        <div class="flex gap-3 mb-4 items-center">
            <select id="calBizFilter" class="text-sm max-w-xs" onchange="filterCalendar()">
                <option value="">— All Businesses —</option>
                {% for biz in businesses %}
                <option value="{{ biz.id }}">{{ biz.name }}</option>
                {% endfor %}
            </select>
            <input type="text" id="calSearch" class="text-sm max-w-xs" placeholder="🔍 Search prospect name or phone..." oninput="filterCalendar()">
            <span class="text-xs text-[#64748b] ml-auto"><span id="calCount">{{ all_appointments|length }}</span> appointments</span>
        </div>

        <!-- Appointments table -->
        <div class="overflow-x-auto card">
            {% if all_appointments %}
            <table id="calTable">
                <thead>
                    <tr><th>Business</th><th>Prospect</th><th>Phone</th><th>Time</th><th>Status</th><th>Notes</th><th>Created</th></tr>
                </thead>
                <tbody>
                    {% for apt in all_appointments %}
                    <tr class="cal-row" data-biz="{{ apt.business_id }}" data-search="{{ (apt.prospect_name or apt.lead_name or '')|lower }} {{ (apt.phone or '') }}">
                        <td class="font-semibold text-sm">{{ apt.biz_name or apt.business_id[:12]+'..' }}</td>
                        <td>{{ apt.prospect_name or apt.lead_name or 'Prospect' }}</td>
                        <td class="font-mono text-xs">{{ apt.phone or '-' }}</td>
                        <td class="text-xs text-[#94a3b8]">{{ apt.appointment_time or '-' }}</td>
                        <td>
                            {% if apt.status == 'booked' %}<span class="badge badge-active">📅 Booked</span>
                            {% elif apt.status == 'completed' %}<span class="badge badge-success">✅ Done</span>
                            {% elif apt.status == 'cancelled' %}<span class="badge badge-error">❌ Cancelled</span>
                            {% else %}<span class="badge badge-inactive">{{ apt.status }}</span>{% endif %}
                        </td>
                        <td class="text-xs text-[#64748b] max-w-[200px] truncate" title="{{ apt.notes or '' }}">{{ apt.notes[:60] or '-' }}</td>
                        <td class="text-xs text-[#64748b]">{{ (apt.created_at or '')[:10] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="text-center py-12">
                <div class="text-4xl mb-3">📅</div>
                <p class="text-[#64748b] font-medium">No appointments yet</p>
                <p class="text-xs text-[#5c5c70] mt-1">Appointments will appear here when AI agents book them.</p>
            </div>
            {% endif %}
        </div>

        <script>
        function filterCalendar() {
            var biz = document.getElementById('calBizFilter').value.toLowerCase();
            var q = document.getElementById('calSearch').value.toLowerCase().trim();
            var rows = document.querySelectorAll('.cal-row');
            var count = 0;
            rows.forEach(function(r) {
                var show = true;
                if (biz && r.getAttribute('data-biz') !== biz) show = false;
                if (q && (r.getAttribute('data-search') || '').indexOf(q) === -1) show = false;
                r.style.display = show ? '' : 'none';
                if (show) count++;
            });
            document.getElementById('calCount').textContent = count;
        }
        </script>
        {% elif tab == 'mrr' %}
        <h2 class="text-xl font-bold mb-6">💰 MRR Dashboard</h2>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div class="card"><div class="text-xs text-[#64748b]">Monthly Recurring Revenue</div><div class="text-2xl font-bold text-green-400">${{ mrr.mrr or 0 }}</div></div>
            <div class="card"><div class="text-xs text-[#64748b]">Active Subscribers</div><div class="text-2xl font-bold">{{ mrr.active }}</div></div>
            <div class="card"><div class="text-xs text-[#64748b]">Churn (30d)</div><div class="text-2xl font-bold {% if mrr.churn > 0.05 %}text-red-400{% else %}text-white{% endif %}">{{ "%.1f"|format(mrr.churn * 100) }}%</div></div>
            <div class="card"><div class="text-xs text-[#64748b]">Failed Payments</div><div class="text-2xl font-bold text-red-400">{{ mrr.dunning|length }}</div></div>
        </div>
        <div class="card mb-6">
            <h3 class="font-bold mb-3">🔴 Dunning List (failed/incomplete payments)</h3>
            {% if mrr.dunning %}
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">Customer</th><th>Amount</th><th>Status</th><th>Due</th></tr></thead><tbody>
            {% for d in mrr.dunning %}<tr class="border-b border-[#1a1a28]"><td class="py-2">{{ d.customer }}</td><td>${{ d.amount }}</td><td>{{ d.status }}</td><td>{{ d.due }}</td></tr>{% endfor %}
            </tbody></table>
            {% else %}<p class="text-xs text-[#5c5c70]">No failed payments 🎉</p>{% endif %}
        </div>
        <div class="card">
            <h3 class="font-bold mb-3">📦 Revenue by Plan</h3>
            {% if mrr.by_plan %}
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">Plan</th><th>Subscribers</th><th>MRR</th></tr></thead><tbody>
            {% for p in mrr.by_plan %}<tr class="border-b border-[#1a1a28]"><td class="py-2">{{ p.plan }}</td><td>{{ p.count }}</td><td>${{ p.mrr }}</td></tr>{% endfor %}
            </tbody></table>
            {% else %}<p class="text-xs text-[#5c5c70]">No subscription data (is Stripe configured?)</p>{% endif %}
        </div>
        {% elif tab == 'coupons' %}
        <h2 class="text-xl font-bold mb-6">🎟️ Coupons & Promotions</h2>
        <div class="card mb-6 max-w-xl">
            <h3 class="font-bold mb-3">Create Coupon</h3>
            <form method="POST" action="/admin/coupon-create" class="space-y-3">
                <label class="text-xs text-[#64748b] block mb-1">Coupon Name</label>
                <input type="text" name="name" placeholder="Launch Week 50%" class="text-xs">
                <div class="grid grid-cols-3 gap-3">
                    <div><label class="text-xs text-[#64748b] block mb-1">Percent Off</label><input type="number" name="percent" value="50" min="1" max="100" class="text-xs"></div>
                    <div><label class="text-xs text-[#64748b] block mb-1">Months</label><input type="number" name="duration" value="1" min="1" class="text-xs"></div>
                    <div><label class="text-xs text-[#64748b] block mb-1">Code</label><input type="text" name="code" placeholder="LAUNCH50" class="text-xs font-mono"></div>
                </div>
                <button type="submit" class="btn-primary text-sm"><i class="fas fa-plus mr-1"></i> Create Coupon</button>
            </form>
        </div>
        <div class="card">
            <h3 class="font-bold mb-3">Active Promo Codes</h3>
            {% if coupons %}
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">Code</th><th>Discount</th><th>Redeemed</th><th>Max</th><th>Active</th></tr></thead><tbody>
            {% for c in coupons %}<tr class="border-b border-[#1a1a28]"><td class="py-2 font-mono">{{ c.code }}</td><td>{{ c.discount }}</td><td>{{ c.redeemed }}</td><td>{{ c.max or '∞' }}</td><td>{% if c.active %}<span class="text-green-400">✅</span>{% else %}<span class="text-red-400">❌</span>{% endif %}</td></tr>{% endfor %}
            </tbody></table>
            {% else %}<p class="text-xs text-[#5c5c70]">No promo codes yet</p>{% endif %}
        </div>
        {% elif tab == 'trials' %}
        <h2 class="text-xl font-bold mb-6">⏳ Trial Expiry Radar</h2>
        <div class="card">
            {% if trials %}
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">Business</th><th>Trial Ends</th><th>Days Left</th><th>Plan</th><th>Actions</th></tr></thead><tbody>
            {% for t in trials %}<tr class="border-b border-[#1a1a28]">
                <td class="py-2">{{ t.name }}</td><td>{{ t.trial_end }}</td>
                <td>{% if t.days_left < 0 %}<span class="text-red-400">expired</span>{% elif t.days_left <= 3 %}<span class="text-amber-400">{{ t.days_left }}d ⚠️</span>{% else %}{{ t.days_left }}d{% endif %}</td>
                <td>{{ t.plan }}</td>
                <td><form method="POST" action="/admin/trial-extend/{{ t.id }}" style="display:inline"><button class="btn-secondary text-xs py-1 px-2">+7 days</button></form> <form method="POST" action="/admin/trial-nudge/{{ t.id }}" style="display:inline"><button class="btn-primary text-xs py-1 px-2">📲 Nudge</button></form></td>
            </tr>{% endfor %}
            </tbody></table>
            {% else %}<p class="text-xs text-[#5c5c70]">No businesses on trial</p>{% endif %}
        </div>
        {% elif tab == 'usage' %}
        <h2 class="text-xl font-bold mb-6">📊 Usage vs Plan Limits</h2>
        <div class="card">
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">Business</th><th>Plan</th><th>Limit</th><th>Used (mo)</th><th>Usage</th><th>Status</th></tr></thead><tbody>
            {% for u in usage_rows %}<tr class="border-b border-[#1a1a28]">
                <td class="py-2">{{ u.name }}</td><td>{{ u.plan }}</td><td>{{ u.limit }} min</td><td>{{ u.used }} min</td>
                <td><div class="w-32 bg-[#1a1a28] rounded-full h-2"><div class="h-2 rounded-full {% if u.pct > 90 %}bg-red-500{% elif u.pct > 70 %}bg-amber-500{% else %}bg-green-500{% endif %}" style="width: {{ u.pct }}%"></div></div></td>
                <td>{% if u.pct >= 100 %}<span class="text-red-400 font-bold">OVER ⚠️</span>{% elif u.pct > 80 %}<span class="text-amber-400">near limit</span>{% else %}<span class="text-green-400">ok</span>{% endif %}</td>
            </tr>{% endfor %}
            </tbody></table>
        </div>
        {% elif tab == 'scoreboard' %}
        <h2 class="text-xl font-bold mb-6">🏆 Agent Performance Scoreboard</h2>
        <div class="card">
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">#</th><th>Business</th><th>Calls</th><th>Answered</th><th>Answer Rate</th><th>Bookings</th><th>Booking Rate</th></tr></thead><tbody>
            {% for s in score_rows %}<tr class="border-b border-[#1a1a28]">
                <td class="py-2">{{ loop.index }}</td><td class="font-semibold">{{ s.name }}</td><td>{{ s.calls }}</td><td>{{ s.answered }}</td><td>{{ s.answer_rate }}%</td><td>{{ s.bookings }}</td><td>{% if s.booking_rate %}<span class="{% if s.booking_rate >= 20 %}text-green-400{% elif s.booking_rate >= 10 %}text-amber-400{% else %}text-red-400{% endif %}">{{ s.booking_rate }}%</span>{% else %}—{% endif %}</td>
            </tr>{% endfor %}
            </tbody></table>
        </div>
        {% elif tab == 'transcripts' %}
        <h2 class="text-xl font-bold mb-6">📜 Transcript Review Center</h2>
        <div class="card mb-6 max-w-xl">
            <form method="GET" action="/admin" class="flex gap-2">
                <input type="hidden" name="tab" value="transcripts">
                <input type="text" name="q" value="{{ tx_query or '' }}" placeholder="Search transcripts (e.g. appointment, price, hello)..." class="text-xs flex-1">
                <button class="btn-primary text-xs">Search</button>
            </form>
        </div>
        <div class="card">
            {% if tx_rows %}
            {% for t in tx_rows %}
            <div class="border-b border-[#1a1a28] py-3">
                <div class="flex items-center justify-between mb-1">
                    <span class="font-semibold text-sm">{{ t.biz }}</span>
                    <span class="text-[#5c5c70] text-xs">{{ t.created_at }} · {{ t.status }} · {{ t.duration or 0 }}s</span>
                </div>
                <details><summary class="text-xs text-[#818cf8] cursor-pointer">View transcript</summary>
                <pre class="mt-2 bg-[#12121a] rounded-lg p-3 text-xs text-[#cbd5e1] whitespace-pre-wrap">{{ t.transcript or '(no transcript)' }}</pre>
                </details>
                <form method="POST" action="/admin/transcript-flag/{{ t.id }}" class="mt-2"><button class="btn-secondary text-xs py-1 px-2 {% if t.flagged %}border-red-700 text-red-400{% endif %}">{% if t.flagged %}🏳️ Flagged{% else %}🚩 Flag</button>{% endif %}</form>
            </div>
            {% endfor %}
            {% else %}<p class="text-xs text-[#5c5c70]">No transcripts{% if tx_query %} matching "{{ tx_query }}"{% endif %}</p>{% endif %}
        </div>
        {% elif tab == 'health' %}
        <h2 class="text-xl font-bold mb-6">🩺 Setup Health Board</h2>
        <div class="card">
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">Business</th><th>Assistant</th><th>Phone</th><th>KB</th><th>Script</th><th>Webhook</th><th>Payment</th><th>Score</th></tr></thead><tbody>
            {% for h in health_rows %}<tr class="border-b border-[#1a1a28]">
                <td class="py-2 font-semibold">{{ h.name }}</td>
                <td>{% if h.assistant %}<span class="text-green-400">✅</span>{% else %}<span class="text-red-400">❌</span>{% endif %}</td>
                <td>{% if h.phone %}<span class="text-green-400">✅</span>{% else %}<span class="text-red-400">❌</span>{% endif %}</td>
                <td>{% if h.kb %}<span class="text-green-400">✅</span>{% else %}<span class="text-amber-400">⚠️</span>{% endif %}</td>
                <td>{% if h.script %}<span class="text-green-400">✅</span>{% else %}<span class="text-amber-400">⚠️</span>{% endif %}</td>
                <td>{% if h.webhook %}<span class="text-green-400">✅</span>{% else %}<span class="text-amber-400">⚠️</span>{% endif %}</td>
                <td>{% if h.payment %}<span class="text-green-400">✅</span>{% else %}<span class="text-red-400">❌</span>{% endif %}</td>
                <td><span class="{% if h.score >= 5 %}text-green-400{% elif h.score >= 3 %}text-amber-400{% else %}text-red-400{% endif %} font-bold">{{ h.score }}/7</span></td>
            </tr>{% endfor %}
            </tbody></table>
        </div>
        {% elif tab == 'broadcast' %}
        <h2 class="text-xl font-bold mb-6">📣 Broadcast Center</h2>
        <div class="card max-w-xl">
            <h3 class="font-bold mb-3">Send to all business owners</h3>
            <form method="POST" action="/admin/broadcast-send" class="space-y-3">
                <label class="flex items-center gap-2"><input type="checkbox" name="channel_email" value="1" checked class="w-auto"> Email (AgentMail)</label>
                <label class="flex items-center gap-2"><input type="checkbox" name="channel_sms" value="1" checked class="w-auto"> SMS (sms-gate)</label>
                <input type="text" name="subject" placeholder="Subject (email only)" class="text-xs">
                <textarea name="message" rows="4" placeholder="Your message to all {{ health_rows|length }} business owners..." class="text-xs"></textarea>
                <button type="submit" class="btn-primary text-sm" onclick="return confirm('Send broadcast to ALL businesses?')"><i class="fas fa-paper-plane mr-1"></i> Send Broadcast</button>
            </form>
        </div>
        {% elif tab == 'backup' %}
        <h2 class="text-xl font-bold mb-6">💾 Backup & Restore</h2>
        <div class="card mb-6 max-w-xl">
            <h3 class="font-bold mb-3">Create snapshot</h3>
            <p class="text-xs text-[#64748b] mb-3">Copies the live database to the backup folder (keeps last 10).</p>
            <form method="POST" action="/admin/backup-now"><button class="btn-primary text-sm"><i class="fas fa-download mr-1"></i> Backup Now</button></form>
        </div>
        <div class="card">
            <h3 class="font-bold mb-3">Snapshots</h3>
            {% if backup_files %}
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">File</th><th>Size</th><th>Download</th></tr></thead><tbody>
            {% for b in backup_files %}<tr class="border-b border-[#1a1a28]"><td class="py-2 font-mono">{{ b.name }}</td><td>{{ b.size }}</td><td><a href="/admin/backup-download/{{ b.name }}" class="text-[#818cf8]">⬇️</a></td></tr>{% endfor %}
            </tbody></table>
            {% else %}<p class="text-xs text-[#5c5c70]">No backups yet</p>{% endif %}
        </div>
        {% elif tab == 'inbox' %}
        <h2 class="text-xl font-bold mb-6">📥 Unified Inbox (all SMS)</h2>
        <div class="card">
            {% if inbox_rows %}
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">Time</th><th>Business</th><th>Phone</th><th>Dir</th><th>Message</th><th>Reply</th></tr></thead><tbody>
            {% for m in inbox_rows %}<tr class="border-b border-[#1a1a28] align-top">
                <td class="py-2 whitespace-nowrap">{{ m.created_at }}</td>
                <td class="py-2">{{ m.biz }}</td>
                <td class="py-2 font-mono">{{ m.phone }}</td>
                <td class="py-2">{% if m.direction == 'in' %}<span class="text-green-400">← IN</span>{% else %}<span class="text-[#818cf8]">→ OUT</span>{% endif %}</td>
                <td class="py-2 max-w-md">{{ m.body }}</td>
                <td class="py-2"><form method="POST" action="/admin/inbox-reply" class="flex gap-1"><input type="hidden" name="phone" value="{{ m.phone }}"><input type="hidden" name="business_id" value="{{ m.business_id }}"><input type="text" name="body" placeholder="Reply..." class="text-xs w-40"><button class="btn-primary text-xs py-1 px-2">Send</button></form></td>
            </tr>{% endfor %}
            </tbody></table>
            {% else %}<p class="text-xs text-[#5c5c70]">No SMS yet</p>{% endif %}
        </div>
        {% elif tab == 'costs' %}
        <h2 class="text-xl font-bold mb-6">💵 LLM Cost & Margin Tracker</h2>
        <div class="card mb-4"><p class="text-xs text-[#5c5c70]">Estimated: voice ~$0.12/min (grok-4.3 via VAPI), AI SMS ~$0.006/msg. Adjust constants in code.</p></div>
        <div class="card">
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">Business</th><th>Plan Price</th><th>Voice Cost</th><th>SMS AI Cost</th><th>Est. Total</th><th>Margin</th></tr></thead><tbody>
            {% for c in cost_rows %}<tr class="border-b border-[#1a1a28]">
                <td class="py-2 font-semibold">{{ c.name }}</td><td>${{ c.price }}</td><td>${{ c.voice_cost }}</td><td>${{ c.sms_cost }}</td><td>${{ c.total }}</td>
                <td class="{% if c.margin < 0 %}text-red-400{% elif c.margin < c.price * 0.5 %}text-amber-400{% else %}text-green-400{% endif %} font-bold">${{ c.margin }}</td>
            </tr>{% endfor %}
            </tbody></table>
        </div>
        {% elif tab == 'abtest' %}
        <h2 class="text-xl font-bold mb-6">🧪 Script A/B Testing</h2>
        <div class="card mb-6 max-w-xl">
            <h3 class="font-bold mb-3">Create Script Variant</h3>
            <form method="POST" action="/admin/abtest-create" class="space-y-3">
                <select name="business_id" class="text-xs" required><option value="">— Business —</option>{% for b in health_rows %}<option value="{{ b.id }}">{{ b.name }}</option>{% endfor %}</select>
                <input type="text" name="variant_name" placeholder="Variant name (e.g. v2 short intro)" class="text-xs">
                <textarea name="script" rows="4" placeholder="New script text..." class="text-xs"></textarea>
                <button type="submit" class="btn-primary text-sm"><i class="fas fa-flask mr-1"></i> Create Variant</button>
            </form>
        </div>
        <div class="card">
            <h3 class="font-bold mb-3">Variants</h3>
            {% if ab_rows %}
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">Business</th><th>Variant</th><th>Calls</th><th>Bookings</th><th>Rate</th><th>Status</th><th>Activate</th></tr></thead><tbody>
            {% for a in ab_rows %}<tr class="border-b border-[#1a1a28]">
                <td class="py-2">{{ a.biz }}</td><td class="py-2">{{ a.name }}</td><td>{{ a.calls }}</td><td>{{ a.bookings }}</td><td>{{ a.rate or '—' }}</td>
                <td>{% if a.active %}<span class="text-green-400">LIVE</span>{% else %}<span class="text-[#5c5c70]">draft</span>{% endif %}</td>
                <td>{% if not a.active %}<form method="POST" action="/admin/abtest-activate/{{ a.id }}"><button class="btn-primary text-xs py-1 px-2">Activate</button></form>{% endif %}</td>
            </tr>{% endfor %}
            </tbody></table>
            {% else %}<p class="text-xs text-[#5c5c70]">No variants yet</p>{% endif %}
        </div>
        {% elif tab == 'audit' %}
        <h2 class="text-xl font-bold mb-6">🕵️ Admin Audit Log</h2>
        <div class="card">
            {% if audit_rows %}
            <table class="w-full text-xs"><thead><tr class="text-left text-[#64748b] border-b border-[#1a1a28]"><th class="py-2">Time</th><th>Action</th><th>Detail</th></tr></thead><tbody>
            {% for a in audit_rows %}<tr class="border-b border-[#1a1a28]"><td class="py-2 whitespace-nowrap">{{ a.created_at }}</td><td class="py-2 font-mono">{{ a.action }}</td><td class="py-2">{{ a.detail }}</td></tr>{% endfor %}
            </tbody></table>
            {% else %}<p class="text-xs text-[#5c5c70]">No audit entries yet</p>{% endif %}
        </div>
        {% elif tab == 'security' %}
        <h2 class="text-xl font-bold mb-6">🛡️ Admin Security</h2>
        <div class="card max-w-xl mb-4">
            <h3 class="font-bold mb-3">Two-Factor Authentication (TOTP)</h3>
            {% if twofa.enabled %}
            <p class="text-xs text-green-400 mb-3">✅ 2FA is enabled — a code is required at every login.</p>
            <form method="POST" action="/admin/security-2fa-disable"><button class="btn-danger text-sm"><i class="fas fa-unlock mr-1"></i> Disable 2FA</button></form>
            {% else %}
            <p class="text-xs text-[#64748b] mb-3">Enable TOTP: scan the QR with Google Authenticator / Authy, then enter the 6-digit code.</p>
            {% if twofa.secret %}
            <div class="bg-[#12121a] rounded-lg p-4 mb-3 text-center">
                <img src="{{ twofa.qr }}" alt="2FA QR" class="mx-auto w-48 h-48">
                <p class="text-xs text-[#5c5c70] mt-2">Secret: <code class="font-mono">{{ twofa.secret }}</code></p>
            </div>
            <form method="POST" action="/admin/security-2fa-verify" class="flex gap-2">
                <input type="text" name="code" placeholder="6-digit code" class="text-xs font-mono w-32" maxlength="6" autocomplete="one-time-code">
                <button class="btn-primary text-sm">Verify & Enable</button>
            </form>
            {% else %}
            <form method="POST" action="/admin/security-2fa-setup"><button class="btn-primary text-sm"><i class="fas fa-qrcode mr-1"></i> Generate QR Code</button></form>
            {% endif %}
            {% endif %}
        </div>
        {% if twofa.enabled or twofa.backup_count or session.get('admin_2fa_new_codes') %}
        <div class="card max-w-xl">
            <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
                <h3 class="font-bold">🔑 Backup Codes</h3>
                <form method="POST" action="/admin/security-2fa-backup-codes"><button class="btn-secondary text-sm"><i class="fas fa-sync mr-1"></i> {% if twofa.backup_count %}Regenerate{% else %}Generate{% endif %}</button></form>
            </div>
            {% if session.get('admin_2fa_new_codes') %}
            <div class="bg-[#12121a] border border-yellow-500/30 rounded-lg p-4 mb-3">
                <p class="text-xs text-yellow-400 font-semibold mb-2">⚠️ Save these codes somewhere safe. Each one works <strong>once</strong> at login if you lose your phone.</p>
                <div class="grid grid-cols-2 gap-2 font-mono text-sm">
                    {% for c in session['admin_2fa_new_codes'] %}<span class="bg-[#1a1a28] rounded px-3 py-2 text-center">{{ c }}</span>{% endfor %}
                </div>
                <form method="POST" action="/admin/security-2fa-dismiss" class="mt-3"><button class="btn-primary text-xs">I saved them</button></form>
            </div>
            {% endif %}
            <p class="text-xs text-[#64748b]">Remaining unused backup codes: <span class="font-bold text-[#e2e8f0]">{{ twofa.backup_count }}</span></p>
        </div>
        {% endif %}
        {% elif tab == 'reviews-ai' %}
        <div class="flex items-center justify-between mb-6">
            <h2 class="text-xl font-bold">{% if ra_settings.service == 'website' %}🌐 Review AI — Web Development Outreach{% else %}⭐ Review AI — Google Review Response Service{% endif %}</h2>
            <span id="raRunningBadge" class="text-xs font-semibold px-3 py-1.5 rounded-lg" style="background:#1a1a28;border:1px solid #252533;color:#94a3b8">…</span>
        </div>

        <!-- LIVE: who's on the phone right now -->
        <div id="raLiveBar" class="card mb-6" style="{% if not ra_live %}display:none{% endif %}">
            <div class="flex items-center gap-3 flex-wrap">
                <span class="text-xs font-bold uppercase tracking-wide text-[#f87171]">🔴 Live Calls</span>
                <span id="raLiveList" class="text-sm">
                    {% for l in ra_live %}<span class="inline-flex items-center gap-2 mr-4"><span class="w-2 h-2 rounded-full animate-pulse" style="background:#f87171"></span><b>{{ l.business_name }}</b><span class="text-[#94a3b8] font-mono text-xs">{{ l.phone }}</span><span class="text-[#fbbf24] text-xs">{{ l.status }}</span></span>{% endfor %}
                </span>
            </div>
        </div>

        <!-- Stats -->
        <div class="grid grid-cols-3 md:grid-cols-6 gap-3 mb-6">
            <div class="card text-center"><div class="stat-value">{{ ra_stats.total }}</div><div class="text-xs text-[#64748b] mt-1">🎯 Found</div></div>
            <div class="card text-center"><div class="stat-value" style="color:#60a5fa">{{ ra_stats.new }}</div><div class="text-xs text-[#64748b] mt-1">🆕 To Call</div></div>
            <div class="card text-center"><div class="stat-value" style="color:#c084fc">{{ ra_stats.called }}</div><div class="text-xs text-[#64748b] mt-1">📞 Called</div></div>
            <div class="card text-center"><div class="stat-value" style="color:#4ade80">{{ ra_stats.interested }}</div><div class="text-xs text-[#64748b] mt-1">🔥 Interested</div></div>
            <div class="card text-center"><div class="stat-value" style="color:#f87171">{{ ra_stats.no_answer }}</div><div class="text-xs text-[#64748b] mt-1">📵 No Answer</div></div>
            <div class="card text-center"><div class="stat-value" style="color:#38bdf8">{{ ra_stats.no_website }}</div><div class="text-xs text-[#64748b] mt-1">🌐 No Website</div></div>
        </div>

        <!-- Actions -->
        <div class="card mb-6">
            <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
                <h3 class="font-bold">⚡ Actions</h3>
                <div class="flex items-center gap-2 flex-wrap">
                    <form method="POST" action="/admin/review-ai/scrape" class="inline"><button class="btn-primary text-xs" style="padding:8px 14px">🔍 Find Prospects</button></form>
                    {% if ra_settings.service != 'website' %}
                    <form method="POST" action="/admin/review-ai/count-unanswered" class="inline"><button class="btn-secondary text-xs" style="padding:8px 14px">🔢 Count Unanswered</button></form>
                    {% endif %}
                    <form method="POST" action="/admin/review-ai/call" class="inline flex items-center gap-1">
                        <input type="number" name="max_calls" placeholder="calls" min="1" max="20" value="{{ ra_settings.max_calls_per_run }}" style="width:70px;padding:8px 10px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:12px">
                        <button class="text-xs font-semibold" style="padding:8px 14px;border-radius:8px;background:linear-gradient(135deg,#a855f7,#ec4899);color:#fff">📞 Call Next N</button>
                    </form>
                    <form method="POST" action="/admin/review-ai/verify" class="inline"><button class="btn-secondary text-xs" style="padding:8px 14px">📱 Verify Numbers</button></form>
                    <form method="POST" action="/admin/review-ai/sync" class="inline"><button class="btn-secondary text-xs" style="padding:8px 14px">📊 Sync Outcomes</button></form>
                    <form method="POST" action="/admin/review-ai/stop" class="inline"><button class="btn-danger text-xs" style="padding:8px 14px">⏹ Stop</button></form>
                </div>
            </div>
            <div class="text-[11px] text-[#64748b] mb-2">Live log:</div>
            <div id="raLog" class="bg-[#0c0c18] rounded-lg p-3 text-[11px] font-mono text-[#94a3b8] max-h-32 overflow-y-auto" style="white-space:pre-wrap">{% for l in ra_log %}{{ l }}
{% endfor %}</div>
        </div>

        <!-- Settings -->
        <div class="card mb-6">
            <h3 class="font-bold mb-3">⚙️ Settings</h3>
            <form method="POST" action="/admin/review-ai/save-settings">
                <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3">
                    <div><label class="text-[10px] text-[#64748b] uppercase font-semibold">City</label><input name="city" value="{{ ra_settings.city }}" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:13px"></div>
                    <div><label class="text-[10px] text-[#64748b] uppercase font-semibold">State</label><input name="state" value="{{ ra_settings.state }}" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:13px"></div>
                    <div><label class="text-[10px] text-[#64748b] uppercase font-semibold">Max per category</label><input name="max_per_category" value="{{ ra_settings.max_per_category }}" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:13px"></div>
                    <div><label class="text-[10px] text-[#64748b] uppercase font-semibold">Service (call pitch)</label>
                        <select name="service" id="raService" onchange="raServiceChanged()" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:13px">
                            <option value="reviews" {% if ra_settings.service != 'website' %}selected{% endif %}>⭐ Review Responses</option>
                            <option value="website" {% if ra_settings.service == 'website' %}selected{% endif %}>🌐 Web Development</option>
                        </select>
                    </div>
                    <div id="raPricingCell"><label class="text-[10px] text-[#64748b] uppercase font-semibold">Pricing</label><input name="pricing" value="{{ ra_settings.pricing }}" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:13px"></div>
                    <div id="raWebPricingCell" style="display:none"><label class="text-[10px] text-[#64748b] uppercase font-semibold">Website pricing</label><input name="website_pricing" value="{{ ra_settings.website_pricing }}" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:13px"></div>
                </div>
                <div class="mb-3">
                    <label class="text-[10px] text-[#64748b] uppercase font-semibold">Categories (comma separated)</label>
                    <input name="categories" value="{{ ra_settings.categories }}" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:13px">
                </div>
                <div id="raReviewsBox" class="mb-3">
                    <label class="text-[10px] text-[#64748b] uppercase font-semibold">Review-response call script (placeholders: {business_name} {unanswered} {pricing} {phone})</label>
                    <textarea name="script" rows="7" style="width:100%;padding:10px 14px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:12px;font-family:monospace">{{ ra_settings.script }}</textarea>
                </div>
                <div id="raWebsiteBox" class="mb-3" style="display:none">
                    <label class="text-[10px] text-[#64748b] uppercase font-semibold">Web-dev call script (placeholders: {business_name} {website_pricing} {phone}) — calls only businesses with NO website</label>
                    <textarea name="website_script" rows="7" style="width:100%;padding:10px 14px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:12px;font-family:monospace">{{ ra_settings.website_script }}</textarea>
                </div>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                    <div><label class="text-[10px] text-[#64748b] uppercase font-semibold">Voice</label><input name="voice_id" value="{{ ra_settings.voice_id }}" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:13px"></div>
                    <div><label class="text-[10px] text-[#64748b] uppercase font-semibold">Max calls / run</label><input name="max_calls_per_run" value="{{ ra_settings.max_calls_per_run }}" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:13px"></div>
                    <div><label class="text-[10px] text-[#64748b] uppercase font-semibold">Delay (sec)</label><input name="delay_seconds" value="{{ ra_settings.delay_seconds }}" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:13px"></div>
                    <div><label class="text-[10px] text-[#64748b] uppercase font-semibold">Payment link</label><input name="payment_link" value="{{ ra_settings.payment_link }}" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:11px;font-family:monospace"></div>
                    <div><label class="text-[10px] text-[#64748b] uppercase font-semibold">Signup URL</label><input name="signup_url" value="{{ ra_settings.signup_url }}" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:11px;font-family:monospace"></div>
                    <div><label class="text-[10px] text-[#64748b] uppercase font-semibold">Enabled</label>
                        <select name="enabled" style="width:100%;padding:9px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:13px">
                            <option value="1" {% if ra_settings.enabled == '1' %}selected{% endif %}>✅ ON</option>
                            <option value="0" {% if ra_settings.enabled != '1' %}selected{% endif %}>⛔ OFF</option>
                        </select>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button class="btn-primary text-sm">💾 Save Settings</button>
                    <span class="text-[11px] text-[#64748b]">Assistant: {% if ra_settings.assistant_id %}<span class="text-green-400 font-mono">{{ ra_settings.assistant_id[:16] }}…</span>{% else %}<span class="text-yellow-400">not created yet (auto-creates on first call)</span>{% endif %}</span>
                </div>
            </form>
        </div>

        <!-- Follow-up queue: interested clients needing attention -->
        <div class="card mb-6" style="border-color:#22c55e30">
            <div class="flex items-center justify-between mb-3">
                <h3 class="font-bold">🔥 Follow-up Queue — interested clients ({{ ra_followup|length }})</h3>
                <span class="text-[11px] text-[#64748b]">said YES on the call · package sent · awaiting signup or follow-up</span>
            </div>
            {% if ra_followup %}
            <div class="overflow-x-auto">
            <table class="table-auto w-full text-xs">
                <thead><tr><th>Business</th><th>Phone</th><th>Line</th><th>Service</th><th>Package</th><th>Called</th><th>Call</th><th></th></tr></thead>
                <tbody>
                {% for p in ra_followup %}
                <tr>
                    <td class="font-semibold">{{ p.business_name[:32] }}</td>
                    <td class="font-mono">{{ p.phone }}</td>
                    <td>{% if p.line_type == 'mobile' %}<span class="text-[10px]" style="color:#4ade80">📱</span>{% elif p.line_type == 'landline' %}<span class="text-[10px]" style="color:#fbbf24">🏢</span>{% elif p.line_type %}<span class="text-[10px]" style="color:#c084fc">📠</span>{% else %}<span class="text-[10px] text-[#5c5c70]">…</span>{% endif %}</td>
                    <td>{% if p.service == 'website' %}🌐 Web{% else %}⭐ Reviews{% endif %}</td>
                    <td>{% if p.sample_sent_at %}<span style="color:#4ade80">✅ {{ p.sample_sent_at[:16] }}</span>{% else %}<span class="text-[#fbbf24]">pending</span>{% endif %}</td>
                    <td class="text-[#5c5c70]">{{ (p.last_call_at or '')[:16] }}</td>
                    <td class="whitespace-nowrap">{% if p.last_call_id %}<button class="btn-secondary text-[10px]" style="padding:3px 7px" onclick="raAudio('{{ p.last_call_id }}')">🎧</button> <button class="btn-secondary text-[10px]" style="padding:3px 7px" onclick="raTranscript('{{ p.last_call_id }}')">📄</button>{% if p.has_recording or p.has_transcript %} <span title="saved to DB/disk" style="color:#4ade80">💾</span>{% endif %}{% endif %}</td>
                    <td class="whitespace-nowrap">
                        <button class="btn-primary text-[10px]" style="padding:4px 8px" onclick="raSample('{{ p.id }}')">📤 Package</button>
                        <button class="btn-secondary text-[10px]" style="padding:4px 8px" onclick="raAction('complete','{{ p.id }}')">✅ Done</button>
                        <button class="btn-secondary text-[10px]" style="padding:4px 8px" onclick="raAction('call-again','{{ p.id }}')">📞 Again</button>
                    </td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
            </div>
            {% else %}
            <p class="text-[12px] text-[#5c5c70] py-4 text-center">No interested clients yet — they land here automatically after a call ends with a "yes".</p>
            {% endif %}
        </div>

        <!-- Prospects -->
        <div class="card mb-6">
            <div class="flex items-center justify-between mb-3">
                <h3 class="font-bold">🎯 Prospects ({{ ra_prospects|length }})</h3>
                <input id="raSearch" oninput="raFilter()" placeholder="🔍 filter…" style="padding:8px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:12px;width:180px">
            </div>
            <div class="overflow-x-auto">
            <table class="table-auto w-full text-xs">
                <thead><tr><th>Business</th><th>Phone</th><th>Line</th><th>⭐</th><th>Reviews</th><th>Unanswered</th><th>🌐</th><th>Status</th><th>Last Call</th><th></th></tr></thead>
                <tbody>
                {% for p in ra_prospects %}
                <tr class="ra-row" data-search="{{ p.business_name }} {{ p.phone }} {{ p.category }}">
                    <td class="font-semibold">{{ p.business_name[:34] }}<div class="text-[10px] text-[#5c5c70]">{{ p.category }} · {{ p.city }}</div></td>
                    <td class="font-mono">{{ p.phone }}</td>
                    <td>{% if p.line_type == 'mobile' %}<span class="text-[10px]" style="color:#4ade80">📱</span>{% elif p.line_type == 'landline' %}<span class="text-[10px]" style="color:#fbbf24">🏢</span>{% elif p.line_type %}<span class="text-[10px]" style="color:#c084fc">📠</span>{% else %}<span class="text-[10px] text-[#5c5c70]">…</span>{% endif %}</td>
                    <td>{% if p.rating %}⭐ {{ p.rating }}{% else %}—{% endif %}</td>
                    <td>{{ p.review_count or '—' }}</td>
                    <td>{% if p.unanswered_count is not none %}<b class="text-[#fbbf24]">{{ p.unanswered_count }}</b>{% else %}<span class="text-[#5c5c70]">…</span>{% endif %}</td>
                    <td>{% if p.website %}<span title="{{ p.website }}" style="color:#4ade80">✅</span>{% else %}<b style="color:#f87171">❌</b>{% endif %}</td>
                    <td>
                        {% if p.status == 'new' %}<span class="badge badge-active">🆕 New</span>
                        {% elif p.status == 'called' %}<span class="badge" style="background:#8b5cf620;color:#c084fc">📞 Called</span>
                        {% elif p.status == 'interested' %}<span class="badge" style="background:#22c55e20;color:#4ade80">🔥 Interested</span>
                        {% elif p.status == 'not_interested' %}<span class="badge badge-inactive">🙅 No</span>
                        {% elif p.status == 'no_answer' %}<span class="badge badge-error">📵 No Ans</span>
                        {% elif p.status == 'do_not_call' %}<span class="badge badge-error">🚫 DNC</span>
                        {% elif p.status == 'completed' %}<span class="badge" style="background:#22c55e20;color:#4ade80">✅ Done</span>
                        {% else %}<span class="badge">{{ p.status }}</span>{% endif %}
                    </td>
                    <td class="text-[#5c5c70]">{{ (p.last_outcome or '')[:16] }}{% if p.last_call_at %}<div class="text-[10px]">{{ p.last_call_at[:16] }}</div>{% endif %}</td>
                    <td class="whitespace-nowrap">
                        {% if p.status == 'interested' %}<button class="btn-primary text-[10px]" style="padding:4px 8px" onclick="raSample('{{ p.id }}')">📤 Package{% if p.sample_sent_at %} ✓{% endif %}</button>{% endif %}
                        {% if p.last_call_id %}<button class="btn-secondary text-[10px]" style="padding:4px 8px" onclick="raAudio('{{ p.last_call_id }}')">🎧</button> <button class="btn-secondary text-[10px]" style="padding:4px 8px" onclick="raTranscript('{{ p.last_call_id }}')">📄</button>{% endif %}
                        <button class="btn-secondary text-[10px]" style="padding:4px 8px" onclick="raAction('complete','{{ p.id }}')">✅</button>
                        <button class="btn-secondary text-[10px]" style="padding:4px 8px" onclick="raAction('call-again','{{ p.id }}')">📞</button>
                        <button class="btn-secondary text-[10px]" style="padding:4px 8px" onclick="raAction('reset','{{ p.id }}')">↺</button>
                        <button class="btn-secondary text-[10px]" style="padding:4px 8px" onclick="raAction('dnc','{{ p.id }}')">🚫</button>
                        <button class="btn-danger text-[10px]" style="padding:4px 8px" onclick="raAction('delete','{{ p.id }}')">🗑</button>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="8" class="text-center text-[#5c5c70] py-8">No prospects yet — hit 🔍 Find Prospects</td></tr>
                {% endfor %}
                </tbody>
            </table>
            </div>
        </div>

        <!-- Leads (signups) -->
        <div class="card mb-6">
            <div class="flex items-center justify-between mb-3">
                <h3 class="font-bold">📝 Service Leads — signups ({{ ra_leads|length }} shown)</h3>
                <a href="https://diazites.online/review-service" target="_blank" class="text-[11px] text-[#38bdf8] hover:underline">service page ↗</a>
            </div>
            {% if ra_leads %}
            <div class="overflow-x-auto">
            <table class="table-auto w-full text-xs">
                <thead><tr><th>Business</th><th>Contact</th><th>Email</th><th>Phone</th><th>Status</th><th>Time</th></tr></thead>
                <tbody>
                {% for l in ra_leads %}
                <tr>
                    <td class="font-semibold">{{ l.business_name[:30] }}</td>
                    <td>{{ l.contact_name[:20] }}</td>
                    <td class="text-[#94a3b8]">{{ l.email[:28] }}</td>
                    <td class="font-mono">{{ l.phone }}</td>
                    <td>{% if l.status == 'paid' %}<span class="badge" style="background:#22c55e20;color:#4ade80">💰 PAID</span>{% elif l.status == 'new' %}<span class="badge badge-active">🆕 New</span>{% else %}<span class="badge">{{ l.status }}</span>{% endif %}</td>
                    <td class="text-[#5c5c70]">{{ (l.created_at or '')[:16] }}</td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
            </div>
            {% else %}
            <p class="text-[12px] text-[#5c5c70] py-4 text-center">No signups yet — they come from the service page, or prospects who click the signup link in their SMS/email package.</p>
            {% endif %}
        </div>

        <!-- Calls log -->
        <div class="card">
            <h3 class="font-bold mb-3">📞 Call Log ({{ ra_calls|length }})</h3>
            <div class="overflow-x-auto">
            <table class="table-auto w-full text-xs">
                <thead><tr><th>#</th><th>Business</th><th>Status</th><th>Outcome</th><th>Cost</th><th>Dur</th><th>Time</th><th></th></tr></thead>
                <tbody>
                {% for c in ra_calls %}
                <tr>
                    <td class="text-[#5c5c70]">{{ c.id }}</td>
                    <td class="font-semibold">{{ (c.business_name or '')[:30] }}</td>
                    <td>{% if c.status == 'interested' %}<span class="badge" style="background:#22c55e20;color:#4ade80">🔥 {{ c.status }}</span>{% elif c.status == 'placed' %}<span class="badge" style="background:#8b5cf620;color:#c084fc">⏳ {{ c.status }}</span>{% else %}<span class="badge">{{ c.status }}</span>{% endif %}</td>
                    <td class="text-[#94a3b8]">{{ (c.outcome or '—')[:20] }}</td>
                    <td class="font-mono">${{ '%.2f'|format(c.cost or 0) }}</td>
                    <td>{{ c.duration or 0 }}s</td>
                    <td class="text-[#5c5c70]">{{ (c.created_at or '')[:16] }}</td>
                    <td>{% if c.call_id %}<button class="btn-secondary text-[10px]" style="padding:3px 7px" onclick="raTranscript('{{ c.call_id }}')">📄</button> <button class="btn-secondary text-[10px]" style="padding:3px 7px" onclick="raAudio('{{ c.call_id }}')">🎧</button>{% endif %}</td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
            </div>
        </div>

        <!-- Transcript modal -->
        <div id="raTrModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:50;align-items:center;justify-content:center;padding:20px" onclick="if(event.target===this)this.style.display='none'">
            <div class="card" style="max-width:640px;width:100%;max-height:80vh;overflow-y:auto">
                <div class="flex items-center justify-between mb-3">
                    <h3 class="font-bold">📄 Call Transcript</h3>
                    <button class="btn-secondary text-xs" onclick="document.getElementById('raTrModal').style.display='none'">✕</button>
                </div>
                <div id="raTrBody" class="text-[12px] font-mono text-[#cbd5e1] whitespace-pre-wrap" style="line-height:1.6">…</div>
            </div>
        </div>

        <!-- Recording player modal -->
        <div id="raAuModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:50;align-items:center;justify-content:center;padding:20px" onclick="if(event.target===this)this.style.display='none'">
            <div class="card" style="max-width:520px;width:100%">
                <div class="flex items-center justify-between mb-3">
                    <h3 class="font-bold">🎧 Call Recording</h3>
                    <button class="btn-secondary text-xs" onclick="document.getElementById('raAuModal').style.display='none'">✕</button>
                </div>
                <audio id="raAuPlayer" controls autoplay style="width:100%">
                    <source src="" type="audio/mpeg">
                </audio>
                <p class="text-[11px] text-[#64748b] mt-2">No audio? The recording may still be processing — try again in a minute.</p>
            </div>
        </div>

        <script>
        function raServiceChanged(){
            var w = document.getElementById('raService').value === 'website';
            document.getElementById('raReviewsBox').style.display = w ? 'none' : '';
            document.getElementById('raWebsiteBox').style.display = w ? '' : 'none';
            document.getElementById('raPricingCell').style.display = w ? 'none' : '';
            document.getElementById('raWebPricingCell').style.display = w ? '' : 'none';
        }
        raServiceChanged();
        function raFilter(){
            var q = document.getElementById('raSearch').value.toLowerCase();
            document.querySelectorAll('.ra-row').forEach(function(r){
                r.style.display = (r.getAttribute('data-search')||'').toLowerCase().indexOf(q) !== -1 ? '' : 'none';
            });
        }
        function raAction(kind, id){
            var msg = kind === 'delete' ? 'Delete this prospect?' :
                      kind === 'dnc' ? 'Mark do-not-call?' :
                      kind === 'complete' ? 'Mark COMPLETED? It will never be called again.' :
                      kind === 'call-again' ? 'Call this prospect NOW?' :
                      'Reset to new?';
            if (!confirm(msg)) return;
            fetch('/admin/review-ai/' + kind + '/' + id, {method: 'POST'}).then(function(r){ return r.json(); })
              .then(function(d){ if (d && d.message) alert(d.message); location.reload(); })
              .catch(function(){ alert('Failed'); });
        }
        function raTranscript(callId){
            var m = document.getElementById('raTrModal');
            var body = document.getElementById('raTrBody');
            body.textContent = 'Loading…';
            m.style.display = 'flex';
            fetch('/admin/review-ai/transcript/' + callId).then(function(r){ return r.json(); })
              .then(function(d){
                var out = [];
                if (d.summary) out.push('📌 SUMMARY: ' + d.summary + '\\n────────────────────────');
                if (d.messages && d.messages.length){
                    out.push(d.messages.map(function(p){ return (p[0] === 'user' ? '👤 ' : '🤖 ') + p[1]; }).join('\\n'));
                } else if (d.transcript){
                    out.push(d.transcript);
                } else {
                    out.push('No transcript yet (call may still be live).');
                }
                body.textContent = out.join('\\n');
              }).catch(function(){ body.textContent = 'Failed to load transcript.'; });
        }
        function raAudio(callId){
            var m = document.getElementById('raAuModal');
            var player = document.getElementById('raAuPlayer');
            player.src = '/admin/review-ai/recording/' + callId;
            player.load();
            m.style.display = 'flex';
            player.play().catch(function(){});
        }
        function raSample(id){
            if (!confirm('Send the free sample review-response SMS now?')) return;
            fetch('/admin/review-ai/sample-sms/' + id, {method: 'POST'}).then(function(r){ return r.json(); })
              .then(function(d){ alert(d.message); }).catch(function(){ alert('Failed'); });
        }
        function raPoll(){
            fetch('/admin/review-ai/status').then(function(r){ return r.json(); }).then(function(d){
                var r = d.running || {};
                var parts = [];
                if (r.scrape) parts.push('🔍 scraping');
                if (r.count) parts.push('🔢 counting');
                if (r.calls) parts.push('📞 calling');
                var badge = document.getElementById('raRunningBadge');
                if (parts.length){
                    badge.textContent = '⏳ ' + parts.join(' · ');
                    badge.style.color = '#fbbf24'; badge.style.borderColor = '#f59e0b40';
                } else {
                    badge.textContent = '● Idle';
                    badge.style.color = '#4ade80'; badge.style.borderColor = '#22c55e40';
                }
                var log = document.getElementById('raLog');
                if (d.log && d.log.length){ log.textContent = d.log.join('\\n'); log.scrollTop = log.scrollHeight; }
                // LIVE calls — who's on the phone right now
                var bar = document.getElementById('raLiveBar');
                var list = document.getElementById('raLiveList');
                if (d.live && d.live.length){
                    bar.style.display = '';
                    list.innerHTML = d.live.map(function(l){
                        return '<span class="inline-flex items-center gap-2 mr-4"><span class="w-2 h-2 rounded-full animate-pulse" style="background:#f87171"></span><b>' + l.business_name + '</b><span class="text-[#94a3b8] font-mono text-xs">' + l.phone + '</span><span class="text-[#fbbf24] text-xs">' + l.status + '</span></span>';
                    }).join('');
                } else {
                    bar.style.display = 'none';
                }
            }).catch(function(){});
        }
        raPoll();
        setInterval(raPoll, 6000);
        </script>
        {% endif %}
    </div>

    {% else %}
    <!-- LOGIN PAGE -->
    <div class="w-full min-h-screen flex items-center justify-center p-4">
        <div class="max-w-sm w-full card text-center">
            <div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#6366f1] to-[#8b5cf6] flex items-center justify-center text-white font-bold text-2xl mx-auto mb-4">A</div>
            {% if twofa_step %}
            <h2 class="text-lg font-bold mb-1">Two-Factor Authentication</h2>
            <p class="text-xs text-[#64748b] mb-6">Enter the 6-digit code from your authenticator app, or a backup code.</p>
            <form method="POST" action="/admin" class="space-y-3">
                <input type="text" name="code" placeholder="6-digit or backup code" class="text-center font-mono" autofocus autocomplete="one-time-code">
                <button type="submit" class="btn-primary w-full">Verify →</button>
            </form>
            {% else %}
            <h2 class="text-lg font-bold mb-1">Admin Login</h2>
            <p class="text-xs text-[#64748b] mb-6">Diazites Management</p>
            <form method="POST" action="/admin" class="space-y-3">
                <input type="password" name="password" placeholder="Admin Password" class="text-center" autofocus>
                <button type="submit" class="btn-primary w-full">Login →</button>
            </form>
            {% endif %}
            {% if error %}<p class="text-red-400 text-xs mt-3">{{ error }}</p>{% endif %}
        </div>
    </div>
    {% endif %}

    <script>
    // Buy number for a business with area code prompt
    function buyNumberForBiz(bizId, bizName) {
        const ac = prompt('Enter area code for the new number (e.g. 305, 954, 786) or leave blank for any:', '');
        if (ac === null) return; // Cancelled
        const areaCode = ac.trim();
        const msg = areaCode ? `Buy a number in area ${areaCode} for ${bizName}?` : `Buy a number from any area for ${bizName}?`;
        if (!confirm(msg)) return;
        window.location.href = '/admin/business/' + bizId + '/buy-phone' + (areaCode ? '?area_code=' + areaCode : '');
    }
    // Auto-dismiss flashes
    document.querySelectorAll('.animate-bounce').forEach(el => {
        setTimeout(() => el.remove(), 4000);
    });
    // ── Mobile drawer menu ──
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    const mobileDrawer = document.getElementById('mobileDrawer');
    const drawerBackdrop = document.getElementById('drawerBackdrop');
    const drawerClose = document.getElementById('drawerClose');
    function openDrawer() { mobileDrawer.classList.add('show'); drawerBackdrop.classList.add('show'); document.body.style.overflow = 'hidden'; }
    function closeDrawer() { mobileDrawer.classList.remove('show'); drawerBackdrop.classList.remove('show'); document.body.style.overflow = ''; }
    if (hamburgerBtn) hamburgerBtn.addEventListener('click', openDrawer);
    if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
    if (drawerBackdrop) drawerBackdrop.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });
    // ── Sidebar search filter (works in desktop sidebar + mobile drawer) ──
    document.querySelectorAll('.menu-filter').forEach(inp => {
        inp.addEventListener('input', function() {
            const q = this.value.trim().toLowerCase();
            const root = this.closest('.sidebar') || this.closest('.drawer');
            if (!root) return;
            root.querySelectorAll('a.sidebar-item').forEach(a => {
                const hay = ((a.dataset.label || '') + ' ' + (a.getAttribute('href') || '')).toLowerCase();
                a.style.display = (!q || hay.includes(q)) ? '' : 'none';
            });
            root.querySelectorAll('.sidebar-section').forEach(sec => {
                let any = false;
                let el = sec.nextElementSibling;
                while (el && el.classList && !el.classList.contains('sidebar-section')) {
                    if (el.classList.contains('sidebar-item') && el.style.display !== 'none') { any = true; break; }
                    el = el.nextElementSibling;
                }
                sec.style.display = any ? '' : 'none';
            });
        });
    });
    </script>
</body>
</html>"""

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect('/admin')
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def admin_root():
    return redirect('/admin')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        # ── Step 2: TOTP / backup code ──
        if session.get('admin_2fa_pending'):
            code = request.form.get('code', '').strip()
            if verify_2fa(code, consume=True):
                session['admin_logged_in'] = True
                session.pop('admin_2fa_pending', None)
                session.permanent = True
                audit('2fa_login', 'admin authenticated with 2FA')
                return redirect('/admin?tab=dashboard')
            return render_template_string(ADMIN_HTML, session=session, error='Invalid code. Try again or use a backup code.', tab='', twofa_step=True)
        # ── Step 1: password ──
        pw = request.form.get('password', '')
        if pw == ADMIN_PASSWORD:
            if load_2fa().get('enabled'):
                session['admin_2fa_pending'] = True
                return render_template_string(ADMIN_HTML, session=session, error='', tab='', twofa_step=True)
            session['admin_logged_in'] = True
            session.permanent = True
            return redirect('/admin?tab=dashboard')
        return render_template_string(ADMIN_HTML, session=session, error='Invalid password', tab='')
    # GET
    if session.get('admin_2fa_pending'):
        return render_template_string(ADMIN_HTML, session=session, error='', tab='', twofa_step=True)
    # If already logged in, show dashboard with data
    if session.get('admin_logged_in'):
        session.permanent = True  # Refresh session expiry on every page view
        return admin_dashboard()
    return render_template_string(ADMIN_HTML, session=session, error='', tab='')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/admin')

# admin_dashboard is defined below
@app.route('/admin/business/<bid>')
@admin_required
def view_business(bid):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if not biz:
        return "Business not found", 404
    
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ?", (bid,))
    leads_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM call_log WHERE business_id = ?", (bid,))
    calls_count = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(cost),0) FROM call_log WHERE business_id = ?", (bid,))
    total_cost = c.fetchone()[0]
    c.execute("SELECT * FROM call_log WHERE business_id = ? ORDER BY created_at DESC LIMIT 10", (bid,))
    recent = [dict(r) for r in c.fetchall()]
    
    c.execute("SELECT * FROM leads WHERE business_id = ? ORDER BY created_at DESC LIMIT 20", (bid,))
    recent_leads = [dict(r) for r in c.fetchall()]
    
    return render_template_string("""<!DOCTYPE html>
<html><head><title>Business Detail</title><script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>body{background:#050508;font-family:Inter,sans-serif}@import url('https://fonts.googleapis.com/css2?family=Inter:opsz@14..32&display=swap');
.card{background:#0d0d14;border:1px solid #1a1a28;border-radius:12px;padding:20px;}</style></head>
<body class="text-[#e2e8f0] p-6">
<div class="max-w-4xl mx-auto">
<a href="/admin?tab=businesses" class="text-[#818cf8] text-sm hover:underline mb-4 inline-block">&larr; Back</a>
<h2 class="text-xl font-bold mb-4">{{ biz.name }} <span class="text-xs text-[#64748b] font-normal">({{ biz.id }})</span></h2>
<div class="grid grid-cols-3 gap-4 mb-6">
<div class="card"><div class="text-xs text-[#64748b]">Industry</div><div class="font-semibold">{{ biz.industry }}</div></div>
<div class="card"><div class="text-xs text-[#64748b]">Plan</div><div class="font-semibold">{{ biz.plan or 'starter' }}</div></div>
<div class="card"><div class="text-xs text-[#64748b]">Email</div><div class="font-semibold text-xs truncate">{{ biz.email or '—' }}</div></div>
<div class="card"><div class="text-xs text-[#64748b]">Leads</div><div class="font-semibold">{{ leads_count }}</div></div>
<div class="card"><div class="text-xs text-[#64748b]">Calls Made</div><div class="font-semibold">{{ calls_count }}</div></div>
<div class="card"><div class="text-xs text-[#64748b]">Total AI Cost</div><div class="font-semibold text-[#f472b6]">${{ "%.2f"|format(total_cost) }}</div></div>
<div class="card"><div class="text-xs text-[#64748b]">Dashboard</div><div class="font-semibold text-xs text-[#818cf8] truncate">{{ request.host.replace(':8086',':8085') }}/login</div></div>
<div class="card"><div class="text-xs text-[#64748b]">🧠 Max Tokens</div><div class="font-semibold">{{ biz.max_tokens or 200 }}</div></div>
<div class="card"><div class="text-xs text-[#64748b]">⚡ Voice Speed</div><div class="font-semibold">{{ biz.voice_speed or '1.0' }}×</div></div>
<div class="card"><div class="text-xs text-[#64748b]">📞 Concurrency</div><div class="font-semibold">{{ biz.concurrency or 5 }}</div></div>
<div class="card"><div class="text-xs text-[#64748b]">🤖 VAPI Assistant</div><div class="font-semibold text-xs truncate">{% if biz.vapi_assistant_id %}<span class="text-green-400">✅ {{ biz.vapi_assistant_id[:12] }}...</span>{% else %}<span class="text-yellow-400">❌ Not created</span>{% endif %}</div></div>
<div class="card"><div class="text-xs text-[#64748b]">📞 Phone Number</div><div class="font-semibold text-xs truncate">{% if biz.vapi_phone_id %}<span class="text-green-400">✅ {{ biz.vapi_phone_id[:12] }}...</span>{% else %}<span class="text-yellow-400">❌ Not assigned</span>{% endif %}</div></div>
</div>
<div class="flex gap-3 mb-6 flex-wrap">
    {% if not biz.vapi_assistant_id %}
    <a href="/admin/business/{{ biz.id }}/setup-vapi" class="btn-primary text-xs py-2 px-4" onclick="return confirm('Create VAPI assistant for {{ biz.name }}?'')"><i class="fas fa-robot mr-1"></i> Setup VAPI Assistant</a>
    {% else %}
    <span class="text-xs text-green-400 py-2 px-4 border border-green-700 rounded-lg"><i class="fas fa-check-circle mr-1"></i> VAPI Assistant Ready</span>
    {% endif %}
    {% if not biz.vapi_phone_id %}
    <button onclick="buyNumberForBiz('{{ biz.id }}', '{{ biz.name }}')" class="btn-primary text-xs py-2 px-4"><i class="fas fa-phone mr-1"></i> Assign Phone Number</button>
    {% else %}
    <span class="text-xs text-green-400 py-2 px-4 border border-green-700 rounded-lg"><i class="fas fa-check-circle mr-1"></i> Phone Number Ready</span>
    {% endif %}
    <a href="/admin/business/{{ biz.id }}/resend-credentials" class="btn-secondary text-xs py-2 px-4" onclick="return confirm('Resend credentials to the business email?')"><i class="fas fa-envelope mr-1"></i> Resend Credentials</a>
</div>
<!-- Knowledge Base & Script Settings -->
<div class="grid grid-cols-2 gap-6 mb-6">
    <div class="card">
        <h3 class="font-bold mb-2">🎙️ Script Template</h3>
        <p class="text-xs text-[#64748b] mb-2">The call script the AI reads during outbound calls.</p>
        <form method="POST" action="/admin/business/{{ biz.id }}/update-settings">
            <textarea name="script_template" rows="5" class="text-xs font-mono mb-2">{{ biz.script_template or '' }}</textarea>
            <button type="submit" class="btn-primary text-xs w-full">Save Script</button>
        </form>
    </div>
    <div class="card">
        <h3 class="font-bold mb-2">🧠 Knowledge Base</h3>
        <p class="text-xs text-[#64748b] mb-2">Business info the AI uses when speaking with leads (services, pricing, hours, etc.).</p>
        <form method="POST" action="/admin/business/{{ biz.id }}/update-settings">
            <textarea name="knowledge_base" rows="5" class="text-xs font-mono mb-2">{{ biz.knowledge_base or '' }}</textarea>
            <button type="submit" class="btn-primary text-xs w-full">Save Knowledge Base</button>
        </form>
    </div>
    <div class="card col-span-2">
        <h3 class="font-bold mb-2">🤖 AI Agent Prompt</h3>
        <p class="text-xs text-[#64748b] mb-2">System prompt that controls how the AI behaves on calls.</p>
        <form method="POST" action="/admin/business/{{ biz.id }}/update-settings">
            <textarea name="agent_prompt" rows="6" class="text-xs font-mono mb-2">{{ biz.agent_prompt or "You are a real-time AI voice agent speaking with customers over the phone. Respond within 0.5-1 second. Keep responses to 1-2 short sentences." }}</textarea>
            <button type="submit" class="btn-primary text-xs w-full">Save Agent Prompt</button>
        </form>
    </div>
</div>

<!-- Add Leads -->
<div class="card mb-6">
    <h3 class="font-bold mb-2">📱 Add Leads</h3>
    <p class="text-xs text-[#64748b] mb-2">Paste phone numbers to add leads for this business (one per line).</p>
    <form method="POST" action="/admin/campaign/add-leads/{{ biz.id }}" class="space-y-3">
        <textarea name="leads" rows="4" class="text-xs font-mono" placeholder="+13051234567&#10;John: +19541234567&#10;John,Acme Plumbing: +17861234567"></textarea>
        <div class="flex gap-2">
            <button type="submit" class="btn-primary text-xs"><i class="fas fa-plus mr-1"></i> Add Leads</button>
            <a href="/admin?tab=campaigns" class="btn-secondary text-xs"><i class="fas fa-bullhorn mr-1"></i> Campaigns</a>
            <a href="/admin/business/{{ biz.id }}" class="btn-secondary text-xs"><i class="fas fa-sync mr-1"></i> Refresh</a>
        </div>
    </form>
</div>

<!-- Recent Leads -->
<h3 class="font-bold mb-2">Recent Leads ({{ leads_count }} total)</h3>
<div class="card mb-6 max-h-48 overflow-y-auto">
{% for lead in recent_leads %}
<div class="flex justify-between items-center py-2 border-b border-[#1a1a28] last:border-0 text-xs">
    <div>
        <span class="font-semibold text-[#e2e8f0]">{{ lead.phone }}</span>
        <span class="text-[#64748b]">{% if lead.name %} — {{ lead.name }}{% endif %}</span>
    </div>
    <div>
        <span class="badge {% if lead.state == 'NEW' %}badge-active{% else %}badge-inactive{% endif %}">{{ lead.state }}</span>
    </div>
</div>
{% endfor %}
</div>

<h3 class="font-bold mb-3">Recent Calls</h3>
{% for c in recent %}
<div class="card mb-2">
<div class="flex justify-between text-xs"><span>{{ c.created_at[:16] }}</span><span class="text-[#64748b]">${{ "%.2f"|format(c.cost or 0) }}</span></div>
<p class="text-xs text-[#94a3b8] mt-1">{{ (c.transcript or 'No transcript')[:150] }}</p>
</div>
{% endfor %}
</div></body></html>""", biz=biz, leads_count=leads_count, calls_count=calls_count, total_cost=total_cost, recent=recent, recent_leads=recent_leads)

@app.route('/admin/business/delete/<bid>', methods=['POST'])
@admin_required
def delete_business(bid):
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM call_log WHERE business_id = ?", (bid,))
    c.execute("DELETE FROM leads WHERE business_id = ?", (bid,))
    c.execute("DELETE FROM campaigns WHERE business_id = ?", (bid,))
    c.execute("DELETE FROM businesses WHERE id = ?", (bid,))
    db.commit()
    flash('Business deleted', 'success')
    return redirect('/admin?tab=businesses')

@app.route('/admin/business/<bid>/resend-credentials')
@admin_required
def resend_credentials(bid):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT name, email FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if not biz:
        flash('Business not found', 'error')
        return redirect('/admin?tab=businesses')
    email_to = biz['email'] or ''
    if not email_to:
        flash(f'No email on file for {biz["name"]}. Edit the business to add an email first.', 'error')
        return redirect(f'/admin/business/{bid}')
    try:
        send_business_email(bid, biz['name'], email_to)
        flash(f'✅ Credentials resent to {email_to}', 'success')
    except Exception as e:
        flash(f'❌ Failed to send: {e}', 'error')
    return redirect(f'/admin/business/{bid}')

@app.route('/admin/business/<bid>/setup-vapi')
@admin_required
def setup_vapi(bid):
    """Create a VAPI assistant for this business."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if not biz:
        flash('Business not found', 'error')
        return redirect('/admin?tab=businesses')
    
    name = biz['name']
    industry = biz['industry'] or 'general'
    script = biz['script_template'] or ''
    kb = biz['knowledge_base'] or ''
    voice_id = biz['voice_id'] or 'burt'
    max_tokens = int(biz['max_tokens'] or 200) if biz['max_tokens'] else 200
    
    full_script = build_diazites_prompt(
        business_name=name,
        industry=industry,
        script=script,
        knowledge_base=kb
    )
    # Multilingual by default: auto-detect caller language & respond in it
    full_script += "\n\nIMPORTANT: You are a MULTI-LINGUAL assistant. Detect the caller's language and respond in that same language. You speak: English, Spanish, French, German, Portuguese, Chinese, Arabic, Hindi, Korean, Japanese. Switch languages naturally when the caller switches."
    
    import subprocess, json
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
                "maxTokens": max_tokens,
                "systemPrompt": full_script
            },
            "transcriber": {"provider": "openai", "model": "gpt-4o-transcribe"},
            "voice": {
                "provider": "11labs",
                "voiceId": voice_id,
                "model": "eleven_v3"
            },
            "firstMessage": f"Hi, this is {name}'s assistant from Diazites. We help {industry} businesses never miss a call. Do you have a moment?",
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
            flash(f'❌ VAPI error: {assistant.get("message", result.stdout[:200])}', 'error')
            return redirect(f'/admin/business/{bid}')
    except:
        flash(f'❌ VAPI API error: {result.stdout[:200]}', 'error')
        return redirect(f'/admin/business/{bid}')
    
    c.execute("UPDATE businesses SET vapi_assistant_id = ? WHERE id = ?", (assistant_id, bid))
    db.commit()
    flash(f'✅ VAPI assistant created for {name}! ID: {assistant_id}', 'success')
    return redirect(f'/admin/business/{bid}')

@app.route('/admin/business/<bid>/buy-phone')
@admin_required
def buy_phone(bid):
    """Buy a new phone number from Twilio and register with Vapi."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT name, vapi_assistant_id, vapi_phone_id FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if not biz:
        flash('Business not found', 'error')
        return redirect('/admin?tab=businesses')
    
    if not biz['vapi_assistant_id']:
        flash('⚠️ Please create a VAPI assistant first, then assign a phone number.', 'error')
        return redirect(f'/admin/business/{bid}')
    
    if biz['vapi_phone_id']:
        flash(f'✅ {biz["name"]} already has a phone number assigned.', 'info')
        return redirect(f'/admin/business/{bid}')
    
    import subprocess, json
    from twilio_helper import buy_and_assign_number
    
    # Check if there's already an unassigned Vapi number first
    result = subprocess.run([
        "curl", "-s", f"{VAPI_BASE}/phone-number",
        "-H", f"Authorization: Bearer {VAPI_API_KEY}"
    ], capture_output=True, text=True)
    
    try:
        all_phones = json.loads(result.stdout)
        if isinstance(all_phones, list):
            c.execute("SELECT vapi_phone_id FROM businesses WHERE vapi_phone_id IS NOT NULL")
            used = set(r[0] for r in c.fetchall())
            for p in all_phones:
                if p.get('id') not in used and not p.get('assistantId'):
                    pid = p['id']
                    pnumber = p.get('number', '?')
                    c.execute("UPDATE businesses SET vapi_phone_id = ? WHERE id = ?", (pid, bid))
                    db.commit()
                    # Set inbound assistant
                    subprocess.run([
                        "curl", "-s", "-X", "PATCH", f"{VAPI_BASE}/phone-number/{pid}",
                        "-H", f"Authorization: Bearer {VAPI_API_KEY}",
                        "-H", "Content-Type: application/json",
                        "-d", json.dumps({"assistantId": biz['vapi_assistant_id']})
                    ], capture_output=True, text=True)
                    flash(f'✅ Phone {pnumber} assigned to {biz["name"]}!', 'success')
                    return redirect(f'/admin/business/{bid}')
    except:
        pass
    
    # No unassigned numbers — buy one from Twilio directly
    flash('⏳ No unassigned numbers. Buying new number from Twilio...', 'info')
    
    area_code = request.args.get('area_code', '')
    phone_id, phone_number, error = buy_and_assign_number(biz['vapi_assistant_id'], area_code or None)
    
    if phone_id:
        c.execute("UPDATE businesses SET vapi_phone_id = ? WHERE id = ?", (phone_id, bid))
        db.commit()
        flash(f'✅ New number {phone_number} bought & assigned to {biz["name"]}!', 'success')
    else:
        if phone_number:
            flash(f'⚠️ Bought {phone_number} from Twilio but Vapi registration failed: {error}', 'error')
        else:
            flash(f'❌ Could not buy number: {error}', 'error')
        flash('💡 You can also buy numbers at https://dashboard.vapi.ai/phone-numbers and assign them manually.', 'info')
    
    return redirect(f'/admin/business/{bid}')

@app.route('/admin/create-business', methods=['POST'])
@admin_required
def create_business():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Business name required', 'error')
        return redirect('/admin?tab=create')
    
    bid = str(uuid.uuid4())[:12]
    cid = 'camp-' + bid
    industry = request.form.get('industry', 'general')
    plan = request.form.get('plan', 'starter')
    
    # Handle custom vs standard package
    if plan == 'custom':
        monthly_price = int(request.form.get('monthly_price', 0))
        calls_included = int(request.form.get('calls_included', 1000))
        features_desc = request.form.get('features_desc', 'Custom package')
        max_tokens = int(request.form.get('max_tokens', 200))
        voice_speed = request.form.get('voice_speed', '1.0')
        concurrency = int(request.form.get('concurrency', 5))
        plan_label = f"Custom - ${monthly_price}/mo"
    else:
        tier = PRICING_TIERS.get(plan, PRICING_TIERS['starter'])
        monthly_price = int(request.form.get('monthly_price', tier['price']))
        calls_included = tier['calls_included']
        features_desc = tier['features']
        max_tokens = int(request.form.get('max_tokens', 200))
        voice_speed = request.form.get('voice_speed', '1.0')
        concurrency = int(request.form.get('concurrency', 5))
        plan_label = plan  # keep the key for standard plans
    
    db = get_db()
    c = db.cursor()
    
    c.execute("""INSERT INTO businesses 
        (id, name, industry, phone_number, vapi_assistant_id, vapi_phone_id,
         script_template, knowledge_base, plan, monthly_price, status,
         max_tokens, voice_speed, concurrency, calls_included, features_desc, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, datetime('now'))""",
        (bid, name, industry, request.form.get('phone_number',''),
         None, None,
         request.form.get('script_template', f"You are a professional employee of {name}. Help them book more clients. You are a real person — never mention being AI, a robot, or software."),
         f"Industry: {industry}. Business: {name}.",
         plan_label, monthly_price,
         max_tokens, voice_speed, concurrency, calls_included, features_desc))
    
    c.execute("""INSERT INTO campaigns (id, business_id, status)
        VALUES (?, ?, 'idle')""", (cid, bid))
    
    db.commit()
    
    flash(f'✅ Business "<a href="/admin/business/{bid}" class="underline">{name}</a>" created! ID: <code>{bid}</code>', 'success')
    
    # Send email with login credentials
    try:
        send_business_email(bid, name, request.form.get('email', ''))
    except Exception as e:
        flash(f'Business created but email failed: {e}', 'error')
    
    return redirect(f'/admin?tab=businesses')

@app.route('/admin/update-email-config', methods=['POST'])
@admin_required
def update_email_config():
    config = {
        'host': request.form.get('smtp_host', ''),
        'port': request.form.get('smtp_port', '587'),
        'tls': request.form.get('smtp_tls', '1'),
        'email': request.form.get('smtp_email', ''),
        'password': request.form.get('smtp_password', ''),
    }
    with open('/root/voice-agent-manager/smtp_config.json', 'w') as f:
        json.dump(config, f)
    flash('✅ SMTP config saved!', 'success')
    return redirect('/admin?tab=email')

@app.route('/admin/test-email', methods=['POST'])
@admin_required
def test_email():
    to = request.form.get('test_to', '')
    if not to:
        flash('Email address required', 'error')
        return redirect('/admin?tab=email')
    try:
        send_email(to, '🧪 Diazites - Test Email',
            'This is a test email from your Diazites Admin.\\n\\nIf you received this, your SMTP configuration is working!')
        flash(f'✅ Test email sent to {to}!', 'success')
    except Exception as e:
        flash(f'❌ Failed: {e}', 'error')
    return redirect('/admin?tab=email')

def load_smtp_config():
    try:
        with open('/root/voice-agent-manager/smtp_config.json') as f:
            return json.load(f)
    except:
        return {'host': '', 'port': '587', 'tls': '1', 'email': '', 'password': ''}

def send_email(to, subject, body):
    """Send email — AgentMail first (verified working), Resend SMTP fallback."""
    # 1) AgentMail (proven path: appointment confirmations use it)
    try:
        key = os.environ.get("AGENTMAIL_API_KEY", "")
        if not key:
            for _p in ("/root/.env", "/root/voice-agent-manager/.env"):
                try:
                    with open(_p) as _f:
                        for _line in _f:
                            _line = _line.strip()
                            if _line.startswith("AGENTMAIL_API_KEY="):
                                key = _line.split("=", 1)[1].strip().strip('"').strip("'")
                                break
                except Exception:
                    continue
                if key:
                    break
        if key:
            payload = {"to": to, "subject": subject, "text": body}
            req = urllib.request.Request(
                "https://api.agentmail.to/v0/inboxes/aiworkers@agentmail.to/messages/send",
                data=json.dumps(payload).encode(),
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                         "User-Agent": "DiazitesAdmin/1.0"},
                method="POST")
            urllib.request.urlopen(req, timeout=15)
            print(f"📧 AgentMail: {subject} -> {to}")
            return
    except Exception as e:
        print(f"⚠️ AgentMail failed ({e}), falling back to SMTP")
    # 2) Resend SMTP fallback
    config = load_smtp_config()
    if not config.get('host') or not config.get('email'):
        raise Exception('SMTP not configured. Go to Email Config tab.')
    
    import smtplib
    from email.mime.text import MIMEText
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = config['email']
    msg['To'] = to
    
    port = int(config.get('port', 587))
    if port == 465:
        with smtplib.SMTP_SSL(config['host'], port, timeout=10) as server:
            if config.get('password'):
                smtp_user = 'resend' if 'resend' in config.get('host','') else config['email']
                server.login(smtp_user, config['password'])
            server.send_message(msg)
    else:
        with smtplib.SMTP(config['host'], port, timeout=10) as server:
            if config.get('tls') != '0':
                server.starttls()
            if config.get('password'):
                smtp_user = 'resend' if 'resend' in config.get('host','') else config['email']
                server.login(smtp_user, config['password'])
            server.send_message(msg)

def send_business_email(bid, biz_name, email_to):
    """Send welcome email to new business client."""
    if not email_to:
        return  # No email provided, skip
    dashboard_url = "https://diazites.online"
    subject = f"🎉 Welcome to Diazites - Your {biz_name} Dashboard"
    body = f"""
Hi {biz_name} Team,

Your AI voice agent has been created and is ready to go!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 YOUR LOGIN CREDENTIALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Dashboard URL: {dashboard_url}
Business ID:   {bid}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 GETTING STARTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to {dashboard_url}
2. Enter your Business ID: {bid}
3. Click "Access Dashboard"
4. Upload your leads (Leads tab)
5. Choose your AI voice (Settings tab)
6. Click "Start" to begin your campaign

Your AI agent will start calling prospects and booking appointments automatically.

Need help? Contact your account manager.

Best,
Diazites Team
"""
    send_email(email_to, subject, body)
    print(f"📧 Welcome email sent to {email_to} for {biz_name}")

@app.route('/admin/update-twilio', methods=['POST'])
@admin_required
def update_twilio():
    config = {
        'account_sid': request.form.get('account_sid', ''),
        'auth_token': request.form.get('auth_token', ''),
        'from_number': request.form.get('from_number', ''),
        'enabled': request.form.get('sms_enabled') == '1',
    }
    with open('/root/voice-agent-manager/twilio_config.json', 'w') as f:
        json.dump(config, f)
    flash('✅ SMS config saved!', 'success')
    return redirect('/admin?tab=sms')

def load_twilio_config():
    try:
        with open('/root/voice-agent-manager/twilio_config.json') as f:
            return json.load(f)
    except:
        return {'account_sid': '', 'auth_token': '', 'from_number': '', 'enabled': False}

@app.route('/admin/bulk-sms', methods=['POST'])
@admin_required
def admin_bulk_sms():
    """Send bulk SMS from admin: all leads, one business's leads, uploaded phone list, pasted numbers, or business owners."""
    message = (request.form.get('message', '') or '').strip()
    target = request.form.get('target', 'all')
    if not message:
        flash('❌ Message is required', 'danger')
        return redirect('/admin?tab=sms')

    from smsgate_sms import send_sms, _clean_phone

    db = get_db()
    c = db.cursor()
    recipients = []  # list of (phone, business_id, lead_id, name)

    if target == 'all':
        c.execute("SELECT id, phone, business_id, name FROM leads WHERE phone IS NOT NULL AND phone != ''")
        for r in c.fetchall():
            recipients.append((r[1], r[2], r[0], r[3]))
    elif target == 'business':
        bid = request.form.get('business_id', '')
        c.execute("SELECT id, phone, business_id, name FROM leads WHERE business_id = ? AND phone IS NOT NULL AND phone != ''", (bid,))
        for r in c.fetchall():
            recipients.append((r[1], r[2], r[0], r[3]))
    elif target == 'owners':
        c.execute("SELECT id, name, phone_number FROM businesses WHERE phone_number IS NOT NULL AND phone_number != ''")
        for r in c.fetchall():
            recipients.append((r[2], r[0], None, r[1]))
    elif target == 'paste':
        pasted = (request.form.get('pasted_numbers', '') or '')
        for line in pasted.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith('phone') or line.lower().startswith('number'):
                continue
            parts = [p.strip() for p in line.split(',')]
            cleaned = _clean_phone(parts[0])
            if cleaned:
                name = parts[1] if len(parts) > 1 else None
                recipients.append((cleaned, None, None, name))
    elif target == 'upload':
        f = request.files.get('phone_file')
        if not f or not f.filename:
            flash('❌ Please upload a phone list file', 'danger')
            return redirect('/admin?tab=sms')
        content = f.read().decode('utf-8', errors='ignore')
        lines = content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith('phone') or line.lower().startswith('number'):
                continue
            parts = [p.strip() for p in line.split(',')]
            phone = parts[0]
            cleaned = _clean_phone(phone)
            if cleaned:
                name = parts[1] if len(parts) > 1 else None
                recipients.append((cleaned, None, None, name))

    # Dedupe by phone (keep first name found)
    seen = set()
    deduped = []
    for phone, bid, lid, name in recipients:
        cleaned = _clean_phone(phone)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            deduped.append((cleaned, bid, lid, name))
    db.close()

    if not deduped:
        flash('❌ No valid phone numbers found', 'danger')
        return redirect('/admin?tab=sms')

    # Personalization: replace {name} / {business} per recipient
    def personalize(msg, name, bid):
        m = msg.replace('{name}', (name or 'there').strip() or 'there')
        if '{business}' in m:
            biz_name = ''
            if bid:
                try:
                    bdb = sqlite3.connect('/root/voice-agent-businesses.db')
                    row = bdb.execute("SELECT name FROM businesses WHERE id = ?", (bid,)).fetchone()
                    if row:
                        biz_name = row[0] or ''
                    bdb.close()
                except:
                    pass
            m = m.replace('{business}', biz_name or 'your business')
        return m

    # Send with small delay between messages
    sent, failed = 0, 0
    errors = []
    for i, (phone, bid, lid, name) in enumerate(deduped):
        try:
            final_msg = personalize(message, name, bid)
            ok = send_sms(phone, final_msg, business_id=bid, lead_id=lid)
            if ok:
                sent += 1
            else:
                failed += 1
                errors.append(phone)
        except Exception as e:
            failed += 1
            errors.append(phone)
        if i < len(deduped) - 1:
            time.sleep(1)  # rate-limit: ~1 msg/sec

    if failed:
        flash(f'✅ Sent {sent} / {len(deduped)} SMS. {failed} failed.', 'success')
    else:
        flash(f'✅ Sent {sent} SMS to all {len(deduped)} recipients!', 'success')
    return redirect('/admin?tab=sms')

@app.route('/admin/bulk-sms-preview', methods=['POST'])
@admin_required
def admin_bulk_sms_preview():
    """Count recipients for a bulk SMS target WITHOUT sending (JS preview)."""
    target = request.form.get('target', 'all')
    from smsgate_sms import _clean_phone
    db = get_db()
    c = db.cursor()
    numbers = []

    if target == 'all':
        c.execute("SELECT phone FROM leads WHERE phone IS NOT NULL AND phone != ''")
        numbers = [r[0] for r in c.fetchall()]
    elif target == 'business':
        bid = request.form.get('business_id', '')
        c.execute("SELECT phone FROM leads WHERE business_id = ? AND phone IS NOT NULL AND phone != ''", (bid,))
        numbers = [r[0] for r in c.fetchall()]
    elif target == 'owners':
        c.execute("SELECT phone_number FROM businesses WHERE phone_number IS NOT NULL AND phone_number != ''")
        numbers = [r[0] for r in c.fetchall()]
    elif target == 'paste':
        pasted = (request.form.get('pasted_numbers', '') or '')
        for line in pasted.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(',')]
            cleaned = _clean_phone(parts[0])
            if cleaned:
                numbers.append(cleaned)
    elif target == 'upload':
        f = request.files.get('phone_file')
        if f and f.filename:
            content = f.read().decode('utf-8', errors='ignore')
            for line in content.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
                line = line.strip()
                if not line or line.lower().startswith(('phone', 'number')):
                    continue
                cleaned = _clean_phone(line.split(',')[0].strip())
                if cleaned:
                    numbers.append(cleaned)
    db.close()

    # Dedupe + validate
    seen = set()
    valid = []
    for n in numbers:
        cleaned = _clean_phone(n)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            valid.append(cleaned)

    return jsonify({'count': len(valid), 'sample': valid[:5]})

@app.route('/admin/sms-inbox', methods=['GET'])
@admin_required
def admin_sms_inbox():
    """Admin view: ALL incoming + outgoing SMS across every business (reply center)."""
    db = get_db()
    db.row_factory = sqlite3.Row
    c = db.cursor()
    inc = []
    try:
        c.execute("""SELECT i.*, b.name as biz_name FROM incoming_sms i
                     LEFT JOIN businesses b ON i.business_id = b.id
                     ORDER BY i.received_at DESC LIMIT 200""")
        inc = [dict(r) for r in c.fetchall()]
    except Exception:
        inc = []
    out = []
    try:
        c.execute("""SELECT o.*, b.name as biz_name FROM outgoing_sms o
                     LEFT JOIN businesses b ON o.business_id = b.id
                     ORDER BY o.sent_at DESC LIMIT 200""")
        out = [dict(r) for r in c.fetchall()]
    except Exception:
        out = []
    db.close()

    merged = []
    for m in inc:
        merged.append({'id': m['id'], 'direction': 'IN', 'which': 'in',
                       'number': m.get('sender') or m.get('recipient') or '',
                       'body': m.get('body') or '', 'time': m.get('received_at') or '',
                       'biz': m.get('biz_name') or m.get('business_id') or '—',
                       'lead_id': m.get('lead_id'), 'saved': m.get('saved', 0)})
    for m in out:
        merged.append({'id': m['id'], 'direction': 'OUT', 'which': 'out',
                       'number': m.get('phone') or m.get('recipient') or '',
                       'body': m.get('body') or '', 'time': m.get('sent_at') or '',
                       'biz': m.get('biz_name') or m.get('business_id') or '—',
                       'lead_id': m.get('lead_id'), 'saved': m.get('saved', 0)})
    merged.sort(key=lambda x: x['time'] or '', reverse=True)
    return jsonify({'messages': merged[:200], 'total': len(merged)})

@app.route('/admin/sms-reply', methods=['POST'])
@admin_required
def admin_sms_reply():
    """Admin replies to any SMS thread. Sends via sms-gate.app, logged to outgoing_sms."""
    to_phone = (request.form.get('to', '') or '').strip()
    message = (request.form.get('message', '') or '').strip()
    business_id = (request.form.get('business_id', '') or '').strip() or None
    if not to_phone or not message:
        return jsonify({'success': False, 'error': 'to and message required'}), 400
    from smsgate_sms import send_sms, _clean_phone
    cleaned = _clean_phone(to_phone)
    # Try to attach a lead if this is a known number for that business
    lead_id = None
    if business_id:
        try:
            db = get_db()
            db.row_factory = sqlite3.Row
            c = db.cursor()
            c.execute("SELECT id FROM leads WHERE business_id = ? AND phone = ? LIMIT 1", (business_id, cleaned))
            row = c.fetchone()
            if row:
                lead_id = row['id']
            db.close()
        except Exception:
            pass
    try:
        ok = send_sms(cleaned, message, business_id=business_id, lead_id=lead_id)
        if ok:
            return jsonify({'success': True, 'message': 'Reply sent'})
        return jsonify({'success': False, 'error': 'SMS provider failed to queue reply'}), 502
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/update-stripe', methods=['POST'])
@admin_required
def update_stripe():
    from premium_features import save_stripe_config, load_stripe_config
    config = {
        'secret_key': request.form.get('secret_key', ''),
        'publishable_key': request.form.get('publishable_key', ''),
        'webhook_secret': request.form.get('webhook_secret', ''),
        'enabled': request.form.get('stripe_enabled') == '1',
    }
    save_stripe_config(config)
    flash('✅ Stripe config saved!', 'success')
    return redirect('/admin?tab=stripe')

GA_CONFIG_PATH = "/root/voice-agent-manager/ga_config.json"

def load_ga_config():
    try:
        with open(GA_CONFIG_PATH) as f:
            cfg = json.load(f)
        return {'ga_id': cfg.get('ga_id', ''), 'sc_key': cfg.get('sc_key', '')}
    except Exception:
        return {'ga_id': '', 'sc_key': ''}

@app.route('/admin/update-ga-config', methods=['POST'])
@admin_required
def update_ga_config():
    cfg = {
        'ga_id': request.form.get('ga_id', '').strip(),
        'sc_key': request.form.get('sc_key', '').strip(),
    }
    with open(GA_CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)
    flash('✅ Analytics config saved!', 'success')
    return redirect('/admin?tab=analytics')

def load_stripe_config():
    from premium_features import load_stripe_config as lsc
    return lsc()

@app.route('/admin/agent-tars-run', methods=['POST'])
@admin_required
def agent_tars_run():
    task = request.form.get('task', '').strip()
    if not task:
        flash('❌ Please enter a task', 'error')
        return redirect('/admin?tab=agent-tars')
    
    import subprocess, datetime, os, signal
    config_path = '/root/voice-agent-manager/agent-tars.config.json'
    
    # Store task + mark as processing
    with open('/dev/shm/tars_status.json', 'w') as f:
        json.dump({'status': 'processing', 'task': task[:100], 'time': datetime.datetime.now().strftime('%H:%M:%S')}, f)
    if os.path.exists('/dev/shm/tars_result.json'):
        os.remove('/dev/shm/tars_result.json')
    
    def run_tars_task(task_text, cfg_path):
        try:
            # Kill any leftover TARS port holders
            for p in ['8899', '8900']:
                subprocess.run(['fuser', '-k', f'{p}/tcp'], capture_output=True, timeout=5)
            
            result = subprocess.run(
                ['agent-tars', '--headless', '--input', task_text, '--format', 'text', '--config', cfg_path, '--port', '8900'],
                capture_output=True, text=True, timeout=180
            )
            output = result.stdout.strip() or result.stderr.strip() or 'No output'
            with open('/dev/shm/tars_result.json', 'w') as f:
                json.dump({'result': output, 'task': task_text[:100], 'time': datetime.datetime.now().strftime('%H:%M:%S')}, f)
            with open('/dev/shm/tars_status.json', 'w') as f:
                json.dump({'status': 'done', 'task': task_text[:100], 'time': datetime.datetime.now().strftime('%H:%M:%S')}, f)
        except subprocess.TimeoutExpired:
            with open('/dev/shm/tars_status.json', 'w') as f:
                json.dump({'status': 'error', 'error': 'Task timed out after 180 seconds'}, f)
        except Exception as e:
            with open('/dev/shm/tars_status.json', 'w') as f:
                json.dump({'status': 'error', 'error': str(e)[:200]}, f)
    
    threading.Thread(target=run_tars_task, args=(task, config_path), daemon=True).start()
    
    flash('⏳ TARS task started in background. Refresh the page in a moment to see the result.', 'info')
    return redirect('/admin?tab=agent-tars')

@app.route('/admin/agent-tars-status')
@admin_required
def agent_tars_status():
    import shutil
    which = shutil.which('agent-tars') or 'not found'
    return render_template_string(f"""
    <!DOCTYPE html>
    <html><head><title>Agent TARS Status</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body{{background:#050508;color:#e2e8f0;font-family:Inter,sans-serif}}</style></head>
    <body class="p-8">
    <div class="max-w-2xl mx-auto">
        <a href="/admin?tab=agent-tars" class="text-[#818cf8] text-sm hover:underline mb-4 inline-block">&larr; Back</a>
        <h2 class="text-xl font-bold mb-6">🤖 Agent TARS — Server Status</h2>
        <div class="card space-y-3">
            <div class="flex justify-between"><span class="text-[#64748b]">Binary</span><span class="font-mono text-xs">{which}</span></div>
            <div class="flex justify-between"><span class="text-[#64748b]">Version</span><span class="font-mono text-xs">v0.3.0</span></div>
            <div class="flex justify-between"><span class="text-[#64748b]">Model</span><span class="font-mono text-xs">DeepSeek v4 Flash</span></div>
            <div class="flex justify-between"><span class="text-[#64748b]">Status</span><span class="text-green-400">✅ Ready</span></div>
        </div>
        <div class="card mt-6">
            <h3 class="font-bold mb-3">📋 Quick Test</h3>
            <p class="text-xs text-[#64748b] mb-3">Run a simple test to verify TARS is working:</p>
            <form method="POST" action="/admin/agent-tars-run">
                <input type="hidden" name="task" value="What is the current date and time? Just respond with the date.">
                <button class="btn-primary text-xs"><i class="fas fa-flask mr-1"></i> Run Test</button>
            </form>
        </div>
    </div>
    </body></html>
    """)


@app.route('/admin/api/search-leads')
@admin_required
def admin_api_search_leads():
    """Search existing leads database or return suggestions based on query."""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'results': [], 'error': 'No query provided'})
    
    results = []
    try:
        db = get_db()
        c = db.cursor()
        
        # Search existing leads first
        like_q = f'%{q}%'
        c.execute("""
            SELECT DISTINCT phone, name, business_name FROM leads 
            WHERE name LIKE ? OR business_name LIKE ? OR phone LIKE ?
            LIMIT 10
        """, (like_q, like_q, like_q))
        for row in c.fetchall():
            results.append({'name': row['name'] or row['business_name'] or 'Unknown', 
                           'phone': row['phone'] or '', 'address': '', 'url': ''})
        
        # Also search businesses that match the query type
        c.execute("""
            SELECT name, industry, id FROM businesses 
            WHERE name LIKE ? OR industry LIKE ?
            LIMIT 5
        """, (like_q, like_q))
        for row in c.fetchall():
            name = row['name'] or ''
            if name and not any(r['name'] == name for r in results):
                results.append({'name': f'{name} ({row["industry"] or "?"})',
                               'phone': '', 'address': '', 
                               'url': f'/admin/business/{row["id"]}', 
                               'is_business': True})
        
        return jsonify({'results': results, 
                        'note': f'Found {len(results)} from database. To find new leads, search on Google/Yelp in your browser and paste numbers below.'})
    except Exception as e:
        return jsonify({'results': [], 'error': str(e), 
                        'note': 'Search from database. Paste new leads manually below.'})


@app.route('/admin/api/update-tier', methods=['POST'])
@admin_required
def admin_api_update_tier():
    """Update a pricing tier configuration."""
    data = request.get_json(silent=True) or {}
    key = data.get('key', '')
    tier = data.get('tier', {})
    
    if not key or not tier:
        return jsonify({'success': False, 'error': 'Missing key or tier data'}), 400
    if key not in PRICING_TIERS:
        return jsonify({'success': False, 'error': f'Unknown tier: {key}'}), 400
    
    # Validate fields
    try:
        PRICING_TIERS[key] = {
            'name': str(tier.get('name', PRICING_TIERS[key]['name'])),
            'price': int(tier.get('price', PRICING_TIERS[key]['price'])),
            'calls_included': int(tier.get('calls_included', PRICING_TIERS[key]['calls_included'])),
            'minutes_limit': int(tier.get('minutes_limit', PRICING_TIERS[key].get('minutes_limit', 0))),
            'features': str(tier.get('features', PRICING_TIERS[key]['features'])),
        }
        # Save to file so it persists across restarts
        try:
            cfg_dir = '/root/voice-agent-manager'
            with open(os.path.join(cfg_dir, 'pricing_tiers.json'), 'w') as f:
                import json as j2
                j2.dump(PRICING_TIERS, f, indent=2)
        except Exception as e:
            print(f"Could not save tiers to file: {e}")
        
        return jsonify({'success': True, 'tier': PRICING_TIERS[key]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/api/change-plan', methods=['POST'])
@admin_required
def admin_api_change_plan():
    """Change a client's plan."""
    data = request.get_json(silent=True) or {}
    bid = data.get('business_id', '')
    plan = data.get('plan', '')
    
    if not bid or not plan:
        return jsonify({'success': False, 'error': 'Missing business_id or plan'}), 400
    if plan not in PRICING_TIERS:
        return jsonify({'success': False, 'error': f'Unknown plan: {plan}'}), 400
    
    db = get_db()
    c = db.cursor()
    tier = PRICING_TIERS[plan]
    c.execute("UPDATE businesses SET plan=?, monthly_price=? WHERE id=?",
              (plan, tier['price'], bid))
    db.commit()
    db.close()
    return jsonify({'success': True, 'plan': plan, 'price': tier['price']})


@app.route('/admin/api/add-minutes', methods=['POST'])
@admin_required
def admin_api_add_minutes():
    """Add extra minutes to a business."""
    data = request.get_json(silent=True) or {}
    bid = data.get('business_id', '')
    minutes = int(data.get('minutes', 0))
    
    if not bid or minutes <= 0:
        return jsonify({'success': False, 'error': 'Missing business_id or invalid minutes'}), 400
    
    db = get_db()
    c = db.cursor()
    
    # Ensure extra_minutes column exists
    try:
        c.execute("ALTER TABLE businesses ADD COLUMN extra_minutes INTEGER DEFAULT 0")
    except:
        pass
    
    c.execute("SELECT extra_minutes FROM businesses WHERE id=?", (bid,))
    row = c.fetchone()
    current = row[0] if row and row[0] else 0
    new_total = current + minutes
    c.execute("UPDATE businesses SET extra_minutes=? WHERE id=?", (new_total, bid))
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'extra_minutes': new_total, 'added': minutes})


@app.route('/admin/campaign/start', methods=['POST'])
@admin_required
def admin_campaign_start():
    """Start a campaign for a business (with optional leads)."""
    bid = request.form.get('business_id', '').strip()
    if not bid:
        flash('❌ Please select a business.', 'error')
        return redirect('/admin?tab=campaigns')
    
    leads_text = request.form.get('leads', '').strip()
    db = get_db()
    c = db.cursor()
    
    # Add leads if provided
    if leads_text:
        added = 0
        for line in leads_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            # Support formats: +phone, Name: +phone, Name,Business: +phone
            phone = line
            name = ''
            biz_name = ''
            if ':' in line:
                parts = line.split(':')
                name_biz = parts[0].strip()
                phone = parts[1].strip()
                if ',' in name_biz:
                    parts2 = [x.strip() for x in name_biz.split(',', 1)]
                    name = parts2[0]
                    biz_name = parts2[1] if len(parts2) > 1 else ''
                else:
                    name = name_biz
            # Clean phone
            phone = phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
            if not phone.startswith('+'):
                phone = '+1' + phone.lstrip('1')
            if len(phone) < 10:
                continue
            
            lid = f"lead_{uuid.uuid4().hex[:12]}"
            c.execute("INSERT OR IGNORE INTO leads (id, business_id, phone, name, business_name, state) VALUES (?,?,?,?,?,'NEW')",
                      (lid, bid, phone, name, biz_name))
            added += 1
        db.commit()
        flash(f'✅ {added} leads added!', 'success')
    
    # Check if there are leads now
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ? AND state = 'NEW'", (bid,))
    count = c.fetchone()[0]
    if count == 0:
        flash('❌ No leads to call! Add leads first.', 'error')
        return redirect('/admin?tab=campaigns')
    
    # Start the campaign via HTTP to main dashboard
    try:
        import requests
        r = requests.post('http://localhost:8085/campaign/start', 
                         data={}, timeout=5,
                         cookies={'session': session.get('_permanent', '')})
    except Exception as e:
        # Fallback: directly update DB and start thread
        c.execute("UPDATE campaigns SET status='running', started_at=datetime('now') WHERE business_id=?", (bid,))
        db.commit()
        c.execute("DELETE FROM campaign_log WHERE business_id=?", (bid,))
        db.commit()
    
    flash(f'🚀 Campaign started for {count} leads!', 'success')
    return redirect('/admin?tab=campaigns')

@app.route('/admin/campaign/start/<bid>', methods=['POST'])
@admin_required
def admin_campaign_start_bid(bid):
    """Start campaign for a specific business."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ? AND state = 'NEW'", (bid,))
    count = c.fetchone()[0]
    if count == 0:
        flash('❌ No leads to call!', 'error')
        return redirect('/admin?tab=campaigns')
    
    c.execute("UPDATE campaigns SET status='running', started_at=datetime('now') WHERE business_id=?", (bid,))
    db.commit()
    c.execute("DELETE FROM campaign_log WHERE business_id=?", (bid,))
    db.commit()
    flash(f'🚀 Campaign started for {count} leads!', 'success')
    return redirect('/admin?tab=campaigns')

@app.route('/admin/campaign/stop/<bid>', methods=['POST'])
@admin_required
def admin_campaign_stop(bid):
    """Stop campaign for a business."""
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE campaigns SET status='stopped' WHERE business_id=?", (bid,))
    db.commit()
    flash('⏹️ Campaign stopped.', 'info')
    return redirect('/admin?tab=campaigns')

@app.route('/admin/campaign/add-leads/<bid>', methods=['POST'])
@admin_required
def admin_campaign_add_leads(bid):
    """Add leads to a business campaign."""
    leads_text = request.form.get('leads', '').strip()
    if not leads_text:
        if request.form.get('redirect') == 'false':
            return jsonify({'success': False, 'message': 'No leads provided.'})
        flash('❌ No leads provided.', 'error')
        return redirect('/admin?tab=campaigns')
    
    db = get_db()
    c = db.cursor()
    added = 0
    for line in leads_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        phone = line
        name = ''
        biz_name = ''
        if ':' in line:
            parts = line.split(':')
            name_biz = parts[0].strip()
            phone = parts[1].strip()
            if ',' in name_biz:
                parts2 = [x.strip() for x in name_biz.split(',', 1)]
                name = parts2[0]
                biz_name = parts2[1] if len(parts2) > 1 else ''
            else:
                name = name_biz
        phone = phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not phone.startswith('+'):
            phone = '+1' + phone.lstrip('1')
        if len(phone) < 10:
            continue
        
        lid = f"lead_{uuid.uuid4().hex[:12]}"
        c.execute("INSERT OR IGNORE INTO leads (id, business_id, phone, name, business_name, state) VALUES (?,?,?,?,?,'NEW')",
                  (lid, bid, phone, name, biz_name))
        added += 1
    db.commit()
    
    # Check if AJAX request (redirect=false)
    if request.form.get('redirect') == 'false':
        return jsonify({'success': True, 'message': f'{added} leads added!'})
    
    flash(f'✅ {added} leads added to campaign!', 'success')
    return redirect('/admin?tab=campaigns')

@app.route('/admin/business/<bid>/update-settings', methods=['POST'])
@admin_required
def admin_business_update_settings(bid):
    """Update script template, knowledge base, or agent prompt for a business."""
    db = get_db()
    c = db.cursor()
    
    script = request.form.get('script_template', '').strip()
    kb = request.form.get('knowledge_base', '').strip()
    agent_prompt = request.form.get('agent_prompt', '').strip()
    
    if script:
        c.execute("UPDATE businesses SET script_template = ? WHERE id = ?", (script, bid))
    if kb:
        c.execute("UPDATE businesses SET knowledge_base = ? WHERE id = ?", (kb, bid))
    if agent_prompt:
        c.execute("UPDATE businesses SET agent_prompt = ? WHERE id = ?", (agent_prompt, bid))
    
    db.commit()
    flash('✅ Settings updated!', 'success')
    return redirect(f'/admin/business/{bid}')

def admin_dashboard():
    tab = request.args.get('tab', 'dashboard')
    db = get_db()
    c = db.cursor()
    
    # Stats
    c.execute("SELECT COUNT(*) FROM businesses")
    total_businesses = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'running'")
    active_campaigns = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM leads")
    total_leads = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(cost),0) FROM call_log")
    total_ai_cost = c.fetchone()[0]
    
    # Businesses with campaign data
    c.execute("""
        SELECT b.*, COALESCE(c.calls_made,0) as calls_made, 
               COALESCE(c.appointments_booked,0) as appointments_booked,
               COALESCE(c.total_cost,0) as total_cost,
               COALESCE(c.leads_imported,0) as leads_imported,
               c.status as campaign_status,
               (SELECT COUNT(*) FROM leads WHERE business_id = b.id AND state = 'NEW') as leads_count,
               (SELECT COALESCE(SUM(duration),0) FROM call_log WHERE business_id = b.id) as total_duration
        FROM businesses b
        LEFT JOIN campaigns c ON b.id = c.business_id
        ORDER BY b.created_at DESC
    """)
    businesses = [dict(r) for r in c.fetchall()]
    
    # Tier breakdown
    tier_breakdown = {'starter': 0, 'pro': 0, 'premium': 0, 'enterprise': 0}
    total_revenue = 0
    for biz in businesses:
        plan = biz.get('plan', 'starter')
        if plan in tier_breakdown:
            tier_breakdown[plan] = tier_breakdown.get(plan, 0) + 1
        price = int(biz.get('monthly_price') or PRICING_TIERS.get(plan, PRICING_TIERS['starter'])['price'])
        total_revenue += price
    
    # Recent activity
    c.execute("""
        SELECT cl.*, b.name FROM call_log cl
        LEFT JOIN businesses b ON cl.business_id = b.id
        ORDER BY cl.created_at DESC LIMIT 10
    """)
    recent_activity = [dict(r) for r in c.fetchall()]
    
    # Sub counts
    sub_counts = {k: 0 for k in PRICING_TIERS}
    for biz in businesses:
        p = biz.get('plan', 'starter')
        if p in sub_counts:
            sub_counts[p] += 1
    
    # VAPI numbers
    vapi_numbers = []
    vapi_assistant_count = 0
    try:
        r = subprocess.run(["curl","-s",f"{VAPI_BASE}/assistant",
            "-H",f"Authorization: Bearer {VAPI_API_KEY}"], capture_output=True, text=True)
        data = json.loads(r.stdout)
        if isinstance(data, dict): data = data.get('data', data)
        if isinstance(data, list): vapi_assistant_count = len(data)
    except: pass
    
    try:
        r = subprocess.run(["curl","-s",f"{VAPI_BASE}/phone-number",
            "-H",f"Authorization: Bearer {VAPI_API_KEY}"], capture_output=True, text=True)
        data = json.loads(r.stdout)
        if isinstance(data, list):
            vapi_numbers = [{'number':n.get('number','?'), 'name':n.get('name',''), 'provider':n.get('provider','?')} for n in data]
    except: pass
    
    # Chatbot settings
    chatbot_provider = 'xai'
    chatbot_model = ''
    chatbot_api_key = ''
    try:
        c.execute("SELECT key, value FROM settings WHERE key IN ('chatbot_provider','chatbot_model','chatbot_api_key')")
        for row in c.fetchall():
            if row[0] == 'chatbot_provider': chatbot_provider = row[1]
            elif row[0] == 'chatbot_model': chatbot_model = row[1]
            elif row[0] == 'chatbot_api_key': chatbot_api_key = '***' if row[1] else ''
    except: pass
    
    # All appointments across all businesses
    c.execute("""
        SELECT a.*, b.name as biz_name
        FROM appointments a
        LEFT JOIN businesses b ON a.business_id = b.id
        ORDER BY a.created_at DESC LIMIT 100
    """)
    all_appointments = [dict(r) for r in c.fetchall()]
    
    # Affiliates tab data
    c.execute("SELECT * FROM affiliates ORDER BY created_at DESC")
    affiliates = [dict(r) for r in c.fetchall()]
    c.execute("SELECT e.*, a.name as affiliate_name FROM affiliate_events e "
              "LEFT JOIN affiliates a ON e.affiliate_id = a.id ORDER BY e.created_at DESC LIMIT 200")
    affiliate_events = [dict(r) for r in c.fetchall()]
    c.execute("SELECT p.*, a.name as affiliate_name FROM affiliate_payouts p "
              "LEFT JOIN affiliates a ON p.affiliate_id = a.id ORDER BY p.created_at DESC")
    affiliate_payouts = [dict(r) for r in c.fetchall()]

    return render_template_string(ADMIN_HTML,
        session=session, tab=tab, businesses=businesses,
        industries=INDUSTRY_PRESETS, tiers=PRICING_TIERS,
        VAPI_API_KEY=VAPI_API_KEY, sub_counts=sub_counts,
        vapi_numbers=vapi_numbers, vapi_assistant_count=vapi_assistant_count,
        chatbot_provider=chatbot_provider, chatbot_model=chatbot_model, chatbot_api_key=chatbot_api_key,
        all_appointments=all_appointments,
        affiliates=affiliates, affiliate_events=affiliate_events, affiliate_payouts=affiliate_payouts,
        tars_result=json.load(open('/dev/shm/tars_result.json'))['result'] if os.path.exists('/dev/shm/tars_result.json') else None,
        tars_status=json.load(open('/dev/shm/tars_status.json')) if os.path.exists('/dev/shm/tars_status.json') else None,
        last_task=session.get('tars_last_task', ''),
            default_script="Premium AI employee for this business. Uses the Diazites voice framework — sounds like a real human with 10+ years of experience. Edit this to customize behavior.",
            stats={
            'total_businesses': total_businesses,
            'active_campaigns': active_campaigns,
            'total_leads': total_leads,
            'total_revenue': total_revenue,
            'total_ai_cost': total_ai_cost,
            'tier_breakdown': tier_breakdown
        },
        recent_activity=recent_activity,
        smtp_config=load_smtp_config(),
        twilio_config=load_twilio_config(),
        stripe_config=load_stripe_config(),
        ga_config=load_ga_config(),
        **admin_extra_data(tab))

@app.route('/admin/affiliates/pay', methods=['POST'])
@admin_required
def admin_affiliate_pay():
    event_id = request.form.get('event_id', '')
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE affiliate_events SET status='paid', paid_at=datetime('now') WHERE id=? AND event_type='signup'", (event_id,))
    db.commit()
    db.close()
    flash('💰 Commission marked as paid!', 'success')
    return redirect('/admin?tab=affiliates')


@app.route('/admin/affiliates/rate', methods=['POST'])
@admin_required
def admin_affiliate_rate():
    aid = request.form.get('affiliate_id', '')
    try:
        rate = float(request.form.get('rate', 50))
    except (TypeError, ValueError):
        rate = 50
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE affiliates SET commission_per_signup=? WHERE id=?", (rate, aid))
    db.commit()
    db.close()
    flash(f'✅ Commission rate set to ${rate:.0f}', 'success')
    return redirect('/admin?tab=affiliates')


@app.route('/admin/affiliates/toggle', methods=['POST'])
@admin_required
def admin_affiliate_toggle():
    aid = request.form.get('affiliate_id', '')
    db = get_db()
    c = db.cursor()
    row = c.execute("SELECT status FROM affiliates WHERE id=?", (aid,)).fetchone()
    if row:
        new_status = 'inactive' if row[0] == 'active' else 'active'
        c.execute("UPDATE affiliates SET status=? WHERE id=?", (new_status, aid))
        db.commit()
    db.close()
    flash('✅ Affiliate status updated', 'success')
    return redirect('/admin?tab=affiliates')


@app.route('/admin/affiliates/payout-pay', methods=['POST'])
@admin_required
def admin_affiliate_payout_pay():
    payout_id = request.form.get('payout_id', '')
    db = get_db()
    c = db.cursor()
    row = c.execute("SELECT affiliate_id, amount FROM affiliate_payouts WHERE id=?", (payout_id,)).fetchone()
    if row:
        c.execute("UPDATE affiliate_payouts SET status='paid', paid_at=datetime('now') WHERE id=?", (payout_id,))
        c.execute("UPDATE affiliate_events SET status='paid', paid_at=datetime('now') "
                  "WHERE affiliate_id=? AND event_type='signup' AND status='pending'", (row[0],))
        db.commit()
        flash(f'💸 Payout of ${float(row[1]):.0f} settled — commissions marked paid!', 'success')
    else:
        flash('Payout not found', 'error')
    db.close()
    return redirect('/admin?tab=affiliates')


@app.route('/admin/affiliates/delete', methods=['POST'])
@admin_required
def admin_affiliate_delete():
    aid = request.form.get('affiliate_id', '')
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM affiliate_events WHERE affiliate_id=?", (aid,))
    c.execute("DELETE FROM affiliate_payouts WHERE affiliate_id=?", (aid,))
    c.execute("DELETE FROM affiliates WHERE id=?", (aid,))
    db.commit()
    db.close()
    flash('🗑️ Affiliate + all events/payouts deleted', 'success')
    return redirect('/admin?tab=affiliates')


@app.route('/admin/affiliates/mark-all-paid', methods=['POST'])
@admin_required
def admin_affiliate_mark_all_paid():
    aid = request.form.get('affiliate_id', '')
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE affiliate_events SET status='paid', paid_at=datetime('now') "
              "WHERE affiliate_id=? AND event_type='signup' AND status='pending'", (aid,))
    c.execute("UPDATE affiliate_payouts SET status='paid', paid_at=datetime('now') "
              "WHERE affiliate_id=? AND status='pending'", (aid,))
    db.commit()
    db.close()
    flash('✅ All pending commissions + payouts marked paid', 'success')
    return redirect('/admin?tab=affiliates')


@app.route('/admin/affiliates/delete-event', methods=['POST'])
@admin_required
def admin_affiliate_delete_event():
    eid = request.form.get('event_id', '')
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM affiliate_events WHERE id=?", (eid,))
    db.commit()
    db.close()
    flash('🗑️ Event deleted', 'success')
    return redirect('/admin?tab=affiliates')


@app.route('/admin/affiliates/delete-payout', methods=['POST'])
@admin_required
def admin_affiliate_delete_payout():
    pid = request.form.get('payout_id', '')
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM affiliate_payouts WHERE id=?", (pid,))
    db.commit()
    db.close()
    flash('🗑️ Payout request deleted', 'success')
    return redirect('/admin?tab=affiliates')


@app.route('/admin/update-chatbot', methods=['POST'])
@admin_required
def update_chatbot():
    db = get_db()
    c = db.cursor()
    
    provider = request.form.get('chatbot_provider', 'xai')
    model = request.form.get('chatbot_model', '').strip()
    api_key = request.form.get('chatbot_api_key', '').strip()
    
    # Only update if a new key is provided (don't overwrite with masked ***)
    if api_key and api_key != '***':
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('chatbot_api_key', ?)", (api_key,))
    
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('chatbot_provider', ?)", (provider,))
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('chatbot_model', ?)", (model,))
    db.commit()
    
    flash(f'✅ Chatbot settings saved! Provider: {provider}', 'success')
    return redirect('/admin?tab=chatbot')

# ============================================================
# NEW ADMIN FEATURES (MRR, Coupons, Trials, Usage, Scoreboard,
# Transcripts, Health, Broadcast, Backup, Inbox, Costs, A/B, Audit, 2FA)
# ============================================================

import shutil, threading, base64, io as _io
import datetime as _dt

PLAN_LIMITS = {'starter': 500, 'pro': 2000, 'premium': 10000, 'enterprise': 99999}
PLAN_PRICES = {'starter': 97, 'pro': 197, 'premium': 497, 'enterprise': 0}
VOICE_COST_PER_MIN = 0.12
SMS_AI_COST_PER_MSG = 0.006
BACKUP_DIR = "/root/voice-agent-manager/backups"
TWOFA_PATH = "/root/voice-agent-manager/admin_2fa.json"


def _2fa_hash(code):
    return hashlib.sha256(code.encode()).hexdigest()


def _2fa_normalize(code):
    """Normalize a code for comparison: strip spaces/dashes, uppercase."""
    return ''.join(ch for ch in code.strip().upper() if ch.isalnum())


def _gen_backup_codes(n=10):
    import secrets
    codes = []
    for _ in range(n):
        hx = secrets.token_hex(3).upper()
        codes.append(f"{hx[:3]}-{hx[3:]}")
    return codes


def load_2fa():
    try:
        with open(TWOFA_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_2fa(d):
    with open(TWOFA_PATH, 'w') as f:
        json.dump(d, f)


def verify_2fa(code, d=None, consume=False):
    """Verify a TOTP code OR a (hashed) backup code. Backup codes are one-time."""
    import pyotp
    d = d if d is not None else load_2fa()
    if not d.get('enabled'):
        return False
    norm = _2fa_normalize(code)
    if d.get('secret'):
        try:
            if pyotp.TOTP(d['secret']).verify(norm):
                return True
        except Exception:
            pass
    h = _2fa_hash(norm)
    hashes = d.get('backup_codes') or []
    if h in hashes:
        if consume:
            hashes.remove(h)
            d['backup_codes'] = hashes
            save_2fa(d)
        return True
    return False


def _load_env_keys():
    """Load /root/.env + manager .env into os.environ (idempotent)."""
    for p in ("/root/.env", "/root/voice-agent-manager/.env"):
        try:
            for line in open(p):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except Exception:
            pass


def init_tables():
    db = sqlite3.connect(DB_PATH)
    db.execute("CREATE TABLE IF NOT EXISTS script_variants (id INTEGER PRIMARY KEY AUTOINCREMENT, business_id TEXT, name TEXT, script TEXT, active INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    db.execute("CREATE TABLE IF NOT EXISTS call_flags (call_id TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    db.execute("CREATE TABLE IF NOT EXISTS admin_audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, detail TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    db.commit()
    db.close()


def audit(action, detail=""):
    try:
        init_tables()
        db = sqlite3.connect(DB_PATH)
        db.execute("INSERT INTO admin_audit_log (action, detail) VALUES (?,?)", (action, str(detail)[:500]))
        db.commit()
        db.close()
    except Exception:
        pass


def get_stripe_key():
    try:
        with open("/root/voice-agent-manager/stripe_config.json") as f:
            return json.load(f).get("secret_key", "")
    except Exception:
        return ""


def get_mrr_data():
    base = {'mrr': 0, 'active': 0, 'churn': 0, 'dunning': [], 'by_plan': []}
    key = get_stripe_key()
    if not key:
        try:
            db = sqlite3.connect(DB_PATH)
            base['active'] = db.execute("SELECT COUNT(*) FROM businesses WHERE stripe_subscription_id IS NOT NULL AND stripe_subscription_id != ''").fetchone()[0]
            db.close()
        except Exception:
            pass
        return base
    try:
        import stripe as stripe_lib
        stripe_lib.api_key = key
        subs = stripe_lib.Subscription.list(status='active', limit=100)
        trialing = stripe_lib.Subscription.list(status='trialing', limit=100)
        mrr = 0
        by_plan = {}
        for s in list(subs.data) + list(trialing.data):
            for it in (s.get('items') or {}).get('data', []):
                price = it.get('price') or {}
                amt = (price.get('unit_amount') or 0) / 100
                interval = ((price.get('recurring') or {}).get('interval') or 'month')
                if interval == 'year':
                    amt /= 12
                mrr += amt
                nick = price.get('nickname') or 'other'
                by_plan[nick] = by_plan.get(nick, 0) + amt
        # dunning
        invs = stripe_lib.Invoice.list(status='open', limit=100)
        dunning = []
        for inv in invs.data:
            if inv.get('status') in ('open', 'past_due', 'uncollectible'):
                dunning.append({
                    'customer': inv.get('customer_email') or inv.get('customer') or '?',
                    'amount': round((inv.get('amount_due') or 0) / 100, 2),
                    'status': inv.get('status'),
                    'due': _dt.datetime.fromtimestamp(inv.get('created') or 0).strftime('%Y-%m-%d'),
                })
        # churn: canceled last 30d / (active+canceled)
        try:
            cutoff = int(_dt.datetime.now().timestamp()) - 30 * 86400
            canceled = stripe_lib.Subscription.list(status='canceled', created={'gte': cutoff}, limit=100)
            churn = len(canceled.data) / max(1, len(subs.data) + len(canceled.data))
        except Exception:
            churn = 0
        return {'mrr': round(mrr), 'active': len(subs.data), 'churn': churn,
                'dunning': dunning, 'by_plan': [{'plan': k, 'count': 0, 'mrr': round(v)} for k, v in by_plan.items()]}
    except Exception as e:
        base['error'] = str(e)
        return base


def get_coupons():
    key = get_stripe_key()
    if not key:
        return []
    try:
        import stripe as stripe_lib
        stripe_lib.api_key = key
        codes = stripe_lib.PromotionCode.list(limit=50)
        out = []
        for c in codes.data:
            coup = c.get('coupon') or {}
            pct = coup.get('percent_off')
            out.append({
                'code': c.get('code'),
                'discount': f"{pct}%" if pct else f"${(coup.get('amount_off') or 0) / 100:.0f}",
                'redeemed': c.get('times_redeemed') or 0,
                'max': c.get('max_redemptions'),
                'active': bool(c.get('active')) and bool(coup.get('valid', True)),
            })
        return out
    except Exception:
        return []


def get_trials():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT id, name, plan, trial_end, owner_phone, email FROM businesses WHERE trial_end IS NOT NULL AND trial_end != ''").fetchall()
    db.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            te = _dt.datetime.fromisoformat(str(d['trial_end']).replace('Z', ''))
        except Exception:
            continue
        d['trial_end'] = te.strftime('%Y-%m-%d')
        d['days_left'] = (te - _dt.datetime.now()).days
        out.append(d)
    out.sort(key=lambda x: x['days_left'])
    return out


def get_usage():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT id, name, plan FROM businesses").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        used_secs = db.execute("SELECT COALESCE(SUM(duration),0) FROM call_log WHERE business_id=? AND created_at > datetime('now','start of month')", (d['id'],)).fetchone()[0] or 0
        used_min = int(used_secs / 60)
        limit = PLAN_LIMITS.get((d['plan'] or 'starter').lower(), 500)
        out.append({'id': d['id'], 'name': d['name'], 'plan': d['plan'] or 'starter', 'limit': limit,
                    'used': used_min, 'pct': min(100, int(used_min / limit * 100) if limit else 0)})
    db.close()
    return out


def get_scoreboard():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT id, name FROM businesses").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        calls = db.execute("SELECT COUNT(*) FROM call_log WHERE business_id=?", (d['id'],)).fetchone()[0]
        answered = db.execute("SELECT COUNT(*) FROM call_log WHERE business_id=? AND duration > 10", (d['id'],)).fetchone()[0]
        try:
            bookings = db.execute("SELECT COUNT(*) FROM appointments WHERE business_id=?", (d['id'],)).fetchone()[0]
        except Exception:
            bookings = 0
        out.append({
            'name': d['name'], 'calls': calls, 'answered': answered,
            'answer_rate': round(answered / calls * 100) if calls else 0,
            'bookings': bookings,
            'booking_rate': round(bookings / calls * 100) if calls else 0,
        })
    db.close()
    out.sort(key=lambda x: x['bookings'], reverse=True)
    return out


def get_transcripts(q=None):
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    if q:
        rows = db.execute("SELECT cl.*, b.name as biz FROM call_log cl JOIN businesses b ON cl.business_id=b.id WHERE cl.transcript LIKE ? ORDER BY cl.created_at DESC LIMIT 50", (f"%{q}%",)).fetchall()
    else:
        rows = db.execute("SELECT cl.*, b.name as biz FROM call_log cl JOIN businesses b ON cl.business_id=b.id WHERE cl.transcript IS NOT NULL AND cl.transcript != '' ORDER BY cl.created_at DESC LIMIT 50").fetchall()
    db.close()
    flags = set()
    try:
        fdb = sqlite3.connect(DB_PATH)
        flags = set(r[0] for r in fdb.execute("SELECT call_id FROM call_flags").fetchall())
        fdb.close()
    except Exception:
        pass
    return [dict(r, flagged=r['id'] in flags) for r in rows]


def get_health():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT id, name, vapi_assistant_id, vapi_phone_id, knowledge_base, script_template, trial_end, stripe_subscription_id, plan FROM businesses").fetchall()
    db.close()
    out = []
    for r in rows:
        d = dict(r)
        d['assistant'] = bool(d.get('vapi_assistant_id'))
        d['phone'] = bool(d.get('vapi_phone_id'))
        d['kb'] = bool(d.get('knowledge_base'))
        d['script'] = bool(d.get('script_template'))
        d['webhook'] = bool(d.get('vapi_assistant_id'))
        d['payment'] = bool(d.get('stripe_subscription_id')) or bool(d.get('trial_end'))
        d['score'] = sum([d['assistant'], d['phone'], d['kb'], d['script'], d['webhook'], d['payment']])
        out.append(d)
    return out


def get_backup_files():
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        files = []
        for fn in sorted(os.listdir(BACKUP_DIR), reverse=True)[:10]:
            fp = os.path.join(BACKUP_DIR, fn)
            files.append({'name': fn, 'size': f"{os.path.getsize(fp) / 1048576:.1f} MB"})
        return files
    except Exception:
        return []


def get_inbox():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            "SELECT 'in' as direction, business_id, phone, body, created_at FROM incoming_sms "
            "UNION ALL SELECT 'out' as direction, business_id, phone, body, created_at FROM outgoing_sms "
            "ORDER BY created_at DESC LIMIT 100").fetchall()
        biz_names = {r['id']: r['name'] for r in db.execute("SELECT id, name FROM businesses").fetchall()}
    except Exception:
        rows = []
        biz_names = {}
    db.close()
    out = []
    for r in rows:
        d = dict(r)
        d['biz'] = biz_names.get(d.get('business_id'), '?')
        out.append(d)
    return out


def get_costs():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT id, name, plan FROM businesses").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        mins = (db.execute("SELECT COALESCE(SUM(duration),0)/60.0 FROM call_log WHERE business_id=?", (d['id'],)).fetchone()[0] or 0)
        try:
            sms_n = db.execute("SELECT COUNT(*) FROM outgoing_sms WHERE business_id=? AND created_at > datetime('now','start of month')", (d['id'],)).fetchone()[0]
        except Exception:
            sms_n = 0
        voice = mins * VOICE_COST_PER_MIN
        sms_cost = sms_n * SMS_AI_COST_PER_MSG
        total = voice + sms_cost
        price = PLAN_PRICES.get((d['plan'] or 'starter').lower(), 0)
        out.append({'name': d['name'], 'price': price, 'voice_cost': round(voice, 2),
                    'sms_cost': round(sms_cost, 2), 'total': round(total, 2), 'margin': round(price - total, 2)})
    db.close()
    return out


def get_abtests():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM script_variants ORDER BY created_at DESC LIMIT 50").fetchall()
    biz_names = {r['id']: r['name'] for r in db.execute("SELECT id, name FROM businesses").fetchall()}
    out = []
    for r in rows:
        d = dict(r)
        d['biz'] = biz_names.get(d['business_id'], '?')
        calls = db.execute("SELECT COUNT(*) FROM call_log WHERE business_id=?", (d['business_id'],)).fetchone()[0]
        try:
            bookings = db.execute("SELECT COUNT(*) FROM appointments WHERE business_id=?", (d['business_id'],)).fetchone()[0]
        except Exception:
            bookings = 0
        d['calls'] = calls
        d['bookings'] = bookings
        d['rate'] = round(bookings / calls * 100) if calls else None
        out.append(d)
    db.close()
    return out


def get_audit():
    try:
        init_tables()
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT action, detail, created_at FROM admin_audit_log ORDER BY id DESC LIMIT 200").fetchall()
        db.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_twofa():
    try:
        with open(TWOFA_PATH) as f:
            d = json.load(f)
        bcount = len(d.get('backup_codes') or [])
        if d.get('enabled'):
            return {'enabled': True, 'backup_count': bcount}
        if d.get('secret'):
            try:
                import qrcode
                from pyotp import totp
                uri = totp.TOTP(d['secret']).provisioning_uri(name='Diazites Admin', issuer_name='Diazites')
                img = qrcode.make(uri)
                buf = _io.BytesIO()
                img.save(buf, format='PNG')
                qr = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
                return {'enabled': False, 'secret': d['secret'], 'qr': qr, 'backup_count': bcount}
            except Exception:
                return {'enabled': False, 'secret': d['secret'], 'backup_count': bcount}
    except Exception:
        pass
    return {'enabled': False, 'backup_count': 0}


def admin_extra_data(tab):
    init_tables()
    data = {}
    if tab == 'mrr':
        data['mrr'] = get_mrr_data()
    elif tab == 'coupons':
        data['coupons'] = get_coupons()
    elif tab == 'trials':
        data['trials'] = get_trials()
    elif tab == 'usage':
        data['usage_rows'] = get_usage()
    elif tab == 'scoreboard':
        data['score_rows'] = get_scoreboard()
    elif tab == 'transcripts':
        q = request.args.get('q', '').strip()
        data['tx_query'] = q
        data['tx_rows'] = get_transcripts(q)
    elif tab == 'health':
        data['health_rows'] = get_health()
    elif tab == 'backup':
        data['backup_files'] = get_backup_files()
    elif tab == 'inbox':
        data['inbox_rows'] = get_inbox()
    elif tab == 'costs':
        data['cost_rows'] = get_costs()
    elif tab == 'abtest':
        data['ab_rows'] = get_abtests()
    elif tab == 'audit':
        data['audit_rows'] = get_audit()
    elif tab == 'security':
        data['twofa'] = get_twofa()
    elif tab == 'reviews-ai':
        import review_ai
        data.update(review_ai.tab_data())
    if tab in ('broadcast', 'abtest'):
        data['health_rows'] = get_health()
    return data


@app.route('/admin/coupon-create', methods=['POST'])
@admin_required
def admin_coupon_create():
    name = request.form.get('name', '').strip()
    percent = int(request.form.get('percent', 50) or 50)
    duration = int(request.form.get('duration', 1) or 1)
    code = request.form.get('code', '').strip().upper()
    key = get_stripe_key()
    if not key:
        flash('❌ Stripe not configured', 'error')
        return redirect('/admin?tab=coupons')
    try:
        import stripe as stripe_lib
        stripe_lib.api_key = key
        coup = stripe_lib.Coupon.create(percent_off=percent, duration='repeating', duration_in_months=duration, name=name)
        promo = stripe_lib.PromotionCode.create(coupon=coup['id'], code=code or None)
        audit('coupon_create', f"{promo.get('code')} -{percent}% x{duration}mo")
        flash(f"✅ Coupon {promo.get('code')} created (-{percent}%)", 'success')
    except Exception as e:
        flash(f'❌ Stripe error: {str(e)[:120]}', 'error')
    return redirect('/admin?tab=coupons')


@app.route('/admin/trial-extend/<bid>', methods=['POST'])
@admin_required
def admin_trial_extend(bid):
    db = sqlite3.connect(DB_PATH)
    row = db.execute("SELECT name, trial_end, stripe_subscription_id FROM businesses WHERE id=?", (bid,)).fetchone()
    try:
        new_end = (_dt.datetime.now() + _dt.timedelta(days=7)).isoformat()
        if row and row[1]:
            try:
                new_end = (_dt.datetime.fromisoformat(str(row[1]).replace('Z', '')) + _dt.timedelta(days=7)).isoformat()
            except Exception:
                pass
        db.execute("UPDATE businesses SET trial_end=? WHERE id=?", (new_end, bid))
        db.commit()
        if row and row[2]:
            try:
                import stripe as stripe_lib
                stripe_lib.api_key = get_stripe_key()
                stripe_lib.Subscription.modify(row[2], trial_end=int(_dt.datetime.fromisoformat(new_end.replace('Z', '')).timestamp()))
            except Exception:
                pass
        audit('trial_extend', f"{row[0] if row else bid} +7d")
        flash('✅ Trial extended 7 days', 'success')
    except Exception as e:
        flash(f'❌ {str(e)[:100]}', 'error')
    db.close()
    return redirect('/admin?tab=trials')


@app.route('/admin/trial-nudge/<bid>', methods=['POST'])
@admin_required
def admin_trial_nudge(bid):
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT name, owner_phone, email FROM businesses WHERE id=?", (bid,)).fetchone()
    db.close()
    if not row:
        flash('❌ Business not found', 'error')
        return redirect('/admin?tab=trials')
    _load_env_keys()
    msg = f"Hi {row['name']}! Your Diazites AI voice agent trial is ending soon. Upgrade to keep your number & agent active: diazites.online"
    sent = False
    try:
        from smsgate_sms import send_sms
        if row['owner_phone']:
            send_sms(row['owner_phone'], msg, business_id=bid)
            sent = True
    except Exception as e:
        flash(f'⚠️ SMS failed: {str(e)[:80]}', 'error')
    audit('trial_nudge', f"{row['name']} -> {row['owner_phone']}")
    flash('✅ Nudge sent' if sent else '⚠️ No SMS sent', 'success' if sent else 'error')
    return redirect('/admin?tab=trials')


@app.route('/admin/broadcast-send', methods=['POST'])
@admin_required
def admin_broadcast_send():
    subject = request.form.get('subject', '').strip()
    message = request.form.get('message', '').strip()
    do_email = request.form.get('channel_email') == '1'
    do_sms = request.form.get('channel_sms') == '1'
    if not message:
        flash('❌ Message is required', 'error')
        return redirect('/admin?tab=broadcast')
    _load_env_keys()
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    bizs = db.execute("SELECT id, name, email, owner_phone FROM businesses").fetchall()
    db.close()
    counts = {'email': 0, 'sms': 0}

    def _send():
        for b in bizs:
            if do_email and b['email']:
                try:
                    from agentmail_email import send_agentmail
                    send_agentmail(b['email'], subject or 'Diazites Update', message)
                    counts['email'] += 1
                except Exception:
                    pass
            if do_sms and b['owner_phone']:
                try:
                    from smsgate_sms import send_sms
                    send_sms(b['owner_phone'], message[:480], business_id=b['id'])
                    counts['sms'] += 1
                except Exception:
                    pass

    t = threading.Thread(target=_send)
    t.start()
    audit('broadcast', f"to {len(bizs)} businesses (email={do_email}, sms={do_sms})")
    flash(f'📣 Broadcast sending to {len(bizs)} businesses in background...', 'success')
    return redirect('/admin?tab=broadcast')


@app.route('/admin/backup-now', methods=['POST'])
@admin_required
def admin_backup_now():
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        name = f"voice-agent-businesses-{_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
        shutil.copy(DB_PATH, os.path.join(BACKUP_DIR, name))
        files = sorted(os.listdir(BACKUP_DIR))
        for old in files[:-10]:
            os.remove(os.path.join(BACKUP_DIR, old))
        audit('backup_now', name)
        flash(f'✅ Backup created: {name}', 'success')
    except Exception as e:
        flash(f'❌ {str(e)[:100]}', 'error')
    return redirect('/admin?tab=backup')


@app.route('/admin/backup-download/<name>')
@admin_required
def admin_backup_download(name):
    fp = os.path.join(BACKUP_DIR, os.path.basename(name))
    if os.path.exists(fp):
        return send_file(fp, as_attachment=True)
    flash('❌ Backup not found', 'error')
    return redirect('/admin?tab=backup')


@app.route('/admin/inbox-reply', methods=['POST'])
@admin_required
def admin_inbox_reply():
    phone = request.form.get('phone', '').strip()
    body = request.form.get('body', '').strip()
    bid = request.form.get('business_id', '').strip()
    if not phone or not body:
        flash('❌ Phone and message required', 'error')
        return redirect('/admin?tab=inbox')
    _load_env_keys()
    try:
        from smsgate_sms import send_sms
        ok = send_sms(phone, body, business_id=bid)
        db = sqlite3.connect(DB_PATH)
        db.execute("INSERT INTO outgoing_sms (business_id, phone, body, status) VALUES (?,?,?,'sent')", (bid, phone, body))
        db.commit()
        db.close()
        audit('inbox_reply', f"{phone}: {body[:60]}")
        flash('✅ Reply sent', 'success' if ok else 'warning')
    except Exception as e:
        flash(f'❌ {str(e)[:100]}', 'error')
    return redirect('/admin?tab=inbox')


@app.route('/admin/transcript-flag/<call_id>', methods=['POST'])
@admin_required
def admin_transcript_flag(call_id):
    init_tables()
    db = sqlite3.connect(DB_PATH)
    exists = db.execute("SELECT 1 FROM call_flags WHERE call_id=?", (call_id,)).fetchone()
    if exists:
        db.execute("DELETE FROM call_flags WHERE call_id=?", (call_id,))
        msg = 'unflagged'
    else:
        db.execute("INSERT INTO call_flags (call_id) VALUES (?)", (call_id,))
        msg = 'flagged'
    db.commit()
    db.close()
    audit('transcript_flag', f"{call_id} {msg}")
    flash(f'✅ Call {msg}', 'success')
    return redirect('/admin?tab=transcripts')


@app.route('/admin/abtest-create', methods=['POST'])
@admin_required
def admin_abtest_create():
    bid = request.form.get('business_id', '').strip()
    name = request.form.get('variant_name', '').strip() or 'variant'
    script = request.form.get('script', '').strip()
    if not bid or not script:
        flash('❌ Business and script required', 'error')
        return redirect('/admin?tab=abtest')
    db = sqlite3.connect(DB_PATH)
    db.execute("INSERT INTO script_variants (business_id, name, script) VALUES (?,?,?)", (bid, name, script))
    db.commit()
    db.close()
    audit('abtest_create', f"{bid} / {name}")
    flash('✅ Variant created', 'success')
    return redirect('/admin?tab=abtest')


@app.route('/admin/abtest-activate/<vid>', methods=['POST'])
@admin_required
def admin_abtest_activate(vid):
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    v = db.execute("SELECT * FROM script_variants WHERE id=?", (vid,)).fetchone()
    if not v:
        db.close()
        flash('❌ Variant not found', 'error')
        return redirect('/admin?tab=abtest')
    db.execute("UPDATE script_variants SET active=0 WHERE business_id=?", (v['business_id'],))
    db.execute("UPDATE script_variants SET active=1 WHERE id=?", (vid,))
    db.execute("UPDATE businesses SET script_template=? WHERE id=?", (v['script'], v['business_id']))
    db.commit()
    db.close()
    audit('abtest_activate', f"variant {vid} for {v['business_id']}")
    flash('✅ Variant activated (script applied to business)', 'success')
    return redirect('/admin?tab=abtest')


@app.route('/admin/security-2fa-setup', methods=['POST'])
@admin_required
def admin_2fa_setup():
    try:
        import pyotp
        secret = pyotp.random_base32()
        codes = _gen_backup_codes()
        save_2fa({'enabled': False, 'secret': secret, 'backup_codes': [_2fa_hash(_2fa_normalize(c)) for c in codes]})
        session['admin_2fa_new_codes'] = codes
        audit('2fa_setup', 'QR generated, backup codes created')
    except Exception as e:
        flash(f'❌ pyotp missing: {str(e)[:80]}', 'error')
    return redirect('/admin?tab=security')


@app.route('/admin/security-2fa-verify', methods=['POST'])
@admin_required
def admin_2fa_verify():
    code = request.form.get('code', '').strip()
    try:
        d = load_2fa()
        import pyotp
        if d.get('secret') and pyotp.TOTP(d['secret']).verify(_2fa_normalize(code)):
            d['enabled'] = True
            save_2fa(d)
            audit('2fa_enable', 'TOTP enabled')
            flash('✅ 2FA enabled! Backup codes below — save them somewhere safe.', 'success')
        else:
            flash('❌ Invalid code', 'error')
    except Exception as e:
        flash(f'❌ {str(e)[:80]}', 'error')
    return redirect('/admin?tab=security')


@app.route('/admin/security-2fa-backup-codes', methods=['POST'])
@admin_required
def admin_2fa_backup_codes():
    d = load_2fa()
    if not d.get('secret'):
        flash('❌ No 2FA to manage', 'error')
        return redirect('/admin?tab=security')
    codes = _gen_backup_codes()
    d['backup_codes'] = [_2fa_hash(_2fa_normalize(c)) for c in codes]
    save_2fa(d)
    session['admin_2fa_new_codes'] = codes
    audit('2fa_backup_codes', 'backup codes regenerated')
    flash('🆕 New backup codes generated — copy them now!', 'success')
    return redirect('/admin?tab=security')


@app.route('/admin/security-2fa-dismiss', methods=['POST'])
@admin_required
def admin_2fa_dismiss():
    session.pop('admin_2fa_new_codes', None)
    return redirect('/admin?tab=security')


@app.route('/admin/security-2fa-disable', methods=['POST'])
@admin_required
def admin_2fa_disable():
    try:
        os.remove(TWOFA_PATH)
        session.pop('admin_2fa_new_codes', None)
        audit('2fa_disable', 'TOTP disabled')
        flash('✅ 2FA disabled', 'success')
    except Exception:
        flash('❌ No 2FA to disable', 'error')
    return redirect('/admin?tab=security')


# ── REVIEW AI (Google review responses service) ──

@app.route('/admin/review-ai/save-settings', methods=['POST'])
@admin_required
def admin_review_ai_save_settings():
    import review_ai
    s = review_ai.get_settings()
    updates = {
        'city': request.form.get('city', s['city']).strip(),
        'state': request.form.get('state', s['state']).strip().upper(),
        'categories': request.form.get('categories', s['categories']).strip(),
        'max_per_category': request.form.get('max_per_category', s['max_per_category']).strip(),
        'pricing': request.form.get('pricing', s['pricing']).strip(),
        'script': request.form.get('script', s['script']),
        'service': request.form.get('service', s['service']),
        'website_pricing': request.form.get('website_pricing', s['website_pricing']).strip(),
        'website_script': request.form.get('website_script', s['website_script']),
        'voice_id': request.form.get('voice_id', s['voice_id']).strip(),
        'enabled': '1' if request.form.get('enabled') else '0',
        'max_calls_per_run': request.form.get('max_calls_per_run', s['max_calls_per_run']).strip(),
        'delay_seconds': request.form.get('delay_seconds', s['delay_seconds']).strip(),
    }
    review_ai.save_settings(updates)
    audit('review_ai_save', f"city={updates['city']} pricing={updates['pricing']} enabled={updates['enabled']}")
    flash('✅ Review AI settings saved', 'success')
    return redirect('/admin?tab=reviews-ai')


@app.route('/admin/review-ai/scrape', methods=['POST'])
@admin_required
def admin_review_ai_scrape():
    import review_ai
    if review_ai.running_state()['scrape']:
        flash('⚠️ Scrape already running', 'warning')
        return redirect('/admin?tab=reviews-ai')
    review_ai.scrape_prospects()
    flash('🔍 Prospect search started (background) — refresh in a minute', 'success')
    return redirect('/admin?tab=reviews-ai')


@app.route('/admin/review-ai/count-unanswered', methods=['POST'])
@admin_required
def admin_review_ai_count():
    import review_ai
    if review_ai.running_state()['count']:
        flash('⚠️ Counting already running', 'warning')
        return redirect('/admin?tab=reviews-ai')
    review_ai.count_unanswered_all()
    flash('🔢 Unanswered review counting started (background)', 'success')
    return redirect('/admin?tab=reviews-ai')


@app.route('/review-service')
def review_service_page():
    """Public service page (served at diazites.online/review-service via 8086)."""
    import review_ai
    return review_ai.service_page_html(
        thankyou=request.args.get('thankyou') == '1',
        error=request.args.get('error') == '1',
        service='reviews')


@app.route('/review-service/signup', methods=['POST'])
def review_service_signup():
    import review_ai
    ok, _ = review_ai.signup_lead(request.form, service='reviews')
    return redirect('/review-service?thankyou=1' if ok else '/review-service?error=1')


@app.route('/website-service')
def website_service_page():
    """Public Website Builder service page (diazites.online/website-service)."""
    import review_ai
    return review_ai.service_page_html(
        thankyou=request.args.get('thankyou') == '1',
        error=request.args.get('error') == '1',
        service='website')


@app.route('/website-service/signup', methods=['POST'])
def website_service_signup():
    import review_ai
    ok, _ = review_ai.signup_lead(request.form, service='website')
    return redirect('/website-service?thankyou=1' if ok else '/website-service?error=1')


@app.route('/admin/review-ai/verify', methods=['POST'])
@admin_required
def admin_review_ai_verify():
    import review_ai
    try:
        n = review_ai.verify_prospects()
        flash(f'📱 Number verification: {n} numbers classified', 'success')
    except Exception as e:
        flash(f'❌ Verify error: {str(e)[:120]}', 'error')
    return redirect('/admin?tab=reviews-ai')


@app.route('/admin/review-ai/call', methods=['POST'])
@admin_required
def admin_review_ai_call():
    import review_ai
    s = review_ai.get_settings()
    if s.get('enabled') != '1':
        flash('❌ Review AI is disabled — enable it in settings first', 'error')
        return redirect('/admin?tab=reviews-ai')
    if review_ai.running_state()['calls']:
        flash('⚠️ Call run already in progress', 'warning')
        return redirect('/admin?tab=reviews-ai')
    n = request.form.get('max_calls', '') or ''
    review_ai.run_calls(max_calls=int(n) if n.isdigit() else None)
    flash('📞 Call run started (background)', 'success')
    return redirect('/admin?tab=reviews-ai')


@app.route('/admin/review-ai/stop', methods=['POST'])
@admin_required
def admin_review_ai_stop():
    import review_ai
    review_ai.stop_all()
    flash('⏹ Stop signal sent', 'success')
    return redirect('/admin?tab=reviews-ai')


@app.route('/admin/review-ai/sync', methods=['POST'])
@admin_required
def admin_review_ai_sync():
    import review_ai
    try:
        review_ai.sync_call_outcomes()
        flash('📊 Call outcomes synced', 'success')
    except Exception as e:
        flash(f'❌ Sync error: {str(e)[:120]}', 'error')
    return redirect('/admin?tab=reviews-ai')


@app.route('/admin/review-ai/dnc/<pid>', methods=['POST'])
@admin_required
def admin_review_ai_dnc(pid):
    import review_ai
    db = review_ai._db()
    db.execute("UPDATE review_prospects SET status='do_not_call' WHERE id=?", (pid,))
    db.commit()
    db.close()
    return jsonify({'success': True})


@app.route('/admin/review-ai/sample-sms/<pid>', methods=['POST'])
@admin_required
def admin_review_ai_sample_sms(pid):
    import review_ai
    return jsonify(review_ai.send_sample_sms(pid))


@app.route('/admin/review-ai/reset/<pid>', methods=['POST'])
@admin_required
def admin_review_ai_reset(pid):
    """Reset a prospect to 'new' so it can be called again."""
    import review_ai
    db = review_ai._db()
    db.execute("UPDATE review_prospects SET status='new', last_outcome=NULL WHERE id=?", (pid,))
    db.commit()
    db.close()
    return jsonify({'success': True})


@app.route('/admin/review-ai/delete/<pid>', methods=['POST'])
@admin_required
def admin_review_ai_delete(pid):
    import review_ai
    db = review_ai._db()
    db.execute("DELETE FROM review_ai_calls WHERE prospect_id=?", (pid,))
    db.execute("DELETE FROM review_prospects WHERE id=?", (pid,))
    db.commit()
    db.close()
    return jsonify({'success': True})


@app.route('/admin/review-ai/complete/<pid>', methods=['POST'])
@admin_required
def admin_review_ai_complete(pid):
    """Mark prospect completed — never called again."""
    import review_ai
    review_ai.mark_completed(pid)
    return jsonify({'success': True})


@app.route('/admin/review-ai/call-again/<pid>', methods=['POST'])
@admin_required
def admin_review_ai_call_again(pid):
    """Re-call a prospect right now with its own service pitch."""
    import review_ai
    return jsonify(review_ai.call_again(pid))


@app.route('/admin/review-ai/transcript/<call_id>')
@admin_required
def admin_review_ai_transcript(call_id):
    import review_ai
    return jsonify(review_ai.call_transcript(call_id))


@app.route('/admin/review-ai/recording/<call_id>')
@admin_required
def admin_review_ai_recording(call_id):
    """Stream a call recording (Vapi authenticated endpoint → proxied audio)."""
    import review_ai
    from flask import Response
    data, ctype = review_ai.call_recording(call_id)
    if not data:
        return jsonify({'error': 'No recording available yet (calls need to end first)'}), 404
    return Response(data, mimetype=ctype or 'audio/mpeg')


@app.route('/admin/review-ai/status')
@admin_required
def admin_review_ai_status():
    import review_ai
    d = review_ai.tab_data()
    return jsonify({
        'running': d['ra_running'],
        'stats': d['ra_stats'],
        'log': d['ra_log'][-12:],
        'live': d['ra_live'],
    })


if __name__ == '__main__':
    print("🚀 Diazites ADMIN Panel")
    print(f"📊 DB: {DB_PATH}")
    print("🌐 http://localhost:8086/admin")
    print("🔑 Password: from .env (ADMIN_PASSWORD)")
    app.run(host='0.0.0.0', port=8086, debug=False, threaded=True)
