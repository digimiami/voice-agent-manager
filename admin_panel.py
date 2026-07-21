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
Password:    admin123
"""

import os, sys, json, sqlite3, csv, io, hashlib, time, threading, subprocess, uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, redirect, session, url_for, flash
from functools import wraps

DB_PATH = "/root/voice-agent-businesses.db"
VAPI_API_KEY = "49e91b8a-21d2-458c-a586-d6368289e5a6"
VAPI_BASE = "https://api.vapi.ai"

app = Flask(__name__)
app.secret_key = "admin-secret-key-hermes-2026"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

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
    "starter": {"name": "Starter", "price": 299, "calls_included": 500, "features": "AI agent, 1 number, 500 calls/mo"},
    "pro": {"name": "Pro", "price": 599, "calls_included": 2000, "features": "AI agent, 1 number, 2K calls/mo, lead mgmt"},
    "premium": {"name": "Premium", "price": 999, "calls_included": 5000, "features": "AI agent, 2 numbers, 5K calls/mo, forwarding"},
    "enterprise": {"name": "Enterprise", "price": 1999, "calls_included": 15000, "features": "AI agent, 5 numbers, 15K calls/mo, white-label"},
    "custom": {"name": "Custom", "price": 0, "calls_included": 0, "features": "Fully customizable package"}
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
        .sidebar { width: 220px; min-height: 100vh; background: #0d0d14; border-right: 1px solid #1a1a28; padding: 20px; }
        .sidebar-item { padding: 8px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; color: #64748b; transition: all 0.2s; }
        .sidebar-item:hover { background: #1a1a28; color: #e2e8f0; }
        .sidebar-item.active { background: rgba(99,102,241,0.1); color: #818cf8; }
    </style>
</head>
<body class="text-[#e2e8f0] min-h-screen flex">
    {% if session.get('admin_logged_in') %}
    <!-- SIDEBAR -->
    <div class="sidebar hidden md:block">
        <div class="flex items-center gap-2 mb-8">
            <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-[#6366f1] to-[#8b5cf6] flex items-center justify-center text-white font-bold text-sm">A</div>
            <div>
                <div class="font-bold text-sm">Diazites</div>
                <div class="text-xs text-[#64748b]">SaaS Panel</div>
            </div>
        </div>
        <div class="space-y-1">
            {% set admin_tabs = [
                ('dashboard', 'gauge', 'Dashboard'),
                ('businesses', 'building', 'Businesses'),
                ('create', 'plus-circle', 'New Business'),
                ('campaigns', 'bullhorn', 'Campaigns'),
                ('subscriptions', 'credit-card', 'Subscriptions'),
                ('billing', 'file-invoice-dollar', 'Billing'),
                ('vapi', 'phone', 'VAPI Config'),
                ('chatbot', 'robot', 'Chatbot'),
                ('industries', 'industry', 'Industries'),
                ('email', 'envelope', 'Email Config'),
                ('sms', 'message', 'SMS/Calendar'),
                ('stripe', 'credit-card', 'Stripe'),
                ('agent-tars', 'robot', 'Agent TARS')
            ] %}
            {% for key, icon, label in admin_tabs %}
            <a href="?tab={{ key }}" class="sidebar-item flex items-center gap-2 {% if tab == key %}active{% endif %}">
                <i class="fas fa-{{ icon }} w-4 text-center"></i> {{ label }}
            </a>
            {% endfor %}
        </div>
        <div class="mt-auto pt-8">
            <a href="/admin/logout" class="sidebar-item flex items-center gap-2 text-red-400">
                <i class="fas fa-sign-out-alt w-4 text-center"></i> Logout
            </a>
        </div>
    </div>

    <!-- MAIN -->
    <div class="flex-1 p-4 sm:p-6 overflow-x-hidden">
        <!-- Mobile header -->
        <div class="flex items-center justify-between md:hidden mb-4">
            <div class="font-bold gradient-text">Diazites</div>
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
            <h2 class="text-xl font-bold">🏪 Businesses ({{ businesses|length }})</h2>
            <a href="?tab=create" class="btn-primary text-xs"><i class="fas fa-plus mr-1"></i> New Business</a>
        </div>

        <div class="overflow-x-auto">
        <table>
            <tr><th>ID</th><th>Name</th><th>Industry</th><th>Plan</th><th>Status</th><th>Calls</th><th>Appts</th><th>MRR</th><th>Actions</th></tr>
            {% for biz in businesses %}
            <tr>
                <td class="font-mono text-xs text-[#64748b]">{{ biz.id[:12] }}..</td>
                <td class="font-semibold text-[#e2e8f0]">{{ biz.name }}</td>
                <td><span class="badge badge-pro">{{ (biz.industry or '?')[:12] }}</span></td>
                <td>{{ (biz.plan or 'starter')|title }}</td>
                <td><span class="badge {% if biz.status == 'active' %}badge-active{% else %}badge-inactive{% endif %}">{{ biz.status or 'active' }}</span></td>
                <td>{{ biz.calls_made or 0 }}</td>
                <td>{{ biz.appointments_booked or 0 }}</td>
                <td class="text-[#4ade80]">${{ "%.0f"|format(biz.monthly_price|int) if biz.monthly_price else "299" }}</td>
                <td>
                    <a href="/admin/business/{{ biz.id }}" class="text-[#818cf8] text-xs hover:underline mr-2"><i class="fas fa-eye"></i> View</a>
                    <a href="/admin/business/{{ biz.id }}/resend-credentials" class="text-[#fbbf24] text-xs hover:underline mr-2" onclick="return confirm('Resend credentials to {{ biz.name }}?')"><i class="fas fa-envelope"></i></a>
                    <form method="POST" action="/admin/business/delete/{{ biz.id }}" style="display:inline" onsubmit="return confirm('Delete business and all data?')">
                        <button class="text-red-400 text-xs hover:underline"><i class="fas fa-trash"></i></button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </table>
        </div>

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
        <h2 class="text-xl font-bold mb-6">📋 Subscriptions</h2>

        <div class="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-6">
            {% for key, tier in tiers.items() %}
            <div class="card text-center card-hover {% if key == 'pro' %}border-[#6366f1]! border-opacity-50{% endif %}">
                <div class="text-xs text-[#64748b] uppercase tracking-wider">{{ tier.name }}</div>
                <div class="text-2xl font-bold mt-2 text-[#e2e8f0]">${{ tier.price }}<span class="text-sm text-[#64748b]">/mo</span></div>
                <div class="text-xs text-[#64748b] mt-1">{{ tier.features }}</div>
                <div class="text-xs text-[#4ade80] mt-3">{{ tier.calls_included }} calls included</div>
                <div class="mt-3"><span class="text-sm font-semibold">{{ sub_counts[key] or 0 }}</span> <span class="text-xs text-[#64748b]">clients</span></div>
            </div>
            {% endfor %}
        </div>

        <div class="card">
            <h3 class="font-bold mb-3">Clients by Plan</h3>
            <table>
                <tr><th>Business</th><th>Plan</th><th>Price</th><th>Calls Used</th><th>% of Limit</th><th>Billing</th><th>Status</th></tr>
                {% for biz in businesses %}
                {% set plan = biz.plan or 'starter' %}
                {% set tier = tiers[plan] if plan in tiers else tiers['starter'] %}
                {% set pct = ((biz.calls_made|int or 0) / tier.calls_included * 100)|round if tier.calls_included > 0 else 0 %}
                <tr>
                    <td>{{ biz.name }}</td>
                    <td><span class="badge badge-pro">{{ tier.name }}</span></td>
                    <td>${{ "%.0f"|format(biz.monthly_price|int or tier.price) }}</td>
                    <td>{{ biz.calls_made or 0 }}</td>
                    <td>
                        <div class="flex items-center gap-2">
                            <div class="h-1.5 w-20 bg-[#1a1a28] rounded-full overflow-hidden">
                                <div class="h-full bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] rounded-full" style="width:{{ pct|float }}%"></div>
                            </div>
                            <span class="text-xs">{{ "%.0f"|format(pct) }}%</span>
                        </div>
                    </td>
                    <td><span class="badge badge-active">Monthly</span></td>
                    <td><span class="badge badge-active">Active</span></td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <!-- TAB: BILLING -->
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

        <!-- TAB: SMS/CALENDAR CONFIG -->
        {% elif tab == 'sms' %}
        <h2 class="text-xl font-bold mb-6">📱 SMS & Calendar Configuration</h2>
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
                <input type="text" name="from_number" value="{{ twilio_config.from_number or '' }}" placeholder="+1234567890" class="mb-4">
                <button type="submit" class="btn-primary text-sm"><i class="fas fa-save mr-1"></i> Save SMS Config</button>
            </form>
        </div>
        <div class="max-w-xl card">
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
        {% endif %}
    </div>

    {% else %}
    <!-- LOGIN PAGE -->
    <div class="w-full min-h-screen flex items-center justify-center p-4">
        <div class="max-w-sm w-full card text-center">
            <div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#6366f1] to-[#8b5cf6] flex items-center justify-center text-white font-bold text-2xl mx-auto mb-4">A</div>
            <h2 class="text-lg font-bold mb-1">Admin Login</h2>
            <p class="text-xs text-[#64748b] mb-6">Diazites Management</p>
            <form method="POST" action="/admin" class="space-y-3">
                <input type="password" name="password" placeholder="Admin Password" class="text-center" autofocus>
                <button type="submit" class="btn-primary w-full">Login →</button>
            </form>
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

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if pw == 'admin123':
            session['admin_logged_in'] = True
            session.permanent = True
            return redirect('/admin?tab=dashboard')
        return render_template_string(ADMIN_HTML, session=session, error='Invalid password', tab='')
    # If already logged in, show dashboard with data
    if session.get('admin_logged_in'):
        return admin_dashboard()
    return render_template_string(ADMIN_HTML, session=session, error='', tab='')

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
    script = biz['script_template'] or f"You are an AI assistant for {name}. Help them book more clients. Keep responses under 30 seconds."
    kb = biz['knowledge_base'] or f"Industry: {industry}. Business: {name}."
    voice_id = biz['voice_id'] or 'burt'
    max_tokens = int(biz['max_tokens'] or 200) if biz['max_tokens'] else 200
    
    full_script = f"{script}\n\nKnowledge Base Context:\n{kb}\n\nKeep responses under 30 seconds. If prospect asks for email or calendar, say a team member will handle it."
    
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
            "voice": {
                "provider": "11labs",
                "voiceId": voice_id
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
        "-H", f"Authorization: Bearer ***"
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
                        "-H", f"Authorization: Bearer ***",
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
         request.form.get('script_template', f"You are an AI assistant for {name}. Help them book more clients."),
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
    """Send email via configured SMTP."""
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
               (SELECT COUNT(*) FROM leads WHERE business_id = b.id AND state = 'NEW') as leads_count
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
    
    return render_template_string(ADMIN_HTML,
        session=session, tab=tab, businesses=businesses,
        industries=INDUSTRY_PRESETS, tiers=PRICING_TIERS,
        VAPI_API_KEY=VAPI_API_KEY, sub_counts=sub_counts,
        vapi_numbers=vapi_numbers, vapi_assistant_count=vapi_assistant_count,
        chatbot_provider=chatbot_provider, chatbot_model=chatbot_model, chatbot_api_key=chatbot_api_key,
        tars_result=json.load(open('/dev/shm/tars_result.json'))['result'] if os.path.exists('/dev/shm/tars_result.json') else None,
        tars_status=json.load(open('/dev/shm/tars_status.json')) if os.path.exists('/dev/shm/tars_status.json') else None,
        last_task=session.get('tars_last_task', ''),
            default_script="You are an AI assistant for {name}. Your goal: book a 10-minute discovery call with the prospect. Speak naturally and professionally.",
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
        stripe_config=load_stripe_config())

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

if __name__ == '__main__':
    print("🚀 Diazites ADMIN Panel")
    print(f"📊 DB: {DB_PATH}")
    print("🌐 http://localhost:8086/admin")
    print("🔑 Password: admin123")
    app.run(host='0.0.0.0', port=8086, debug=False)
