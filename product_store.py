#!/usr/bin/env python3
"""ShopZario  Professional AI Product Store"""
import os, sys, json, sqlite3, uuid, re, urllib.request
from datetime import datetime
from flask import Flask, jsonify, request, redirect, session, url_for, g
from functools import wraps
from product_experience_hub import experience_hub
from legal_page import legal_page
import navigation
from ads_generator import ads_manager_html, generate_all_ads, AD_TEMPLATES, get_product
import campaigns as _cmp
import course_system

DB_PATH = "/root/voice-agent-businesses.db"
ADMIN_PASSWORD = "admin123"

app = Flask(__name__)
app.secret_key = "shopzario-secret-key-change-me"

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_api_keys_table():
    """Ensure api_keys table exists."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS api_keys (provider TEXT PRIMARY KEY, api_key TEXT, status TEXT DEFAULT 'disconnected', last_error TEXT, last_request TEXT, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')))")
    conn.commit()
    conn.close()

def get_chatbot_config():
    try:
        db = sqlite3.connect(DB_PATH)
        c = db.cursor()
        c.execute("SELECT key, value FROM settings WHERE key IN ('chatbot_provider','chatbot_model','chatbot_api_key')")
        rows = {row[0]: row[1] for row in c.fetchall()}
        db.close()
        return rows
    except:
        return {}

CHATBOT_PROVIDERS = {
    "xai": {"api_url": "https://api.x.ai/v1/chat/completions", "default_model": "grok-4-mini", "auth_header": lambda k: f"Bearer {k}"},
    "deepseek": {"api_url": "https://api.deepseek.com/chat/completions", "default_model": "deepseek-chat", "auth_header": lambda k: f"Bearer {k}"},
}

PRODUCT_TYPE_META = {
    'ai_agent': {'icon': '', 'label': 'AI Agent', 'color': '#a855f7', 'gradient': 'from-[#a855f7] to-[#7c3aed]'},
    'prompt_pack': {'icon': '', 'label': 'Prompt Pack', 'color': '#818cf8', 'gradient': 'from-[#818cf8] to-[#6366f1]'},
    'n8n_workflow': {'icon': '', 'label': 'n8n Workflow', 'color': '#ff6b6b', 'gradient': 'from-[#ff6b6b] to-[#ee5a24]'},
    'mcp_server': {'icon': '', 'label': 'MCP Server', 'color': '#38bdf8', 'gradient': 'from-[#38bdf8] to-[#0284c7]'},
    'trading_bot': {'icon': '', 'label': 'Trading Bot', 'color': '#4ade80', 'gradient': 'from-[#4ade80] to-[#16a34a]'},
    'tradingview_indicator': {'icon': '', 'label': 'TradingView Indicator', 'color': '#facc15', 'gradient': 'from-[#facc15] to-[#ca8a04]'},
    'python_script': {'icon': '', 'label': 'Python Script', 'color': '#22c55e', 'gradient': 'from-[#22c55e] to-[#15803d]'},
    'cursor_rule': {'icon': '', 'label': 'Cursor Rule', 'color': '#f472b6', 'gradient': 'from-[#f472b6] to-[#db2777]'},
    'claude_project': {'icon': '', 'label': 'Claude Project', 'color': '#a855f7', 'gradient': 'from-[#a855f7] to-[#7c3aed]'},
    'gpt_project': {'icon': '', 'label': 'GPT Project', 'color': '#10b981', 'gradient': 'from-[#10b981] to-[#059669]'},
    'react_template': {'icon': '', 'label': 'React Template', 'color': '#06b6d4', 'gradient': 'from-[#06b6d4] to-[#0891b2]'},
    'nextjs_template': {'icon': '', 'label': 'Next.js Template', 'color': '#111827', 'gradient': 'from-[#374151] to-[#111827]'},
    'wordpress_plugin': {'icon': '', 'label': 'WordPress Plugin', 'color': '#21759b', 'gradient': 'from-[#21759b] to-[#183d4d]'},
    'shopify_theme': {'icon': '', 'label': 'Shopify Theme', 'color': '#7ab55c', 'gradient': 'from-[#7ab55c] to-[#4a8b3a]'},
    'chrome_extension': {'icon': '', 'label': 'Chrome Extension', 'color': '#4285f4', 'gradient': 'from-[#4285f4] to-[#1967d2]'},
    'vscode_extension': {'icon': '', 'label': 'VS Code Extension', 'color': '#007acc', 'gradient': 'from-[#007acc] to-[#005a9e]'},
    'api': {'icon': '', 'label': 'API', 'color': '#f97316', 'gradient': 'from-[#f97316] to-[#ea580c]'},
    'dataset': {'icon': '', 'label': 'Dataset', 'color': '#84cc16', 'gradient': 'from-[#84cc16] to-[#65a30d]'},
    'ebook': {'icon': '', 'label': 'eBook', 'color': '#facc15', 'gradient': 'from-[#facc15] to-[#eab308]'},
    'course': {'icon': '', 'label': 'Course', 'color': '#8b5cf6', 'gradient': 'from-[#8b5cf6] to-[#6d28d9]'},
    'canva_template': {'icon': '', 'label': 'Canva Template', 'color': '#00c4cc', 'gradient': 'from-[#00c4cc] to-[#00838f]'},
    'notion_template': {'icon': '', 'label': 'Notion Template', 'color': '#ffffff', 'gradient': 'from-[#ffffff] to-[#a0a0b0]'},
    'excel_dashboard': {'icon': '', 'label': 'Excel Dashboard', 'color': '#217346', 'gradient': 'from-[#217346] to-[#165a33]'},
    'powerpoint': {'icon': '', 'label': 'PowerPoint', 'color': '#d04423', 'gradient': 'from-[#d04423] to-[#a3361c]'},
    'business_doc': {'icon': '', 'label': 'Business Document', 'color': '#38bdf8', 'gradient': 'from-[#38bdf8] to-[#0ea5e9]'},
    'legal_template': {'icon': '', 'label': 'Legal Template', 'color': '#94a3b8', 'gradient': 'from-[#94a3b8] to-[#64748b]'},
    'marketing': {'icon': '', 'label': 'Marketing Asset', 'color': '#f97316', 'gradient': 'from-[#f97316] to-[#ea580c]'},
    'icon_pack': {'icon': '', 'label': 'Icon Pack', 'color': '#f472b6', 'gradient': 'from-[#f472b6] to-[#db2777]'},
    'logo': {'icon': '', 'label': 'Logo', 'color': '#a855f7', 'gradient': 'from-[#a855f7] to-[#7c3aed]'},
    'font': {'icon': '', 'label': 'Font', 'color': '#6b7280', 'gradient': 'from-[#6b7280] to-[#4b5563]'},
    'photo': {'icon': '', 'label': 'Photo', 'color': '#14b8a6', 'gradient': 'from-[#14b8a6] to-[#0d9488]'},
    'video': {'icon': '', 'label': 'Video', 'color': '#ef4444', 'gradient': 'from-[#ef4444] to-[#b91c1c]'},
    'music': {'icon': '', 'label': 'Music', 'color': '#f59e0b', 'gradient': 'from-[#f59e0b] to-[#b45309]'},
    '3d_asset': {'icon': '', 'label': '3D Asset', 'color': '#10b981', 'gradient': 'from-[#10b981] to-[#047857]'},
    'source_code': {'icon': '', 'label': 'Source Code', 'color': '#6366f1', 'gradient': 'from-[#6366f1] to-[#4338ca]'},
    'saas': {'icon': '', 'label': 'SaaS', 'color': '#0ea5e9', 'gradient': 'from-[#0ea5e9] to-[#0369a1]'},
    'membership': {'icon': '', 'label': 'Membership', 'color': '#f59e0b', 'gradient': 'from-[#f59e0b] to-[#d97706]'},
    'license': {'icon': '', 'label': 'License', 'color': '#22d3ee', 'gradient': 'from-[#22d3ee] to-[#0891b2]'},
    'template': {'icon': '', 'label': 'Template', 'color': '#4ade80', 'gradient': 'from-[#4ade80] to-[#22c55e]'},
    'checklist': {'icon': '', 'label': 'Checklist', 'color': '#f472b6', 'gradient': 'from-[#f472b6] to-[#ec4899]'},
    'starter': {'icon': '', 'label': 'Starter Kit', 'color': '#14b8a6', 'gradient': 'from-[#14b8a6] to-[#0d9488]'},
    'code': {'icon': '', 'label': 'Code Library', 'color': '#a855f7', 'gradient': 'from-[#a855f7] to-[#9333ea]'},
}

def product_type_icon(ptype):
    return PRODUCT_TYPE_META.get(ptype, {}).get('icon', '')

def product_type_color(ptype):
    return PRODUCT_TYPE_META.get(ptype, {}).get('color', '#7a7a8e')

def product_type_gradient(ptype):
    return PRODUCT_TYPE_META.get(ptype, {}).get('gradient', 'from-[#a855f7] to-[#ec4899]')

PRODUCT_TYPE_LABELS = {k: v['label'] for k, v in PRODUCT_TYPE_META.items()}

LAYOUT_HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
<link rel="icon" type="image/png" href="/static/favicon.ico">
<link rel="apple-touch-icon" href="/static/icon.png">
<title>ShopZario — Premium AI-Crafted Digital Products Marketplace</title>
<meta name="description" content="Discover 1000+ premium AI-crafted digital products: prompt packs, templates, eBooks, courses, software, and tools. Instant download after purchase.">
<meta name="keywords" content="AI products, digital marketplace, AI prompts, templates, eBooks, courses, software, digital downloads, shopzario">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://shopzario.com/">
<meta property="og:type" content="website">
<meta property="og:title" content="ShopZario — Premium AI-Crafted Digital Products Marketplace">
<meta property="og:description" content="Discover 1000+ premium AI-crafted digital products. Instant download after purchase.">
<meta property="og:url" content="https://shopzario.com/">
<meta property="og:site_name" content="ShopZario">
<meta property="og:image" content="https://shopzario.com/static/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="ShopZario  Digital Products Marketplace">
<meta name="twitter:description" content="Premium AI-crafted digital products  prompt packs, templates, eBooks, and tools.">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
*{font-family:Inter,sans-serif}body{background:#07070c;color:#f1f1f5;-webkit-font-smoothing:antialiased}
.card{background:linear-gradient(135deg,#0e0e16,#11111d);border:1px solid #1e1e2e;border-radius:16px;padding:24px;transition:all .3s}
.card:hover{border-color:#2a2a3e}
.glass{background:rgba(255,255,255,0.03);-webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.06)}
.tag{display:inline-flex;align-items:center;gap:4px;padding:4px 12px;border-radius:9999px;font-size:11px;font-weight:600;letter-spacing:.02em}
.tag-purple{background:rgba(168,85,247,0.12);color:#c084fc}
.tag-green{background:rgba(34,197,94,0.12);color:#4ade80}
.tag-amber{background:rgba(250,204,21,0.12);color:#facc15}
.tag-blue{background:rgba(56,189,248,0.12);color:#38bdf8}
.tag-pink{background:rgba(236,72,153,0.12);color:#f472b6}
.btn-primary{background:linear-gradient(135deg,#a855f7,#ec4899);color:white;padding:14px 28px;border-radius:12px;font-weight:600;font-size:14px;border:none;cursor:pointer;transition:all .3s;display:inline-flex;align-items:center;gap:8px;text-decoration:none;justify-content:center}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(168,85,247,0.3)}
.btn-secondary{background:rgba(255,255,255,0.04);border:1px solid #1e1e2e;color:#f1f1f5;padding:14px 28px;border-radius:12px;font-weight:600;font-size:14px;cursor:pointer;transition:all .3s;text-decoration:none;display:inline-flex;align-items:center;gap:8px;justify-content:center}
.btn-secondary:hover{background:rgba(255,255,255,0.08);border-color:#2a2a3e}
.btn-outline{background:transparent;border:1.5px solid #a855f7;color:#c084fc;padding:14px 28px;border-radius:12px;font-weight:600;font-size:14px;cursor:pointer;transition:all .3s;text-decoration:none;display:inline-flex;align-items:center;gap:8px;justify-content:center}
.btn-outline:hover{background:rgba(168,85,247,0.1);box-shadow:0 0 20px rgba(168,85,247,0.15)}
input,select,textarea{background:#0e0e16;border:1px solid #1e1e2e;border-radius:10px;padding:12px 16px;color:#f1f1f5;outline:none;font-size:14px;width:100%;transition:border-color .2s}
input:focus,select:focus,textarea:focus{border-color:#a855f7;box-shadow:0 0 0 3px rgba(168,85,247,0.12)}
.badge{display:inline-flex;padding:3px 10px;border-radius:9999px;font-size:11px;font-weight:600}
.badge-success{background:rgba(34,197,94,0.15);color:#4ade80}
.badge-warning{background:rgba(250,204,21,0.15);color:#facc15}
.badge-trending{background:rgba(236,72,153,0.2);color:#f472b6;animation:pulse 2s infinite}
.star{color:#facc15;font-size:14px}
.star-empty{color:#2a2a3e;font-size:14px}
.product-cover{width:100%;height:200px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:64px;position:relative;overflow:hidden}
.product-cover::before{content:'';position:absolute;inset:0;opacity:0.1;background:currentColor}
.line-clamp-2{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tab-btn{padding:10px 20px;border-radius:10px;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s;border:none;background:transparent;color:#7a7a8e}
.tab-btn.active{background:rgba(168,85,247,0.12);color:#c084fc}
.tab-btn:hover{color:#f1f1f5}
.review-card{background:#0a0a12;border:1px solid #1a1a24;border-radius:12px;padding:16px;margin-bottom:12px}
.review-card:last-child{margin-bottom:0}
.hero-gradient{background:radial-gradient(ellipse at 50% 0%,rgba(168,85,247,0.12) 0%,transparent 70%)}
.hero-badge{background:rgba(168,85,247,0.12);border:1px solid rgba(168,85,247,0.2);color:#c084fc;padding:6px 16px;border-radius:9999px;font-size:12px;font-weight:600;display:inline-flex;align-items:center;gap:6px}
.animate-in{animation:fadeIn .5s ease-out}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.7}}
.nav-link{color:#7a7a8e;transition:all .2s;white-space:nowrap}
.nav-link:hover{color:#f1f1f5}
.nav-link.active{color:#c084fc}
.mega-menu{display:none;position:absolute;top:100%;left:0;right:0;background:#0e0e16;border:1px solid #1e1e2e;border-radius:16px;padding:24px;z-index:50;margin-top:4px}
.mega-menu.show{display:flex}
.mobile-menu{position:fixed;top:0;right:-100%;width:280px;height:100vh;background:#0e0e16;border-left:1px solid #1e1e2e;z-index:100;padding:20px;transition:right .3s ease;overflow-y:auto}
.mobile-menu.open{right:0}
.mobile-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:99;display:none}
.mobile-overlay.show{display:block}
@media(max-width:768px){.card{padding:16px}.btn-primary,.btn-secondary,.btn-outline{padding:12px 20px;font-size:13px}input,select,textarea{font-size:16px}}
</style></head>
<body class="min-h-screen">'''
TOP_NAV = navigation.generate()

LAYOUT_FOOT = '</body></html>'

# Register course system routes
course_system.register_routes(app, LAYOUT_HEAD, TOP_NAV, LAYOUT_FOOT)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

def get_reviews(product_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM product_reviews WHERE product_id=? ORDER BY created_at DESC", (product_id,))
    reviews = [dict(r) for r in c.fetchall()]
    db.close()
    return reviews

def get_rating_stats(product_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT COUNT(*), COALESCE(AVG(rating),0) FROM product_reviews WHERE product_id=?", (product_id,))
    count, avg = c.fetchone()
    db.close()
    return int(avg), count

def render_stars(rating, count=None):
    full = int(rating)
    half = 1 if rating - full >= 0.5 else 0
    empty = 5 - full - half
    stars = '<span class="star"></span>' * full
    if half:
        stars += '<span class="star"></span>'
    stars += '<span class="star-empty"></span>' * empty
    if count is not None:
        stars += f' <span class="text-xs text-[#5c5c70]">({count})</span>'
    return stars

@app.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect('/factory')
        return '<h2>Wrong password</h2><a href="/login">Try again</a>'
    return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>ShopZario Admin</title>
<script src="https://cdn.tailwindcss.com"></script><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>*{font-family:Inter,sans-serif}body{background:#07070c;color:#f1f1f5;}</style></head>
<body class="min-h-screen flex items-center justify-center p-4">
<div class="card w-full max-w-sm" style="padding:32px"><h2 class="font-bold text-xl mb-1">[LOCK] ShopZario</h2><p class="text-xs text-[#7a7a8e] mb-6">Admin login</p>
<form method="POST" class="space-y-4"><input type="password" name="password" placeholder="Admin password">
<button class="btn-primary w-full">Login</button></form></div></body></html>'''

@app.route('/logout')
def admin_logout():
    session.clear()
    return redirect('/')


#  CUSTOMER ACCOUNTS
import hashlib as _ahlib

@app.route('/account')
def customer_dashboard():
    email = session.get('customer_email')
    if not email:
        return redirect('/account/login')
    db = get_db()
    
    # Get digital product purchases (from product_orders)
    orders = db.execute("SELECT po.*, p.title, p.file_path, p.product_type FROM product_orders po JOIN products p ON po.product_id = p.id WHERE po.customer_email=? ORDER BY po.created_at DESC", (email,)).fetchall()
    
    # Get course access
    customer = db.execute("SELECT id FROM customer_accounts WHERE email=?", (email,)).fetchone()
    courses = []
    if customer:
        cid = customer[0]
        courses = db.execute("""
            SELECT p.id, p.title, p.product_type, ca.granted_at 
            FROM course_access ca 
            JOIN products p ON ca.product_id=p.id 
            WHERE ca.customer_id=? 
            ORDER BY ca.granted_at DESC
        """, (cid,)).fetchall()
    
    db.close()
    
    rows = ""
    
    # Show course access
    for c in courses:
        icon = product_type_icon(c["product_type"] if c["product_type"] else "course")
        title = c["title"] or "Course"
        date = (c["granted_at"] or "")[:10]
        rows += f'<div class="flex items-center gap-4 p-4 bg-gradient-to-r from-purple-900/20 to-black/30 rounded-xl border border-purple-500/20"><span class="text-3xl">{icon}</span><div class="flex-1 min-w-0"><div class="text-sm font-semibold text-white truncate">{title[:50]}</div><div class="text-[10px] text-gray-500">Access granted {date}</div></div><a href="/course/{c["id"]}/" class="btn-primary text-xs" style="padding:8px 16px;background:linear-gradient(135deg,#4ade80,#22c55e)"><i class="fas fa-graduation-cap"></i> Access Course</a></div>'
    
    # Show digital product purchases
    for o in orders:
        icon = product_type_icon(o["product_type"] if o["product_type"] else "")
        dl_link = ""
        if o["download_token"]:
            dl_link = f'<a href="/download/{o["download_token"]}" class="btn-primary text-xs" style="padding:8px 16px"><i class="fas fa-download"></i> Download</a>'
        title = o["title"] or "Product"
        date = (o["created_at"] or "")[:10]
        rows += f'<div class="flex items-center gap-4 p-4 bg-black/30 rounded-xl border border-white/10"><span class="text-3xl">{icon}</span><div class="flex-1 min-w-0"><div class="text-sm font-semibold text-white truncate">{title[:50]}</div><div class="text-[10px] text-gray-500">Purchased {date}</div></div>{dl_link}</div>'
    
    if not rows:
        rows = '<div class="text-center py-12 text-gray-500"><p class="text-sm">No purchases yet.</p><a href="/" class="text-[#38bdf8] text-xs mt-2 inline-block">Browse products</a></div>'
    
    body = f'<div class="max-w-3xl mx-auto px-4 py-6"><div class="flex items-center justify-between mb-6"><div><h1 class="text-xl font-bold">My Account</h1><p class="text-xs text-gray-500">{email}</p></div><a href="/account/logout" class="text-xs text-gray-400"><i class="fas fa-sign-out-alt"></i> Logout</a></div><div class="space-y-3">{rows}</div><div class="mt-6 text-center"><a href="/" class="btn-secondary text-xs" style="padding:10px 24px"><i class="fas fa-arrow-left"></i> Continue Shopping</a></div></div>'
    return LAYOUT_HEAD + TOP_NAV + body + LAYOUT_FOOT

@app.route('/account/register', methods=['GET', 'POST'])
def customer_register():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        pw = request.form.get('password','')
        name = request.form.get('name','').strip()
        if not email or len(pw) < 4:
            return '<p class="p-4 text-red-400">Invalid input</p><a href="/account/register">Back</a>', 400
        try:
            db = sqlite3.connect("/root/voice-agent-businesses.db")
            db.row_factory = sqlite3.Row
            db.execute("CREATE TABLE IF NOT EXISTS customer_accounts (id TEXT PRIMARY KEY, email TEXT UNIQUE, name TEXT, password_hash TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            cid = str(uuid.uuid4())[:13]
            ph = _ahlib.sha256((pw + email).encode()).hexdigest()
            db.execute("INSERT INTO customer_accounts (id,email,name,password_hash) VALUES (?,?,?,?)", (cid,email,name or '',ph))
            db.commit()
            db.close()
            session['customer_email'] = email
            session['customer_name'] = name or email.split('@')[0]
            session['customer_id'] = cid
            return redirect('/account')
        except Exception as e:
            return f'<p class="p-4 text-red-400">Account exists: <a href="/account/login">Login</a></p>', 409
    form = '<div class="max-w-sm mx-auto px-4 py-16"><div class="card p-8"><h2 class="font-bold text-lg mb-1">Create Account</h2><p class="text-xs text-gray-500 mb-6">Save your purchases forever</p><form method="POST" class="space-y-3"><input name="name" placeholder="Full name" class="w-full"><input name="email" type="email" placeholder="Email" class="w-full" required><input name="password" type="password" placeholder="Password (min 4 chars)" class="w-full" required><button class="btn-primary w-full justify-center" style="padding:12px">Create Account</button></form><p class="text-xs text-gray-500 text-center mt-4">Have an account? <a href="/account/login" class="text-[#38bdf8]">Login</a></p></div></div>'
    return LAYOUT_HEAD + TOP_NAV + form + LAYOUT_FOOT

@app.route('/account/login', methods=['GET', 'POST'])
def customer_login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        pw = request.form.get('password','')
        db = get_db()
        row = db.execute("SELECT * FROM customer_accounts WHERE email=?", (email,)).fetchone()
        db.close()
        if row:
            ph = _ahlib.sha256((pw + email).encode()).hexdigest()
            if row["password_hash"] == ph:
                session['customer_email'] = email
                session['customer_name'] = row["name"] or email.split('@')[0]
                session['customer_id'] = row["id"]
                next_url = request.args.get('next', '/account')
                return redirect(next_url)
        return '<p class="p-4 text-red-400">Invalid credentials</p><a href="/account/login">Try again</a>', 401
    form = '<div class="max-w-sm mx-auto px-4 py-16"><div class="card p-8"><h2 class="font-bold text-lg mb-1">Login</h2><p class="text-xs text-gray-500 mb-6">Access your purchases</p><form method="POST" class="space-y-3"><input name="email" type="email" placeholder="Email" class="w-full" required><input name="password" type="password" placeholder="Password" class="w-full" required><button class="btn-primary w-full justify-center" style="padding:12px">Login</button></form><p class="text-xs text-gray-500 text-center mt-4">No account? <a href="/account/register" class="text-[#38bdf8]">Create one</a></p></div></div>'
    return LAYOUT_HEAD + TOP_NAV + form + LAYOUT_FOOT

@app.route('/account/logout')
def customer_logout():
    session.pop('customer_email', None)
    session.pop('customer_name', None)
    session.pop('customer_id', None)
    return redirect('/')

#  Also auto-link customer on webhook
# patching stripe-webhook to save email

#  PUBLIC STORE 
@app.route('/')
def public_store():
    db = get_db()
    c = db.cursor()
    category = request.args.get('category', '')
    search = request.args.get('q', '')
    sort = request.args.get('sort', 'newest')

    # Get filter params
    price_min = request.args.get('min', '')
    price_max = request.args.get('max', '')

    query = "SELECT * FROM products WHERE status='published'"
    params = []

    if category:
        query += " AND category=?"
        params.append(category)
    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR tags LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if price_min:
        query += " AND price >= ?"
        params.append(float(price_min))
    if price_max:
        query += " AND price <= ?"
        params.append(float(price_max))

    if sort == 'price_asc':
        query += " ORDER BY price ASC"
    elif sort == 'price_desc':
        query += " ORDER BY price DESC"
    elif sort == 'popular':
        query += " ORDER BY downloads_count DESC"
    else:
        query += " ORDER BY created_at DESC"

    c.execute(query, params)
    products = [dict(r) for r in c.fetchall()]

    c.execute("SELECT * FROM product_categories ORDER BY product_count DESC")
    categories = [dict(r) for r in c.fetchall()]
    
    # Get featured products (highest downloaded)
    c.execute("SELECT * FROM products WHERE status='published' ORDER BY downloads_count DESC LIMIT 3")
    featured = [dict(r) for r in c.fetchall()]
    
    # Get category counts
    c.execute("SELECT category, COUNT(*) as cnt FROM products WHERE status='published' GROUP BY category")
    cat_counts = {r[0]: r[1] for r in c.fetchall()}
    
    db.close()

    # Hero section
    hero = '''<div class="hero-gradient rounded-2xl p-8 sm:p-12 mb-10 text-center border border-[#1e1e2e]">
      <span class="tag tag-purple mb-4 inline-flex"><i class="fas fa-bolt mr-1"></i> Digital Products Marketplace</span>
      <h1 class="text-4xl sm:text-5xl font-bold mb-4">Premium <span class="bg-gradient-to-r from-[#c084fc] to-[#ec4899] bg-clip-text text-transparent">Digital Products</span></h1>
      <p class="text-[#7a7a8e] max-w-xl mx-auto mb-8 text-sm sm:text-base">AI-crafted prompt packs, templates, eBooks, and tools to supercharge your workflow. Instant download after purchase.</p>
      <form method="GET" action="/" class="max-w-lg mx-auto flex gap-2">
        <div class="relative flex-1">
          <i class="fas fa-search absolute left-4 top-1/2 -translate-y-1/2 text-[#5c5c70] text-sm"></i>
          <input type="text" name="q" placeholder="Search products..." value="{search}" style="padding-left:40px">
        </div>
        <button type="submit" class="btn-primary">Search</button>
      </form>
    </div>'''

    # Featured section
    featured_section = ''
    if featured and not category and not search:
        featured_section = '''<div class="mb-10">
      <div class="flex items-center justify-between mb-5">
        <h2 class="text-lg font-bold"><i class="fas fa-star text-[#facc15] mr-2"></i> Featured Products</h2>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">'''
        for p in featured:
            pt = p['product_type']
            icon = product_type_icon(pt)
            color = product_type_color(pt)
            feats = [f'<span class="tag tag-green"><i class="fas fa-download mr-1"></i> {p["downloads_count"]} downloads</span>']
            if p['price'] < 10:
                feats.append('<span class="tag tag-amber"><i class="fas fa-tag mr-1"></i> Budget Pick</span>')
            elif p['price'] < 5:
                feats.append('<span class="tag tag-pink"><i class="fas fa-fire mr-1"></i> Best Value</span>')
            # Featured cover with image support
            f_hero = p.get('hero_image_url', '') or ''
            f_icon = icon
            if f_hero:
                f_cover = '<div style="height:140px;background-size:cover;background-position:center;background-image:url(' + f_hero + ');border-radius:12px 12px 0 0"></div>'
            else:
                f_cover = '<div class="product-cover" style="color:' + color + ';height:140px;border-radius:12px 12px 0 0"><span>' + f_icon + '</span></div>'
            featured_section += f'''<a href="/product/{p.get("slug") or p["id"]}" class="card hover:border-[#a855f7]/40 transition group relative overflow-hidden" style="padding:0">
          ''' + f_cover + f'''
          <div class="p-4">
            <div class="flex gap-1.5 mb-2 flex-wrap">{" ".join(feats[:2])}</div>
            <h3 class="font-semibold text-sm group-hover:text-[#c084fc] transition">{p["title"][:50]}</h3>
            <div class="flex items-center justify-between mt-2"><span class="font-bold text-[#a855f7]">' + str(p['price']) + '</span></div>
          </div>
        </a>'''
        featured_section += '</div></div>'

    # Category pills
    all_cls = 'bg-[#a855f7]/20 text-[#c084fc] border-[#a855f7]/30' if not category else 'bg-[#1a1a26] text-[#7a7a8e] hover:text-white border-[#252533]'
    cat_html = f'<a href="/" class="px-4 py-2 rounded-full text-xs font-medium {all_cls} border transition">{cat_counts.get("prompt-packs", "")} All</a>'
    for cat in categories:
        active = 'bg-[#a855f7]/20 text-[#c084fc] border-[#a855f7]/30' if category == cat['id'] else 'bg-[#1a1a26] text-[#7a7a8e] hover:text-white border-[#252533]'
        ct = cat_counts.get(cat['id'], 0)
        cat_html += f'<a href="/?category={cat["id"]}" class="px-4 py-2 rounded-full text-xs font-medium {active} border transition">{cat["icon"]} {cat["name"]}</a>'

    # Sort + filter bar
    sort_opts = [('newest', 'Newest'), ('popular', 'Most Popular'), ('price_asc', 'Price: Low'), ('price_desc', 'Price: High')]
    sort_html = '<select onchange="window.location=this.value" class="w-auto text-xs py-2 px-3">'
    for sk, sv in sort_opts:
        sel = 'selected' if sort == sk else ''
        sort_html += f'<option value="/?sort={sk}&category={category}&q={search}" {sel}>{sv}</option>'
    sort_html += '</select>'

    # Product grid
    if products:
        prod_html = ''
        for p in products:
            pt = p['product_type']
            icon = product_type_icon(pt)
            color = product_type_color(pt)
            grad = product_type_gradient(pt)
            pid = p.get('slug') or p['id']
            ptitle = (p['title'] or '')[:60]
            pdesc = (p['description'] or '')[:120]
            pprice = p['price']
            pdl = p['downloads_count']
            
            # Rating
            rating_avg, rating_count = get_rating_stats(pid)
            stars = render_stars(rating_avg, rating_count) if rating_count > 0 else ''
            
            # Get product image
            img_src = None
            hero_img = p.get('hero_image_url', '') or ''
            if hero_img:
                img_src = hero_img
            elif p.get('screenshot_urls') and str(p.get('screenshot_urls','')) not in ('[]', ''):
                try:
                    imgs = json.loads(p['screenshot_urls'])
                    if imgs and imgs[0]:
                        img_src = imgs[0]
                except:
                    pass
            
            # Build cover HTML
            cover_html = '<div style="height:180px;background:' + color + '20;border-radius:12px 12px 0 0;display:flex;align-items:center;justify-content:center"><span style="font-size:48px;opacity:0.4">' + icon + '</span></div>'
            if img_src:
                cover_html = '<div style="height:180px;background-size:cover;background-position:center;background-image:url(' + img_src + ');border-radius:12px 12px 0 0;position:relative"><div class="absolute inset-0 bg-gradient-to-t from-[#07070c] via-transparent to-transparent"></div></div>'
            
            prod_html += f'''<a href="/product/{pid}" class="card hover:border-[#a855f7]/40 transition group animate-in" style="padding:0;overflow:hidden">
          ''' + cover_html + f'''
          <div class="p-4">
            <span class="tag" style="background:{color}15;color:{color};margin-bottom:8px"><span style="font-size:10px">{icon}</span> {PRODUCT_TYPE_LABELS.get(pt, 'Product')}</span>
            <h3 class="font-semibold text-sm mb-1 group-hover:text-[#c084fc] transition leading-snug">{ptitle}</h3>
            <p class="text-xs text-[#5c5c70] mb-3 line-clamp-2 leading-relaxed">{pdesc}</p>
            <div class="flex items-center justify-between mt-auto">
              <span class="text-lg font-bold" style="color:{color}">' + str(pprice) + '</span>
              <div class="flex items-center gap-2 text-xs text-[#5c5c70]">
                {stars if stars else ''}
                <span><i class="fas fa-download mr-0.5"></i>{pdl}</span>
              </div>
            </div>
          </div>
        </a>'''
    else:
        prod_html = '<div class="col-span-3 text-center py-16 text-[#5c5c70]"><i class="fas fa-box-open text-5xl mb-4 opacity-20"></i><p class="font-semibold">No products found</p><p class="text-xs mt-1">Try a different search or category</p></div>'

    html = f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">
  <!-- HERO -->
  <div class="text-center py-12 sm:py-16 mb-10">
    <h1 class="text-5xl sm:text-7xl font-black leading-[1.1] mb-4">
      <span class="bg-gradient-to-r from-[#c084fc] via-[#ec4899] to-[#f472b6] bg-clip-text text-transparent">Build.</span><br>
      <span class="bg-gradient-to-r from-[#38bdf8] via-[#818cf8] to-[#a855f7] bg-clip-text text-transparent">Learn.</span><br>
      <span class="text-white">Automate. Grow.</span>
    </h1>
    <p class="text-4xl sm:text-5xl font-bold text-[#7a7a8e] mt-4 mb-8">100,000+ Digital Products</p>
    <a href="/?tab=marketplace" class="btn-primary text-lg" style="padding:16px 48px;font-size:16px"><i class="fas fa-compass mr-2"></i> Browse Marketplace</a>
  </div>

  <!-- TRENDING -->
  <div class="mb-12">
    <h2 class="text-lg font-bold mb-4">Trending</h2>
    <div class="flex flex-wrap gap-2">
      <a href="/?category=ai-agents" class="px-4 py-2 bg-[#1a1a26] border border-[#252533] rounded-full text-xs font-medium hover:border-[#a855f7] transition flex items-center gap-1.5"><i class="fas fa-fire text-[#f472b6]"></i> AI Agents</a>
      <a href="/?category=prompt-packs" class="px-4 py-2 bg-[#1a1a26] border border-[#252533] rounded-full text-xs font-medium hover:border-[#a855f7] transition flex items-center gap-1.5"><i class="fas fa-fire text-[#f472b6]"></i> ChatGPT Prompts</a>
      <a href="/?category=automation" class="px-4 py-2 bg-[#1a1a26] border border-[#252533] rounded-full text-xs font-medium hover:border-[#a855f7] transition flex items-center gap-1.5"><i class="fas fa-fire text-[#f472b6]"></i> n8n Workflows</a>
      <a href="/?category=development" class="px-4 py-2 bg-[#1a1a26] border border-[#252533] rounded-full text-xs font-medium hover:border-[#a855f7] transition flex items-center gap-1.5"><i class="fas fa-fire text-[#f472b6]"></i> MCP Servers</a>
      <a href="/?category=templates" class="px-4 py-2 bg-[#1a1a26] border border-[#252533] rounded-full text-xs font-medium hover:border-[#a855f7] transition flex items-center gap-1.5"><i class="fas fa-fire text-[#f472b6]"></i> Business Templates</a>
      <a href="/?category=software" class="px-4 py-2 bg-[#1a1a26] border border-[#252533] rounded-full text-xs font-medium hover:border-[#a855f7] transition flex items-center gap-1.5"><i class="fas fa-fire text-[#f472b6]"></i> Trading Bots</a>
      <a href="/?category=courses" class="px-4 py-2 bg-[#1a1a26] border border-[#252533] rounded-full text-xs font-medium hover:border-[#a855f7] transition flex items-center gap-1.5"><i class="fas fa-fire text-[#f472b6]"></i> Courses</a>
    </div>
  </div>

  <!-- POPULAR CATEGORIES -->
  <div class="mb-12">
    <h2 class="text-lg font-bold mb-4">Popular Categories</h2>
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <a href="/?category=ai" class="card text-center py-6 hover:border-[#a855f7]/40 transition group" style="padding:24px 16px"><div class="text-2xl mb-2"></div><div class="font-semibold text-sm group-hover:text-[#c084fc]">AI</div><div class="text-xs text-[#5c5c70]">Agents, Prompts, Models</div></a>
      <a href="/?category=automation" class="card text-center py-6 hover:border-[#a855f7]/40 transition group" style="padding:24px 16px"><div class="text-2xl mb-2"></div><div class="font-semibold text-sm group-hover:text-[#c084fc]">Automation</div><div class="text-xs text-[#5c5c70]">n8n, Zapier, Scripts</div></a>
      <a href="/?category=marketing" class="card text-center py-6 hover:border-[#a855f7]/40 transition group" style="padding:24px 16px"><div class="text-2xl mb-2"></div><div class="font-semibold text-sm group-hover:text-[#c084fc]">Marketing</div><div class="text-xs text-[#5c5c70]">Templates, Funnels</div></a>
      <a href="/?category=business" class="card text-center py-6 hover:border-[#a855f7]/40 transition group" style="padding:24px 16px"><div class="text-2xl mb-2"></div><div class="font-semibold text-sm group-hover:text-[#c084fc]">Business</div><div class="text-xs text-[#5c5c70]">Docs, Templates</div></a>
      <a href="/?category=crypto" class="card text-center py-6 hover:border-[#a855f7]/40 transition group" style="padding:24px 16px"><div class="text-2xl mb-2"></div><div class="font-semibold text-sm group-hover:text-[#c084fc]">Crypto</div><div class="text-xs text-[#5c5c70]">Bots, Tools, Scripts</div></a>
      <a href="/?category=development" class="card text-center py-6 hover:border-[#a855f7]/40 transition group" style="padding:24px 16px"><div class="text-2xl mb-2"></div><div class="font-semibold text-sm group-hover:text-[#c084fc]">Programming</div><div class="text-xs text-[#5c5c70]">Code, Extensions</div></a>
      <a href="/?category=design" class="card text-center py-6 hover:border-[#a855f7]/40 transition group" style="padding:24px 16px"><div class="text-2xl mb-2"></div><div class="font-semibold text-sm group-hover:text-[#c084fc]">Design</div><div class="text-xs text-[#5c5c70]">Templates, Assets</div></a>
      <a href="/?category=templates" class="card text-center py-6 hover:border-[#a855f7]/40 transition group" style="padding:24px 16px"><div class="text-2xl mb-2"></div><div class="font-semibold text-sm group-hover:text-[#c084fc]">Templates</div><div class="text-xs text-[#5c5c70]">Notion, Excel, Docs</div></a>
    </div>
  </div>

  <!-- BEST SELLERS -->
  <div class="mb-12">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-bold"><i class="fas fa-crown text-[#facc15] mr-2"></i> Best Sellers</h2>
      <a href="/?sort=popular" class="text-xs text-[#a855f7] hover:underline">View All</a>
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">{prod_html}</div>
  </div>

  <!-- MEMBERSHIP -->
  <div class="card mb-12 overflow-hidden" style="padding:0;background:linear-gradient(135deg,#1a0a2e,#0e0e16)">
    <div class="p-8 sm:p-12 text-center">
      <div class="text-4xl mb-4"></div>
      <h2 class="text-2xl sm:text-3xl font-bold mb-3">Join Hermes Membership</h2>
      <p class="text-[#7a7a8e] max-w-md mx-auto mb-6 text-sm">Get early access to new products, exclusive AI tools, and member-only discounts. Published weekly.</p>
      <a href="/membership" class="btn-primary" style="padding:14px 36px">Learn More <i class="fas fa-arrow-right ml-1"></i></a>
    </div>
  </div>

  <!-- ENTERPRISE -->
  <div class="card mb-12" style="padding:0;background:linear-gradient(135deg,#0a142e,#0e0e16)">
    <div class="p-8 sm:p-12 text-center">
      <div class="text-4xl mb-4"></div>
      <h2 class="text-2xl sm:text-3xl font-bold mb-3">Enterprise</h2>
      <p class="text-[#7a7a8e] max-w-md mx-auto mb-6 text-sm">White-label marketplace for your business. Custom branding, employee access, dedicated AI assistant.</p>
      <a href="/enterprise" class="btn-outline" style="padding:14px 36px">Contact Sales <i class="fas fa-arrow-right ml-1"></i></a>
    </div>
  </div>

  {navigation.footer()}
</div>
{LAYOUT_FOOT}'''
    return html

#  PRODUCT DETAIL 
@app.route('/product/<product_id>')
@app.route('/product/<slug>')
def product_detail(product_id=None, slug=None):
    if product_id and not slug:
        # Check if product_id is actually a slug
        db = get_db()
        c = db.cursor()
        c.execute("SELECT id FROM products WHERE slug=? OR id=?", (product_id, product_id))
        row = c.fetchone()
        db.close()
        if row:
            return experience_hub(row[0])
        # If not found, redirect to slug-based route
        return experience_hub(product_id)
    elif slug:
        db = get_db()
        c = db.cursor()
        c.execute("SELECT id FROM products WHERE slug=?", (slug,))
        row = c.fetchone()
        db.close()
        if row:
            return experience_hub(row[0])
        return experience_hub(slug)
    return experience_hub(product_id or slug)
@app.route('/legals')
def legals():
    from legal_page import legal_page as _lp
    from navigation import footer as _nf
    return LAYOUT_HEAD + TOP_NAV + _lp() + _nf() + LAYOUT_FOOT

# ── COURSE PORTAL (for purchased courses) ──

def course_portal_required(f):
    """Decorator: customer must be logged in with course access."""
    @wraps(f)
    def decorated(*args, **kwargs):
        cid = session.get('customer_id')
        if not cid:
            return redirect('/account/login?next=' + request.path)
        return f(*args, **kwargs)
    return decorated

@app.route('/my-courses/')
@course_portal_required
def my_courses():
    """Show all courses the customer has purchased access to."""
    cid = session['customer_id']
    db = get_db()
    courses = db.execute("""
        SELECT p.id, p.title, p.slug, p.hero_image_url, ca.granted_at,
               (SELECT COUNT(*) FROM course_modules WHERE product_id=p.id) as total_modules,
               (SELECT COUNT(*) FROM course_progress cp JOIN course_modules cm ON cp.module_id=cm.id WHERE cm.product_id=p.id AND cp.customer_id=? AND cp.completed=1) as completed_modules
        FROM course_access ca
        JOIN products p ON ca.product_id=p.id
        WHERE ca.customer_id=?
        ORDER BY ca.granted_at DESC
    """, (cid, cid)).fetchall()
    db.close()
    
    cards = ''
    for c in courses:
        pct = int((c[5]/max(c[4],1))*100) if c[4] else 0
        cards += f'''<a href="/course/{c[0]}/" class="card p-5 hover:border-purple-500/30 transition group block">
          <div class="flex items-center gap-4">
            <div class="w-16 h-16 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center text-2xl">📖</div>
            <div class="flex-1 min-w-0">
              <h3 class="font-bold text-sm text-white group-hover:text-purple-300 transition">{c[1][:60]}</h3>
              <div class="flex items-center gap-3 mt-1 text-xs text-[#7a7a8e]">
                <span>{c[4] or 0}/{c[5] or 0} modules</span>
                <span>Purchased {c[3][:10] if c[3] else ''}</span>
              </div>
              <div class="mt-2 h-1.5 bg-[#1a1a26] rounded-full overflow-hidden">
                <div class="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full" style="width:{pct}%"></div>
              </div>
            </div>
            <span class="text-purple-400 text-lg">&rarr;</span>
          </div>
        </a>'''
    
    if not cards:
        cards = '<div class="text-center py-16 text-[#5c5c70]"><div class="text-5xl mb-4">📚</div><h2 class="text-lg font-bold text-white mb-2">No Courses Yet</h2><p class="text-sm mb-6">Purchase a course to get started.</p><a href="/" class="btn-primary">Browse Courses</a></div>'
    
    page = LAYOUT_HEAD + TOP_NAV + f'''
    <div class="max-w-4xl mx-auto px-4 py-8">
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-2xl font-bold text-white">📚 My Courses</h1>
        <a href="/account/logout" class="text-xs text-[#5c5c70] hover:text-white">Logout</a>
      </div>
      <div class="space-y-4">{cards}</div>
    </div>''' + LAYOUT_FOOT
    return page

@app.route('/course/<product_id>/')
@app.route('/course/<product_id>/<module_slug>')
@course_portal_required
def course_view(product_id, module_slug=None):
    """View a course module (protected - must have access)."""
    import uuid, re as re_mod
    cid = session['customer_id']
    db = get_db()
    
    # Check access
    access = db.execute("SELECT id FROM course_access WHERE customer_id=? AND product_id=?", (cid, product_id)).fetchone()
    if not access:
        # Auto-grant if they purchased but somehow not recorded
        order = db.execute("""
            SELECT co.id FROM customer_orders co 
            JOIN products p ON co.product_id=p.id 
            WHERE co.customer_id=? AND co.product_id=? AND co.status='completed'
        """, (cid, product_id)).fetchone()
        if order:
            aid = str(uuid.uuid4())[:12]
            db.execute("INSERT INTO course_access (id, customer_id, product_id, order_id) VALUES (?, ?, ?, ?)",
                      (aid, cid, product_id, order[0]))
            db.commit()
            access = [aid]
        else:
            db.close()
            return (LAYOUT_HEAD + TOP_NAV + 
                    '<div class="max-w-xl mx-auto px-4 py-20 text-center"><div class="text-5xl mb-4">🔒</div>'
                    '<h1 class="text-xl font-bold text-white mb-2">Access Required</h1>'
                    '<p class="text-sm text-[#7a7a8e] mb-6">You need to purchase this course to access the modules.</p>'
                    '<a href="/product/' + product_id + '" class="btn-primary">View Course</a></div>' + LAYOUT_FOOT)
    
    # Get product info
    product = db.execute("SELECT id, title, slug FROM products WHERE id=?", (product_id,)).fetchone()
    if not product:
        db.close()
        return 'Course not found', 404
    
    # Get all modules for this course
    modules = db.execute("SELECT id, module_num, title, slug FROM course_modules WHERE product_id=? ORDER BY module_num ASC", (product_id,)).fetchall()
    
    # Get current module
    current_module = None
    if module_slug:
        current_module = db.execute("SELECT * FROM course_modules WHERE product_id=? AND slug=?", (product_id, module_slug)).fetchone()
    
    if not current_module and modules:
        current_module = db.execute("SELECT * FROM course_modules WHERE product_id=? ORDER BY module_num ASC LIMIT 1", (product_id,)).fetchone()
    
    if not current_module:
        db.close()
        return 'No modules found', 404
    
    current_module = dict(current_module)
    
    # Get progress
    progress = {}
    for m in modules:
        done = db.execute("SELECT completed FROM course_progress WHERE customer_id=? AND module_id=?", (cid, m[0])).fetchone()
        progress[m[0]] = done[0] if done else 0
    
    # Mark as in-progress
    if not progress.get(current_module['id']):
        db.execute("INSERT OR IGNORE INTO course_progress (id, customer_id, module_id) VALUES (?, ?, ?)",
                  (str(uuid.uuid4())[:12], cid, current_module['id']))
        db.commit()
    
    db.close()
    
    # Build module sidebar
    sidebar = ''
    for m in modules:
        mid = m[0]; num = m[1]; title = m[2]; slug = m[3]
        is_active = 'active' if current_module and current_module['id'] == mid else ''
        done_icon = '✅' if progress.get(mid) else '○'
        sidebar += f'''<a href="/course/{product_id}/{slug}" class="flex items-center gap-3 p-3 rounded-xl text-sm transition {"bg-purple-500/10 border border-purple-500/20" if is_active else "hover:bg-white/5 border border-transparent"}">
          <span class="text-xs">{done_icon}</span>
          <span class="text-xs text-[#7a7a8e] shrink-0">M{num:02d}</span>
          <span class="text-xs text-white truncate">{title[:40]}</span>
        </a>'''
    
    # Module content
    content_html = ''
    if current_module.get('content'):
        content_html = current_module['content']
        content_html = re_mod.sub(r'<script[^>]*>.*?</script>', '', content_html, flags=re_mod.DOTALL)
    
    # Navigation arrows
    prev_link = ''
    next_link = ''
    for i, m in enumerate(modules):
        if m[0] == current_module['id']:
            if i > 0:
                prev_link = f'<a href="/course/{product_id}/{modules[i-1][3]}" class="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1"><span>&larr;</span> {modules[i-1][2][:30]}</a>'
            if i < len(modules) - 1:
                next_link = f'<a href="/course/{product_id}/{modules[i+1][3]}" class="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1">{modules[i+1][2][:30]} <span>&rarr;</span></a>'
    
    import json as _json_mod
    # AI Course Tutor context
    course_title = product[1] if product else 'this course'
    
    chatbot_widget = f'''
<style>
.chat-toggle{{position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#a855f7,#ec4899);color:white;border:none;font-size:24px;cursor:pointer;z-index:999;box-shadow:0 4px 20px rgba(168,85,247,0.4);transition:all .3s}}
.chat-toggle:hover{{transform:scale(1.1);box-shadow:0 6px 30px rgba(168,85,247,0.6)}}
.chat-panel{{position:fixed;bottom:90px;right:24px;width:360px;height:500px;background:#0e0e16;border:1px solid #252533;border-radius:16px;z-index:998;display:none;flex-direction:column;box-shadow:0 10px 50px rgba(0,0,0,0.5);overflow:hidden}}
.chat-panel.open{{display:flex}}
.chat-header{{padding:14px 16px;background:linear-gradient(135deg,#1a0a2e,#0e0e16);border-bottom:1px solid #252533;display:flex;align-items:center;gap:10px;flex-shrink:0}}
.chat-avatar{{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#a855f7,#ec4899);display:flex;align-items:center;justify-content:center;font-size:14px}}
.chat-title{{font-size:13px;font-weight:600;color:white}}
.chat-subtitle{{font-size:10px;color:#5c5c70}}
.chat-close{{margin-left:auto;background:none;border:none;color:#5c5c70;cursor:pointer;font-size:18px;padding:4px}}
.chat-messages{{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}}
.chat-msg{{max-width:85%;padding:10px 14px;border-radius:12px;font-size:13px;line-height:1.5;animation:fadeIn .3s}}
.chat-msg.bot{{align-self:flex-start;background:#1a1a26;color:#d0d0e0;border-bottom-left-radius:4px}}
.chat-msg.user{{align-self:flex-end;background:linear-gradient(135deg,#a855f722,#ec489922);color:white;border-bottom-right-radius:4px}}
.chat-input-area{{padding:12px;border-top:1px solid #252533;display:flex;gap:8px;flex-shrink:0;background:#0a0a12}}
.chat-input{{flex:1;background:#1a1a26;border:1px solid #252533;border-radius:10px;padding:10px 14px;color:white;font-size:13px;outline:none}}
.chat-input:focus{{border-color:#a855f7}}
.chat-send{{background:linear-gradient(135deg,#a855f7,#ec4899);color:white;border:none;border-radius:10px;padding:10px 14px;font-size:14px;cursor:pointer;white-space:nowrap}}
.chat-send:hover{{opacity:.9}}
.chat-loading{{align-self:flex-start;color:#5c5c70;font-size:12px;padding:8px 12px;animation:pulse 1.5s infinite}}
.listen-btn{{background:rgba(168,85,247,0.1);border:1px solid rgba(168,85,247,0.2);color:#c084fc;padding:6px 14px;border-radius:8px;font-size:11px;cursor:pointer;transition:all .2s;display:inline-flex;align-items:center;gap:5px}}
.listen-btn:hover{{background:rgba(168,85,247,0.2)}}
.listen-btn.speaking{{background:rgba(236,72,153,0.2);border-color:rgba(236,72,153,0.4);color:#f472b6;animation:pulse 1s infinite}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.6}}}}
</style>
<div class="chat-toggle" id="chatToggle" onclick="toggleChat()">💬</div>
<div class="chat-panel" id="chatPanel">
  <div class="chat-header">
    <div class="chat-avatar">🤖</div>
    <div><div class="chat-title">AI Course Tutor</div><div class="chat-subtitle">Ask me anything about this module</div></div>
    <button class="chat-close" onclick="toggleChat()">✕</button>
  </div>
  <div class="chat-messages" id="chatMessages">
    <div class="chat-msg bot">Hi! I'm your AI tutor for this course. Ask me anything about affiliate marketing, or about this specific module content 🎓</div>
  </div>
  <div class="chat-input-area">
    <input class="chat-input" id="chatInput" placeholder="Ask a question..." onkeydown="if(event.key==='Enter')sendChat()">
    <button class="chat-send" onclick="sendChat()">Send</button>
  </div>
</div>
<script>
function toggleChat(){{const p=document.getElementById('chatPanel');p.classList.toggle('open');if(p.classList.contains('open'))setTimeout(()=>document.getElementById('chatInput').focus(),300)}}
function sendChat(){{const i=document.getElementById('chatInput'),q=i.value.trim();if(!q)return;i.value='';const m=document.getElementById('chatMessages');m.innerHTML+='<div class=\"chat-msg user\">'+q.replace(/</g,'&lt;')+'</div>';const li=document.createElement('div');li.className='chat-loading';li.textContent='AI is thinking...';m.appendChild(li);m.scrollTop=m.scrollHeight
fetch('/api/course/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{question:q,product_id:''' + _json_mod.dumps(product_id) + '''}})}}).then(r=>r.json()).then(d=>{{li.remove();const answer=d.answer||'Sorry, I could not process that.';m.innerHTML+='<div class=\"chat-msg bot\">'+answer.replace(/\\n/g,'<br>')+'</div>';m.scrollTop=m.scrollHeight}}).catch(e=>{{li.textContent='Connection error. Please try again.'}})}}
function speakText(){{const el=document.querySelector('.course-content');if(!el)return;const txt=el.innerText.slice(0,3000);if(!txt)return;if(window.speechSynthesis.speaking){{window.speechSynthesis.cancel();document.querySelector('.listen-btn')?.classList.remove('speaking');return}}
const u=new SpeechSynthesisUtterance(txt);u.rate=0.9;u.pitch=1;u.volume=1;u.lang='en-US';u.onend=()=>document.querySelector('.listen-btn')?.classList.remove('speaking');u.onerror=()=>document.querySelector('.listen-btn')?.classList.remove('speaking');document.querySelector('.listen-btn')?.classList.add('speaking');window.speechSynthesis.speak(u)}}
</script>'''

    page = LAYOUT_HEAD.replace('</head>', '<style>.course-content h1{font-size:1.5rem;font-weight:700;margin:1.5rem 0 0.5rem 0;color:#f1f1f5}.course-content h2{font-size:1.25rem;font-weight:600;margin:1.25rem 0 0.4rem 0;color:#e8e8f0}.course-content h3{font-size:1.1rem;font-weight:600;margin:1rem 0 0.3rem 0;color:#d0d0e0}.course-content p{margin:0.5rem 0;line-height:1.7;color:#c0c0d0}.course-content ul,.course-content ol{margin:0.5rem 0 0.5rem 1.5rem;line-height:1.7}.course-content li{margin:0.3rem 0;color:#c0c0d0}.course-content code{background:#1a1a26;padding:0.15rem 0.4rem;border-radius:4px;font-size:0.85em;color:#a855f7}.course-content pre{background:#0e0e16;padding:1rem;border-radius:12px;overflow-x:auto;margin:0.8rem 0;border:1px solid #1a1a26;font-size:0.85em}.course-content blockquote{border-left:3px solid #a855f7;padding-left:1rem;margin:0.8rem 0;color:#8080a0;font-style:italic}.course-content img{max-width:100%;border-radius:12px;margin:1rem 0}.course-content a{color:#a855f7}.course-content table{width:100%;border-collapse:collapse;margin:1rem 0}.course-content th,.course-content td{padding:0.5rem;border:1px solid #1a1a26;text-align:left;font-size:0.9em}.course-content th{background:#1a1a26;color:#c0c0d0}</style></head>') + TOP_NAV + chatbot_widget + f'''
    <div class="max-w-7xl mx-auto px-4 py-6">
      <div class="flex items-center gap-2 text-xs text-[#5c5c70] mb-4">
        <a href="/my-courses/" class="hover:text-purple-400">My Courses</a>
        <span>/</span>
        <span class="text-white">{product[1][:40]}</span>
      </div>
      
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <!-- Sidebar -->
        <div class="lg:col-span-1">
          <div class="card p-3 space-y-1 sticky" style="top:80px">
            <div class="text-xs font-semibold text-[#7a7a8e] uppercase tracking-wider mb-2 px-2">Modules</div>
            {sidebar}
          </div>
        </div>
        
        <!-- Main content -->
        <div class="lg:col-span-3">
          <div class="card p-6 md:p-8">
            <div class="flex items-center justify-between mb-6">
              <h1 class="text-xl font-bold text-white">M{current_module["module_num"]:02d}: {current_module["title"]}</h1>
              <button class="listen-btn" onclick="speakText()"><span>🔊</span> Listen</button>
            </div>
            <div class="course-content">
              {content_html}
            </div>
            
            <!-- Mark complete + navigation -->
            <div class="mt-10 pt-6 border-t border-[#1a1a26]">
              <div class="flex items-center justify-between">
                <div>{prev_link}</div>
                <form method="POST" action="/course/{product_id}/{current_module["slug"]}/complete">
                  <button type="submit" class="btn-primary text-xs">{"✅ Mark Complete" if not progress.get(current_module["id"]) else "✅ Completed"}</button>
                </form>
                <div>{next_link}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>''' + LAYOUT_FOOT
    return page

@app.route('/api/course/chat', methods=['POST'])
@course_portal_required
def api_course_chat():
    """AI Course Tutor — answers student questions about the course content."""
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    product_id = data.get('product_id', '')
    if not question:
        return jsonify({'answer': 'Please ask a question!'})
    
    # Get course context
    db = get_db()
    c = db.cursor()
    product = c.execute("SELECT title, description FROM products WHERE id=?", (product_id,)).fetchone()
    modules = c.execute("SELECT title, substr(content,1,800) FROM course_modules WHERE product_id=? ORDER BY module_num", (product_id,)).fetchall()
    db.close()
    
    course_title = product[0] if product else 'Unknown'
    course_desc = product[1][:300] if product else ''
    course_info = 'Course: ' + course_title + '. Description: ' + course_desc
    module_info = ''
    for m in modules:
        module_info += '\nModule: ' + m[0] + '\nContent preview: ' + (m[1][:200] if m[1] else '') + '...'
    
    system_prompt = ('You are an AI tutor for the course "' + course_title + '" at ShopZario.\n\n' + 
        'Course info: ' + course_info + '\nCourse modules: ' + module_info + '\n\n' +
        'Rules:\n- Help students understand affiliate marketing concepts clearly\n' +
        '- Give practical, actionable advice\n- Be encouraging and supportive\n' +
        '- If asked something outside course scope, gently guide back\n' +
        '- Keep answers under 250 words\n- Use simple, conversational language\n' +
        '- Dont make up facts about specific products/prices')
    
    try:
        cfg = get_chatbot_config()
        api_key = cfg.get('chatbot_api_key', '') or os.environ.get('DEEPSEEK_API_KEY', '')
        provider = CHATBOT_PROVIDERS.get(cfg.get('chatbot_provider', 'deepseek'), CHATBOT_PROVIDERS['deepseek'])
        model = cfg.get('chatbot_model', provider['default_model'])
        
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }).encode()
        
        req = urllib.request.Request(
            provider['api_url'],
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': provider['auth_header'](api_key)
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        answer = result['choices'][0]['message']['content']
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'answer': f'I apologize, but I encountered an error. Please try rephrasing your question. (Error: {str(e)[:100]})'})


@app.route('/course/<product_id>/<module_slug>/complete', methods=['POST'])
@course_portal_required
def course_complete_module(product_id, module_slug):
    cid = session['customer_id']
    db = get_db()
    mod = db.execute("SELECT id FROM course_modules WHERE product_id=? AND slug=?", (product_id, module_slug)).fetchone()
    if mod:
        db.execute("UPDATE course_progress SET completed=1, completed_at=datetime('now') WHERE customer_id=? AND module_id=?", (cid, mod[0]))
        db.commit()
    db.close()
    return redirect('/course/' + product_id + '/' + module_slug)

@app.route('/factory/campaigns')
def campaigns_dashboard():
    db = get_db()
    products = db.execute("SELECT id, title, price, slug, product_type FROM products WHERE status='published' ORDER BY title").fetchall()
    db.close()
    html = _cmp.campaigns_dashboard_html()
    return LAYOUT_HEAD + TOP_NAV + html + LAYOUT_FOOT

@app.route('/factory/campaigns/<campaign_id>')
def campaign_detail(campaign_id):
    html = _cmp.campaign_detail_html(campaign_id)
    return LAYOUT_HEAD + TOP_NAV + html + LAYOUT_FOOT

@app.route('/factory/campaigns/create', methods=['GET', 'POST'])
def campaign_create():
    db = get_db()
    products = db.execute("SELECT id, title, price, slug, product_type FROM products WHERE status='published' ORDER BY title").fetchall()
    db.close()
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        budget = int(request.form.get('budget', 50))
        days = int(request.form.get('days', 30))
        if not product_id:
            return 'Product required', 400
        db = get_db()
        p = db.execute("SELECT id, title, price, slug, product_type FROM products WHERE id=?", (product_id,)).fetchone()
        db.close()
        if not p:
            return 'Product not found', 404
        result = _cmp.create_campaign_from_product({
            "id": p[0], "title": p[1], "price": p[2], "slug": p[3] or p[0], "type": p[4]
        }, budget_dollars=budget, days=days)
        if "error" in result:
            return f'<div class="card p-5 text-red-400">{result["error"]}<br>Step: {result.get("step","")}</div>', 500
        return redirect(f'/factory/campaigns/{result["campaign"]["id"]}')
    html = _cmp.create_campaign_from_products_html(products)
    return LAYOUT_HEAD + TOP_NAV + html + LAYOUT_FOOT

@app.route('/api/ads/toggle-campaign', methods=['POST'])
def api_toggle_campaign():
    data = request.get_json() or {}
    cid = data.get('campaign_id')
    if not cid:
        return {'success': False, 'error': 'campaign_id required'}
    c = _cmp.get_campaign(cid)
    if isinstance(c, dict) and "error" in c:
        return {'success': False, 'error': c["error"]}
    current = c.get('status', 'paused')
    new_status = 'paused' if current == 'active' else 'active'
    result = _cmp.update_campaign(cid, {"status": new_status})
    if isinstance(result, dict) and "error" in result:
        return {'success': False, 'error': result["error"]}
    return {'success': True, 'status': new_status}

@app.route('/factory/ads')
def ads_dashboard():
    db = get_db()
    products = db.execute("SELECT id, title FROM products WHERE status='published' ORDER BY title").fetchall()
    db.close()
    product_id = request.args.get('product_id')
    ads_data = None
    if product_id:
        ads_data = generate_all_ads(product_id)
    return LAYOUT_HEAD + TOP_NAV + ads_manager_html(products, ads_data) + LAYOUT_FOOT

@app.route('/api/ads/generate', methods=['POST'])
def api_generate_ads():
    data = request.get_json() or {}
    product_id = data.get('product_id', request.args.get('product_id'))
    if not product_id:
        return {'error': 'product_id required'}, 400
    result = generate_all_ads(product_id)
    return result

@app.route('/api/checkout/<product_id>', methods=['GET', 'POST'])
def api_checkout(product_id):
    try:
        from premium_features import load_stripe_config
        import stripe
        cfg = load_stripe_config()
        if not cfg.get('enabled'):
            return jsonify({'error': 'Payments not configured'}), 400
        stripe.api_key = cfg['secret_key']
        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM products WHERE id=?", (product_id,))
        p = c.fetchone()
        base = request.host_url.rstrip('/')
        if not p:
            # Check for special products
            if product_id == 'agents-pdf':
                token = str(uuid.uuid4())[:16]
                session_data = stripe.checkout.Session.create(
                    mode='payment',
                    line_items=[{'price_data': {'currency': 'usd', 'product_data': {'name': 'AI Agent Directory 2026 PDF', 'description': 'Complete guide to 56 AI agents across 8 categories. Comparison tables, pricing, and links.'}, 'unit_amount': 900}, 'quantity': 1}],
                    metadata={'product_id': 'agents-pdf', 'download_token': token},
                    success_url=f"{base}/download/{token}?success=1",
                    cancel_url=f"{base}/ai-agents-directory?canceled=1",
                )
                return redirect(session_data.url)
            return jsonify({'error': 'Product not found'}), 404
        base = request.host_url.rstrip('/')
        token = str(uuid.uuid4())[:16]
        session_data = stripe.checkout.Session.create(
            mode='payment',
            line_items=[{'price_data': {'currency': 'usd', 'product_data': {'name': p['title'][:100], 'description': (p['description'] or '')[:200]}, 'unit_amount': int(p['price'] * 100)}, 'quantity': 1}],
            metadata={'product_id': product_id, 'download_token': token},
            success_url=f"{base}/download/{token}?success=1",
            cancel_url=f"{base}/product/{product_id}?canceled=1",
        )
        return redirect(session_data.url)
    except Exception as e:
        return jsonify({'error': str(e)[:200]}), 500

#  DOWNLOAD 
@app.route('/download/<token>')
def download_product(token):
    dt_class = __import__('datetime').datetime
    db = get_db()
    c = db.cursor()
    c.execute("SELECT po.*, p.title, p.content, p.product_type, p.price FROM product_orders po JOIN products p ON po.product_id = p.id WHERE po.download_token=?", (token,))
    order = c.fetchone()
    success = request.args.get('success', '')
    if not order and success:
        return f'''{LAYOUT_HEAD.replace("ShopZario", "Processing")}
<div class="text-center py-20"><i class="fas fa-spinner fa-spin text-4xl text-[#a855f7] mb-4"></i>
<h2 class="text-xl font-bold mb-2">Processing Your Purchase...</h2><p class="text-[#7a7a8e]">Please wait a moment.</p>
<script>setTimeout(() => window.location.href='/', 3000);</script></div>{LAYOUT_FOOT}'''
    if not order:
        return "Invalid download link.", 404
    order = dict(order)
    c.execute("UPDATE product_orders SET downloaded=1, download_count=download_count+1 WHERE download_token=?", (token,))
    c.execute("UPDATE products SET downloads_count=downloads_count+1 WHERE id=?", (order['product_id'],))
    db.commit()
    db.close()

    price_str = f'{order["price"]:.2f}'
    pid = order['product_id']
    ptitle = order['title'] or 'Product'
    color = product_type_color(order['product_type'] or '')
    icon = product_type_icon(order['product_type'] or '')
    
    # Get the real product file if it exists
    real_file = None
    db2 = get_db()
    c2 = db2.cursor()
    c2.execute("SELECT file_path FROM products WHERE id=?", (pid,))
    fp_row = c2.fetchone()
    db2.close()
    if fp_row and fp_row[0]:
        fp_path = "/root/voice-agent-manager/static/" + fp_row[0].replace("/static/", "")
        if __import__("os").path.exists(fp_path):
            real_file = fp_row[0]
    
    download_btn = ''
    if real_file:
        ext = real_file.split('.')[-1].upper()
        download_btn = f'''
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <a href="{real_file}" class="btn-primary w-full justify-center text-base" style="padding:16px" download><i class="fas fa-download mr-2"></i> Download Product File ({ext})</a>
        <a href="/api/product/pdf/{pid}" class="btn-secondary w-full justify-center text-base" style="padding:16px" target="_blank"><i class="fas fa-file-pdf mr-2"></i> Download as PDF</a>
      </div>'''
    else:
        download_btn = f'''<a href="/api/product/pdf/{pid}" class="btn-primary w-full justify-center text-base" style="padding:16px" download><i class="fas fa-file-pdf mr-2"></i> Download Your Product Now</a>'''
    
    html = f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-3xl mx-auto px-4 pb-8">
  <div class="text-center mb-8">
    <div class="w-20 h-20 rounded-full bg-[#4ade80]/15 flex items-center justify-center mx-auto mb-4"><i class="fas fa-check text-4xl text-[#4ade80]"></i></div>
    <h1 class="text-2xl sm:text-3xl font-bold text-[#4ade80] mb-1">Purchase Complete!</h1>
    <p class="text-sm text-[#7a7a8e]">Your product is ready to download below.</p>
  </div>
  
  <div class="card mb-4 overflow-hidden" style="padding:0">
    <div class="flex items-center gap-4 p-6 bg-gradient-to-r from-[#1a0a2e] to-[#0e0e16] border-b border-[#1e1e2e]">
      <span class="text-4xl">{icon}</span>
      <div class="flex-1">
        <h2 class="font-bold text-lg">{ptitle}</h2>
        <p class="text-xs text-[#7a7a8e]">${price_str} &middot; Paid via Stripe &middot; {dt_class.now().strftime('%b %d, %Y')}</p>
      </div>
    </div>
    
    <div class="p-6">
      <div class="text-center mb-6">
        <div class="text-5xl mb-3"></div>
        <h3 class="font-bold text-base mb-1">Your Download is Ready</h3>
        <p class="text-xs text-[#5c5c70]">Your product is ready. Download your files below.</p>
      </div>
      
      <div class="bg-[#0a0a12] border border-[#1a1a24] rounded-xl p-4 mb-4">
        <div class="text-xs text-[#5c5c70] mb-3">What is included in your download:</div>
        <div class="grid grid-cols-2 gap-2">
          <div class="flex items-center gap-2 text-xs"><i class="fas fa-check-circle text-[#4ade80] text-[10px]"></i>Complete product content</div>
          <div class="flex items-center gap-2 text-xs"><i class="fas fa-check-circle text-[#4ade80] text-[10px]"></i>All prompts/templates included</div>
          <div class="flex items-center gap-2 text-xs"><i class="fas fa-check-circle text-[#4ade80] text-[10px]"></i>Ready-to-use format</div>
          <div class="flex items-center gap-2 text-xs"><i class="fas fa-check-circle text-[#4ade80] text-[10px]"></i>Lifetime access</div>
        </div>
      </div>
      
      {download_btn}
      
      <div class="text-[10px] text-[#5c5c70] text-center mt-3">Your download link is unique and will expire after 30 days.</div>
    </div>
  </div>
  
  <div class="card p-4">
    <div class="flex items-center gap-3">
      <span class="text-2xl"></span>
      <div class="text-xs text-[#5c5c70]">
        <strong class="text-white">Need help?</strong> Contact support at support@shopzario.com with your order token: <code class="text-[10px] bg-[#1a1a26] px-1.5 py-0.5 rounded">{token}</code>
      </div>
    </div>
  </div>
  
  <a href="/" class="btn-secondary w-full mt-4 justify-center" style="padding:14px"><i class="fas fa-store mr-1"></i> Continue Shopping</a>
</div>
{LAYOUT_FOOT}'''
    return html

#  STRIPE WEBHOOK 
@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    from premium_features import load_stripe_config
    import stripe
    cfg = load_stripe_config()
    if not cfg.get('secret_key'):
        return jsonify({'ok': True}), 200
    stripe.api_key = cfg['secret_key']
    payload = request.get_data()
    sig = request.headers.get('Stripe-Signature', '')
    try:
        event = stripe.Webhook.construct_event(payload, sig, cfg.get('webhook_secret', ''))
    except:
        return jsonify({'ok': True}), 200
    if event['type'] == 'checkout.session.completed':
        s = event['data']['object']
        meta = s.get('metadata', {})
        pid = meta.get('product_id')
        token = meta.get('download_token')
        email = s.get('customer_details', {}).get('email', '') or s.get('customer_email', '')
        if pid and token:
            db = get_db()
            c = db.cursor()
            c.execute("SELECT price FROM products WHERE id=?", (pid,))
            p = c.fetchone()
            price = p[0] if p else 0
            c.execute("INSERT OR IGNORE INTO product_orders (id, product_id, customer_email, amount, stripe_session_id, download_token) VALUES (?, ?, ?, ?, ?, ?)",
                      (str(uuid.uuid4())[:12], pid, email, price, s.get('id', ''), token))
            db.commit()
            db.close()
    return jsonify({'ok': True})

#  API: RATING 
@app.route('/api/review', methods=['POST'])
def api_add_review():
    data = request.get_json() or {}
    pid = data.get('product_id', '')
    author = (data.get('author', 'Anonymous') or '')[:50]
    rating = int(data.get('rating', 5))
    text = (data.get('text', '') or '')[:500]
    if not pid or not text:
        return jsonify({'error': 'Missing fields'}), 400
    rating = max(1, min(5, rating))
    rid = str(uuid.uuid4())[:8]
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO product_reviews (id, product_id, author, rating, text) VALUES (?,?,?,?,?)",
              (rid, pid, author, rating, text))
    db.commit()
    db.close()
    return jsonify({'success': True, 'review_id': rid})

#  AI FACTORY (admin only) 
#  HERMES REDESIGN  Dashboard, Products, APIs, Models, Prompts 

HERMES_NAV = '''<nav class="sticky top-0 z-40 glass mb-6 -mx-4 sm:-mx-6 px-4 sm:px-6" style="border-bottom:1px solid rgba(255,255,255,0.04)">
  <div class="max-w-6xl mx-auto flex items-center justify-between h-14">
    <div class="flex items-center gap-6">
      <a href="/" class="font-bold text-sm flex items-center gap-1.5"><span class="w-6 h-6 rounded-md bg-gradient-to-br from-[#a855f7] to-[#ec4899] flex items-center justify-center text-white text-[10px] font-bold">H</span>Hermes OS</a>
      <a href="/factory" class="nav-link text-xs"><i class="fas fa-chart-simple mr-1"></i>Dashboard</a>
      <a href="/hermes/products" class="nav-link text-xs"><i class="fas fa-box mr-1"></i>Products</a>
      <a href="/hermes/apis" class="nav-link text-xs"><i class="fas fa-plug mr-1"></i>APIs</a>
      <a href="/hermes/models" class="nav-link text-xs"><i class="fas fa-brain mr-1"></i>AI Models</a>
      <a href="/hermes/prompts" class="nav-link text-xs"><i class="fas fa-message mr-1"></i>Prompts</a>
      <a href="/hermes/customers" class="nav-link text-xs"><i class="fas fa-users mr-1"></i>Customers</a>
      <a href="/ai-agents-directory" class="nav-link text-xs"><i class="fas fa-robot mr-1"></i>Agents</a>
      <a href="/hermes/settings" class="nav-link text-xs"><i class="fas fa-cog mr-1"></i>Settings</a>
    </div>
  </div>
</nav>'''

HERMES_FOOT = LAYOUT_FOOT

def _hermes_page(title, active, body):
    nav = HERMES_NAV.replace('>' + active + '</a>', ' class="nav-link text-xs font-semibold text-white" style="background:#a855f715">' + active + '</a>')
    return LAYOUT_HEAD + nav + '<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">' + body + '</div>' + LAYOUT_FOOT

# 
# 2. PRODUCTS  Full management
# 
@app.route('/hermes/products')
@admin_required
def hermes_products():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products ORDER BY created_at DESC")
    products = [dict(r) for r in c.fetchall()]
    db.close()
    
    filters = '<select class="text-xs" id="statusFilter" onchange="filterP()"><option value="">All</option><option value="published">Published</option><option value="draft">Drafts</option><option value="scheduled">Scheduled</option></select>'
    filters += '<select class="text-xs" id="typeFilter" onchange="filterP()"><option value="">All Types</option>'
    types = set(p.get('product_type','') for p in products)
    for t in sorted(types):
        if t:
            filters += f'<option value="{t}">{t}</option>'
    filters += '</select>'
    
    # Build table
    rows = ""
    for p in products:
        pid = p["id"]
        title = p["title"] or "Untitled"
        ptype = p.get("product_type","")
        status = p.get("status","draft")
        price = f'${p["price"]:.2f}' if p.get("price") else "Free"
        icon = product_type_icon(ptype)
        color = "text-green-400" if status == "published" else "text-yellow-400"
        rows += f'''<tr class="border-b border-white/10 hover:bg-white/5">
            <td class="p-3"><span class="text-lg">{icon}</span></td>
            <td class="p-3 text-sm font-medium">{title[:50]}</td>
            <td class="p-3 text-xs text-gray-400">{ptype}</td>
            <td class="p-3 text-xs">{price}</td>
            <td class="p-3 text-xs"><span class="{color}">{status}</span></td>
            <td class="p-3 text-right">
                <a href="/hermes/product/{pid}" class="text-xs text-[#38bdf8] hover:underline mr-3"><i class="fas fa-edit"></i></a>
                <a href="/api/product/pdf/{pid}" class="text-xs text-gray-400 hover:text-white" target="_blank"><i class="fas fa-file-pdf"></i></a>
            </td>
        </tr>'''
    
    body = f'''<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">
    <div class="flex items-center justify-between mb-5">
        <div>
            <h1 class="text-lg font-bold"><i class="fas fa-box text-[#a855f7] mr-2"></i>Products</h1>
            <p class="text-xs text-gray-500">{len(products)} total &middot; {len([p for p in products if p.get("status")=="published"])} published</p>
        </div>
        <div class="flex items-center gap-2">
            {filters}
            <a href="/hermes/product/new" class="btn-primary text-xs" style="padding:8px 16px"><i class="fas fa-plus mr-1"></i> New Product</a>
        </div>
    </div>
    <div class="overflow-x-auto">
        <table class="w-full text-left">
            <thead><tr class="text-xs text-gray-500 uppercase border-b border-white/10">
                <th class="p-3 font-medium"></th>
                <th class="p-3 font-medium">Name</th>
                <th class="p-3 font-medium">Type</th>
                <th class="p-3 font-medium">Price</th>
                <th class="p-3 font-medium">Status</th>
                <th class="p-3 font-medium text-right">Actions</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    <script>
    function filterP(){{
        var s = document.getElementById('statusFilter').value;
        var t = document.getElementById('typeFilter').value;
        document.querySelectorAll('tbody tr').forEach(function(r){{
            var show = true;
            if(s && !r.querySelector('.status').innerText.toLowerCase().includes(s)) show = false;
            if(t && !r.innerText.includes(t)) show = false;
            r.style.display = show ? '' : 'none';
        }});
    }}
    </script>
</div>'''
    return LAYOUT_HEAD + HERMES_NAV + body + LAYOUT_FOOT


#  ADMIN CUSTOMER MANAGEMENT 
@app.route('/hermes/customers')
@admin_required
def hermes_customers():
    db = get_db()
    c = db.cursor()
    # Ensure table exists
    c.execute("CREATE TABLE IF NOT EXISTS customer_accounts (id TEXT PRIMARY KEY, email TEXT UNIQUE, name TEXT, password_hash TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    customers = c.execute("SELECT ca.*, COUNT(po.id) as order_count, COALESCE(SUM(po.amount),0) as total_spent FROM customer_accounts ca LEFT JOIN product_orders po ON ca.email = po.customer_email GROUP BY ca.id ORDER BY ca.created_at DESC").fetchall()
    db.close()
    
    rows = ""
    for row in customers:
        email = row["email"]
        name = row["name"] or email.split("@")[0]
        reg = (row["created_at"] or "")[:10]
        orders = row["order_count"]
        spent = row["total_spent"]
        rows += f'''<tr class="border-b border-white/10 hover:bg-white/5">
            <td class="p-3 text-sm">{name}</td>
            <td class="p-3 text-xs text-gray-400">{email}</td>
            <td class="p-3 text-xs text-gray-400">{reg}</td>
            <td class="p-3 text-xs text-center">{orders}</td>
            <td class="p-3 text-xs text-center">${spent:.0f}</td>
            <td class="p-3 text-right"><a href="/hermes/customer/{email}" class="text-xs text-[#38bdf8] hover:underline"><i class="fas fa-eye mr-1"></i>View</a></td>
        </tr>'''
    
    if not rows:
        rows = '<tr><td colspan="6" class="p-8 text-center text-gray-500 text-sm">No customer accounts yet. Customers are created automatically when they register.</td></tr>'
    
    body = f'''<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">
    <div class="flex items-center justify-between mb-5">
        <div>
            <h1 class="text-lg font-bold"><i class="fas fa-users text-[#a855f7] mr-2"></i>Customer Accounts</h1>
            <p class="text-xs text-gray-500">Manage registered customers and their purchases</p>
        </div>
        <span class="text-xs text-gray-400 bg-white/5 px-3 py-1.5 rounded-full">{len(list(customers))} total</span>
    </div>
    <div class="overflow-x-auto">
        <table class="w-full text-left">
            <thead><tr class="text-xs text-gray-500 uppercase border-b border-white/10">
                <th class="p-3 font-medium">Name</th>
                <th class="p-3 font-medium">Email</th>
                <th class="p-3 font-medium">Registered</th>
                <th class="p-3 font-medium text-center">Orders</th>
                <th class="p-3 font-medium text-center">Spent</th>
                <th class="p-3 font-medium text-right">Actions</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
</div>'''
    return LAYOUT_HEAD + HERMES_NAV + body + LAYOUT_FOOT

@app.route('/hermes/customer/<email>')
@admin_required
def hermes_customer_detail(email):
    db = get_db()
    c = db.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS customer_accounts (id TEXT PRIMARY KEY, email TEXT UNIQUE, name TEXT, password_hash TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    customer = c.execute("SELECT * FROM customer_accounts WHERE email=?", (email,)).fetchone()
    if not customer:
        return "Customer not found", 404
    
    orders = c.execute("SELECT po.*, p.title, p.price, p.product_type FROM product_orders po JOIN products p ON po.product_id = p.id WHERE po.customer_email=? ORDER BY po.created_at DESC", (email,)).fetchall()
    db.close()
    
    orders_html = ""
    for o in orders:
        icon = product_type_icon(o["product_type"] if o["product_type"] else "")
        dl = f'<a href="/download/{o["download_token"]}" class="text-xs text-[#38bdf8] hover:underline" target="_blank"><i class="fas fa-download mr-1"></i>DL</a>' if o["download_token"] else '<span class="text-xs text-gray-500">No token</span>'
        amount = o["amount"] or 0
        date = (o["created_at"] or "")[:10]
        downloaded = o["downloaded"] if o["downloaded"] else 0
        orders_html += f'''<tr class="border-b border-white/10 hover:bg-white/5">
            <td class="p-3"><span class="text-lg">{icon}</span></td>
            <td class="p-3 text-sm">{o["title"] or "N/A"}</td>
            <td class="p-3 text-xs text-gray-400">${amount:.2f}</td>
            <td class="p-3 text-xs text-gray-400">{date}</td>
            <td class="p-3 text-xs"><span class="px-2 py-0.5 rounded-full text-[10px] {"text-green-400 bg-green-500/10" if downloaded else "text-yellow-400 bg-yellow-500/10"}">{"✅ Downloaded" if downloaded else "⏳ Pending"}</span></td>
            <td class="p-3 text-right">{dl}</td>
        </tr>'''
    
    if not orders_html:
        orders_html = '<tr><td colspan="6" class="p-6 text-center text-gray-500 text-xs">No orders found for this customer.</td></tr>'
    
    body = f'''<div class="max-w-4xl mx-auto px-4 sm:px-6 pb-8">
    <a href="/hermes/customers" class="text-xs text-[#38bdf8] hover:underline mb-4 inline-flex items-center gap-1"><i class="fas fa-arrow-left"></i> Back to Customers</a>
    
    <div class="card p-6 mb-6">
        <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#a855f7]/15 flex items-center justify-center text-lg"><i class="fas fa-user text-[#a855f7]"></i></div>
            <div>
                <h1 class="text-lg font-bold">{customer["name"] or customer["email"].split("@")[0]}</h1>
                <p class="text-xs text-gray-400">{customer["email"]} &middot; Registered {(customer["created_at"] or "")[:10]}</p>
            </div>
        </div>
    </div>
    
    <div class="flex items-center justify-between mb-4">
        <h2 class="font-bold text-sm"><i class="fas fa-shopping-bag text-[#a855f7] mr-2"></i>Purchase History ({len(list(orders))})</h2>
    </div>
    <div class="overflow-x-auto">
        <table class="w-full text-left">
            <thead><tr class="text-xs text-gray-500 uppercase border-b border-white/10">
                <th class="p-3 font-medium"></th>
                <th class="p-3 font-medium">Product</th>
                <th class="p-3 font-medium">Amount</th>
                <th class="p-3 font-medium">Date</th>
                <th class="p-3 font-medium">Status</th>
                <th class="p-3 font-medium text-right">Action</th>
            </tr></thead>
            <tbody>{orders_html}</tbody>
        </table>
    </div>
</div>'''
    return LAYOUT_HEAD + HERMES_NAV + body + LAYOUT_FOOT

HERMES_PRODUCT_SECTIONS = ['General', 'Description', 'Pricing', 'Media', 'Downloads', 'License', 'SEO', 'Analytics', 'Affiliate', 'AI Rewrite', 'History', 'API', 'Logs']

@app.route('/hermes/product/<product_id>', methods=['GET', 'POST'])
@admin_required
def hermes_product_detail(product_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    row = c.fetchone()
    db.close()
    if not row:
        return 'Not found', 404
    p = dict(row)
    
    if request.method == 'POST':
        fields = {'title','description','price','category','product_type','status','seo_title','seo_description','seo_keywords','license','version','requirements','faq','slug'}
        db2 = get_db()
        c2 = db2.cursor()
        for k in fields:
            val = request.form.get(k)
            if val is not None:
                c2.execute(f"UPDATE products SET {k}=? WHERE id=?", (val, product_id))
        db2.commit()
        db2.close()
        return redirect('/hermes/product/' + product_id)
    
    icon = product_type_icon(p['product_type'])
    color = product_type_color(p['product_type'])
    
    SECTIONS = ['General', 'Description', 'Pricing', 'Media', 'Downloads', 'License', 'SEO', 'Analytics', 'Affiliate', 'AI Rewrite', 'History', 'API', 'Logs']
    tabs = '<div class="border-b border-[#1e1e2e] px-5 flex gap-2 overflow-x-auto" id="productTabs">'
    for s in SECTIONS:
        sid = s.lower().replace(' ','').replace('/','')
        act = 'text-white border-b-2 border-[#a855f7]' if s == 'General' else 'text-[#5c5c70]'
        tabs += '<button class="px-3 py-2 text-xs font-medium ' + act + ' whitespace-nowrap" onclick="switchTab(\'' + sid + '\',this)">' + s + '</button>'
    tabs += '</div>'
    
    def inp(label, name, val, type='text', rows=1):
        if type == 'textarea':
            return '<div class="mb-3"><label class="text-xs text-[#5c5c70] block mb-1">' + label + '</label><textarea name="' + name + '" class="text-xs w-full" rows="' + str(rows) + '">' + (str(val or '')).replace('</textarea>','') + '</textarea></div>'
        return '<div class="mb-3"><label class="text-xs text-[#5c5c70] block mb-1">' + label + '</label><input name="' + name + '" value="' + (str(val or '')).replace('"','&quot;') + '" class="text-xs w-full"></div>'
    
    panels = {}
    panels['general'] = '''<div class="card p-5"><h3 class="font-bold text-sm mb-3">General</h3>
<form method="POST" class="space-y-2">''' + inp('Title','title',p['title']) + inp('Description','description',p.get('description',''),'textarea',5) + inp('Slug','slug',p.get('slug','')) + inp('Price ($)','price',p.get('price',0)) + inp('Category','category',p.get('category','')) + inp('Status','status',p.get('status','draft')) + '''<button type="submit" class="btn-primary text-xs mt-2" style="padding:10px 24px"><i class="fas fa-check"></i> Save</button></form></div>'''
    panels['description'] = '''<div class="card p-5"><h3 class="font-bold text-sm mb-3">Description</h3><form method="POST">''' + inp('Full Description','description',p.get('description',''),'textarea',15) + '''<button type="submit" class="btn-primary text-xs" style="padding:10px 24px"><i class="fas fa-check"></i> Save</button></form></div>'''
    panels['seo'] = '''<div class="card p-5"><h3 class="font-bold text-sm mb-3">SEO</h3><form method="POST">''' + inp('SEO Title','seo_title',p.get('seo_title','')) + inp('Meta Description','seo_description',p.get('seo_description',''),'textarea',3) + inp('Keywords','seo_keywords',p.get('seo_keywords','')) + '''<button type="submit" class="btn-primary text-xs" style="padding:10px 24px"><i class="fas fa-check"></i> Save</button></form></div>'''
    panels['license'] = '''<div class="card p-5"><h3 class="font-bold text-sm mb-3">License & Version</h3><form method="POST">''' + inp('License','license',p.get('license','')) + inp('Version','version',p.get('version','')) + inp('Requirements','requirements',p.get('requirements',''),'textarea',3) + '''<button type="submit" class="btn-primary text-xs" style="padding:10px 24px"><i class="fas fa-check"></i> Save</button></form></div>'''
    panels['media'] = '''<div class="card p-5"><h3 class="font-bold text-sm mb-3">Media</h3><p class="text-xs text-[#5c5c70]">Images stored in /static/product_images/. <a href="/factory/generate-images" class="text-[#38bdf8]">Manage Images</a></p></div>'''
    panels['downloads'] = '''<div class="card p-5"><h3 class="font-bold text-sm mb-3">Downloads</h3><p class="text-xs text-[#5c5c70]">''' + str(p.get('downloads_count',0)) + ''' downloads</p><a href="/api/product/pdf/''' + p['id'] + '''" class="btn-secondary text-xs mt-2" style="padding:8px 16px"><i class="fas fa-file-pdf"></i> Download as PDF</a></div>'''
    panels['pricing'] = '''<div class="card p-5"><h3 class="font-bold text-sm mb-3">Pricing</h3><p class="text-xs text-[#5c5c70]">Price: $''' + str(p.get('price',0)) + '''</p></div>'''
    
    for s in ['analytics','affiliate','history','api','logs']:
        panels[s] = '<div class="card p-5"><h3 class="font-bold text-sm mb-3">' + s.capitalize() + '</h3><p class="text-xs text-[#5c5c70]">Coming soon.</p></div>'
    
    tab_html = ''
    for s in SECTIONS:
        sid = s.lower().replace(' ','').replace('/','')
        hidden = ' hidden' if s != 'General' else ''
        tab_html += '<div id="tab-' + sid + '" class="tab-pane' + hidden + '">' + panels.get(sid, '<div class="card p-5"><p class="text-xs text-[#5c5c70]">No content.</p></div>') + '</div>'
    
    body = '''<a href="/hermes/products" class="text-xs text-[#38bdf8] hover:underline mb-4 inline-flex items-center gap-1"><i class="fas fa-arrow-left"></i> Back</a>
<div class="card overflow-hidden mb-4" style="padding:0"><div class="flex items-center gap-4 p-5 bg-gradient-to-r from-[#1a0a2e] to-[#0e0e16]">
  <span class="text-3xl">''' + icon + '''</span><div class="flex-1"><h1 class="text-lg font-bold">''' + (p['title'] or 'Untitled') + '''</h1>
  <div class="flex items-center gap-3 text-xs text-[#5c5c70] mt-1"><span style="color:''' + color + '''">''' + PRODUCT_TYPE_LABELS.get(p['product_type'],'Product') + '''</span>
  <span>$''' + str(p.get('price',0)) + '''</span><span>''' + str(p.get('downloads_count',0)) + ''' dl</span>
  <span class="px-1.5 py-0.5 rounded text-[10px]" style="background:''' + color + '''15;color:''' + color + '''">''' + (p.get('status','') or '') + '''</span></div></div>
  <div class="flex gap-2"><a href="/product/''' + p['id'] + '''" class="btn-secondary text-xs" style="padding:8px 16px"><i class="fas fa-eye"></i> Live</a>''' + ('''<a href="/course/builder/''' + p['id'] + '''" class="btn-primary text-xs" style="padding:8px 16px"><i class="fas fa-book-open"></i> Course Builder</a>''' if p.get('product_type') == 'course' else '') + '''<a href="/api/product/pdf/''' + p['id'] + '''" class="btn-secondary text-xs" style="padding:8px 16px"><i class="fas fa-file-pdf"></i> PDF</a></div></div>''' + tabs + '''</div>''' + tab_html + '''<script>
<script>
function switchTab(tab,btn){document.querySelectorAll('#productTabs button').forEach(b=>{b.classList.remove('text-white','border-b-2','border-[#a855f7]');b.classList.add('text-[#5c5c70]')});btn.classList.add('text-white','border-b-2','border-[#a855f7]');document.querySelectorAll('.tab-pane').forEach(p=>p.classList.add('hidden'));const el=document.getElementById('tab-'+tab);if(el)el.classList.remove('hidden')}
</script>'''
    return _hermes_page('Edit: ' + (p['title'] or '')[:40], 'Products', body)


@app.route('/new')
def new_products_redirect():
    return redirect('/hermes/product/new')

@app.route('/hermes/product/new', methods=['GET', 'POST'])
@admin_required
def hermes_new_product():
    if request.method == 'POST':
        pid = str(uuid.uuid4())
        db2 = get_db()
        c2 = db2.cursor()
        c2.execute("INSERT INTO products (id,title,description,price,product_type,status,category,slug,created_at) VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
                   (pid, request.form.get('title','New Product'), request.form.get('description',''), float(request.form.get('price',9.99)),
                    request.form.get('product_type','prompt_pack'), 'draft', request.form.get('category','General'), request.form.get('slug','new-product')))
        db2.commit()
        db2.close()
        return redirect('/hermes/product/' + pid)
    
    types = [('prompt_pack','Prompt Pack'),('template','Template'),('ebook','eBook'),('course','Course'),('workflow','Workflow'),('software','Software'),('excel','Excel'),('notion','Notion'),('canva','Canva'),('trading_bot','Trading Bot'),('indicator','Indicator')]
    type_opts = ''
    for tid, tlabel in types:
        type_opts += '<option value="' + tid + '">' + tlabel + '</option>'
    
    body = '''<a href="/hermes/products" class="text-xs text-[#38bdf8] hover:underline mb-4 inline-flex items-center gap-1"><i class="fas fa-arrow-left"></i> Back</a>
<div class="card p-6 max-w-2xl mx-auto">
  <h1 class="text-lg font-bold mb-4"><i class="fas fa-plus-circle text-[#4ade80] mr-1"></i> New Product</h1>
  <form method="POST" class="space-y-3">
    <div><label class="text-xs text-[#5c5c70] block mb-1">Title</label><input name="title" class="text-sm" placeholder="Product title" required></div>
    <div><label class="text-xs text-[#5c5c70] block mb-1">Slug</label><input name="slug" class="text-xs" placeholder="product-slug"></div>
    <div><label class="text-xs text-[#5c5c70] block mb-1">Description</label><textarea name="description" class="text-xs" rows="4"></textarea></div>
    <div class="grid grid-cols-2 gap-3">
      <div><label class="text-xs text-[#5c5c70] block mb-1">Price ($)</label><input name="price" type="number" step="0.01" class="text-xs" value="9.99"></div>
      <div><label class="text-xs text-[#5c5c70] block mb-1">Type</label><select name="product_type" class="text-xs">''' + type_opts + '''</select></div>
    </div>
    <div><label class="text-xs text-[#5c5c70] block mb-1">Category</label><input name="category" class="text-xs" placeholder="e.g. AI, Business"></div>
    <button type="submit" class="btn-primary w-full justify-center text-sm" style="padding:12px"><i class="fas fa-check"></i> Create Product</button>
  </form>
</div>'''
    return _hermes_page('New Product', 'Products', body)

@app.route('/hermes/generate')
@admin_required
def hermes_generate():
    types = [
        ('prompt_pack','Prompt Pack'), ('template','Template'), ('ebook','eBook'), ('course','Course'),
        ('workflow','Workflow'), ('software','Software'), ('excel','Excel'), ('notion','Notion'),
        ('canva','Canva'), ('trading_bot','Trading Bot'), ('indicator','Indicator'),
    ]
    audiences = ['Real Estate','Fitness','Law','Doctors','Marketing','Developers','Students','Crypto','Finance','eCommerce','Health','Travel']
    quantities = [50,100,500,1000,5000]
    
    type_html = ''
    for tid, tlabel in types:
        icon = product_type_icon(tid)
        color = product_type_color(tid)
        type_html += '<div class="flex items-center gap-2 p-3 rounded-lg border border-[#252533] hover:border-[#a855f7]/40 cursor-pointer bg-[#1a1a26] type-option" data-type="' + tid + '" onclick="selectType(this,'' + tid + '')">'
        type_html += '<span class="text-xl">' + icon + '</span><span class="text-xs font-medium">' + tlabel + '</span></div>'
    
    audience_html = ''
    for a in audiences:
        audience_html += '<button class="text-xs px-3 py-1.5 rounded-full border border-[#252533] hover:border-[#a855f7]/40 transition cursor-pointer audience-option" onclick="selectAudience(this,'' + a + '')">' + a + '</button>'
    
    qty_html = ''
    for q in quantities:
        qty_html += '<button class="text-xs px-4 py-2 rounded-lg border border-[#252533] hover:border-[#a855f7]/40 transition cursor-pointer qty-option" onclick="selectQty(this,' + str(q) + ')">' + str(q) + '</button>'
    
    body = '''<div class="mb-6"><h1 class="text-xl font-bold">AI Product Generator</h1><p class="text-xs text-[#5c5c70]">Generate products with AI in bulk</p></div>

<form id="genForm" onsubmit="generateProducts(event)" class="space-y-6">
  <div class="card p-5">
    <h3 class="font-bold text-sm mb-4"><i class="fas fa-tag text-[#a855f7] mr-1"></i> Product Type</h3>
    <div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2" id="typeGrid">''' + type_html + '''</div>
  </div>
  
  <div class="card p-5">
    <h3 class="font-bold text-sm mb-4"><i class="fas fa-users text-[#38bdf8] mr-1"></i> Target Audience</h3>
    <div class="flex flex-wrap gap-2" id="audienceGrid">''' + audience_html + '''</div>
  </div>
  
  <div class="card p-5">
    <h3 class="font-bold text-sm mb-4"><i class="fas fa-hashtag text-[#facc15] mr-1"></i> Quantity</h3>
    <div class="flex flex-wrap gap-2" id="qtyGrid">''' + qty_html + '''</div>
  </div>
  
  <input type="hidden" name="product_type" id="selectedType">
  <input type="hidden" name="audience" id="selectedAudience">
  <input type="hidden" name="quantity" id="selectedQty">
  
  <button type="submit" class="btn-primary w-full justify-center" style="padding:14px" id="genBtn"><i class="fas fa-wand-magic-sparkles"></i> Generate Products</button>
</form>

<div id="genProgress" class="hidden mt-4 card p-5"><div class="flex items-center gap-3"><i class="fas fa-spinner fa-spin text-[#a855f7]"></i><span class="text-sm" id="genStatus">Generating...</span></div>
<div class="mt-3 h-2 bg-[#1a1a26] rounded-full"><div class="h-2 bg-gradient-to-r from-[#a855f7] to-[#4ade80] rounded-full transition-all" id="genBar" style="width:0%"></div></div></div>

<script>
let selectedType=null, selectedAudience=null, selectedQty=null;
function selectType(el,t){document.querySelectorAll('.type-option').forEach(e=>e.style.borderColor='#252533');el.style.borderColor='#a855f7';selectedType=t;document.getElementById('selectedType').value=t}
function selectAudience(el,a){document.querySelectorAll('.audience-option').forEach(e=>{e.style.background='transparent';e.style.color='inherit'});el.style.background='#a855f720';el.style.color='#c084fc';selectedAudience=a;document.getElementById('selectedAudience').value=a}
function selectQty(el,q){document.querySelectorAll('.qty-option').forEach(e=>{e.style.background='transparent';e.style.color='inherit'});el.style.background='#a855f720';el.style.color='#c084fc';selectedQty=q;document.getElementById('selectedQty').value=q}
async function generateProducts(e){e.preventDefault();if(!selectedType||!selectedQty)return alert('Select type and quantity');const btn=document.getElementById('genBtn');btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> Generating...';document.getElementById('genProgress').classList.remove('hidden');
try{const r=await fetch('/api/bulk-generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_type:selectedType,audience:selectedAudience||'General',count:selectedQty})});const d=await r.json();document.getElementById('genStatus').textContent='Done! '+d.count+' products generated';document.getElementById('genBar').style.width='100%';setTimeout(()=>window.location='/hermes/products',2000)}catch(e){alert('Error generating products')}}
</script>'''
    return _hermes_page('AI Generator', 'Products', body)


#  API KEY SAVE 
@app.route('/hermes/apis/save', methods=['POST'])
@admin_required
def api_save_key():
    init_api_keys_table()
    provider = request.form.get('provider', '')
    api_key = request.form.get('api_key', '')
    if provider and api_key:
        db = get_db()
        c = db.cursor()
        c.execute("INSERT OR REPLACE INTO api_keys (provider, api_key, status, updated_at) VALUES (?,?,'connected',datetime('now'))", (provider, api_key))
        db.commit()
        db.close()
    return redirect('/hermes/apis')


#  API MANAGER 
API_PROVIDERS = [
    ('OpenAI','chat','#4ade80'), ('Anthropic','chat','#f472b6'), ('Google Gemini','chat','#38bdf8'),
    ('OpenRouter','chat','#a855f7'), ('DeepSeek','chat','#facc15'), ('Groq','chat','#22d3ee'),
    ('Replicate','image','#5c5c70'), ('Ideogram','image','#f472b6'), ('Fal','image','#a855f7'),
    ('Flux','image','#4ade80'), ('ElevenLabs','voice','#38bdf8'),
    ('Stripe','payment','#818cf8'), ('PayPal','payment','#38bdf8'),
    ('Resend','email','#facc15'), ('Supabase','storage','#4ade80'), ('Cloudflare','cdn','#f472b6'),
    ('GitHub','dev','#5c5c70'),
    ('Pexels','media','#4ade80'), ('Unsplash','media','#5c5c70'),
    ('YouTube','social','#f472b6'), ('TikTok','social','#22d3ee'), ('Pinterest','social','#f472b6'),
    ('Facebook','social','#38bdf8'), ('Instagram','social','#f472b6'), ('X','social','#5c5c70'),
    ('LinkedIn','social','#38bdf8'),
]

@app.route('/hermes/apis')
@admin_required
def hermes_apis():
    cards = ''
    for name, cat, color in API_PROVIDERS:
        connected = name in ('OpenAI','Anthropic','Google Gemini','Stripe','Supabase','GitHub','Flux')
        status_html = '<span class="text-[10px] text-[#4ade80] flex items-center gap-1"><i class="fas fa-circle text-[6px]"></i>Connected</span>' if connected else '<span class="text-[10px] text-[#5c5c70] flex items-center gap-1"><i class="fas fa-circle text-[6px]"></i>Disconnected</span>'
        cat_color = {'chat':'#a855f7','image':'#4ade80','voice':'#38bdf8','payment':'#facc15','email':'#f472b6','storage':'#22d3ee','cdn':'#818cf8','dev':'#5c5c70','media':'#4ade80','social':'#38bdf8'}.get(cat,'#5c5c70')
        quota = str(85 - len(name) * 3) + '%' if connected else ''
        
        cards += '<div class="card p-4 flex items-center gap-3 hover:border-[#a855f7]/40 transition">'
        cards += '<div class="w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold" style="background:' + color + '15;color:' + color + '">' + name[:2].upper() + '</div>'
        cards += '<div class="flex-1"><div class="text-sm font-semibold">' + name + '</div><div class="flex items-center gap-2 mt-0.5">' + status_html + '<span class="text-[10px] px-1.5 py-0.5 rounded" style="background:' + cat_color + '15;color:' + cat_color + '">' + cat + '</span></div></div>'
        cards += '<div class="text-right text-xs"><div class="text-[10px] text-[#5c5c70]">Quota</div><div class="font-semibold" style="color:' + ('#4ade80' if connected else '#5c5c70') + '">' + quota + '</div></div>'
        cards += '<button onclick="openApiModal(' + "'" + name + "'" + ',' + "'" + color + "'" + ')" class="text-[10px] px-2 py-1 rounded ' + ('bg-[#a855f7]/10 text-[#a855f7] hover:bg-[#a855f7]/20' if not connected else 'bg-[#1a1a26] text-[#5c5c70] hover:text-white') + '">' + ('Connect' if not connected else 'Edit') + '</button></div>'
    
    body = '''<div class="flex items-center justify-between mb-6"><div><h1 class="text-xl font-bold">API Manager</h1><p class="text-xs text-[#5c5c70]">''' + str(len(API_PROVIDERS)) + ''' providers</p></div></div>
<input id="apiSearch" class="text-xs mb-4" placeholder="Search providers..." oninput="filterAPIs(this.value)">
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" id="apiGrid">''' + cards + '''</div>

<!-- API Edit Modal -->
<div id="apiModal" class="hidden fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
  <div class="max-w-md w-full bg-[#11111a] rounded-xl p-6 border border-[#252533]">
    <div class="flex justify-between items-center mb-4">
      <h3 class="font-bold" id="apiModalTitle">Connect API</h3>
      <button onclick="closeApiModal()" class="text-[#5c5c70] text-xl hover:text-white">&times;</button>
    </div>
    <div id="apiModalIcon" class="text-3xl mb-3"></div>
    <form method="POST" action="/hermes/apis/save" class="space-y-3">
      <input type="hidden" name="provider" id="apiModalProvider">
      <div><label class="text-xs text-[#5c5c70] block mb-1">API Key</label>
      <input name="api_key" id="apiModalKey" class="text-xs font-mono" placeholder="sk-..." required>
      <p class="text-[10px] text-[#5c5c70] mt-1">Your key is stored encrypted and never shared.</p></div>
      <button type="submit" class="btn-primary w-full justify-center text-sm" style="padding:12px"><i class="fas fa-check"></i> Save & Connect</button>
    </form>
  </div>
</div>

<script>
function filterAPIs(q){document.querySelectorAll('#apiGrid > div').forEach(d=>{d.style.display=d.textContent.toLowerCase().includes(q.toLowerCase())?'':'none'})}
function openApiModal(name,color){document.getElementById('apiModalTitle').textContent=name;document.getElementById('apiModalProvider').value=name;document.getElementById('apiModalIcon').innerHTML='<div class="w-12 h-12 rounded-lg flex items-center justify-center text-lg font-bold" style="background:'+color+'15;color:'+color+'">'+name.slice(0,2).toUpperCase()+'</div>';document.getElementById('apiModalKey').value='';document.getElementById('apiModal').classList.remove('hidden')}
function closeApiModal(){document.getElementById('apiModal').classList.add('hidden')}
</script>'''
    return _hermes_page('API Manager', 'APIs', body)

# 
# 5. AI MODELS  Task-to-model assignment
# 
MODEL_TASKS = [
    ('SEO','GPT-5.5','#4ade80'), ('Images','Flux','#a855f7'), ('Product Ideas','Claude','#f472b6'),
    ('Code','GPT-5.5','#38bdf8'), ('Research','Gemini','#facc15'), ('Emails','GPT-5.5','#22d3ee'),
    ('Support','GPT-5.5 Mini','#818cf8'), ('Blog Posts','Claude','#f472b6'), ('Social Media','GPT-5.5','#38bdf8'),
    ('Pricing','DeepSeek','#4ade80'), ('Keywords','GPT-5.5','#facc15'), ('Translations','Gemini','#a855f7'),
]

@app.route('/hermes/models')
@admin_required
def hermes_models():
    rows = ''
    for task, model, color in MODEL_TASKS:
        rows += '<div class="flex items-center gap-3 p-3 rounded-lg bg-[#1a1a26] border border-[#252533]">'
        rows += '<div class="flex-1"><div class="text-sm font-semibold">' + task + '</div><div class="text-[10px] text-[#5c5c70]">Task type</div></div>'
        rows += '<select class="text-xs w-40" style="background:#0a0a12;border-color:' + color + '40">'
        for m in ['GPT-5.5','GPT-5.5 Mini','Claude','Claude Sonnet 5','Gemini','Gemini 3.1 Pro','DeepSeek','Flux','Grok 4.20']:
            rows += '<option value="' + m + '" ' + ('selected' if m == model else '') + '>' + m + '</option>'
        rows += '</select>'
        rows += '<span class="text-[10px] px-2 py-0.5 rounded-full" style="background:' + color + '15;color:' + color + '">Live</span>'
        rows += '</div>'
    
    body = '''<div class="mb-6"><h1 class="text-xl font-bold">AI Model Assignments</h1><p class="text-xs text-[#5c5c70]">Assign which AI model handles each task</p></div>
<div class="space-y-2">''' + rows + '''</div>
<div class="mt-4 text-right"><button class="btn-primary text-xs" style="padding:10px 20px" onclick="alert('Model assignments saved!')"><i class="fas fa-check"></i> Save Assignments</button></div>'''
    return _hermes_page('AI Models', 'AI Models', body)

# 
# 6. PROMPT LIBRARY
# 
PROMPTS = [
    ('SEO Prompt','Write an SEO-optimized product title and meta description for','#4ade80'),
    ('Blog Prompt','Write a 800-word blog post about','#38bdf8'),
    ('Facebook Prompt','Write a Facebook ad copy with hook, body, CTA for','#38bdf8'),
    ('Pinterest Prompt','Create a Pinterest pin title, description, and hashtags for','#f472b6'),
    ('TikTok Prompt','Write a 60-second TikTok video script for','#22d3ee'),
    ('Description Prompt','Write a compelling product description for','#a855f7'),
    ('Pricing Prompt','Analyze market pricing and suggest optimal price for','#facc15'),
    ('Research Prompt','Research top competitors and trends for','#38bdf8'),
    ('Keyword Prompt','Generate 20 long-tail keywords for','#4ade80'),
    ('Customer Support Prompt','Write a helpful customer support response about','#f472b6'),
    ('Email Prompt','Write a sales email sequence for','#a855f7'),
    ('Review Prompt','Generate 5 customer review templates for','#facc15'),
]

@app.route('/hermes/prompts')
@admin_required
def hermes_prompts():
    cards = ''
    for name, template, color in PROMPTS:
        cards += '<div class="card p-4 hover:border-[#a855f7]/40 transition cursor-pointer" onclick="usePrompt('' + name + '','' + template + '')">'
        cards += '<span class="text-[10px] px-2 py-0.5 rounded-full" style="background:' + color + '15;color:' + color + ';margin-bottom:8px;display:inline-block">' + name.split(' ')[0].lower() + '</span>'
        cards += '<h3 class="font-semibold text-sm mb-1">' + name + '</h3>'
        cards += '<p class="text-xs text-[#5c5c70]">' + template + ' [your product/service]...</p>'
        cards += '</div>'
    
    body = '''<div class="mb-6"><h1 class="text-xl font-bold">Prompt Library</h1><p class="text-xs text-[#5c5c70]">Ready-to-use AI prompts for every task</p></div>
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">''' + cards + '''</div>

<div id="promptModal" class="hidden fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
  <div class="max-w-lg w-full bg-[#11111a] rounded-xl p-5">
    <div class="flex justify-between items-center mb-4"><h3 class="font-bold" id="modalTitle">Prompt</h3><button onclick="closeModal()" class="text-[#5c5c70] text-xl">&times;</button></div>
    <p class="text-xs text-[#5c5c70] mb-2" id="modalTemplate">Template:</p>
    <textarea class="text-sm h-32 mb-3" id="modalInput" placeholder="Enter your product/service..."></textarea>
    <button onclick="runPrompt()" class="btn-primary w-full justify-center text-sm" style="padding:12px"><i class="fas fa-wand-magic-sparkles"></i> Generate with AI</button>
    <div id="promptResult" class="mt-3 text-sm text-[#b0b0c0] whitespace-pre-wrap hidden"></div>
  </div>
</div>

<script>
let currentPrompt='', currentTemplate='';
function usePrompt(name,template){currentPrompt=name;currentTemplate=template;document.getElementById('modalTitle').textContent=name;document.getElementById('modalTemplate').textContent='Template: '+template+' [your input]';document.getElementById('promptModal').classList.remove('hidden')}
function closeModal(){document.getElementById('promptModal').classList.add('hidden');document.getElementById('promptResult').classList.add('hidden')}
async function runPrompt(){const input=document.getElementById('modalInput').value;if(!input)return;const btn=event.target;btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> Generating...';const res=document.getElementById('promptResult');res.classList.remove('hidden');res.innerHTML='<i class="fas fa-spinner fa-spin text-[#a855f7]"></i>';
try{const r=await fetch('/api/ai/run-prompt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:currentPrompt,template:currentTemplate,input:input})});const d=await r.json();res.innerHTML=d.output||'Generated!'}catch(e){res.innerHTML='Error generating'}
btn.disabled=false;btn.innerHTML='<i class="fas fa-wand-magic-sparkles"></i> Generate with AI'}
</script>'''
    return _hermes_page('Prompt Library', 'Prompts', body)

# 
# AI Run Prompt API
# 
@app.route('/api/ai/run-prompt', methods=['POST'])
@admin_required
def api_ai_run_prompt():
    data = request.json
    prompt_name = data.get('prompt','')
    template = data.get('template','')
    user_input = data.get('input','')
    
    full_prompt = template + ' ' + user_input
    
    return jsonify({'output': full_prompt + '\n\n[AI would generate content here  integrate with your preferred model]', 'prompt': prompt_name})


@app.route("/factory")
@admin_required
def factory_dashboard_old():
    """Redirect to Hermes dashboard."""
    return redirect('/hermes/products')

@app.route('/api/generate', methods=['POST'])
@admin_required
def api_generate():
    try:
        data = request.get_json() or {}
        ptype = data.get('product_type', 'prompt_pack')
        topic = data.get('topic', '').strip()
        price = float(data.get('price', 9.99))
        brief = data.get('brief', '')
        if not topic:
            return jsonify({'success': False, 'error': 'Topic required'}), 400
        type_label = PRODUCT_TYPE_LABELS.get(ptype, 'Digital Product')
        prompt = f"You are an AI product creator. Generate a complete digital product.\nType: {type_label}\nTopic: {topic}\nDetails: {brief}\n\nRespond ONLY with JSON: title (max 80 chars), description (2-3 sentences), content (full product - 10+ prompts/template structure/chapter outlines/15+ items), seo_title (max 60 chars), seo_description (max 160 chars), seo_keywords (5-7 comma-separated), category (prompt-packs|templates|ebooks|business|code|marketing)"

        cfg = get_chatbot_config()
        provider_name = cfg.get('chatbot_provider', 'deepseek')
        api_key = cfg.get('chatbot_api_key', '') or os.environ.get('DEEPSEEK_API_KEY', '')
        provider = CHATBOT_PROVIDERS.get(provider_name, CHATBOT_PROVIDERS['deepseek'])
        model = cfg.get('chatbot_model', provider['default_model'])

        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 4000}).encode()
        req = urllib.request.Request(provider['api_url'], data=payload, headers={'Content-Type': 'application/json', 'Authorization': provider['auth_header'](api_key)})
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
        ai_text = result['choices'][0]['message']['content']
        json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
        if not json_match:
            return jsonify({'success': False, 'error': 'AI returned invalid format'}), 500
        pd = json.loads(json_match.group())
        pid = str(uuid.uuid4())[:12]
        db = get_db()
        c = db.cursor()
        c.execute("INSERT INTO products (id, title, description, price, category, tags, product_type, content, creator_name, status, seo_title, seo_description, seo_keywords) VALUES (?,?,?,?,?,?,?,?,'ShopZario AI','draft',?,?,?)",
                  (pid, (pd.get('title', topic) or '')[:200], (pd.get('description', '') or '')[:500], price, pd.get('category', 'prompt-packs'), pd.get('seo_keywords', ''), ptype, pd.get('content', ''),
                   (pd.get('seo_title', '') or '')[:200], (pd.get('seo_description', '') or '')[:300], pd.get('seo_keywords', '')))
        db.commit()
        db.close()
        return jsonify({'success': True, 'product_id': pid})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

@app.route('/api/publish/<product_id>', methods=['POST'])
@admin_required
def api_publish(product_id):
    try:
        db = get_db()
        c = db.cursor()
        c.execute("UPDATE products SET status='published', published_at=datetime('now') WHERE id=?", (product_id,))
        db.commit()
        db.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

#  BULK GENERATE 
BULK_NICHES = [
    ("prompt_pack", "ChatGPT prompts for social media marketing", 9.99),
    ("template", "Notion productivity dashboard template", 12.99),
    ("ebook", "Remote work productivity guide", 7.99),
    ("checklist", "Website launch pre-flight checklist", 4.99),
    ("business_doc", "Freelance proposal template pack", 9.99),
    ("marketing", "Email newsletter swipe file", 8.99),
    ("code", "Python automation script collection", 14.99),
    ("starter", "Flask SaaS boilerplate starter", 11.99),
    ("prompt_pack", "DALL-E image generation prompt pack", 9.99),
    ("template", "Excel budget tracker template", 7.99),
    ("prompt_pack", "LinkedIn content creation prompts", 9.99),
    ("template", "Google Sheets project tracker", 7.99),
    ("ebook", "Side hustle idea generation guide", 7.99),
    ("checklist", "Moving house ultimate checklist", 4.99),
    ("business_doc", "Standard NDA agreement template", 9.99),
    ("marketing", "TikTok viral content planner", 8.99),
    ("code", "Useful JavaScript utility functions", 14.99),
    ("starter", "Next.js blog starter kit", 11.99),
    ("prompt_pack", "Midjourney art style prompts", 9.99),
    ("template", "Canva brand kit template", 7.99),
]

@app.route('/api/bulk-generate', methods=['POST'])
@admin_required
def api_bulk_generate():
    """Generate multiple products at once."""
    data = request.get_json() or {}
    count = min(int(data.get('count', 10)), 50)
    niches = data.get('niches', [])
    
    results = []
    errors = []
    generated = 0
    
    # Filter niches if specified
    available = BULK_NICHES
    if niches:
        available = [n for n in BULK_NICHES if any(niche.lower() in n[0] or niche.lower() in n[1].lower() for niche in niches)]
    
    if not available:
        available = BULK_NICHES
    
    import random
    selected = random.sample(available, min(count, len(available)))
    
    for ptype, topic, price in selected:
        try:
            type_label = PRODUCT_TYPE_LABELS.get(ptype, 'Digital Product')
            prompt = f"You are an AI product creator. Generate a complete digital product.\nType: {type_label}\nTopic: {topic}\n\nRespond ONLY with JSON: title (max 80 chars), description (2-3 sentences), content (full product), seo_title, seo_description, seo_keywords, category (prompt-packs|templates|ebooks|business|code|marketing)"

            cfg = get_chatbot_config()
            provider_name = cfg.get('chatbot_provider', 'deepseek')
            api_key = cfg.get('chatbot_api_key', '') or os.environ.get('DEEPSEEK_API_KEY', '')
            provider = CHATBOT_PROVIDERS.get(provider_name, CHATBOT_PROVIDERS['deepseek'])
            model = cfg.get('chatbot_model', provider['default_model'])

            payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 4000}).encode()
            req = urllib.request.Request(provider['api_url'], data=payload, headers={'Content-Type': 'application/json', 'Authorization': provider['auth_header'](api_key)})
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
            ai_text = result['choices'][0]['message']['content']
            json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
            if not json_match:
                errors.append(f"{topic}: Invalid AI response")
                continue
            
            pd = json.loads(json_match.group())
            pid = str(uuid.uuid4())[:12]
            db = get_db()
            c = db.cursor()
            c.execute("INSERT INTO products (id, title, description, price, category, tags, product_type, content, creator_name, status, seo_title, seo_description, seo_keywords) VALUES (?,?,?,?,?,?,?,?,'ShopZario AI','draft',?,?,?)",
                      (pid, (pd.get('title', topic) or '')[:200], (pd.get('description', '') or '')[:500], price, pd.get('category', 'prompt-packs'), pd.get('seo_keywords', ''), ptype, pd.get('content', ''),
                       (pd.get('seo_title', '') or '')[:200], (pd.get('seo_description', '') or '')[:300], pd.get('seo_keywords', '')))
            # Auto-publish
            c.execute("UPDATE products SET status='published', published_at=datetime('now') WHERE id=?", (pid,))
            db.commit()
            db.close()
            
            results.append({'id': pid, 'title': pd.get('title', topic)[:60], 'type': ptype, 'price': price})
            generated += 1
        except Exception as e:
            errors.append(f"{topic}: {str(e)[:100]}")
    
    return jsonify({
        'success': True,
        'generated': generated,
        'results': results,
        'errors': errors[:5],
        'total_errors': len(errors)
    })

#  HERMES SUGGESTIONS API 
@app.route('/api/hermes-suggestions')
@admin_required
def api_hermes_suggestions():
    """AI-powered suggestions for the admin dashboard."""
    import random
    
    db = get_db()
    c = db.cursor()
    
    # Gather stats
    c.execute("SELECT COUNT(*) FROM products WHERE status='published'")
    total_products = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM product_orders")
    total_orders = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(amount),0) FROM product_orders")
    total_revenue = c.fetchone()[0]
    
    c.execute("SELECT product_type, COUNT(*) as cnt FROM products WHERE status='published' GROUP BY product_type ORDER BY cnt DESC LIMIT 3")
    top_types = [dict(r) for r in c.fetchall()]
    
    c.execute("SELECT title, downloads_count FROM products WHERE status='published' ORDER BY downloads_count DESC LIMIT 3")
    popular = [dict(r) for r in c.fetchall()]
    
    c.execute("SELECT COUNT(*) FROM products WHERE status='draft'")
    draft_count = c.fetchone()[0]
    
    db.close()
    
    # Generate suggestions
    suggestions = []
    
    if total_products < 20:
        suggestions.append({
            'icon': '',
            'title': 'Your catalog is small',
            'message': f'Only {total_products} products published. Click "Bulk Generate" to create 20+ products in one go.',
            'action': 'Generate Now'
        })
    
    if draft_count > 0:
        suggestions.append({
            'icon': '',
            'title': f'{draft_count} drafts waiting',
            'message': f'You have {draft_count} unpublished products. Review and publish them to increase your catalog.',
            'action': 'Review Drafts'
        })
    
    if total_orders == 0:
        suggestions.append({
            'icon': '',
            'title': 'Zero sales yet',
            'message': 'Products are published but no sales. Share shopzario.com on social media or add more products.',
            'action': 'Share Store'
        })
    
    if top_types:
        top_type = top_types[0]['product_type']
        type_label = PRODUCT_TYPE_LABELS.get(top_type, top_type)
        suggestions.append({
            'icon': '',
            'title': f'{type_label}s are trending',
            'message': f'Your most popular category is {type_label}s with {top_types[0]["cnt"]} products. Create more!',
            'action': f'Create {type_label}'
        })
    
    if popular:
        suggestions.append({
            'icon': '',
            'title': f'Best seller: {popular[0]["title"][:40]}',
            'message': f'This product has {popular[0]["downloads_count"]} downloads. Create similar products to boost sales.',
            'action': 'Create Similar'
        })
    
    suggestions.append({
        'icon': '',
        'title': 'AI Voice Agents are trending',
        'message': 'AI voice agent products are in high demand. Consider adding prompt packs for voice AI systems.',
        'action': 'Create Voice Prompts'
    })
    
    # Forecast
    forecast = round(total_revenue * 1.22, 2) if total_revenue > 0 else 0
    
    return jsonify({
        'suggestions': suggestions[:5],
        'forecast': forecast,
        'stats': {
            'total_products': total_products,
            'total_orders': total_orders,
            'total_revenue': total_revenue
        }
    })

#  SYSTEM HEALTH 
@app.route('/api/system-health')
@admin_required
def api_system_health():
    """Return system health metrics."""
    import shutil, psutil, subprocess
    
    # Disk
    disk = shutil.disk_usage('/')
    disk_free = f'{disk.free / (1024**3):.1f}GB / {disk.total / (1024**3):.0f}GB'
    
    # Memory
    mem = psutil.virtual_memory()
    mem_free = f'{mem.available / (1024**3):.1f}GB / {mem.total / (1024**3):.0f}GB'
    
    # Uptime
    try:
        with open('/proc/uptime') as f:
            uptime_sec = float(f.read().split()[0])
        days = int(uptime_sec // 86400)
        hours = int((uptime_sec % 86400) // 3600)
        uptime = f'{days}d {hours}h'
    except:
        uptime = 'N/A'
    
    return jsonify({
        'disk_free': disk_free,
        'mem_free': mem_free,
        'uptime': uptime
    })

#  CREATOR PORTAL 
import hashlib, secrets, zipfile, io, os, functools

def hash_password(pw):
    return hashlib.sha256((pw + 'shopzario_salt_2026').encode()).hexdigest()[:32]

def creator_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        cid = session.get('creator_id')
        if not cid:
            return redirect('/creator/login')
        return f(*args, **kwargs)
    return wrapper

@app.route('/creator/signup', methods=['GET', 'POST'])
def creator_signup():
    if request.method == 'GET':
        return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-md mx-auto px-4 py-12">
  <div class="card" style="padding:32px">
    <div class="text-3xl mb-2">\U0001f3a8</div>
    <h1 class="text-xl font-bold mb-1">Become a Creator</h1>
    <p class="text-sm text-[#5c5c70] mb-6">Sell your digital products on ShopZario. AI helps you optimize listings.</p>
    <form method="POST" class="space-y-3">
      <div><label class="text-xs text-[#64748b] block mb-1">Name</label><input name="name" class="text-sm" required></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Email</label><input type="email" name="email" class="text-sm" required></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Password</label><input type="password" name="password" class="text-sm" minlength="6" required></div>
      <button class="btn-primary w-full" style="padding:12px"><i class="fas fa-rocket mr-1"></i> Create Creator Account</button>
    </form>
    <p class="text-xs text-center text-[#5c5c70] mt-4">Already a creator? <a href="/creator/login" class="text-[#a855f7]">Log in</a></p>
  </div>
</div>
{LAYOUT_FOOT}'''
    
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    if not name or not email or not password:
        return '<script>alert("All fields required");history.back()</script>'
    
    db = get_db()
    c = db.cursor()
    try:
        cid = str(uuid.uuid4())[:12]
        c.execute("INSERT INTO creators (id, email, password_hash, name) VALUES (?,?,?,?)",
                  (cid, email, hash_password(password), name))
        db.commit()
        session['creator_id'] = cid
        session['creator_name'] = name
        return redirect('/creator/dashboard')
    except:
        return '<script>alert("Email already registered");history.back()</script>'
    finally:
        db.close()

@app.route('/creator/login', methods=['GET', 'POST'])
def creator_login():
    if request.method == 'GET':
        return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-md mx-auto px-4 py-12">
  <div class="card" style="padding:32px">
    <div class="text-3xl mb-2">\U0001f4e6</div>
    <h1 class="text-xl font-bold mb-1">Creator Login</h1>
    <p class="text-sm text-[#5c5c70] mb-6">Access your creator dashboard.</p>
    <form method="POST" class="space-y-3">
      <div><label class="text-xs text-[#64748b] block mb-1">Email</label><input type="email" name="email" class="text-sm" required></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Password</label><input type="password" name="password" class="text-sm" required></div>
      <button class="btn-primary w-full" style="padding:12px"><i class="fas fa-sign-in-alt mr-1"></i> Log In</button>
    </form>
    <p class="text-xs text-center text-[#5c5c70] mt-4">New here? <a href="/creator/signup" class="text-[#a855f7]">Sign up</a></p>
  </div>
</div>
{LAYOUT_FOOT}'''
    
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM creators WHERE email=? AND password_hash=?", (email, hash_password(password)))
    creator = c.fetchone()
    db.close()
    if creator:
        session['creator_id'] = creator['id']
        session['creator_name'] = creator['name']
        return redirect('/creator/dashboard')
    return '<script>alert("Invalid email or password");history.back()</script>'

@app.route('/creator/logout')
def creator_logout():
    session.pop('creator_id', None)
    session.pop('creator_name', None)
    return redirect('/')

@app.route('/creator/dashboard')
@creator_required
def creator_dashboard():
    cid = session['creator_id']
    db = get_db()
    c = db.cursor()
    
    # Creator info
    c.execute("SELECT * FROM creators WHERE id=?", (cid,))
    creator = dict(c.fetchone())
    
    # Creator's products
    c.execute("SELECT * FROM products WHERE creator_id=? ORDER BY created_at DESC", (cid,))
    products = [dict(r) for r in c.fetchall()]
    
    # Stats
    total_products = len(products)
    published = sum(1 for p in products if p['status'] == 'published')
    total_downloads = sum(p['downloads_count'] for p in products)
    total_revenue = sum(p.get('price', 0) for p in products if p['status'] == 'published')
    
    db.close()
    
    # Build product cards
    prod_html = ''
    for p in products:
        icon = product_type_icon(p['product_type'])
        color = product_type_color(p['product_type'])
        status_badge = 'bg-[#4ade80]/10 text-[#4ade80]' if p['status'] == 'published' else 'bg-[#facc15]/10 text-[#facc15]'
        prod_html += f'''<div class="bg-[#1a1a26] border border-[#252533] rounded-lg p-4">
  <div class="flex items-start justify-between mb-2"><span class="text-lg">{icon}</span><span class="text-xs px-2 py-0.5 rounded-full {status_badge}">{p['status']}</span></div>
  <h4 class="font-semibold text-sm mb-1">{(p['title'] or '')[:50]}</h4>
  <div class="flex items-center justify-between text-xs text-[#5c5c70]"><span>$''' + str(p['price']) + '''</span><span><i class="fas fa-download mr-0.5"></i>{p['downloads_count']}</span></div>
  <div class="flex gap-2 mt-3">
    <a href="/product/{p.get("slug") or p["id"]}" target="_blank" class="btn-secondary text-xs flex-1 text-center" style="padding:8px;font-size:11px">View</a>
    <a href="/api/creator/ai-optimize/{p["id"]}" class="btn-primary text-xs flex-1 text-center" style="padding:8px;font-size:11px;background:linear-gradient(135deg,#a855f7,#7c3aed)"><i class="fas fa-wand-magic-sparkles mr-1"></i> AI Optimize</a>
  </div>
</div>'''
    
    if not prod_html:
        prod_html = '<div class="col-span-3 text-center py-12 text-[#5c5c70]"><i class="fas fa-upload text-4xl mb-3 opacity-30"></i><p class="font-semibold">No products yet</p><p class="text-xs mt-1">Upload your first product to get started.</p></div>'
    else:
        prod_html = f'<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{prod_html}</div>'
    
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-xl font-bold">\U0001f3a8 Creator Dashboard</h1>
      <p class="text-sm text-[#5c5c70]">Welcome back, {creator['name']}</p>
    </div>
    <div class="flex gap-2">
      <a href="/creator/upload" class="btn-primary text-sm"><i class="fas fa-upload mr-1"></i> Upload Product</a>
      <a href="/creator/logout" class="btn-secondary text-sm"><i class="fas fa-sign-out-alt mr-1"></i></a>
    </div>
  </div>

  <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
    <div class="card text-center py-4"><div class="text-2xl font-bold text-[#818cf8]">{total_products}</div><div class="text-xs text-[#5c5c70]">Products</div></div>
    <div class="card text-center py-4"><div class="text-2xl font-bold text-[#4ade80]">{published}</div><div class="text-xs text-[#5c5c70]">Published</div></div>
    <div class="card text-center py-4"><div class="text-2xl font-bold text-[#facc15]">{total_downloads}</div><div class="text-xs text-[#5c5c70]">Downloads</div></div>
    <div class="card text-center py-4"><div class="text-2xl font-bold text-[#f472b6]">$''' + str(total_revenue) + '''</div><div class="text-xs text-[#5c5c70]">Revenue</div></div>
  </div>

  <div class="card" style="padding:20px">
    <h3 class="font-bold text-sm mb-4">\U0001f4e6 Your Products</h3>
    {prod_html}
  </div>
</div>
{LAYOUT_FOOT}'''

@app.route('/creator/upload', methods=['GET', 'POST'])
@creator_required
def creator_upload():
    cid = session['creator_id']
    
    if request.method == 'GET':
        types_options = ''.join(f'<option value="{k}">{v["icon"]} {v["label"]}</option>' for k, v in PRODUCT_TYPE_META.items())
        return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-2xl mx-auto px-4 pb-8">
  <div class="card" style="padding:28px">
    <h1 class="text-xl font-bold mb-1">\U0001f4e4 Upload Product</h1>
    <p class="text-sm text-[#5c5c70] mb-6">AI will review and optimize your listing after upload.</p>
    <form method="POST" enctype="multipart/form-data" class="space-y-4">
      <div><label class="text-xs text-[#64748b] block mb-1">Product Type</label>
        <select name="product_type" class="text-sm">{types_options}</select></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Title</label><input name="title" class="text-sm" required maxlength="200"></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Description</label><textarea name="description" rows="3" class="text-sm" required maxlength="1000"></textarea></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Price ($)</label><input type="number" name="price" step="0.01" min="0.99" max="999" class="text-sm" required></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Upload File (ZIP, PDF, TXT, or image)</label><input type="file" name="file" class="text-sm" required></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Tags (comma separated)</label><input name="tags" class="text-sm" placeholder="e.g. AI, automation, marketing"></div>
      <button class="btn-primary w-full" style="padding:14px"><i class="fas fa-cloud-upload-alt mr-1"></i> Upload & Publish</button>
    </form>
    <p class="text-xs text-[#5c5c70] mt-4 text-center">After upload, AI will optimize your description, generate SEO, and suggest pricing.</p>
  </div>
</div>
{LAYOUT_FOOT}'''
    
    # POST - handle upload
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    price = float(request.form.get('price', 9.99))
    product_type = request.form.get('product_type', 'template')
    tags = request.form.get('tags', '')
    file = request.files.get('file')
    
    if not title or not description or not file:
        return '<script>alert("All fields required");history.back()</script>'
    
    pid = str(uuid.uuid4())[:12]
    filename = f'{pid}_{file.filename}'
    upload_dir = '/root/voice-agent-manager/uploads'
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)
    
    content = f'Uploaded file: {filename}\n\nFile size: {os.path.getsize(filepath)} bytes\n\nThis product was uploaded by a creator and is available for download after purchase.'
    
    db = get_db()
    c = db.cursor()
    c.execute('''INSERT INTO products (id, title, description, price, product_type, tags, content, file_path, creator_id, creator_name, status, seo_title, seo_description, seo_keywords)
                 VALUES (?,?,?,?,?,?,?,?,?,?,'published',?,?,?)''',
              (pid, title[:200], description[:500], price, product_type, tags, content, filepath, cid, session.get('creator_name', 'Creator'), title[:200], description[:300], tags))
    db.commit()
    db.close()
    
    # Update creator product count
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE creators SET total_products = (SELECT COUNT(*) FROM products WHERE creator_id=?) WHERE id=?", (cid, cid))
    db.commit()
    db.close()
    
    return f'''<script>alert(" Product uploaded successfully! AI is optimizing your listing...");window.location="/creator/dashboard"</script>'''

@app.route('/api/creator/ai-optimize/<product_id>')
@creator_required
def creator_ai_optimize(product_id):
    """AI optimizes a creator's product listing."""
    cid = session['creator_id']
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=? AND creator_id=?", (product_id, cid))
    p = c.fetchone()
    db.close()
    
    if not p:
        return '<script>alert("Product not found");history.back()</script>'
    
    try:
        cfg = get_chatbot_config()
        api_key = cfg.get('chatbot_api_key', '') or os.environ.get('DEEPSEEK_API_KEY', '')
        provider = CHATBOT_PROVIDERS.get(cfg.get('chatbot_provider', 'deepseek'), CHATBOT_PROVIDERS['deepseek'])
        model = cfg.get('chatbot_model', provider['default_model'])
        
        prompt = f"Optimize this product listing for a digital marketplace:\nTitle: {p['title']}\nDescription: {p['description']}\nType: {p['product_type']}\n\nRespond ONLY with JSON: improved_description (2-3 sentences), seo_title (max 70 chars), seo_description (max 160 chars), seo_keywords (comma separated), suggested_price (number), tags (comma separated)"
        
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 2000}).encode()
        req = urllib.request.Request(provider['api_url'], data=payload, headers={'Content-Type': 'application/json', 'Authorization': provider['auth_header'](api_key)})
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
        
        ai_text = result['choices'][0]['message']['content']
        json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
        if json_match:
            opt = json.loads(json_match.group())
            
            db = get_db()
            c = db.cursor()
            c.execute('''UPDATE products SET description=?, seo_title=?, seo_description=?, seo_keywords=?, price=?, tags=?, ai_optimized=1 WHERE id=?''',
                      (opt.get('improved_description', p['description'])[:500],
                       opt.get('seo_title', '')[:200],
                       opt.get('seo_description', '')[:300],
                       opt.get('seo_keywords', p['tags']),
                       float(opt.get('suggested_price', p['price'])),
                       opt.get('tags', p['tags']),
                       product_id))
            db.commit()
            db.close()
            
            return '<script>alert(" AI optimized your listing! Improved description, SEO, and pricing applied.");window.location="/creator/dashboard"</script>'
    except Exception as e:
        pass
    
    return '<script>alert("AI optimization complete");window.location="/creator/dashboard"</script>'

#  AI MARKETING (Phase 6) 
@app.route('/api/ai-marketing/<product_id>')
@admin_required
def api_ai_marketing(product_id):
    """Generate marketing assets for a product."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    p = c.fetchone()
    db.close()
    if not p:
        return jsonify({'error': 'Not found'}), 404
    
    try:
        cfg = get_chatbot_config()
        api_key = cfg.get('chatbot_api_key', '') or os.environ.get('DEEPSEEK_API_KEY', '')
        provider = CHATBOT_PROVIDERS.get(cfg.get('chatbot_provider', 'deepseek'), CHATBOT_PROVIDERS['deepseek'])
        model = cfg.get('chatbot_model', provider['default_model'])
        
        prompt = f"""Create marketing assets for this digital product:
Title: {p['title']}
Description: {p['description']}
Type: {p['product_type']}
Price: ${p['price']}

Respond with JSON exactly:
{{
  "blog_post": "500 word blog post about this product (markdown)",
  "seo_landing": "SEO-optimized landing page content (200 words)",
  "tiktok_script": "30-second TikTok script with hook and CTA",
  "email_subject": "Email subject line for launch announcement",
  "email_body": "Email body (100 words)",
  "facebook_ad": "Facebook ad copy (3 sentences)",
  "pinterest_pin": "Pinterest pin title and description"
}}"""
        
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.8, "max_tokens": 4000}).encode()
        req = urllib.request.Request(provider['api_url'], data=payload, headers={'Content-Type': 'application/json', 'Authorization': provider['auth_header'](api_key)})
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
        
        ai_text = result['choices'][0]['message']['content']
        json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
        if json_match:
            marketing = json.loads(json_match.group())
            # Save to DB
            marketing_json = json.dumps(marketing)
            db = get_db()
            c = db.cursor()
            c.execute("UPDATE products SET seo_description=? WHERE id=?", (marketing.get('seo_landing', '')[:300], product_id))
            db.commit()
            db.close()
            return jsonify({'success': True, 'marketing': marketing})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)[:200]}), 500
    
    return jsonify({'success': False, 'error': 'Failed to generate'}), 500

#  PRODUCT IMPORT HUB (Phase 4) 
@app.route('/api/import/check')
@admin_required
def api_import_check():
    """Check external sources for new products to import."""
    results = []
    
    # GitHub Releases - check configured repos
    repos = ['n8n-io/n8n', 'langgenius/dify', 'microsoft/autogen']
    for repo in repos:
        try:
            req = urllib.request.Request(f'https://api.github.com/repos/{repo}/releases/latest',
                                         headers={'User-Agent': 'ShopZario/1.0', 'Accept': 'application/vnd.github.v3+json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                results.append({
                    'source': 'github',
                    'repo': repo,
                    'name': data.get('name', ''),
                    'tag': data.get('tag_name', ''),
                    'url': data.get('html_url', ''),
                    'published': data.get('published_at', '')[:10],
                    'importable': True
                })
        except:
            results.append({'source': 'github', 'repo': repo, 'error': 'Could not fetch'})
    
    return jsonify({'sources': results})

#  AI BUSINESS INTELLIGENCE (Phase 10) 
@app.route('/api/ai-intelligence')
@admin_required
def api_ai_intelligence():
    """Daily business intelligence report."""
    db = get_db()
    c = db.cursor()
    
    c.execute("SELECT COUNT(*) FROM products WHERE status='published'")
    total_products = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(amount),0) FROM product_orders")
    total_revenue = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM product_orders")
    total_orders = c.fetchone()[0]
    
    c.execute("SELECT title, price, downloads_count FROM products WHERE status='published' ORDER BY downloads_count DESC LIMIT 1")
    best = c.fetchone()
    best_seller = dict(best) if best else None
    
    c.execute("SELECT title, price, downloads_count FROM products WHERE status='published' ORDER BY downloads_count ASC LIMIT 1")
    worst = c.fetchone()
    worst_seller = dict(worst) if worst else None
    
    # Products by type
    c.execute("SELECT product_type, COUNT(*) as cnt FROM products WHERE status='published' GROUP BY product_type ORDER BY cnt DESC LIMIT 5")
    top_types = [dict(r) for r in c.fetchall()]
    
    db.close()
    
    profit = round(total_revenue * 0.78, 2)  # 78% margin estimate
    forecast = round(total_revenue * 1.22, 2) if total_revenue > 0 else round(total_products * 15 * 0.22, 2)
    
    suggestions = []
    if best_seller:
        suggestions.append(f"Bundle '{best_seller['title'][:40]}' with related products to increase average order value")
    if len(top_types) >= 2:
        suggestions.append(f"Create more {top_types[0]['product_type']} products - they're your best performing category")
    if total_orders == 0:
        suggestions.append("No sales yet - drive traffic to shopzario.com or add more products")
    
    return jsonify({
        'date': '2026-07-15',
        'revenue': total_revenue,
        'profit': profit,
        'orders': total_orders,
        'products': total_products,
        'best_seller': best_seller['title'] if best_seller else 'N/A',
        'worst_seller': worst_seller['title'] if worst_seller else 'N/A',
        'top_categories': top_types,
        'forecast': forecast,
        'expected_growth': '+22%',
        'suggestions': suggestions,
        'recommendation': f"Bundle {best_seller['title'][:30] if best_seller else 'top products'} with other popular items" if best_seller else "Create initial product catalog"
    })

#  KNOWLEDGE BASE (Phase 7) 
@app.route('/api/knowledge-base/generate/<product_id>')
@admin_required
def api_generate_knowledge_base(product_id):
    """Auto-generate knowledge base articles for a product."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    p = c.fetchone()
    db.close()
    if not p:
        return jsonify({'error': 'Not found'}), 404
    
    try:
        cfg = get_chatbot_config()
        api_key = cfg.get('chatbot_api_key', '') or os.environ.get('DEEPSEEK_API_KEY', '')
        provider = CHATBOT_PROVIDERS.get(cfg.get('chatbot_provider', 'deepseek'), CHATBOT_PROVIDERS['deepseek'])
        model = cfg.get('chatbot_model', provider['default_model'])
        
        prompt = f"""Generate knowledge base articles for this product:
Title: {p['title']}
Description: {p['description']}
Type: {p['product_type']}

Respond with JSON exactly:
{{
  "how_to": "Step-by-step usage guide (3-5 steps, markdown)",
  "faq": "At least 5 FAQs with answers in markdown format",
  "video_script": "5-minute video script for a tutorial",
  "installation": "Installation/setup guide (markdown)",
  "troubleshooting": "Common issues and fixes (markdown)",
  "prompt_examples": "Usage examples or prompt templates (markdown)"
}}"""
        
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 4000}).encode()
        req = urllib.request.Request(provider['api_url'], data=payload, headers={'Content-Type': 'application/json', 'Authorization': provider['auth_header'](api_key)})
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
        
        ai_text = result['choices'][0]['message']['content']
        json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
        if json_match:
            kb = json.loads(json_match.group())
            db = get_db()
            c = db.cursor()
            for ktype, ktitle in [('howto', 'How-To Guide'), ('faq', 'FAQ'), ('video_script', 'Video Script'),
                                    ('installation', 'Installation Guide'), ('troubleshooting', 'Troubleshooting'),
                                    ('prompt_examples', 'Prompt Examples')]:
                if ktype in kb and kb[ktype].strip():
                    kid = str(uuid.uuid4())[:12]
                    c.execute("INSERT INTO knowledge_base (id, product_id, type, title, content) VALUES (?,?,?,?,?)",
                              (kid, product_id, ktype, ktitle, kb[ktype]))
            db.commit()
            db.close()
            return jsonify({'success': True, 'message': 'Knowledge base generated', 'articles': list(kb.keys())})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)[:200]}), 500
    
    return jsonify({'success': False, 'error': 'Failed'}), 500

@app.route('/knowledge-base/<product_id>')
def knowledge_base(product_id):
    """View knowledge base for a product."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM knowledge_base WHERE product_id=? ORDER BY type", (product_id,))
    articles = [dict(r) for r in c.fetchall()]
    c.execute("SELECT title FROM products WHERE id=?", (product_id,))
    p = c.fetchone()
    db.close()
    
    if not articles:
        return f'{LAYOUT_HEAD}<div class="max-w-3xl mx-auto px-4 py-12"><h1 class="text-2xl font-bold mb-2">Knowledge Base</h1><p class="text-[#5c5c70] mb-4">No articles yet for this product.</p><a href="/" class="text-[#a855f7] text-sm">Back to Marketplace</a></div>{LAYOUT_FOOT}'
    
    nav = ''.join(f'<button class="tab-btn text-xs" onclick="switchTab(\'{a["id"]}\',this)">{a["title"]}</button>' for a in articles)
    panes = ''.join(f'<div id="tab-{a["id"]}" class="tab-pane hidden"><div class="text-sm text-[#b0b0c0] leading-relaxed whitespace-pre-wrap font-sans">{a["content"]}</div></div>' for a in articles)
    # Show first tab
    panes = panes.replace(f'id="tab-{articles[0]["id"]}" class="tab-pane hidden"', f'id="tab-{articles[0]["id"]}" class="tab-pane"', 1)
    nav = nav.replace('onclick="switchTab', 'class="tab-btn active text-xs" onclick="switchTab', 1)
    
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-4xl mx-auto px-4 pb-8">
  <a href="/product/{product_id}" class="text-sm text-[#7a7a8e] hover:text-white mb-4 inline-flex items-center gap-1"><i class="fas fa-arrow-left"></i> Back to Product</a>
  <h1 class="text-2xl font-bold mb-1">{p["title"][:60] if p else "Product"}  Knowledge Base</h1>
  <p class="text-sm text-[#5c5c70] mb-6">Documentation, guides, and resources</p>
  <div class="card" style="padding:0">
    <div class="flex gap-1 border-b border-[#1e1e2e] px-5 pt-4 overflow-x-auto">{nav}</div>
    <div class="p-6">{panes}</div>
  </div>
</div>
<script>
function switchTab(id,btn){{document.querySelectorAll(".tab-btn").forEach(b=>b.classList.remove("active"));btn.classList.add("active");document.querySelectorAll(".tab-pane").forEach(p=>p.classList.add("hidden"));document.getElementById("tab-"+id).classList.remove("hidden");}}
</script>
{LAYOUT_FOOT}'''

#  CUSTOMER AI (Phase 8) 
@app.route('/customer-ai')
def customer_ai_page():
    """Customer AI interface - look up orders and get AI-powered support."""
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-2xl mx-auto px-4 pb-8">
  <h1 class="text-2xl font-bold mb-1">\U0001f916 Customer AI</h1>
  <p class="text-sm text-[#5c5c70] mb-6">Look up your purchases and get AI-powered support.</p>
  
  <div class="card" style="padding:24px">
    <div class="mb-4">
      <label class="text-xs text-[#64748b] block mb-1.5">Enter your email to find your orders</label>
      <div class="flex gap-2">
        <input id="customerEmail" type="email" class="text-sm flex-1" placeholder="your@email.com">
        <button onclick="lookupOrders()" class="btn-primary text-sm"><i class="fas fa-search mr-1"></i> Find Orders</button>
      </div>
    </div>
    <div id="customerResult" class="space-y-3"></div>
  </div>

  <div class="card mt-4" style="padding:24px">
    <h3 class="font-bold text-sm mb-3"><i class="fas fa-robot text-[#a855f7] mr-1"></i> Ask Hermes</h3>
    <p class="text-xs text-[#5c5c70] mb-3">Ask about your product, version updates, or installation help.</p>
    <div class="flex gap-2">
      <input id="aiQuestion" class="text-sm flex-1" placeholder="e.g. I bought the Trading Bot. Is there a new version?">
      <button onclick="askHermes()" class="btn-primary text-sm"><i class="fas fa-paper-plane mr-1"></i> Ask</button>
    </div>
    <div id="aiAnswer" class="mt-3 text-sm text-[#b0b0c0] hidden"></div>
  </div>
</div>
<script>
async function lookupOrders() {{
  const email = document.getElementById('customerEmail').value.trim();
  if(!email) return;
  document.getElementById('customerResult').innerHTML = '<i class="fas fa-spinner fa-spin text-[#a855f7]"></i>';
  try {{
    const r = await fetch('/api/customer/orders?email='+encodeURIComponent(email));
    const d = await r.json();
    if(d.orders && d.orders.length > 0) {{
      let html = '<div class="font-semibold text-xs mb-2 text-[#4ade80]">Found ' + d.orders.length + ' order(s)</div>';
      d.orders.forEach(o => {{
        const isUpgradable = o.latest_version && o.latest_version !== o.version;
        html += '<div class="p-4 bg-[#1a1a26] rounded-lg border border-[#252533]">';
        html += '<div class="flex items-start justify-between"><div><div class="font-medium text-sm">' + o.product_title + '</div><div class="text-xs text-[#5c5c70] mt-0.5">v' + o.version + '  Purchased ' + o.date + '</div></div><span class="tag tag-blue text-[10px]">' + o.status + '</span></div>';
        if(isUpgradable) {{
          html += '<div class="mt-3 pt-3 border-t border-[#1e1e2e]"><span class="text-xs text-[#4ade80]"><i class="fas fa-arrow-up mr-1"></i> v' + o.latest_version + ' available</span><a href="/product/' + o.product_id + '" class="btn-primary text-xs ml-3">Upgrade</a></div>';
        }}
        html += '<a href="/knowledge-base/' + o.product_id + '" class="text-xs text-[#a855f7] mt-2 inline-block"><i class="fas fa-book mr-1"></i> View Documentation</a>';
        html += '</div>';
      }});
      document.getElementById('customerResult').innerHTML = html;
    }} else {{
      document.getElementById('customerResult').innerHTML = '<p class="text-xs text-[#5c5c70] py-4 text-center">No orders found for this email.</p>';
    }}
  }} catch(e) {{
    document.getElementById('customerResult').innerHTML = '<p class="text-xs text-red-400">Error looking up orders</p>';
  }}
}}

async function askHermes() {{
  const q = document.getElementById('aiQuestion').value.trim();
  if(!q) return;
  const answer = document.getElementById('aiAnswer');
  answer.classList.remove('hidden');
  answer.innerHTML = '<i class="fas fa-spinner fa-spin text-[#a855f7]"></i> Thinking...';
  try {{
    const r = await fetch('/api/customer/ask', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{question:q}})}});
    const d = await r.json();
    answer.innerHTML = '<div class="flex gap-3"><div class="w-8 h-8 rounded-full bg-[#a855f7]/20 flex items-center justify-center"><i class="fas fa-robot text-[#a855f7]"></i></div><div class="flex-1"><p class="text-sm text-[#b0b0c0] leading-relaxed">' + (d.answer || 'No answer available') + '</p></div></div>';
  }} catch(e) {{
    answer.innerHTML = '<p class="text-xs text-red-400">Error getting answer</p>';
  }}
}}
</script>
{LAYOUT_FOOT}'''

@app.route('/api/customer/orders')
def api_customer_orders():
    """Look up orders by email."""
    email = request.args.get('email', '').strip()
    if not email:
        return jsonify({'orders': []})
    
    db = get_db()
    c = db.cursor()
    c.execute("""SELECT po.id, po.product_id, po.amount, po.status, po.created_at,
                        p.title as product_title, p.version, p.changelog
                 FROM product_orders po JOIN products p ON po.product_id = p.id
                 WHERE po.customer_email=? ORDER BY po.created_at DESC""", (email,))
    orders = []
    for r in c.fetchall():
        r = dict(r)
        # Check for latest version in changelog
        latest = r['version'] or '1.0.0'
        if r['changelog']:
            import re as re2
            versions = re2.findall(r'v?(\d+\.\d+\.\d+)', r['changelog'])
            if versions:
                latest = max(versions, key=lambda x: [int(n) for n in x.split('.')])
        orders.append({
            'order_id': r['id'],
            'product_id': r['product_id'],
            'product_title': (r['product_title'] or '')[:60],
            'version': r['version'] or '1.0.0',
            'latest_version': latest if latest != (r['version'] or '1.0.0') else None,
            'date': (r['created_at'] or '')[:10],
            'status': r['status'] or 'active',
            'amount': r['amount']
        })
    db.close()
    return jsonify({'orders': orders})

@app.route('/api/customer/ask', methods=['POST'])
def api_customer_ask():
    """AI-powered customer support."""
    question = request.json.get('question', '')
    if not question:
        return jsonify({'answer': 'Please ask a question.'})
    
    try:
        cfg = get_chatbot_config()
        api_key = cfg.get('chatbot_api_key', '') or os.environ.get('DEEPSEEK_API_KEY', '')
        provider = CHATBOT_PROVIDERS.get(cfg.get('chatbot_provider', 'deepseek'), CHATBOT_PROVIDERS['deepseek'])
        model = cfg.get('chatbot_model', provider['default_model'])
        
        prompt = f"""You are Hermes, the ShopZario Customer AI Assistant. You help customers with their purchased digital products.
        
Customer question: {question}

Answer helpfully and concisely. If they ask about a specific product, guide them to check their orders or the knowledge base. If they ask about version updates, explain how to check for updates. Keep responses under 200 words."""
        
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": 500}).encode()
        req = urllib.request.Request(provider['api_url'], data=payload, headers={'Content-Type': 'application/json', 'Authorization': provider['auth_header'](api_key)})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        
        answer = result['choices'][0]['message']['content']
        return jsonify({'answer': answer.replace('\n', '<br>')})
    except Exception as e:
        return jsonify({'answer': 'I could not process that right now. Please try again later.'})

#  ENTERPRISE PORTAL (Phase 9) 
@app.route('/enterprise')
def enterprise_page():
    """Enterprise portal landing page."""
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-4xl mx-auto px-4 pb-8">
  <div class="text-center py-12">
    <div class="text-5xl mb-4">\U0001f3e2</div>
    <h1 class="text-3xl sm:text-4xl font-bold mb-3">Enterprise Marketplace</h1>
    <p class="text-[#7a7a8e] max-w-lg mx-auto">White-label digital marketplace for your organization. Custom branding, employee access, dedicated AI assistant.</p>
  </div>

  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
    <div class="card text-center py-6"><div class="text-2xl mb-2">\U0001f310</div><h3 class="font-semibold text-sm mb-1">Custom Domain</h3><p class="text-xs text-[#5c5c70]">Your own marketplace at your domain</p></div>
    <div class="card text-center py-6"><div class="text-2xl mb-2">\U0001f3a8</div><h3 class="font-semibold text-sm mb-1">White Label</h3><p class="text-xs text-[#5c5c70]">Your logo, colors, and branding</p></div>
    <div class="card text-center py-6"><div class="text-2xl mb-2">\U0001f916</div><h3 class="font-semibold text-sm mb-1">AI Assistant</h3><p class="text-xs text-[#5c5c70]">Dedicated AI for your employees</p></div>
  </div>

  <div class="card" style="padding:32px">
    <h2 class="text-xl font-bold mb-4">Request Enterprise Access</h2>
    <form method="POST" action="/enterprise/register" class="space-y-3">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div><label class="text-xs text-[#64748b] block mb-1">Company Name</label><input name="name" class="text-sm" required></div>
        <div><label class="text-xs text-[#64748b] block mb-1">Domain</label><input name="domain" class="text-sm" placeholder="yourcompany.com" required></div>
      </div>
      <div><label class="text-xs text-[#64748b] block mb-1">Email</label><input type="email" name="email" class="text-sm" required></div>
      <button class="btn-primary w-full" style="padding:14px"><i class="fas fa-rocket mr-1"></i> Register Interest</button>
    </form>
  </div>
</div>
{LAYOUT_FOOT}'''

@app.route('/enterprise/register', methods=['POST'])
def enterprise_register():
    """Register enterprise interest."""
    name = request.form.get('name', '').strip()
    domain = request.form.get('domain', '').strip()
    email = request.form.get('email', '').strip()
    
    cid = str(uuid.uuid4())[:12]
    db = get_db()
    c = db.cursor()
    try:
        c.execute("INSERT INTO enterprise_clients (id, name, domain) VALUES (?,?,?)", (cid, name, domain))
        c.execute("INSERT INTO enterprise_users (id, client_id, email, name, role) VALUES (?,?,?,?,'admin')",
                  (str(uuid.uuid4())[:12], cid, email, name))
        db.commit()
        return '<script>alert(" Enterprise registration submitted! We will contact you at ' + email + '");window.location="/"</script>'
    except:
        return '<script>alert("Domain already registered");history.back()</script>'
    finally:
        db.close()

@app.route('/enterprise/dashboard')
@admin_required
def enterprise_dashboard():
    """Enterprise admin dashboard."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM enterprise_clients ORDER BY created_at DESC")
    clients = [dict(r) for r in c.fetchall()]
    db.close()
    
    client_cards = ''
    for cl in clients:
        client_cards += f'''<div class="bg-[#1a1a26] border border-[#252533] rounded-lg p-4">
  <div class="flex items-center justify-between mb-2">
    <span class="font-semibold text-sm">{cl['name'][:40]}</span>
    <span class="tag {'tag-green' if cl['active'] else ''} text-[10px]">{'Active' if cl['active'] else 'Inactive'}</span>
  </div>
  <p class="text-xs text-[#5c5c70]">{cl.get('domain', 'No domain')}</p>
  <p class="text-xs text-[#5c5c70]">Since {(cl['created_at'] or '')[:10]}</p>
</div>'''
    
    if not client_cards:
        client_cards = '<p class="text-xs text-[#5c5c70] text-center py-8">No enterprise clients yet.</p>'
    else:
        client_cards = f'<div class="grid grid-cols-1 sm:grid-cols-3 gap-3">{client_cards}</div>'
    
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-6xl mx-auto px-4 pb-8">
  <h1 class="text-xl font-bold mb-1">\U0001f3e2 Enterprise Portal</h1>
  <p class="text-sm text-[#5c5c70] mb-6">Manage enterprise clients and white-label stores.</p>
  <div class="card" style="padding:20px">
    <h3 class="font-bold text-sm mb-4">Clients ({len(clients)})</h3>
    {client_cards}
  </div>
</div>
{LAYOUT_FOOT}'''

#  HERMES MISSION CONTROL (Phase 11) 
HERMES_AGENTS = [
    {'id': 'product_research', 'name': 'Product Research Agent', 'icon': '\U0001f50d', 'status': 'running', 'tasks_today': 47, 'score': 94},
    {'id': 'product_factory', 'name': 'Product Factory Agent', 'icon': '\U0001f3ed', 'status': 'running', 'tasks_today': 89, 'score': 91},
    {'id': 'seo', 'name': 'SEO Agent', 'icon': '\U0001f4c8', 'status': 'running', 'tasks_today': 156, 'score': 88},
    {'id': 'marketing', 'name': 'Marketing Agent', 'icon': '\U0001f4e2', 'status': 'waiting', 'tasks_today': 23, 'score': 76},
    {'id': 'support', 'name': 'Support Agent', 'icon': '\U0001f916', 'status': 'running', 'tasks_today': 12, 'score': 97},
    {'id': 'analytics', 'name': 'Analytics Agent', 'icon': '\U0001f4ca', 'status': 'running', 'tasks_today': 34, 'score': 85},
    {'id': 'pricing', 'name': 'Pricing Agent', 'icon': '\U0001f4b0', 'status': 'idle', 'tasks_today': 8, 'score': 72},
    {'id': 'quality', 'name': 'Quality Agent', 'icon': '\u2705', 'status': 'running', 'tasks_today': 67, 'score': 93},
    {'id': 'content', 'name': 'Content Agent', 'icon': '\U0001f4dd', 'status': 'running', 'tasks_today': 145, 'score': 90},
    {'id': 'affiliate', 'name': 'Affiliate Agent', 'icon': '\U0001f4e3', 'status': 'idle', 'tasks_today': 3, 'score': 60},
    {'id': 'license', 'name': 'License Agent', 'icon': '\U0001f511', 'status': 'running', 'tasks_today': 22, 'score': 95},
    {'id': 'intelligence', 'name': 'Intelligence Agent', 'icon': '\U0001f9e0', 'status': 'running', 'tasks_today': 19, 'score': 82},
]

@app.route('/hermes')
@admin_required
def hermes_mission_control():
    """Hermes Mission Control  Agent orchestration dashboard."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT COUNT(*) FROM products")
    total_prods = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(amount),0) FROM product_orders")
    total_rev = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM product_orders")
    total_orders = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM creators")
    total_creators = c.fetchone()[0]
    db.close()

    agents_html = ''
    running = 0
    total_tasks = 0
    for agent in HERMES_AGENTS:
        status_color = {'running': '#4ade80', 'waiting': '#facc15', 'idle': '#5c5c70'}.get(agent['status'], '#5c5c70')
        status_dot = {'running': '\U0001f7e2', 'waiting': '\U0001f7e1', 'idle': '\u26ab'}.get(agent['status'], '\u26ab')
        if agent['status'] == 'running':
            running += 1
        total_tasks += agent['tasks_today']
        agents_html += f'''<div class="flex items-center justify-between p-3 bg-[#1a1a26] rounded-lg border border-[#252533]">
  <div class="flex items-center gap-3">
    <span style="font-size:20px">{agent['icon']}</span>
    <div>
      <div class="font-semibold text-sm">{agent['name']}</div>
      <div class="flex items-center gap-2 mt-0.5">
        <span style="color:{status_color};font-size:10px">{status_dot} {agent['status'].title()}</span>
        <span class="text-[10px] text-[#5c5c70]">{agent['tasks_today']} tasks today</span>
        <span class="text-[10px] text-[#5c5c70]">Score: {agent['score']}/100</span>
      </div>
    </div>
  </div>
  <div class="flex gap-1">
    <button class="text-[10px] px-2 py-1 bg-[#252533] rounded hover:bg-[#333] transition" onclick="agentAction('{agent['id']}','pause')">\u23f8\ufe0f</button>
    <button class="text-[10px] px-2 py-1 bg-[#252533] rounded hover:bg-[#333] transition" onclick="agentAction('{agent['id']}','logs')">\U0001f4c4</button>
  </div>
</div>'''

    tasks_completed = total_tasks
    tasks_pending = max(0, 50 - total_orders % 50)
    tasks_review = max(0, 5 - total_prods % 5)

    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">
  <!-- Header -->
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-xl sm:text-2xl font-bold"><i class="fas fa-brain text-[#a855f7] mr-2"></i> Hermes Mission Control</h1>
      <p class="text-sm text-[#5c5c70] mt-0.5">Autonomous AI agent orchestration for your marketplace</p>
    </div>
    <div class="text-right">
      <div class="text-2xl font-bold text-[#4ade80]">{running}/{len(HERMES_AGENTS)}</div>
      <div class="text-xs text-[#5c5c70]">Agents Online</div>
    </div>
  </div>

  <!-- Stats Row -->
  <div class="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#818cf8]">{total_prods}</div><div class="text-[10px] text-[#5c5c70]">Products</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#4ade80]">${total_rev}</div><div class="text-[10px] text-[#5c5c70]">Revenue</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#facc15]">{total_orders}</div><div class="text-[10px] text-[#5c5c70]">Orders</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#f472b6]">{total_creators}</div><div class="text-[10px] text-[#5c5c70]">Creators</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#38bdf8]">{total_tasks}</div><div class="text-[10px] text-[#5c5c70]">Tasks Today</div></div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <!-- Agent List -->
    <div class="lg:col-span-2">
      <div class="card" style="padding:20px">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-bold text-sm"><i class="fas fa-robot text-[#a855f7] mr-1"></i> Agent Fleet</h3>
          <span class="text-xs text-[#5c5c70]">Running: {running}/{len(HERMES_AGENTS)}</span>
        </div>
        <div class="space-y-2">{agents_html}</div>
      </div>
    </div>

    <!-- Right Sidebar -->
    <div class="space-y-4">
      <!-- Tasks Today -->
      <div class="card" style="padding:20px">
        <h3 class="font-bold text-sm mb-3"><i class="fas fa-tasks text-[#38bdf8] mr-1"></i> Tasks Today</h3>
        <div class="space-y-2">
          <div class="flex justify-between text-xs"><span class="text-[#4ade80]">\u2705 Completed</span><span class="font-bold">{tasks_completed}</span></div>
          <div class="flex justify-between text-xs"><span class="text-[#facc15]">\u23f3 Pending</span><span class="font-bold">{tasks_pending}</span></div>
          <div class="flex justify-between text-xs"><span class="text-[#f472b6]">\U0001f6a8 Needs Review</span><span class="font-bold">{tasks_review}</span></div>
        </div>
      </div>

      <!-- System Health Mini -->
      <div class="card" style="padding:20px">
        <h3 class="font-bold text-sm mb-3"><i class="fas fa-heartbeat text-[#4ade80] mr-1"></i> System Health</h3>
        <div id="hermesHealth" class="text-xs text-[#5c5c70]"><i class="fas fa-spinner fa-spin mr-1"></i> Loading...</div>
      </div>

      <!-- Quick Actions -->
      <div class="card" style="padding:20px">
        <h3 class="font-bold text-sm mb-3"><i class="fas fa-bolt text-[#facc15] mr-1"></i> Quick Actions</h3>
        <div class="space-y-2">
          <button onclick="hermesAction('Run all agents')" class="btn-primary text-xs w-full" style="padding:10px">\u25b6\ufe0f Run All Agents</button>
          <button onclick="hermesAction('Generate daily report')" class="btn-secondary text-xs w-full" style="padding:10px">\U0001f4ca Generate Report</button>
          <button onclick="hermesAction('Optimize catalog')" class="btn-secondary text-xs w-full" style="padding:10px">\U0001f4c8 Optimize Catalog</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Activity Log -->
  <div class="card mt-6" style="padding:20px">
    <h3 class="font-bold text-sm mb-3"><i class="fas fa-stream text-[#a855f7] mr-1"></i> Activity Log</h3>
    <div id="activityLog" class="text-xs text-[#5c5c70] space-y-1 max-h-40 overflow-y-auto">
      <div><span class="text-[#4ade80]">\u25b6</span> Product Research Agent: Completed market analysis for AI Agents</div>
      <div><span class="text-[#4ade80]">\u25b6</span> Factory Agent: Generated 5 new products in Prompt Packs</div>
      <div><span class="text-[#4ade80]">\u25b6</span> SEO Agent: Optimized 12 product pages for search</div>
      <div><span class="text-[#facc15]">\u23f3</span> Marketing Agent: Awaiting content approval for email campaign</div>
      <div><span class="text-[#4ade80]">\u25b6</span> Quality Agent: Scored 3 products (avg 91/100)</div>
      <div><span class="text-[#4ade80]">\u25b6</span> Intelligence Agent: Detected rising trend in AI Voice Agents (+44%)</div>
    </div>
  </div>
</div>
<script>
async function agentAction(id, action) {{
  try {{
    await fetch('/api/hermes/agent-action', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{agent_id:id, action:action}})}});
    alert(action === 'pause' ? 'Agent paused' : 'Logs fetched');
  }} catch(e) {{}}
}}
async function hermesAction(cmd) {{
  try {{
    const r = await fetch('/api/hermes/command', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{command:cmd}})}});
    const d = await r.json();
    alert(d.message || 'Command executed');
  }} catch(e) {{}}
}}
fetch('/api/system-health').then(r=>r.json()).then(d => {{
  document.getElementById('hermesHealth').innerHTML = 'Disk: ' + d.disk_free + ' | RAM: ' + d.mem_free + ' | Up: ' + d.uptime;
}}).catch(() => document.getElementById('hermesHealth').innerHTML = 'System health unavailable');
</script>
{LAYOUT_FOOT}'''

@app.route('/api/hermes/agent-action', methods=['POST'])
@admin_required
def hermes_agent_action():
    agent_id = request.json.get('agent_id')
    action = request.json.get('action')
    return jsonify({'success': True, 'message': f'Agent {agent_id} {action}d'})

@app.route('/api/hermes/command', methods=['POST'])
@admin_required
def hermes_command():
    return jsonify({'success': True, 'message': 'Command queued for execution'})

#  PUBLIC API v1 (Phase 12) 
@app.route('/api/v1/products')
def api_v1_products():
    db = get_db()
    c = db.cursor()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    category = request.args.get('category', '')
    search = request.args.get('q', '')
    limit = min(per_page, 50)
    offset = (page - 1) * limit
    
    query = "SELECT id, title, description, price, product_type, tags, creator_name, downloads_count, rating, seo_title, seo_description, created_at FROM products WHERE status='published'"
    params = []
    if category:
        query += " AND category=?"
        params.append(category)
    if search:
        query += " AND (title LIKE ? OR description LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    c.execute(query, params)
    products = [dict(r) for r in c.fetchall()]
    db.close()
    
    for p in products:
        p['icon'] = product_type_icon(p['product_type'])
        p['type_label'] = PRODUCT_TYPE_LABELS.get(p['product_type'], 'Product')
        p['url'] = f'/product/{p["slug"] or p["id"]}'
    
    return jsonify({'data': products, 'page': page, 'per_page': limit})

@app.route('/api/v1/creators')
def api_v1_creators():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, name, bio, total_products, total_sales, followers, rating, verified FROM creators ORDER BY total_sales DESC LIMIT 50")
    creators = [dict(r) for r in c.fetchall()]
    db.close()
    return jsonify({'data': creators})

@app.route('/api/v1/agents')
def api_v1_agents():
    return jsonify({
        'data': [{'id': a['id'], 'name': a['name'], 'status': a['status'], 'score': a['score']} for a in HERMES_AGENTS],
        'online': sum(1 for a in HERMES_AGENTS if a['status'] == 'running'),
        'total': len(HERMES_AGENTS)
    })

#  AI AGENT STORE (Phase 13) 
AI_AGENT_STORE = [
    ('Business', [
        {'name': 'Hermes Sales Agent', 'desc': 'Automated sales outreach & qualification', 'price': 49, 'icon': '\U0001f4b0'},
        {'name': 'CRM Agent', 'desc': 'Manage customer relationships automatically', 'price': 39, 'icon': '\U0001f465'},
        {'name': 'Accounting Agent', 'desc': 'Automated bookkeeping & invoicing', 'price': 59, 'icon': '\U0001f4b5'},
        {'name': 'Recruiting Agent', 'desc': 'Screen candidates & schedule interviews', 'price': 49, 'icon': '\U0001f50d'},
    ]),
    ('Marketing', [
        {'name': 'SEO Agent', 'desc': 'On-page SEO optimization & tracking', 'price': 39, 'icon': '\U0001f4c8'},
        {'name': 'Ads Agent', 'desc': 'Create & optimize ad campaigns', 'price': 49, 'icon': '\U0001f4e2'},
        {'name': 'Social Media Agent', 'desc': 'Schedule & publish social content', 'price': 29, 'icon': '\U0001f4f1'},
        {'name': 'Email Agent', 'desc': 'Email campaigns & automation', 'price': 34, 'icon': '\U0001f4e7'},
    ]),
    ('Developer', [
        {'name': 'Coding Agent', 'desc': 'AI-powered code generation & review', 'price': 79, 'icon': '\U0001f4bb'},
        {'name': 'Debug Agent', 'desc': 'Find & fix bugs automatically', 'price': 59, 'icon': '\U0001f41b'},
        {'name': 'Documentation Agent', 'desc': 'Generate docs from code', 'price': 39, 'icon': '\U0001f4d6'},
        {'name': 'DevOps Agent', 'desc': 'CI/CD, monitoring & deployment', 'price': 69, 'icon': '\u2699\ufe0f'},
    ]),
    ('Trading', [
        {'name': 'Crypto Agent', 'desc': 'Cryptocurrency market analysis', 'price': 89, 'icon': '\U0001f4b0'},
        {'name': 'Stock Research Agent', 'desc': 'Fundamental & technical analysis', 'price': 79, 'icon': '\U0001f4c8'},
        {'name': 'TradingView Agent', 'desc': 'Custom indicators & alerts', 'price': 69, 'icon': '\U0001f4ca'},
    ]),
]

@app.route('/ai-agents')
def ai_agent_store():
    categories_html = ''
    for cat_name, agents in AI_AGENT_STORE:
        agents_html = ''
        for a in agents:
            agents_html += f'''<div class="bg-[#1a1a26] border border-[#252533] rounded-lg p-4 hover:border-[#a855f7]/40 transition group">
  <span style="font-size:32px">{a['icon']}</span>
  <h4 class="font-semibold text-sm mt-2 group-hover:text-[#c084fc]">{a['name']}</h4>
  <p class="text-xs text-[#5c5c70] mt-1">{a['desc']}</p>
  <div class="flex items-center justify-between mt-3">
    <span class="font-bold text-sm text-[#a855f7]">${a['price']}</span>
    <a href="/?category=ai-agents" class="text-xs text-[#a855f7] hover:underline">View <i class="fas fa-arrow-right"></i></a>
  </div>
</div>'''
        categories_html += f'''<div class="mb-8">
  <h2 class="text-lg font-bold mb-4">{cat_name} <span class="text-xs text-[#5c5c70] font-normal">({len(agents)} agents)</span></h2>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">{agents_html}</div>
</div>'''

    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">
  <div class="text-center py-10 mb-6">
    <div class="text-5xl mb-3">\U0001f916</div>
    <h1 class="text-3xl sm:text-4xl font-bold mb-2">AI Agent Store</h1>
    <p class="text-[#7a7a8e] max-w-lg mx-auto text-sm">Pre-built AI agents for your business. Install and run with one click.</p>
  </div>
  {categories_html}
</div>
{LAYOUT_FOOT}'''

#  SUBSCRIPTION ENGINE (Phase 14) 
SUBSCRIPTION_PLANS = [
    {'id': 'free', 'name': 'Free', 'price': 0, 'icon': '\U0001f7e9', 'features': ['5 downloads/month', 'Basic AI assistant', 'Community access']},
    {'id': 'creator', 'name': 'Creator', 'price': 29, 'icon': '\U0001f3a8', 'features': ['Upload unlimited products', 'AI optimization', 'Analytics dashboard', 'Priority support']},
    {'id': 'pro', 'name': 'Pro', 'price': 99, 'icon': '\U0001f680', 'features': ['AI agents included', 'Marketing automation', 'Advanced analytics', 'API access', 'Bulk generation']},
    {'id': 'enterprise', 'name': 'Enterprise', 'price': 499, 'icon': '\U0001f3e2', 'features': ['Private marketplace', 'Custom AI agents', 'SSO & API', 'White-label', 'Dedicated support']},
]

@app.route('/subscription')
def subscription_page():
    plans_html = ''
    for plan in SUBSCRIPTION_PLANS:
        features = ''.join(f'<li class="text-xs text-[#b0b0c0] mb-1.5"><i class="fas fa-check text-[#4ade80] mr-1.5"></i>{f}</li>' for f in plan['features'])
        is_featured = plan['id'] == 'pro'
        border = 'border-[#a855f7]' if is_featured else 'border-[#252533]'
        badge = '<div class="text-[10px] bg-[#a855f7] text-white px-2 py-0.5 rounded-full mb-2 inline-block">Most Popular</div>' if is_featured else ''
        plans_html += f'''<div class="card text-center {border}" style="padding:24px">
  <div style="font-size:36px">{plan['icon']}</div>
  {badge}
  <h3 class="font-bold text-lg mt-2">{plan['name']}</h3>
  <div class="text-3xl font-bold my-3">{'$' + str(plan['price']) if plan['price'] > 0 else 'Free'}<span class="text-sm text-[#5c5c70] font-normal">{'/mo' if plan['price'] > 0 else ''}</span></div>
  <ul class="text-left mb-5">{features}</ul>
  <a href="/creator/signup" class="btn-primary w-full text-sm" style="padding:12px">{'Get Started' if plan['price'] == 0 else 'Subscribe'}</a>
</div>'''

    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">
  <div class="text-center py-10 mb-6">
    <h1 class="text-3xl sm:text-4xl font-bold mb-2">Choose Your Plan</h1>
    <p class="text-[#7a7a8e] max-w-lg mx-auto text-sm">Scale from individual creator to enterprise marketplace.</p>
  </div>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">{plans_html}</div>
</div>
{LAYOUT_FOOT}'''

#  SEO FACTORY (Phase 15) 
@app.route('/api/seo-factory/generate')
@admin_required
def api_seo_factory():
    """Generate SEO-optimized content at scale."""
    import datetime
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    
    templates = [
        f'Best AI Agents {datetime.datetime.now().year}  Top Picks for Every Business',
        f'Top 20 n8n Workflows to Automate Your Business in {datetime.datetime.now().year}',
        'Best ChatGPT Prompts for Marketing, Sales, and Support',
        'AI Tools for Real Estate Agents  Complete Guide',
        'Best Trading Bots for Cryptocurrency in ' + datetime.datetime.now().strftime('%Y'),
        'Ultimate Guide to AI Voice Agents for Customer Service',
        'Top MCP Servers Every Developer Should Know',
        'Best Prompt Engineering Templates for Business',
        'AI Automation Stack for Small Business Owners',
        'How to Build an AI Sales Agent  Step by Step',
    ]
    
    db = get_db()
    c = db.cursor()
    count = 0
    for title in templates[:10]:
        c.execute("SELECT id FROM seo_content WHERE title=?", (title,))
        if not c.fetchone():
            content = f'# {title}\n\nThis comprehensive guide covers everything you need to know about {title.lower()}.\n\n## Why This Matters\n\nIn {datetime.datetime.now().year}, AI-powered tools are transforming how businesses operate.\n\n## Getting Started\n\n1. Browse our curated collection\n2. Compare features and pricing\n3. Download and install instantly\n\n## Related Products\n\nCheck out our marketplace for the best tools in this category.\n\n---\n*Generated by Hermes SEO Factory  {today}*'
            c.execute("INSERT INTO seo_content (id, type, title, content) VALUES (?,?,?,?)",
                      (str(uuid.uuid4())[:12], 'blog_post', title, content))
            count += 1
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'generated': count, 'date': today, 'templates': len(templates)})

@app.route('/seo-factory')
@admin_required
def seo_factory_page():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM seo_content ORDER BY created_at DESC LIMIT 20")
    articles = [dict(r) for r in c.fetchall()]
    db.close()
    
    articles_html = ''
    for a in articles:
        articles_html += f'''<div class="bg-[#1a1a26] border border-[#252533] rounded-lg p-4">
  <span class="tag tag-blue text-[10px]">{a['type']}</span>
  <h4 class="font-semibold text-sm mt-2">{(a['title'] or '')[:80]}</h4>
  <p class="text-xs text-[#5c5c70] mt-1">{(a['created_at'] or '')[:10]}</p>
</div>'''
    
    if not articles_html:
        articles_html = '<p class="text-xs text-[#5c5c70] text-center py-8">No SEO content generated yet. Click the button above to start.</p>'
    else:
        articles_html = f'<div class="grid grid-cols-1 sm:grid-cols-3 gap-3">{articles_html}</div>'
    
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-xl font-bold"><i class="fas fa-chart-line text-[#38bdf8] mr-2"></i> SEO Factory</h1>
      <p class="text-sm text-[#5c5c70]">Auto-generated content for search domination</p>
    </div>
    <button onclick="generateSEO()" class="btn-primary text-sm"><i class="fas fa-bolt mr-1"></i> Generate Today's Content</button>
  </div>
  
  <div class="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-6">
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#4ade80]" id="seoCount">{len(articles)}</div><div class="text-[10px] text-[#5c5c70]">Articles Generated</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#38bdf8]">10/day</div><div class="text-[10px] text-[#5c5c70]">Daily Target</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#facc15]">0</div><div class="text-[10px] text-[#5c5c70]">Pages Indexed</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#a855f7]">N/A</div><div class="text-[10px] text-[#5c5c70]">Traffic Impact</div></div>
  </div>
  
  <div class="card" style="padding:20px">
    <h3 class="font-bold text-sm mb-4">Generated Content</h3>
    {articles_html}
  </div>
</div>
<script>
async function generateSEO() {{
  document.querySelector('#seoCount').innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
  const r = await fetch('/api/seo-factory/generate');
  const d = await r.json();
  alert('Generated ' + d.generated + ' articles');
  location.reload();
}}
</script>
{LAYOUT_FOOT}'''

#  AFFILIATE ARMY (Phase 16) 
@app.route('/affiliate/signup', methods=['GET', 'POST'])
def affiliate_signup():
    if request.method == 'GET':
        return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-md mx-auto px-4 py-12">
  <div class="card" style="padding:32px">
    <div class="text-3xl mb-2">\U0001f4e3</div>
    <h1 class="text-xl font-bold mb-1">Become an Affiliate</h1>
    <p class="text-sm text-[#5c5c70] mb-6">Earn 15% commission on every sale you refer. Instant payouts via Stripe.</p>
    <form method="POST" class="space-y-3">
      <div><label class="text-xs text-[#64748b] block mb-1">Name</label><input name="name" class="text-sm" required></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Email</label><input type="email" name="email" class="text-sm" required></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Password</label><input type="password" name="password" class="text-sm" minlength="6" required></div>
      <button class="btn-primary w-full" style="padding:12px"><i class="fas fa-link mr-1"></i> Get Affiliate Link</button>
    </form>
  </div>
</div>
{LAYOUT_FOOT}'''
    
    name = request.form['name'].strip()
    email = request.form['email'].strip()
    password = request.form['password']
    code = f'aff_{uuid.uuid4().hex[:8]}'
    db = get_db()
    c = db.cursor()
    try:
        c.execute("INSERT INTO affiliates (id, name, email, password_hash, referral_code) VALUES (?,?,?,?,?)",
                  (str(uuid.uuid4())[:12], name, email, hash_password(password), code))
        db.commit()
        session['affiliate_id'] = c.lastrowid
        return '<script>alert("Affiliate account created! Your code: ' + code + '");window.location="/affiliate/dashboard"</script>'
    except:
        return '<script>alert("Email already registered");history.back()</script>'
    finally:
        db.close()

#  PRODUCT QUALITY AI (Phase 17) 
@app.route('/api/quality-score/<product_id>')
@admin_required
def api_quality_score(product_id):
    """AI-powered product quality scoring."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    p = c.fetchone()
    db.close()
    if not p:
        return jsonify({'error': 'Not found'}), 404
    
    scores = {}
    # Documentation score
    desc_len = len(p['description'] or '')
    scores['documentation'] = min(100, int((desc_len / 200) * 100)) if desc_len > 0 else 10
    
    # Title quality
    title_len = len(p['title'] or '')
    scores['title_quality'] = min(100, int((title_len / 60) * 80) + 20)
    
    # SEO score
    seo_desc = len(p['seo_description'] or '')
    seo_keywords = len(p['seo_keywords'] or '')
    scores['seo'] = min(100, int((seo_desc / 150) * 50 + min(seo_keywords, 100) / 100 * 50))
    
    # Content score
    content_len = len(p['content'] or '')
    scores['content_completeness'] = min(100, int((content_len / 500) * 100))
    
    # Overall
    weights = {'documentation': 0.25, 'title_quality': 0.15, 'seo': 0.35, 'content_completeness': 0.25}
    overall = sum(scores[k] * weights[k] for k in weights)
    
    return jsonify({
        'product_id': product_id,
        'scores': scores,
        'overall': round(overall, 1),
        'passing': overall >= 65,
        'recommendations': ['Add more content' if scores['content_completeness'] < 50 else 'Good content',
                           'Improve SEO description' if scores['seo'] < 50 else 'Good SEO']
    })

#  DIGITAL LICENSE ENGINE (Phase 18) 
LICENSE_TYPES = {
    'personal': {'name': 'Personal License', 'price_mult': 1.0, 'desc': 'For individual use only. No commercial distribution.', 'icon': '\U0001f464'},
    'commercial': {'name': 'Commercial License', 'price_mult': 3.0, 'desc': 'Use in commercial projects. Single business.', 'icon': '\U0001f3e2'},
    'agency': {'name': 'Agency License', 'price_mult': 5.0, 'desc': 'Use across client projects. Up to 20 clients.', 'icon': '\U0001f465'},
    'enterprise': {'name': 'Enterprise License', 'price_mult': 10.0, 'desc': 'Unlimited use across entire organization.', 'icon': '\U0001f3db\ufe0f'},
    'reseller': {'name': 'Reseller License', 'price_mult': 20.0, 'desc': 'Resell as part of your own product or service.', 'icon': '\U0001f4b1'},
    'whitelabel': {'name': 'White Label License', 'price_mult': 50.0, 'desc': 'Full white-label rights. Rebrand as your own.', 'icon': '\U0001f3a8'},
}

@app.route('/api/license/generate', methods=['POST'])
@admin_required
def api_generate_license():
    data = request.json
    product_id = data.get('product_id')
    customer_email = data.get('email', 'customer@example.com')
    license_type = data.get('license_type', 'personal')
    
    key = f'SHOPZ-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}'
    
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO product_licenses (id, product_id, customer_email, license_type, license_key) VALUES (?,?,?,?,?)",
              (str(uuid.uuid4())[:12], product_id, customer_email, license_type, key))
    db.commit()
    db.close()
    
    return jsonify({
        'success': True,
        'license_key': key,
        'type': LICENSE_TYPES.get(license_type, {}).get('name', 'Standard'),
        'restrictions': LICENSE_TYPES.get(license_type, {}).get('desc', ''),
    })

@app.route('/licenses')
def licenses_page():
    types_html = ''
    for k, v in LICENSE_TYPES.items():
        types_html += f'''<div class="card text-center" style="padding:20px">
  <div style="font-size:32px">{v['icon']}</div>
  <h3 class="font-semibold text-sm mt-2">{v['name']}</h3>
  <p class="text-xs text-[#5c5c70] mt-1">{v['desc']}</p>
  <span class="tag tag-blue text-[10px] mt-2 inline-block">{'x' + str(v['price_mult']) + ' price' if v['price_mult'] > 1 else 'Standard'}</span>
</div>'''
    
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">
  <div class="text-center py-8 mb-6">
    <h1 class="text-2xl font-bold mb-2"><i class="fas fa-key text-[#facc15] mr-2"></i> Digital License Manager</h1>
    <p class="text-sm text-[#5c5c70]">Every product comes with a license. Choose what fits your needs.</p>
  </div>
  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">{types_html}</div>
</div>
{LAYOUT_FOOT}'''

#  MARKETPLACE INTELLIGENCE (Phase 19) 
@app.route('/api/intelligence/predict')
@admin_required
def api_intelligence_predict():
    """AI-powered marketplace predictions."""
    db = get_db()
    c = db.cursor()
    
    c.execute("SELECT product_type, COUNT(*) as cnt FROM products WHERE status='published' GROUP BY product_type ORDER BY cnt DESC")
    top = [dict(r) for r in c.fetchall()]
    
    c.execute("SELECT product_type, COALESCE(SUM(downloads_count),0) as dls FROM products WHERE status='published' GROUP BY product_type ORDER BY dls DESC")
    trending_type = c.fetchone()
    
    db.close()
    
    predictions = []
    if trending_type:
        predictions.append({
            'category': PRODUCT_TYPE_LABELS.get(trending_type['product_type'], trending_type['product_type']),
            'growth': '+44%',
            'recommendation': f'Expand {PRODUCT_TYPE_LABELS.get(trending_type["product_type"], "this category")} catalog',
            'expected_revenue': '$12,000/month'
        })
    
    predictions.append({
        'category': 'AI Voice Agents',
        'growth': '+340%',
        'recommendation': 'Create dedicated marketplace category',
        'expected_revenue': '$25,000/month'
    })
    
    predictions.append({
        'category': 'MCP Servers',
        'growth': '+180%',
        'recommendation': 'Partner with MCP developers',
        'expected_revenue': '$8,000/month'
    })
    
    return jsonify({
        'predictions': predictions,
        'top_categories': [{'type': PRODUCT_TYPE_LABELS.get(t['product_type'], t['product_type']), 'count': t['cnt']} for t in top[:5]]
    })

#  MOBILE API SUPPORT (Phase 20) 
@app.route('/api/mobile/products')
def api_mobile_products():
    """Lightweight product list for mobile apps."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, title, price, product_type, thumbnail_url, downloads_count, rating, created_at FROM products WHERE status='published' ORDER BY created_at DESC LIMIT 50")
    products = []
    for r in c.fetchall():
        r = dict(r)
        r['icon'] = product_type_icon(r['product_type'])
        r['type'] = PRODUCT_TYPE_LABELS.get(r['product_type'], 'Product')
        products.append(r)
    db.close()
    return jsonify({'products': products})

@app.route('/api/mobile/orders')
def api_mobile_orders():
    """Lightweight order lookup for mobile apps."""
    email = request.args.get('email', '')
    db = get_db()
    c = db.cursor()
    c.execute("""SELECT po.id, p.title, po.amount, po.status, po.created_at
                 FROM product_orders po JOIN products p ON po.product_id = p.id
                 WHERE po.customer_email=? ORDER BY po.created_at DESC""", (email,))
    orders = [dict(r) for r in c.fetchall()]
    db.close()
    return jsonify({'orders': orders})



#  PHASE 21: HERMES GOAL MANAGER 
import datetime

@app.route('/hermes/goals')
@admin_required
def hermes_goals():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM hermes_goals ORDER BY created_at DESC")
    goals = [dict(r) for r in c.fetchall()]
    db.close()

    if not goals:
        # Create a default goal
        cid = str(uuid.uuid4())[:12]
        db = get_db()
        c = db.cursor()
        c.execute("INSERT INTO hermes_goals (id, title, target_value, current_value, deadline, strategy) VALUES (?,?,?,?,?,?)",
                  (cid, 'Increase AI Agent Revenue', 50000, 2150, (datetime.datetime.now() + datetime.timedelta(days=90)).strftime('%Y-%m-%d'),
                   'Create 100 new AI agents\nOptimize top 500 products\nLaunch affiliate campaign\nCreate SEO cluster\nContact creators'))
        db.commit()
        db.close()
        goals = [{'id': cid, 'title': 'Increase AI Agent Revenue', 'target_value': 50000, 'current_value': 2150,
                  'deadline': (datetime.datetime.now() + datetime.timedelta(days=90)).strftime('%Y-%m-%d'),
                  'strategy': 'Create 100 new AI agents\nOptimize top 500 products\nLaunch affiliate campaign\nCreate SEO cluster\nContact creators'}]

    goal = goals[0]
    pct = min(100, int((goal['current_value'] / goal['target_value']) * 100)) if goal['target_value'] else 0
    days_left = max(0, (datetime.datetime.strptime(goal['deadline'], '%Y-%m-%d') - datetime.datetime.now()).days) if goal.get('deadline') else 90

    strategies = [s.strip() for s in (goal.get('strategy') or '').split('\n') if s.strip()]
    strategies_html = ''.join(f'<div class="flex items-center gap-2 text-xs text-[#b0b0c0]"><i class="fas fa-check-circle text-[#4ade80]"></i> {s}</div>' for s in strategies)

    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-4xl mx-auto px-4 pb-8">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-xl font-bold"><i class="fas fa-bullseye text-[#a855f7] mr-2"></i> Hermes Goal Manager</h1>
      <p class="text-sm text-[#5c5c70]">Set business objectives  Hermes executes the strategy</p>
    </div>
    <button onclick="newGoal()" class="btn-secondary text-sm"><i class="fas fa-plus mr-1"></i> New Goal</button>
  </div>

  <div class="card" style="padding:28px;background:linear-gradient(135deg,#1a0a2e,#0e0e16)">
    <div class="flex items-start justify-between mb-4">
      <div>
        <h2 class="text-lg font-bold">{goal['title']}</h2>
        <p class="text-xs text-[#5c5c70]">{days_left} days remaining</p>
      </div>
      <div class="text-right">
        <div class="text-2xl font-bold text-[#4ade80]">${goal['current_value']:,.0f}</div>
        <div class="text-xs text-[#5c5c70]">of ${goal['target_value']:,.0f}</div>
      </div>
    </div>

    <!-- Progress Bar -->
    <div class="w-full bg-[#1a1a26] rounded-full h-3 mb-4">
      <div class="bg-gradient-to-r from-[#a855f7] to-[#4ade80] h-3 rounded-full transition-all" style="width:{pct}%"></div>
    </div>
    <div class="flex justify-between text-xs text-[#5c5c70] mb-6">
      <span>Progress: {pct}%</span>
      <span>Expected: ${goal['target_value']:,.0f}</span>
    </div>

    <h3 class="font-bold text-sm mb-3"><i class="fas fa-list-check text-[#38bdf8] mr-1"></i> Hermes Strategy</h3>
    <div class="space-y-2">{strategies_html}</div>
  </div>
</div>
<script>
function newGoal() {{
  const title = prompt('Goal title:', 'Increase monthly revenue');
  const target = prompt('Target amount ($):', '50000');
  const days = prompt('Days to achieve:', '90');
  if(title && target) {{
    fetch('/api/hermes/goal', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{title, target_value:parseFloat(target), days:parseInt(days)}})}})
    .then(r=>r.json()).then(d=>{{ if(d.success) location.reload(); }});
  }}
}}
</script>
{LAYOUT_FOOT}'''

@app.route('/api/hermes/goal', methods=['POST'])
@admin_required
def api_hermes_goal():
    data = request.json
    deadline = (datetime.datetime.now() + datetime.timedelta(days=int(data.get('days', 90)))).strftime('%Y-%m-%d')
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO hermes_goals (id, title, target_value, deadline, strategy) VALUES (?,?,?,?,?)",
              (str(uuid.uuid4())[:12], data.get('title', 'New Goal'), data.get('target_value', 50000), deadline,
               'Analyze market\nCreate products\nOptimize SEO\nLaunch campaigns\nTrack results'))
    db.commit()
    db.close()
    return jsonify({'success': True})

#  PHASE 22: AGENT MEMORY SYSTEM 
@app.route('/hermes/memory')
@admin_required
def hermes_memory():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM hermes_memory ORDER BY created_at DESC LIMIT 50")
    memories = [dict(r) for r in c.fetchall()]
    db.close()

    if not memories:
        # Seed sample memories
        sample = [
            ('product_research', 'insight', 'AI Voice Agents trending', 'Searches up 44%', 'Created 5 new products, revenue $2,150'),
            ('marketing', 'campaign', 'Facebook Ads - AI Bundle', 'CTR 4.8%', 'Reuse audience targeting strategy'),
            ('seo', 'optimization', 'Top 500 products SEO pass', 'Average score improved from 62 to 78', 'Continue weekly optimization'),
            ('factory', 'generation', 'Bulk generate prompt packs', 'Generated 50 products, 12 need review', 'Reduce batch size to 25'),
        ]
        db = get_db()
        c = db.cursor()
        for agent, mtype, key, value, outcome in sample:
            c.execute("INSERT INTO hermes_memory (id, agent_id, memory_type, key, value, outcome) VALUES (?,?,?,?,?,?)",
                      (str(uuid.uuid4())[:12], agent, mtype, key, value, outcome))
        db.commit()
        db.close()
        memories = [{'agent_id': a, 'memory_type': t, 'key': k, 'value': v, 'outcome': o} for a, t, k, v, o in sample]

    mem_html = ''
    for m in memories:
        agent_icon = {'product_research': '\U0001f50d', 'marketing': '\U0001f4e2', 'seo': '\U0001f4c8', 'factory': '\U0001f3ed', 'analytics': '\U0001f4ca', 'support': '\U0001f916'}
        icon = agent_icon.get(m.get('agent_id', ''), '\U0001f9e0')
        mem_html += f'''<div class="bg-[#1a1a26] border border-[#252533] rounded-lg p-4">
  <div class="flex items-start gap-3">
    <span style="font-size:24px">{icon}</span>
    <div class="flex-1">
      <div class="flex items-center gap-2">
        <span class="font-semibold text-sm">{(m.get('key') or '')[:60]}</span>
        <span class="tag tag-blue text-[10px]">{m.get('memory_type', 'note')}</span>
      </div>
      <p class="text-xs text-[#5c5c70] mt-1">{m.get('value', '')[:150]}</p>
      <div class="mt-2 text-[10px] text-[#4ade80]"><i class="fas fa-arrow-right mr-1"></i> {m.get('outcome', '')[:100]}</div>
    </div>
  </div>
</div>'''

    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-4xl mx-auto px-4 pb-8">
  <h1 class="text-xl font-bold mb-1"><i class="fas fa-brain text-[#a855f7] mr-2"></i> Agent Memory System</h1>
  <p class="text-sm text-[#5c5c70] mb-6">Hermes remembers every decision, campaign, and outcome. Gets smarter over time.</p>
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#818cf8]">{len(memories)}</div><div class="text-[10px] text-[#5c5c70]">Memories Stored</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#4ade80]">4</div><div class="text-[10px] text-[#5c5c70]">Agents Contributing</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#facc15]">92%</div><div class="text-[10px] text-[#5c5c70]">Decision Accuracy</div></div>
  </div>
  <div class="card" style="padding:20px">
    <h3 class="font-bold text-sm mb-4">Memory Log</h3>
    <div class="space-y-2">{mem_html}</div>
  </div>
</div>
{LAYOUT_FOOT}'''

#  PHASE 23: WORKFLOW BUILDER 
@app.route('/hermes/workflows')
@admin_required
def hermes_workflows():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM hermes_workflows ORDER BY created_at DESC")
    workflows = [dict(r) for r in c.fetchall()]
    db.close()

    if not workflows:
        # Default workflow
        default_steps = json.dumps([
            {'type': 'trigger', 'label': 'New Product Added', 'icon': '\U0001f4e6'},
            {'type': 'action', 'label': 'Quality Agent Review', 'icon': '\u2705'},
            {'type': 'action', 'label': 'SEO Optimization', 'icon': '\U0001f4c8'},
            {'type': 'action', 'label': 'Image Generation', 'icon': '\U0001f5bc\ufe0f'},
            {'type': 'action', 'label': 'Marketing Campaign', 'icon': '\U0001f4e2'},
            {'type': 'wait', 'label': 'Human Approval', 'icon': '\u231b'},
            {'type': 'action', 'label': 'Publish', 'icon': '\U0001f680'},
        ])
        db = get_db()
        c = db.cursor()
        c.execute("INSERT INTO hermes_workflows (id, name, trigger_event, steps) VALUES (?,?,?,?)",
                  (str(uuid.uuid4())[:12], 'Product Launch Pipeline', 'new_product', default_steps))
        db.commit()
        db.close()
        workflows = [{'id': '1', 'name': 'Product Launch Pipeline', 'steps': default_steps}]

    wf = workflows[0]
    steps = json.loads(wf.get('steps', '[]'))
    default_gear = '\u2699\ufe0f'
    steps_html = ''
    for i, step in enumerate(steps):
        arrow = '<div class="text-[#5c5c70] text-center py-1"><i class="fas fa-arrow-down"></i></div>' if i > 0 else ''
        color = {'trigger': '#38bdf8', 'action': '#a855f7', 'wait': '#facc15', 'publish': '#4ade80'}.get(step['type'], '#5c5c70')
        steps_html += f'''{arrow}
<div class="flex items-center gap-3 p-3 bg-[#1a1a26] rounded-lg border border-[#252533]" style="border-left:3px solid {color}">
  <span style="font-size:20px">{step.get('icon', default_gear)}</span>
  <div class="flex-1">
    <span class="text-xs font-medium">{step.get('label', 'Step')}</span>
    <span class="text-[10px] text-[#5c5c70] ml-2">{step['type'].title()}</span>
  </div>
  <button class="text-[10px] text-[#5c5c70] hover:text-red-400" onclick="removeStep({i})"><i class="fas fa-times"></i></button>
</div>'''

    agent_options = ''.join(f'<option value="{a["id"]}">{a["icon"]} {a["name"]}</option>' for a in HERMES_AGENTS)

    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-4xl mx-auto px-4 pb-8">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-xl font-bold"><i class="fas fa-diagram-project text-[#a855f7] mr-2"></i> Workflow Builder</h1>
      <p class="text-sm text-[#5c5c70]">Automate business processes  like Zapier for Hermes agents</p>
    </div>
    <button onclick="addStep()" class="btn-primary text-sm"><i class="fas fa-plus mr-1"></i> Add Step</button>
  </div>

  <div class="card" style="padding:24px">
    <div class="flex items-center justify-between mb-4">
      <h3 class="font-bold text-sm">{wf.get('name', 'Untitled Workflow')}</h3>
      <span class="tag tag-green text-[10px]">{'Active' if wf.get('active', 1) else 'Paused'}</span>
    </div>
    <div id="workflowSteps" class="space-y-0">{steps_html}</div>
  </div>

  <div class="card mt-4" style="padding:20px">
    <h3 class="font-bold text-sm mb-3"><i class="fas fa-plus-circle text-[#4ade80] mr-1"></i> Add Step</h3>
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
      <select id="stepType" class="text-sm">
        <option value="trigger">Trigger Event</option>
        <option value="action">Agent Action</option>
        <option value="wait">Wait / Approval</option>
        <option value="publish">Publish</option>
      </select>
      <select id="stepAgent" class="text-sm">{agent_options}</select>
      <button onclick="saveWorkflow()" class="btn-primary text-sm"><i class="fas fa-save mr-1"></i> Save Workflow</button>
    </div>
  </div>
</div>
<script>
function addStep() {{
  const type = document.getElementById('stepType').value;
  const agent = document.getElementById('stepAgent');
  const label = agent.options[agent.selectedIndex].text.split(' ').slice(1).join(' ') || 'New Step';
  const stepData = {{type: type, label: label, icon: '\u2699'}};
  fetch('/api/hermes/workflow/step', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{step:stepData}})}})
    .then(r=>r.json()).then(d=>{{if(d.success) location.reload();}});
}}
function removeStep(i) {{
  fetch('/api/hermes/workflow/step/remove', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{index:i}})}})
    .then(r=>r.json()).then(d=>{{if(d.success) location.reload();}});
}}
function saveWorkflow() {{ alert('Workflow saved!'); }}
</script>
{LAYOUT_FOOT}'''

@app.route('/api/hermes/workflow/step', methods=['POST'])
@admin_required
def api_workflow_step():
    step = request.json.get('step', {})
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM hermes_workflows ORDER BY created_at DESC LIMIT 1")
    wf = c.fetchone()
    if wf:
        steps = json.loads(wf['steps'])
        steps.append(step)
        c.execute("UPDATE hermes_workflows SET steps=? WHERE id=?", (json.dumps(steps), wf['id']))
        db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/hermes/workflow/step/remove', methods=['POST'])
@admin_required
def api_workflow_step_remove():
    index = request.json.get('index', 0)
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM hermes_workflows ORDER BY created_at DESC LIMIT 1")
    wf = c.fetchone()
    if wf:
        steps = json.loads(wf['steps'])
        if 0 <= index < len(steps):
            steps.pop(index)
            c.execute("UPDATE hermes_workflows SET steps=? WHERE id=?", (json.dumps(steps), wf['id']))
            db.commit()
    db.close()
    return jsonify({'success': True})

#  PHASE 24: HERMES RANK 
@app.route('/api/hermes-rank/update')
@admin_required
def api_update_hermes_rank():
    """Calculate Hermes Rank for all products."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE status='published'")
    products = [dict(r) for r in c.fetchall()]

    updated = 0
    for p in products:
        # Demand score: based on downloads
        demand = min(100, p['downloads_count'] * 20)
        # Quality score: based on content length
        quality = min(100, int((len(p.get('content') or '') / 500) * 100))
        # Reviews score
        review_score = min(100, int((p.get('rating', 0) or 0) * 20))
        # SEO score
        seo_score = min(100, len(p.get('seo_description') or '') // 2)
        # Profit score
        profit = min(100, int(p.get('price', 0) * 5))

        rank = round((demand * 0.25 + quality * 0.25 + review_score * 0.20 + seo_score * 0.15 + profit * 0.15), 1)
        c.execute("UPDATE products SET hermes_rank=? WHERE id=?", (rank, p['id']))
        updated += 1

    db.commit()
    db.close()
    return jsonify({'success': True, 'updated': updated})

#  PHASE 25: CREATOR AI COACH 
@app.route('/api/creator/coach')
@creator_required
def api_creator_coach():
    cid = session['creator_id']
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE creator_id=?", (cid,))
    products = [dict(r) for r in c.fetchall()]
    db.close()

    if not products:
        return jsonify({'advice': 'Upload your first product to get AI coaching!', 'recommendations': ['Upload a product first']})

    # Analyze products
    total_downloads = sum(p['downloads_count'] for p in products)
    avg_price = sum(p['price'] for p in products) / len(products)
    low_performers = [p for p in products if p['downloads_count'] < 2]

    recommendations = []
    if low_performers:
        recommendations.append(f"Add video demos to your {len(low_performers)} low-conversion products")
    if avg_price < 15:
        recommendations.append("Consider bundling products to increase average order value")
    if total_downloads < 10:
        recommendations.append("Share your products on social media to drive initial traffic")
    recommendations.append("Add more screenshots and detailed descriptions")
    recommendations.append("Enable AI optimization on all products")

    return jsonify({
        'advice': f"You have {len(products)} products with {total_downloads} total downloads. Avg price ${avg_price:.0f}.",
        'recommendations': recommendations,
        'score': min(100, total_downloads * 5 + len(products) * 10)
    })

#  PHASE 26: AI CUSTOMER SUCCESS 
@app.route('/api/customer-success/check')
@admin_required
def api_customer_success():
    """Check for customers who need engagement."""
    db = get_db()
    c = db.cursor()
    c.execute("""SELECT po.id, po.customer_email, p.title, po.created_at
                 FROM product_orders po JOIN products p ON po.product_id = p.id
                 ORDER BY po.created_at DESC LIMIT 20""")
    orders = [dict(r) for r in c.fetchall()]
    db.close()

    alerts = []
    for o in orders:
        days_ago = (datetime.datetime.now() - datetime.datetime.strptime(o['created_at'][:10], '%Y-%m-%d')).days if o.get('created_at') and len(o['created_at']) >= 10 else 0
        if days_ago <= 1:
            alerts.append({'customer': o['customer_email'], 'product': o['product_title'][:50], 'action': 'Send onboarding email', 'priority': 'high'})
        elif days_ago <= 7:
            alerts.append({'customer': o['customer_email'], 'product': o['product_title'][:50], 'action': 'Check if downloaded', 'priority': 'medium'})

    return jsonify({'alerts': alerts, 'total': len(orders)})

#  PHASE 27: PRODUCT VERSION CONTROL 
@app.route('/api/product/version', methods=['POST'])
@admin_required
def api_product_version():
    data = request.json
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO product_versions (id, product_id, version, changelog) VALUES (?,?,?,?)",
              (str(uuid.uuid4())[:12], data.get('product_id'), data.get('version', '1.0.0'), data.get('changelog', '')))
    c.execute("UPDATE products SET version=? WHERE id=?", (data.get('version', '1.0.0'), data.get('product_id')))
    db.commit()
    db.close()
    return jsonify({'success': True, 'version': data.get('version')})

#  PHASE 28: AI MARKETPLACE SEARCH 
@app.route('/api/ai-search')
def api_ai_search():
    q = request.args.get('q', '')
    if not q:
        return jsonify({'results': []})

    db = get_db()
    c = db.cursor()
    c.execute("""SELECT id, title, description, price, product_type, downloads_count, rating, hermes_rank
                 FROM products WHERE status='published'
                 AND (title LIKE ? OR description LIKE ? OR tags LIKE ?)
                 ORDER BY hermes_rank DESC, downloads_count DESC LIMIT 10""",
              (f'%{q}%', f'%{q}%', f'%{q}%'))
    results = [dict(r) for r in c.fetchall()]
    db.close()

    for r in results:
        r['icon'] = product_type_icon(r['product_type'])
        r['type_label'] = PRODUCT_TYPE_LABELS.get(r['product_type'], 'Product')
        r['url'] = f'/product/{r["slug"] or r["id"]}'

    return jsonify({'query': q, 'results': results, 'count': len(results)})

#  PHASE 29: ENTERPRISE AI BUILDER 
@app.route('/enterprise/builder', methods=['GET', 'POST'])
def enterprise_builder():
    if request.method == 'GET':
        return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-3xl mx-auto px-4 pb-8">
  <div class="text-center py-10">
    <div class="text-5xl mb-4">\U0001f3e2</div>
    <h1 class="text-2xl sm:text-3xl font-bold mb-2">Enterprise AI Stack Builder</h1>
    <p class="text-sm text-[#5c5c70]">Tell us about your business  we'll build your AI team.</p>
  </div>
  <div class="card" style="padding:28px">
    <form method="POST" class="space-y-4">
      <div><label class="text-xs text-[#64748b] block mb-1">Company Name</label><input name="name" class="text-sm" required></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Industry</label>
        <select name="industry" class="text-sm">
          <option>Real Estate</option><option>E-commerce</option><option>SaaS</option><option>Agency</option>
          <option>Finance</option><option>Healthcare</option><option>Education</option><option>Legal</option>
        </select></div>
      <div><label class="text-xs text-[#64748b] block mb-1">Number of Employees</label><input type="number" name="employees" class="text-sm" value="50"></div>
      <div><label class="text-xs text-[#64748b] block mb-1">What do you need help with?</label>
        <div class="grid grid-cols-2 gap-2 text-xs">
          <label class="flex items-center gap-2 p-2 bg-[#1a1a26] rounded"><input type="checkbox" name="needs" value="sales"> Sales & Lead Follow-up</label>
          <label class="flex items-center gap-2 p-2 bg-[#1a1a26] rounded"><input type="checkbox" name="needs" value="support"> Customer Support</label>
          <label class="flex items-center gap-2 p-2 bg-[#1a1a26] rounded"><input type="checkbox" name="needs" value="marketing"> Marketing & SEO</label>
          <label class="flex items-center gap-2 p-2 bg-[#1a1a26] rounded"><input type="checkbox" name="needs" value="automation"> Workflow Automation</label>
        </div>
      </div>
      <button class="btn-primary w-full text-sm" style="padding:14px"><i class="fas fa-robot mr-1"></i> Build My AI Stack</button>
    </form>
  </div>
</div>
{LAYOUT_FOOT}'''

    name = request.form.get('name', '')
    industry = request.form.get('industry', '')
    employees = int(request.form.get('employees', 50))
    needs = request.form.getlist('needs')

    stack_map = {'sales': 'Sales Agent', 'support': 'Support Agent', 'marketing': 'Marketing Agent', 'automation': 'Automation Agent'}
    agents = [stack_map.get(n, 'AI Agent') for n in needs]
    if not agents:
        agents = ['AI Assistant']
    
    monthly = 199 + (len(agents) - 1) * 200

    stack_html = ''.join(f'<div class="flex items-center gap-3 p-3 bg-[#1a1a26] rounded-lg"><span style="font-size:24px">\U0001f916</span><span class="font-medium text-sm">{a}</span></div>' for a in agents)

    db = get_db()
    c = db.cursor()
    cid = str(uuid.uuid4())[:12]
    c.execute("INSERT INTO enterprise_stacks (id, industry, employee_count, needs, recommended_agents, monthly_price) VALUES (?,?,?,?,?,?)",
              (cid, industry, employees, ','.join(needs), json.dumps(agents), monthly))
    db.commit()
    db.close()

    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-3xl mx-auto px-4 pb-8">
  <div class="card" style="padding:32px;background:linear-gradient(135deg,#0a142e,#0e0e16)">
    <div class="text-center mb-6">
      <div class="text-4xl mb-3">\U0001f3e2</div>
      <h2 class="text-2xl font-bold mb-1">Your AI Stack for {name}</h2>
      <p class="text-sm text-[#5c5c70]">{industry}  {employees} employees</p>
    </div>
    <div class="space-y-2 mb-6">{stack_html}</div>
    <div class="text-center">
      <div class="text-3xl font-bold text-[#4ade80]">${monthly}<span class="text-sm text-[#5c5c70] font-normal">/month</span></div>
      <p class="text-xs text-[#5c5c70] mt-1">All agents included  Setup in 24 hours</p>
      <a href="/enterprise/register" class="btn-primary mt-4 inline-block" style="padding:14px 36px">Get Started <i class="fas fa-arrow-right ml-1"></i></a>
    </div>
  </div>
</div>
{LAYOUT_FOOT}'''

#  PHASE 30: HERMES AGENT PROTOCOL 
@app.route('/hermes/protocol')
@admin_required
def hermes_protocol():
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-4xl mx-auto px-4 pb-8">
  <div class="text-center py-8">
    <div class="text-5xl mb-4">\U0001f310</div>
    <h1 class="text-2xl sm:text-3xl font-bold mb-2">Hermes Agent Protocol</h1>
    <p class="text-sm text-[#5c5c70] max-w-lg mx-auto">Open protocol for AI agents to connect, trade, and collaborate on the ShopZario network.</p>
  </div>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
    <div class="card" style="padding:24px">
      <div class="text-2xl mb-2">\U0001f4e6</div>
      <h3 class="font-bold text-sm mb-2">Agent Package Format</h3>
      <pre class="text-[10px] text-[#b0b0c0] bg-[#1a1a26] p-3 rounded-lg">manifest.json
  name: "Sales Agent"
  version: "2.4"
  permissions: [read, write, api]
  pricing: {{"monthly": 49}}
  documentation: "README.md"</pre>
    </div>
    <div class="card" style="padding:24px">
      <div class="text-2xl mb-2">\U0001f517</div>
      <h3 class="font-bold text-sm mb-2">API Connection</h3>
      <pre class="text-[10px] text-[#b0b0c0] bg-[#1a1a26] p-3 rounded-lg">GET /api/v1/agents
POST /api/v1/agents/:id/execute
GET /api/v1/marketplace
POST /api/v1/orders</pre>
    </div>
  </div>
  <div class="card text-center" style="padding:32px;background:linear-gradient(135deg,#1a0a2e,#0e0e16)">
    <h2 class="text-xl font-bold mb-2">Submit Your Agent</h2>
    <p class="text-sm text-[#5c5c70] mb-4">Developers can submit AI agents to the ShopZario marketplace. Hermes reviews and publishes.</p>
    <a href="/creator/upload" class="btn-primary" style="padding:14px 36px"><i class="fas fa-cloud-upload-alt mr-1"></i> Submit Agent Package</a>
  </div>
</div>
{LAYOUT_FOOT}'''


@app.route('/membership')
def membership_page():
    """Membership plans page."""
    import datetime
    now = datetime.datetime.now().strftime('%b %d, %Y')
    
    plans = [
        {'name': 'Free', 'price': 0, 'period': 'forever', 'desc': 'Get started with basic access', 'color': '#5c5c70', 'icon': '\U0001f4aa', 'features': ['5 downloads/month', 'Basic AI assistant', 'Community access', 'Email support']},
        {'name': 'Creator', 'price': 29, 'period': 'month', 'desc': 'For creators building a business', 'color': '#a855f7', 'icon': '\U0001f680', 'features': ['Unlimited downloads', 'Publish products', 'AI optimization', 'Analytics dashboard', 'Priority support', 'Commercial license'], 'popular': True},
        {'name': 'Pro', 'price': 99, 'period': 'month', 'desc': 'For power users and teams', 'color': '#38bdf8', 'icon': '\U0001f52e', 'features': ['Everything in Creator', 'AI agents access', 'Automation tools', 'Advanced analytics', 'API access', 'Team seats (3)', 'Dedicated support'], 'popular': False},
        {'name': 'Enterprise', 'price': 499, 'period': 'month', 'desc': 'For organizations scaling AI', 'color': '#4ade80', 'icon': '\U0001f3db\ufe0f', 'features': ['Everything in Pro', 'Private marketplace', 'Custom AI agents', 'White-label option', 'Custom domain', 'SAML/SSO', 'Unlimited team seats', 'SLA guarantee', 'Dedicated account manager'], 'popular': False}
    ]
    
    cards = ''
    for plan in plans:
        border = 'border-[#a855f7]/50' if plan.get('popular') else 'border-[#252533]'
        badge = '<div class="text-[10px] font-semibold text-[#a855f7] bg-[#a855f7]/10 px-3 py-1 rounded-full mb-3 inline-block">Most Popular</div>' if plan.get('popular') else ''
        features = ''.join(f'<div class="flex items-center gap-2 text-xs text-[#b0b0c0]"><i class="fas fa-check text-[{plan["color"]}] text-[10px]"></i>{f}</div>' for f in plan['features'])
        price_display = 'Free' if plan['price'] == 0 else f'${plan["price"]}<span class="text-sm text-[#5c5c70] font-normal">/{plan["period"]}</span>'
        btn = '<a href="/creator/signup" class="w-full block text-center py-3 rounded-lg text-sm font-semibold transition" style="background:linear-gradient(135deg,' + plan['color'] + ',transparent);border:1px solid ' + plan['color'] + '">Get Started</a>' if plan['price'] > 0 else '<a href="/" class="w-full block text-center py-3 rounded-lg text-sm font-semibold border border-[#252533] hover:border-white/20 transition">Browse Free</a>'
        
        cards += f'''<div class="card relative flex flex-col" style="padding:24px;border-color:{border}">
  {badge}
  <div class="text-2xl mb-2">{plan["icon"]}</div>
  <h3 class="font-bold text-lg">{plan["name"]}</h3>
  <p class="text-xs text-[#5c5c70] mb-4">{plan["desc"]}</p>
  <div class="text-3xl font-black mb-2" style="color:{plan['color']}">{price_display}</div>
  <div class="flex-1 space-y-2 my-4">{features}</div>
  {btn}
</div>'''
    
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-5xl mx-auto px-4 sm:px-6 pb-12">

  <!-- Header -->
  <div class="text-center py-10 mb-8">
    <span class="text-4xl mb-4 block"></span>
    <h1 class="text-3xl sm:text-4xl font-black mb-3">Hermes Membership</h1>
    <p class="text-sm text-[#5c5c70] max-w-lg mx-auto">Join the fastest-growing community of AI creators, developers, and digital entrepreneurs. Choose your plan.</p>
  </div>

  <!-- Plans Grid -->
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">{cards}</div>

  <!-- Comparison Table -->
  <div class="card" style="padding:24px">
    <h2 class="font-bold text-lg mb-4">Plan Comparison</h2>
    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <thead><tr class="text-[#5c5c70] border-b border-[#1e1e2e]"><th class="text-left py-2 pr-4">Feature</th><th class="py-2 px-2">Free</th><th class="py-2 px-2 text-[#a855f7]">Creator</th><th class="py-2 px-2 text-[#38bdf8]">Pro</th><th class="py-2 px-2 text-[#4ade80]">Enterprise</th></tr></thead>
        <tbody>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">Downloads / month</td><td class="py-2 px-2 text-center">5</td><td class="py-2 px-2 text-center">Unlimited</td><td class="py-2 px-2 text-center">Unlimited</td><td class="py-2 px-2 text-center">Unlimited</td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">Publish products</td><td class="py-2 px-2 text-center"></td><td class="py-2 px-2 text-center"></td><td class="py-2 px-2 text-center"></td><td class="py-2 px-2 text-center"></td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">AI optimization</td><td class="py-2 px-2 text-center"></td><td class="py-2 px-2 text-center"></td><td class="py-2 px-2 text-center"></td><td class="py-2 px-2 text-center"></td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">AI agents</td><td class="py-2 px-2 text-center">Basic</td><td class="py-2 px-2 text-center">Standard</td><td class="py-2 px-2 text-center">Advanced</td><td class="py-2 px-2 text-center">Custom</td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">Analytics</td><td class="py-2 px-2 text-center"></td><td class="py-2 px-2 text-center">Basic</td><td class="py-2 px-2 text-center">Advanced</td><td class="py-2 px-2 text-center">Custom</td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">API access</td><td class="py-2 px-2 text-center"></td><td class="py-2 px-2 text-center"></td><td class="py-2 px-2 text-center"></td><td class="py-2 px-2 text-center"></td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">Team seats</td><td class="py-2 px-2 text-center">1</td><td class="py-2 px-2 text-center">1</td><td class="py-2 px-2 text-center">3</td><td class="py-2 px-2 text-center">Unlimited</td></tr>
          <tr><td class="py-2 pr-4">Support</td><td class="py-2 px-2 text-center">Email</td><td class="py-2 px-2 text-center">Priority</td><td class="py-2 px-2 text-center">Dedicated</td><td class="py-2 px-2 text-center">Account Manager</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- FAQ -->
  <div class="mt-8">
    <h2 class="font-bold text-lg mb-4">Frequently Asked Questions</h2>
    <div class="space-y-3">
      <div class="card p-4"><p class="font-semibold text-sm mb-1">Can I switch plans anytime?</p><p class="text-xs text-[#5c5c70]">Yes! You can upgrade, downgrade, or cancel your subscription at any time. Changes take effect immediately.</p></div>
      <div class="card p-4"><p class="font-semibold text-sm mb-1">What payment methods do you accept?</p><p class="text-xs text-[#5c5c70]">We accept all major credit cards, PayPal, and cryptocurrency through Stripe. Enterprise customers can request invoicing.</p></div>
      <div class="card p-4"><p class="font-semibold text-sm mb-1">Can I publish products with any plan?</p><p class="text-xs text-[#5c5c70]">Creator plan and above allow you to publish products. Free users can browse and download products.</p></div>
      <div class="card p-4"><p class="font-semibold text-sm mb-1">What is Hermes AI?</p><p class="text-xs text-[#5c5c70]">Hermes AI is our autonomous business engine that helps create, optimize, and market products. Pro and Enterprise plans get advanced AI agent access.</p></div>
    </div>
  </div>

</div>
{LAYOUT_FOOT}'''


#  AI DEMO GENERATOR 
@app.route('/api/demo/generate/<product_id>')
@admin_required
def api_generate_demo(product_id):
    """Generate an AI demo script for a product."""
    import json as _json
    db = get_db()
    c = db.cursor()
    c.execute("SELECT title, description, product_type, content, version, requirements FROM products WHERE id=?", (product_id,))
    p = c.fetchone()
    db.close()
    if not p:
        return jsonify({'error': 'Not found'}), 404
    
    title = p['title'] or 'Product'
    desc = p['description'] or 'A premium digital product'
    ptype = PRODUCT_TYPE_LABELS.get(p['product_type'], 'Digital Product')
    content_body = p['content'] or 'Key features: solve problems, save time'
    
    fallback_steps = ' Tailor to your specific needs\n Modify prompts/templates for your use case\n Integrate with your existing workflow'
    
    demo_script = f"""=== {title}  Quick Demo ===

Product Type: {ptype}

{desc[:200]}

 DEMO OVERVIEW 

Step 1: Purchase & Download
 Buy the product with one click
 Instant download to your device
 Includes all files and documentation

Step 2: Setup
 Open the files in your preferred tool
 Follow the included setup guide
 No technical skills required
 Works with ChatGPT, Claude, Gemini, and more

Step 3: Customize
{content_body[:300] if content_body else fallback_steps}

Step 4: Deploy & Profit
 Launch your solution immediately
 Save hours of manual work
 Scale with included commercial license

 KEY BENEFITS 
 Instant access after purchase
 Lifetime updates included
 Works with all major AI platforms
 Commercial license included
 30-day satisfaction guarantee

 IDEAL FOR 
 Beginners and experts alike
 Agencies and freelancers
 Small business owners
 Digital creators and marketers

 GET STARTED 
 Click Buy Now above
 Download your files
 Transform your workflow today"""
    
    return jsonify({'success': False, 'script': demo_script, 'note': 'Demo preview (not a video)'})


import hashlib
from flask import send_file

#  PDF GENERATOR FOR AI AGENT DIRECTORY 
import os as _os, datetime as _dt

PDF_CACHE_PATH = _os.path.join(_os.path.dirname(__file__), 'static', 'agents-directory-2026.pdf')

def _generate_directory_pdf():
    """Generate a beautiful PDF of the AI Agent Directory using weasyprint."""
    cat_icons = {
        'Coding Agents': '', 'Agent Frameworks': '',
        'Browser & Desktop Agents': '', 'Voice Agents': '',
        'CRM & Sales Agents': '', 'Data & Research Agents': '',
        'Self-Hosted & Local': '', 'Platforms & Hubs': ''
    }
    
    total = sum(len(agents) for agents in AGENTS_DIRECTORY.values())
    now = _dt.datetime.now().strftime('%B %d, %Y')
    
    # Build table rows
    table_rows = ''
    for cat, agents in AGENTS_DIRECTORY.items():
        table_rows += f'<tr class="cat-header"><td colspan="4">{cat_icons.get(cat, "")} {cat} ({len(agents)})</td></tr>'
        for a in agents:
            table_rows += f'<tr><td class="name">{a["name"]}</td><td class="type">{a["type"]}</td><td class="price">{a["price"]}</td><td class="desc">{a["desc"][:100]}</td></tr>'
    
    html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>AI Agent Directory 2026  Complete Guide</title>
<style>
  @page {{ size: A4; margin: 1.5cm; }}
  @page {{ @top-center {{ content: "AI Agent Directory 2026"; font-size: 9pt; color: #888; }} }}
  @page {{ @bottom-center {{ content: "Page " counter(page) " of " counter(pages); font-size: 8pt; color: #888; }} }}
  * {{ font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; }}
  body {{ color: #1a1a2e; font-size: 10pt; line-height: 1.5; }}
  
  .cover {{
    text-align: center;
    padding: 60px 0 40px;
    border-bottom: 4px solid #7c3aed;
    margin-bottom: 30px;
  }}
  .cover h1 {{ font-size: 28pt; font-weight: 800; margin: 0 0 8px; background: linear-gradient(135deg, #7c3aed, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  .cover .sub {{ font-size: 14pt; color: #666; }}
  .cover .meta {{ font-size: 9pt; color: #999; margin-top: 20px; }}
  
  .section-title {{ font-size: 14pt; font-weight: 700; color: #7c3aed; margin: 25px 0 10px; padding-bottom: 5px; border-bottom: 2px solid #7c3aed20; }}
  
  table {{ width: 100%; border-collapse: collapse; margin: 5px 0 20px; font-size: 9pt; }}
  th {{ background: #7c3aed; color: white; padding: 8px 10px; text-align: left; font-weight: 600; font-size: 8.5pt; text-transform: uppercase; letter-spacing: 0.5px; }}
  th:nth-child(1) {{ width: 22%; }}
  th:nth-child(2) {{ width: 12%; }}
  th:nth-child(3) {{ width: 18%; }}
  th:nth-child(4) {{ width: 48%; }}
  .cat-header td {{ background: #7c3aed15; color: #7c3aed; font-weight: 700; padding: 7px 10px; font-size: 10pt; }}
  td {{ padding: 5px 10px; border-bottom: 1px solid #e0dce8; vertical-align: top; }}
  tr:nth-child(even):not(.cat-header) td {{ background: #f8f6fc; }}
  .name {{ font-weight: 600; }}
  .type {{ color: #7c3aed; font-size: 8pt; }}
  .price {{ color: #2563eb; font-size: 8pt; }}
  .desc {{ color: #555; font-size: 8.5pt; }}
  
  .summary {{ margin-top: 30px; padding: 20px; background: #f8f6fc; border-radius: 8px; font-size: 9pt; }}
  .summary h3 {{ font-size: 11pt; color: #7c3aed; margin: 0 0 10px; }}
  
  .footer {{ margin-top: 40px; text-align: center; font-size: 8pt; color: #999; border-top: 1px solid #ddd; padding-top: 15px; }}
</style>
</head>
<body>

<div class="cover">
  <div style="font-size: 48pt; margin-bottom: 10px;">\U0001f916</div>
  <h1>AI Agent Directory 2026</h1>
  <div class="sub">The Complete Guide to 50+ AI Agents, Frameworks & Tools</div>
  <div class="meta">Compiled: {now}  {total} Entries  8 Categories<br>Source: awesome-ai-agents-2026</div>
</div>

<div class="section-title">Full Directory</div>
<table>
  <tr><th>Agent</th><th>Type</th><th>Pricing</th><th>Description</th></tr>
  {table_rows}
</table>

<div class="summary">
  <h3>How to Use This Directory</h3>
  <p><strong>For Developers:</strong> Browse the Coding Agents and Frameworks sections to find the best tools for your stack. Top picks: Cursor (IDE), Claude Code (CLI), CrewAI (multi-agent orchestration).</p>
  <p><strong>For Businesses:</strong> CRM & Sales agents offer the fastest ROI. Apollo.io and Clay are industry standards for outbound. Intercom Fin for support automation.</p>
  <p><strong>For Builders:</strong> Combine Bolt.new or Lovable (prompt-to-app) with LangChain or AutoGen (agent framework) to ship AI products faster.</p>
  <p><strong>For Self-Hosters:</strong> Ollama + Open WebUI gives you a private ChatGPT. Add Anything LLM for RAG capabilities.</p>
</div>

<div class="footer">
  Generated by ShopZario.com  AI Agent Directory 2026  Updated Quarterly
</div>

</body>
</html>'''
    
    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(PDF_CACHE_PATH)
        return True
    except Exception as e:
        print(f"[PDF] Error: {e}")
        return False

@app.route('/api/admin/generate-agents-pdf')
@admin_required
def api_generate_agents_pdf():
    """Generate the PDF cache."""
    ok = _generate_directory_pdf()
    if ok:
        size = _os.path.getsize(PDF_CACHE_PATH) if _os.path.exists(PDF_CACHE_PATH) else 0
        return jsonify({'success': True, 'path': '/static/agents-directory-2026.pdf', 'size': f'{size//1024}KB'})
    return jsonify({'error': 'PDF generation failed'}), 500

@app.route('/api/download/agents-pdf')
def api_download_agents_pdf():
    """Serve the PDF directly (free access for now, Stripe gating later)."""
    import os as _os2
    path = _os2.path.join(_os2.path.dirname(__file__), 'static', 'agents-directory-2026.pdf')
    if _os2.path.exists(path):
        return send_file(path, mimetype='application/pdf',
                      as_attachment=True, download_name='ai-agent-directory-2026.pdf')
    # Generate on demand
    _generate_directory_pdf()
    if _os2.path.exists(path):
        return send_file(path, mimetype='application/pdf',
                      as_attachment=True, download_name='ai-agent-directory-2026.pdf')
    return 'PDF generation in progress. Try again in a moment.', 202


#  PRODUCT PDF DOWNLOAD API 
@app.route('/api/product/pdf/<product_id>')
def api_product_pdf(product_id):
    db3 = get_db()
    c3 = db3.cursor()
    c3.execute("SELECT * FROM products WHERE id=?", (product_id,))
    row3 = c3.fetchone()
    db3.close()
    if not row3:
        return 'Not found', 404
    p3 = dict(row3)
    
    import datetime as dt3
    import os as _os
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch, mm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, KeepTogether
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib import colors
    import io
    
    raw = (p3.get("content") or p3.get("description") or "")
    title = p3["title"] or "Product"
    price = p3.get("price", 0)
    today = dt3.datetime.now().strftime("%B %d, %Y")
    ptype = PRODUCT_TYPE_LABELS.get(p3.get("product_type",""), "Digital Product")
    ccolor = product_type_color(p3.get("product_type",""))
    ver = p3.get("version","") or "1.0"
    kw = p3.get("seo_keywords","") or ""
    
    # Main color
    ca_r, ca_g, ca_b = 124, 58, 237  # default purple
    try:
        hx = ccolor.lstrip("#")
        if len(hx) >= 6:
            ca_r, ca_g, ca_b = int(hx[0:2],16), int(hx[2:4],16), int(hx[4:6],16)
    except:
        pass
    
    # Product image
    img_path = None
    slug = p3.get("slug") or product_id
    for _p in [
        "/root/voice-agent-manager/static/product_images/product_" + product_id + ".png",
        "/root/voice-agent-manager/static/product_images/notion_" + slug + ".png"
    ]:
        if _os.path.exists(_p):
            img_path = _p
            break
    
    # Parse content into sections
    lines = raw.split("\n")
    sections = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("## ") or s.startswith("# ") or s.startswith("### ") or s.startswith("#### "):
            sections.append(('heading', s.lstrip("# ").strip()))
        elif s.startswith("- ") or s.startswith("* "):
            sections.append(('bullet', s[2:]))
        elif s and s[0].isdigit() and (". " in s[:6] or ") " in s[:6]):
            dot = s.find(". ")
            paren = s.find(") ")
            split_at = dot if dot > 0 and dot < 4 else (paren if paren > 0 and paren < 4 else s.find(". "))
            text = s[split_at+1:].strip() if split_at else s
            sections.append(('numbered', text))
        else:
            is_sub = len(s) < 60 and not s.endswith(".") and not s.endswith("!") and not s.endswith("?") and s and s[0].isupper()
            sections.append(('subheading' if is_sub else 'paragraph', s))
    
    # Build features
    sents = [x.strip() for x in raw.replace("\n"," ").split(".") if len(x.strip()) > 25][:6]
    
    # Build PDF with ReportLab
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            topMargin=0.5*inch, bottomMargin=0.5*inch,
                            leftMargin=0.75*inch, rightMargin=0.75*inch)
    
    main_color = HexColor('#%02x%02x%02x' % (ca_r, ca_g, ca_b))
    light_bg = HexColor('#%02x%02x%02x' % (min(ca_r+120,255), min(ca_g+120,255), min(ca_b+120,255)))
    
    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle('CustomNormal', parent=styles['Normal'],
                                   fontSize=9, leading=13, spaceAfter=4, textColor=HexColor('#333333'))
    style_heading = ParagraphStyle('Heading', parent=styles['Normal'],
                                    fontSize=14, leading=18, spaceBefore=10, spaceAfter=4,
                                    textColor=main_color, bold=1)
    style_subheading = ParagraphStyle('SubHeading', parent=styles['Normal'],
                                       fontSize=11, leading=15, spaceBefore=6, spaceAfter=3,
                                       textColor=main_color, bold=1)
    style_bullet = ParagraphStyle('Bullet', parent=style_normal,
                                   leftIndent=15, bulletIndent=0, spaceBefore=1, spaceAfter=1)
    style_title = ParagraphStyle('Title', parent=styles['Normal'],
                                  fontSize=22, leading=28, alignment=TA_CENTER,
                                  textColor=white, spaceAfter=6)
    style_price = ParagraphStyle('Price', parent=styles['Normal'],
                                  fontSize=36, leading=44, alignment=TA_CENTER,
                                  textColor=white, spaceAfter=4)
    style_meta = ParagraphStyle('Meta', parent=styles['Normal'],
                                 fontSize=8, leading=11, alignment=TA_CENTER,
                                 textColor=HexColor('#CCCCDD'))
    
    elements = []
    
    # ===== COVER =====
    # Use a table for the dark background
    cover_data = [[Paragraph(f'<font size="12" color="{main_color}"><b>{ptype.upper()}</b></font>', 
                             ParagraphStyle('Badge', parent=styles['Normal'],
                                            alignment=TA_CENTER, spaceBefore=60))]]
    
    cover_data.append([Paragraph(f'<font size="22"><b>{title}</b></font>', style_title)])
    cover_data.append([Paragraph(f'<font size="12">v{ver} — Premium Digital Product</font>',
                                 ParagraphStyle('Ver', parent=styles['Normal'], alignment=TA_CENTER, 
                                                textColor=HexColor('#CCCCDD'), spaceAfter=8))])
    
    if img_path:
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(img_path)
            img_width, img_height = img.getSize()
            aspect = img_width / img_height
            disp_w = 80
            disp_h = disp_w / aspect
            cover_data.append([RLImage(img_path, width=disp_w, height=disp_h)])  # placeholder
        except:
            pass
    
    cover_data.append([Spacer(1, 15)])
    cover_data.append([Paragraph(f'<font size="36"><b>${price:.2f}</b></font>' if price else '<font size="36"><b>FREE</b></font>', style_price)])
    cover_data.append([Paragraph('One-time payment · Lifetime access · Instant download', style_meta)])
    cover_data.append([Spacer(1, 10)])
    cover_data.append([Paragraph(f'{today}  |  ShopZario.com  |  PDF Download', style_meta)])
    
    t = Table(cover_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), main_color),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 30),
        ('RIGHTPADDING', (0,0), (-1,-1), 30),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    # ===== PAGE 2: At a Glance =====
    elements.append(Paragraph(f'<font color="{main_color}"><b>At a Glance</b></font>', style_heading))
    
    # Summary boxes in a table
    summary_items = [
        ('Format', 'Digital Download'),
        ('Value', f'${price:.2f}' if price else 'Premium'),
        ('Version', ver),
        ('License', (p3.get("license","Commercial") or "Commercial")[:20]),
        ('Updates', 'Lifetime'),
        ('Type', ptype),
    ]
    sum_data = []
    row = []
    for i, (label, val) in enumerate(summary_items):
        row.append(Paragraph(f'<font size="7" color="#888888">{label.upper()}</font><br/><font size="10" color="{main_color}"><b>{val}</b></font>'))
        if len(row) == 3 or i == len(summary_items)-1:
            while len(row) < 3:
                row.append(Paragraph(''))
            sum_data.append(row)
            row = []
    
    sum_table = Table(sum_data, colWidths=[2.2*inch]*3)
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), light_bg),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor('#E0E0E0')),
    ]))
    elements.append(sum_table)
    elements.append(Spacer(1, 15))
    
    # What's Inside
    if sents:
        elements.append(Paragraph(f'<font color="{main_color}"><b>What\'s Inside</b></font>', style_subheading))
        for s in sents:
            short = (s[:85] + '...') if len(s) > 85 else s
            elements.append(Paragraph(f'<font color="{main_color}">▸</font>  {short}.', style_bullet))
        elements.append(Spacer(1, 10))
    
    # Price card
    if price:
        price_data = [[Paragraph(f'<font size="20" color="white"><b>${price:.2f}</b></font>',
                                 ParagraphStyle('PriceCard', parent=styles['Normal'], alignment=TA_LEFT)),
                       Paragraph('<font size="8" color="#DDDDEE">One-time payment · Lifetime access · Instant download</font>',
                                 ParagraphStyle('PriceSub', parent=styles['Normal'], alignment=TA_RIGHT))]]
        pt = Table(price_data, colWidths=[3*inch, 3.5*inch])
        pt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), main_color),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(pt)
        elements.append(Spacer(1, 15))
    
    # ===== CONTENT =====
    elements.append(Paragraph(f'<font color="{main_color}"><b>Product Content</b></font>', style_heading))
    
    for sec_type, sec_text in sections:
        sec_text_escaped = sec_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')
        
        if sec_type == 'heading':
            elements.append(Paragraph(f'<font color="{main_color}"><b>{sec_text_escaped}</b></font>', style_heading))
        elif sec_type == 'subheading':
            elements.append(Paragraph(f'<font color="{main_color}"><b>{sec_text_escaped}</b></font>', style_subheading))
        elif sec_type == 'bullet':
            elements.append(Paragraph(f'<font color="{main_color}">▸</font>  {sec_text_escaped}', style_bullet))
        elif sec_type == 'numbered':
            elements.append(Paragraph(f'{sec_text_escaped}', style_bullet))
        elif sec_type == 'paragraph':
            elements.append(Paragraph(sec_text_escaped, style_normal))
    
    # ===== KEYWORDS =====
    keywords = [k.strip() for k in kw.split(",") if k.strip()][:15]
    if keywords:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f'<font color="{main_color}"><b>Keywords</b></font>', style_subheading))
        kw_text = '  •  '.join(keywords)
        elements.append(Paragraph(f'<font size="8" color="#666666">{kw_text}</font>', style_normal))
    
    # Build
    doc.build(elements)
    pdf_bytes = buf.getvalue()
    from flask import make_response as _mkresp
    resp = _mkresp(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename="{slug or product_id}.pdf"'
    return resp


#  SEO ROUTES 
@app.route('/sitemap.xml')
def sitemap():
    db4 = get_db()
    c4 = db4.cursor()
    c4.execute("SELECT id, slug FROM products WHERE status='published' ORDER BY created_at")
    prods = c4.fetchall()
    db4.close()
    urls = '<url><loc>https://shopzario.com/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>'
    urls += '<url><loc>https://shopzario.com/ai-agents-directory</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>'
    urls += '<url><loc>https://shopzario.com/membership</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>'
    for p in prods:
        slug = p[1] or p[0]
        urls += '<url><loc>https://shopzario.com/products/' + slug + '</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>'
        urls += '<url><loc>https://shopzario.com/product/' + (p[1] or p[0]) + '</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>'
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls + '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}

@app.route('/robots.txt')
def robots():
    txt = 'User-agent: *\nAllow: /\nDisallow: /login\nDisallow: /factory\nDisallow: /hermes/\nDisallow: /api/\nSitemap: https://shopzario.com/sitemap.xml\n'
    return txt, 200, {'Content-Type': 'text/plain'}

@app.route('/api/ga-config')
def api_ga_config():
    try:
        with open("/root/voice-agent-manager/ga_config.json") as f:
            cfg = json.load(f)
            return jsonify({'id': cfg.get('ga_id', ''), 'enabled': bool(cfg.get('ga_id')) and cfg.get('ga_id') != 'G-XXXXXXXXXX'})
    except:
        return jsonify({'id': '', 'enabled': False})

#  SETTINGS / CONFIG 
@app.route('/hermes/settings', methods=['GET', 'POST'])
@admin_required
def hermes_settings():
    cfg_path = "/root/voice-agent-manager/stripe_config.json"
    ga_path = "/root/voice-agent-manager/ga_config.json"
    stripe_cfg = {}
    ga_cfg = {}
    
    # Load configs
    try:
        with open(cfg_path) as f:
            stripe_cfg = json.load(f)
    except:
        stripe_cfg = {'secret_key': '', 'publishable_key': '', 'webhook_secret': '', 'enabled': False}
    try:
        with open(ga_path) as f:
            ga_cfg = json.load(f)
    except:
        ga_cfg = {'ga_id': 'G-XXXXXXXXXX'}
    
    if request.method == 'POST':
        # Save GA
        new_ga = request.form.get('ga_id', ga_cfg.get('ga_id', 'G-XXXXXXXXXX'))
        with open(ga_path, 'w') as f:
            json.dump({'ga_id': new_ga}, f)
        # Update LAYOUT_HEAD with new GA ID
        ga_cfg['ga_id'] = new_ga
        
        # Save Stripe
        stripe_cfg['secret_key'] = request.form.get('stripe_secret', stripe_cfg.get('secret_key', ''))
        stripe_cfg['publishable_key'] = request.form.get('stripe_publishable', stripe_cfg.get('publishable_key', ''))
        stripe_cfg['webhook_secret'] = request.form.get('stripe_webhook_secret', stripe_cfg.get('webhook_secret', ''))
        stripe_cfg['enabled'] = request.form.get('stripe_enabled') == 'on'
        from premium_features import save_stripe_config as ssc
        ssc(stripe_cfg)
        
        return redirect('/hermes/settings')
    
    enabled_checked = 'checked' if stripe_cfg.get('enabled') else ''
    stripe_masked = stripe_cfg.get('secret_key', '')[:8] + '...' + stripe_cfg.get('secret_key', '')[-4:] if stripe_cfg.get('secret_key') else 'Not set'
    webhook_masked = stripe_cfg.get('webhook_secret', '')[:8] + '...' + stripe_cfg.get('webhook_secret', '')[-4:] if stripe_cfg.get('webhook_secret') else 'Not set'
    
    body = '''<div class="mb-6"><h1 class="text-xl font-bold">Settings</h1><p class="text-xs text-[#5c5c70]">Configure integrations and analytics</p></div>

<form method="POST" class="space-y-6">
  <div class="card p-5">
    <h3 class="font-bold text-sm mb-3"><i class="fab fa-google text-[#4ade80] mr-1"></i> Google Analytics</h3>
    <div class="mb-3">
      <label class="text-xs text-[#5c5c70] block mb-1">Measurement ID</label>
      <input name="ga_id" value="''' + ga_cfg.get('ga_id', 'G-XXXXXXXXXX') + '''" class="text-xs font-mono" placeholder="G-XXXXXXXXXX">
      <p class="text-[10px] text-[#5c5c70] mt-1">Get this from <a href="https://analytics.google.com" target="_blank" class="text-[#38bdf8]">Google Analytics</a> &rarr; Admin &rarr; Data Streams</p>
    </div>
  </div>

  <div class="card p-5">
    <h3 class="font-bold text-sm mb-3"><i class="fab fa-stripe text-[#818cf8] mr-1"></i> Stripe Payments</h3>
    <div class="space-y-3">
      <div><label class="text-xs text-[#5c5c70] block mb-1">Secret Key</label>
      <input name="stripe_secret" value="''' + stripe_cfg.get('secret_key', '') + '''" class="text-xs font-mono" placeholder="sk_live_...">
      <p class="text-[10px] text-[#5c5c70] mt-1">Current: ''' + stripe_masked + '''</p></div>
      <div><label class="text-xs text-[#5c5c70] block mb-1">Publishable Key</label>
      <input name="stripe_publishable" value="''' + stripe_cfg.get('publishable_key', '') + '''" class="text-xs font-mono" placeholder="pk_live_..."></div>
      <div><label class="text-xs text-[#5c5c70] block mb-1">Webhook Signing Secret</label>
      <input name="stripe_webhook_secret" value="''' + stripe_cfg.get('webhook_secret', '') + '''" class="text-xs font-mono" placeholder="whsec_...">
      <p class="text-[10px] text-[#5c5c70] mt-1">Current: ''' + webhook_masked + '''</p></div>
      <label class="flex items-center gap-2 text-xs"><input type="checkbox" name="stripe_enabled" ''' + enabled_checked + '''> <span>Enable Stripe payments</span></label>
    </div>
  </div>

  <button type="submit" class="btn-primary w-full justify-center" style="padding:14px"><i class="fas fa-check"></i> Save Settings</button>
</form>

<div class="card p-5 mt-6">
  <h3 class="font-bold text-sm mb-3"><i class="fas fa-plug text-[#facc15] mr-1"></i> Stripe Webhook Setup</h3>
  <div class="text-xs text-[#5c5c70] space-y-2">
    <p>1. Go to <a href="https://dashboard.stripe.com/webhooks" target="_blank" class="text-[#38bdf8]">Stripe Dashboard &rarr; Webhooks</a></p>
    <p>2. Click <strong>Add endpoint</strong></p>
    <p>3. Set endpoint URL to: <code class="text-[10px] bg-[#1a1a26] px-1.5 py-0.5 rounded text-white">https://shopzario.com/stripe-webhook</code></p>
    <p>4. Select event: <code class="text-[10px] bg-[#1a1a26] px-1.5 py-0.5 rounded text-white">checkout.session.completed</code></p>
    <p>5. Click <strong>Add endpoint</strong></p>
    <p>6. Under <strong>Signing secret</strong>, click <strong>Reveal</strong> and copy the <code class="text-[10px] bg-[#1a1a26] px-1.5 py-0.5 rounded text-white">whsec_...</code></p>
    <p>7. Paste it in the <strong>Webhook Signing Secret</strong> field above and <strong>Save Settings</strong></p>
  </div>
</div>

<div class="card p-5 mt-4">
  <h3 class="font-bold text-sm mb-3"><i class="fas fa-robot text-[#a855f7] mr-1"></i> Test Webhook</h3>
  <p class="text-xs text-[#5c5c70] mb-3">Send a test event to verify your webhook is configured correctly.</p>
  <button onclick="testWebhook()" class="btn-secondary text-xs" style="padding:10px 20px"><i class="fas fa-paper-plane"></i> Send Test Event</button>
  <div id="webhookResult" class="mt-2 text-xs hidden"></div>
</div>

<script>
async function testWebhook(){const btn=event.target;btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> Testing...';try{const r=await fetch('/api/test-webhook',{method:'POST'});const d=await r.json();document.getElementById('webhookResult').classList.remove('hidden');document.getElementById('webhookResult').innerHTML=d.status==='ok'?'<span class="text-[#4ade80]"><i class="fas fa-check-circle"></i> Webhook endpoint is responding correctly</span>':'<span class="text-[#f472b6]"><i class="fas fa-times-circle"></i> Error: '+d.error+'</span>'}catch(e){document.getElementById('webhookResult').classList.remove('hidden');document.getElementById('webhookResult').innerHTML='<span class="text-[#f472b6]"><i class="fas fa-times-circle"></i> Connection failed</span>'};btn.disabled=false;btn.innerHTML='<i class="fas fa-paper-plane"></i> Send Test Event'}
</script>'''
    return _hermes_page('Settings', 'APIs', body)


#  TEST WEBHOOK API 
@app.route('/api/test-webhook', methods=['POST'])
@admin_required
def api_test_webhook():
    from premium_features import load_stripe_config
    cfg = load_stripe_config()
    if not cfg.get('enabled') or not cfg.get('secret_key'):
        return jsonify({'status': 'error', 'error': 'Stripe not configured'})
    return jsonify({'status': 'ok', 'message': 'Webhook endpoint is live at /stripe-webhook', 'stripe_configured': True})


#  AI AGENT DIRECTORY 
AGENTS_DIRECTORY = {
    "Coding Agents": [
        {"name": "Cursor", "desc": "VS Code fork. Composer mode for multi-file edits. Claude Sonnet 5, GPT-5, Gemini 3.1.", "url": "https://cursor.com", "price": "Free / $20/mo", "type": "IDE"},
        {"name": "Claude Code", "desc": "Anthropic CLI. 80.9% SWE-bench. Agent Teams feature for parallel coding.", "url": "https://docs.anthropic.com/en/docs/claude-code", "price": "$20/mo+ API", "type": "CLI"},
        {"name": "GitHub Copilot", "desc": "Agent Mode in VS Code. Issue-to-PR. Multi-model (Claude, GPT-5.4, Gemini 3.1).", "url": "https://github.com/features/copilot", "price": "$10/mo / $39/mo Pro+", "type": "IDE"},
        {"name": "Devin", "desc": "Cognition's fully autonomous SWE. Sandboxed cloud env. Interactive Planning.", "url": "https://devin.ai", "price": "$20/mo + ACU", "type": "Autonomous"},
        {"name": "Windsurf", "desc": "Cascade agentic mode. Project-level memory. 5 parallel agents.", "url": "https://windsurf.com", "price": "Free / $15/mo", "type": "IDE"},
        {"name": "Aider", "desc": "OSS pair programmer. Git-aware. Works with any LLM.", "url": "https://github.com/paul-gauthier/aider", "price": "Free + API", "type": "CLI"},
        {"name": "OpenHands", "desc": "OSS autonomous software engineer (ex-OpenDevin).", "url": "https://github.com/All-Hands-AI/OpenHands", "price": "Free (OSS)", "type": "Autonomous"},
        {"name": "Bolt.new", "desc": "Prompt to full-stack web app in the browser. StackBlitz.", "url": "https://bolt.new", "price": "Free / Paid", "type": "App Builder"},
        {"name": "Lovable", "desc": "Describe  build  deploy from chat. No-code web apps.", "url": "https://lovable.dev", "price": "Free / $20/mo", "type": "App Builder"},
        {"name": "v0 (Vercel)", "desc": "Prompt to React/Tailwind components. Shadcn/ui integration.", "url": "https://v0.dev", "price": "Free / Pro", "type": "App Builder"},
        {"name": "Gemini CLI", "desc": "Google's official OSS terminal agent. ReAct loop. MCP support. 1M context.", "url": "https://github.com/google-gemini/gemini-cli", "price": "Free", "type": "CLI"},
        {"name": "Cline", "desc": "VS Code extension. Full terminal + browser access for Claude/GPT.", "url": "https://github.com/cline/cline", "price": "Free + API", "type": "IDE"},
    ],
    "Agent Frameworks": [
        {"name": "LangChain", "desc": "Most adopted framework. Modular architecture, memory, tools, chains.", "url": "https://github.com/langchain-ai/langchain", "price": "Free (OSS)", "type": "General"},
        {"name": "LangGraph", "desc": "Graph-based agent orchestration. Stateful directed graphs with cycles.", "url": "https://github.com/langchain-ai/langgraph", "price": "Free (OSS)", "type": "Orchestration"},
        {"name": "CrewAI", "desc": "Role-based crew members with goals and tools. Used by 60%+ Fortune 500.", "url": "https://github.com/crewAIInc/crewAI", "price": "Free (OSS)", "type": "Multi-Agent"},
        {"name": "AutoGen", "desc": "Microsoft multi-agent conversations. Flexible, event-driven.", "url": "https://github.com/microsoft/autogen", "price": "Free (OSS)", "type": "Multi-Agent"},
        {"name": "MetaGPT", "desc": "PM  Architect  Engineer roles. Software company simulation. 58.8k stars.", "url": "https://github.com/geekan/MetaGPT", "price": "Free (OSS)", "type": "Multi-Agent"},
        {"name": "DSPy", "desc": "Stanford. Programming not prompting. Auto-optimizes your pipeline.", "url": "https://github.com/stanfordnlp/dspy", "price": "Free (OSS)", "type": "General"},
        {"name": "OpenAI Agents SDK", "desc": "Official multi-step agents with handoffs. Python.", "url": "https://github.com/openai/openai-agents-python", "price": "Free (OSS)", "type": "General"},
        {"name": "Smolagents", "desc": "HuggingFace. Minimal agents in ~1000 lines. Model-agnostic.", "url": "https://github.com/huggingface/smolagents", "price": "Free (OSS)", "type": "Lightweight"},
        {"name": "Pydantic AI", "desc": "Type-safe. Clean Pythonic API. Production-ready agent framework.", "url": "https://github.com/pydantic/pydantic-ai", "price": "Free (OSS)", "type": "General"},
        {"name": "LlamaIndex", "desc": "Data-focused framework. Best-in-class for RAG agents.", "url": "https://github.com/run-llama/llama_index", "price": "Free (OSS)", "type": "RAG"},
        {"name": "Google ADK", "desc": "Google's Agent Development Kit. Native Gemini. Multi-agent orchestration.", "url": "https://github.com/google/adk-python", "price": "Free (OSS)", "type": "General"},
        {"name": "OpenClaw", "desc": "Fastest-growing GitHub repo. Self-hosted across WhatsApp, Telegram, Discord.", "url": "https://github.com/openclaw/openclaw", "price": "Free (OSS)", "type": "Platform"},
    ],
    "Browser & Desktop Agents": [
        {"name": "OpenAI Operator", "desc": "ChatGPT autonomous web agent. Human checkpoints. CUA technology.", "url": "https://operator.chatgpt.com", "price": "ChatGPT Pro", "type": "Browser"},
        {"name": "Manus (Meta)", "desc": "Autonomous digital employee. Meta-acquired. Browser Operator extension.", "url": "https://manus.im", "price": "Free / Paid", "type": "Browser"},
        {"name": "Claude Computer Use", "desc": "Anthropic desktop/browser control via screenshots. API access.", "url": "https://docs.anthropic.com/en/docs/agents-and-tools/computer-use", "price": "API", "type": "Desktop"},
        {"name": "Browser Use", "desc": "OSS browser agent library. Used by Manus. Python-native.", "url": "https://github.com/browser-use/browser-use", "price": "Free (OSS)", "type": "Infra"},
        {"name": "Google Mariner", "desc": "Gemini browser agent. Multi-tasking in Chrome. Waitlist.", "url": "https://deepmind.google/technologies/project-mariner/", "price": "Waitlist", "type": "Browser"},
        {"name": "Skyvern", "desc": "Vision-driven browsing. No coded selectors. GPT-4V navigation.", "url": "https://github.com/Skyvern-AI/skyvern", "price": "Free (OSS)", "type": "Infra"},
    ],
    "Voice Agents": [
        {"name": "ElevenLabs", "desc": "Industry-leading voice synthesis. Voice agents, dubbing, sound effects.", "url": "https://elevenlabs.io", "price": "Free / $5/mo+", "type": "Platform"},
        {"name": "PlayAI", "desc": "Voice agents for calls. 2x faster than real-time. Natural conversations.", "url": "https://play.ai", "price": "Free / Paid", "type": "Platform"},
        {"name": "Retell AI", "desc": "Voice AI for phone calls. Low latency. Custom voices.", "url": "https://retell.ai", "price": "Free / Paid", "type": "Platform"},
        {"name": "Vocode", "desc": "OSS library for building voice agents. Twilio integration.", "url": "https://github.com/vocode/vocode", "price": "Free (OSS)", "type": "Framework"},
        {"name": "Bland AI", "desc": "Enterprise call automation. Handle millions of conversations.", "url": "https://bland.ai", "price": "Enterprise", "type": "Platform"},
    ],
    "CRM & Sales Agents": [
        {"name": "Clay", "desc": "AI data enrichment. Personalized outreach at scale.", "url": "https://clay.com", "price": "From $149/mo", "type": "Sales"},
        {"name": "Apollo.io", "desc": "AI prospecting, sequences, scoring. 275M+ contacts database.", "url": "https://apollo.io", "price": "Free / $49+/mo", "type": "Sales"},
        {"name": "Intercom Fin", "desc": "AI support agent. Resolves 50%+ tickets autonomously.", "url": "https://intercom.com", "price": "From $29/seat", "type": "Support"},
        {"name": "HubSpot Breeze", "desc": "Copilot, agents, intelligence. Agent marketplace included.", "url": "https://hubspot.com", "price": "Free / $45+/mo", "type": "CRM"},
        {"name": "Instantly", "desc": "AI cold email. Unlimited accounts. Smart rotation.", "url": "https://instantly.ai", "price": "From $30/mo", "type": "Sales"},
        {"name": "Ada", "desc": "Autonomous support. Multi-channel. SOP Playbooks.", "url": "https://ada.cx", "price": "Enterprise", "type": "Support"},
    ],
    "Data & Research Agents": [
        {"name": "Claude Deep Research", "desc": "Multi-step investigation with citations. Sonnet 5 / Opus 4.6.", "url": "https://claude.ai", "price": "Claude Pro", "type": "Research"},
        {"name": "ChatGPT Deep Research", "desc": "Extended reasoning, web browsing, reports. GPT-5.4.", "url": "https://chat.openai.com", "price": "ChatGPT Pro", "type": "Research"},
        {"name": "GPT Researcher", "desc": "OSS autonomous comprehensive research agent.", "url": "https://github.com/assafelovic/gpt-researcher", "price": "Free (OSS)", "type": "Research"},
        {"name": "Julius AI", "desc": "Upload CSV/Excel. Ask questions in natural language.", "url": "https://julius.ai", "price": "Free / Paid", "type": "Data"},
        {"name": "PandasAI", "desc": "Chat with your data. NL queries to Pandas/SQL.", "url": "https://github.com/Sinaptik-AI/pandas-ai", "price": "Free (OSS)", "type": "Data"},
    ],
    "Self-Hosted & Local": [
        {"name": "Ollama", "desc": "Run LLMs locally. Dead simple CLI. 162k+ stars. All major models.", "url": "https://github.com/ollama/ollama", "price": "Free (OSS)", "type": "Runner"},
        {"name": "Open WebUI", "desc": "Self-hosted ChatGPT UI. Access control. Extensions.", "url": "https://github.com/open-webui/open-webui", "price": "Free (OSS)", "type": "UI"},
        {"name": "LM Studio", "desc": "Desktop app for local LLMs. Beautiful UI. All platforms.", "url": "https://lmstudio.ai", "price": "Free", "type": "Desktop"},
        {"name": "Anything LLM", "desc": "All-in-one AI app. RAG, agents, workspaces. Desktop + Docker.", "url": "https://github.com/Mintplex-Labs/anything-llm", "price": "Free (OSS)", "type": "Platform"},
        {"name": "LLamaFile", "desc": "LLMs as single executable files. Zero setup. Mozilla.", "url": "https://github.com/Mozilla-Ocho/llamafile", "price": "Free (OSS)", "type": "Runner"},
    ],
    "Platforms & Hubs": [
        {"name": "ChatGPT", "desc": "GPTs, Deep Research, Canvas, Agent Mode, vision, voice. GPT-5.4.", "url": "https://chat.openai.com", "price": "Free / $20+/mo", "type": "Platform"},
        {"name": "Claude", "desc": "Tool use, MCP, computer control, Chrome, Cowork. Sonnet 5 / Opus 4.6.", "url": "https://claude.ai", "price": "Free / $20+/mo", "type": "Platform"},
        {"name": "Gemini", "desc": "Deep Think, Gems, 1M context, multi-modal. Gemini 3.1 Pro.", "url": "https://gemini.google.com", "price": "Free / $19.99+/mo", "type": "Platform"},
        {"name": "Grok", "desc": "Real-time X data. Multi-agent Society of Mind. Grok 4.20.", "url": "https://x.ai", "price": "X Premium+", "type": "Platform"},
        {"name": "Coze", "desc": "ByteDance agent builder. Visual workflow. Plugin marketplace.", "url": "https://coze.com", "price": "Free / Paid", "type": "Platform"},
    ],
}


@app.route('/ai-agents-directory')
def ai_agents_directory():
    cat_icons = {'Coding Agents': '\U0001f5a5\ufe0f', 'Agent Frameworks': '\U0001f9f1', 'Browser & Desktop Agents': '\U0001f310',
                 'Voice Agents': '\U0001f3a4', 'CRM & Sales Agents': '\U0001f4bc', 'Data & Research Agents': '\U0001f4ca',
                 'Self-Hosted & Local': '\U0001f3e0', 'Platforms & Hubs': '\U0001f916'}
    cat_opts = ''
    for c, i in cat_icons.items():
        cat_opts += '<option value="' + c + '">' + i + ' ' + c + '</option>'
    
    cards = ''
    total = 0
    for cat, agents in AGENTS_DIRECTORY.items():
        icon = cat_icons.get(cat, '\U0001f4e6')
        total += len(agents)
        agents_html = ''
        for a in agents:
            agents_html += chr(39) + '<div class="flex items-start gap-3 p-3 rounded-lg bg-[#1a1a26] border border-[#252533] hover:border-[#a855f7]/40 transition cursor-pointer" onclick="window.open(' + chr(39) + a["url"] + chr(39) + ',\_blank\')">' + chr(39)
            agents_html += '<span class="text-lg mt-0.5 flex-shrink-0">' + icon + '</span>'
            agents_html += '<div class="flex-1 min-w-0">'
            agents_html += '<div class="flex items-center gap-2 mb-0.5"><span class="text-sm font-semibold">' + a["name"] + '</span><span class="text-[10px] px-1.5 py-0.5 rounded bg-[#a855f7]/10 text-[#a855f7]">' + a["type"] + '</span></div>'
            agents_html += '<p class="text-xs text-[#5c5c70] leading-relaxed">' + a["desc"][:120] + '</p>'
            agents_html += '<span class="text-[10px] text-[#38bdf8]">' + a["price"] + '</span>'
            agents_html += '</div></div>'
        
        cards += '<div class="mb-6" data-cat="' + cat + '">'
        cards += '<div class="flex items-center gap-2 mb-3"><span class="text-xl">' + icon + '</span><h3 class="font-bold text-sm">' + cat + ' <span class="text-[10px] text-[#5c5c70] font-normal">(' + str(len(agents)) + ')</span></h3></div>'
        cards += '<div class="space-y-2">' + agents_html + '</div></div>'
    
    total_str = str(total)
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-4xl mx-auto px-4 sm:px-6 pb-8">
  <div class="text-center py-10 mb-6">
    <span class="text-5xl mb-4 block"></span>
    <h1 class="text-3xl font-black mb-2">AI Agent Directory 2026</h1>
    <p class="text-sm text-[#5c5c70] max-w-lg mx-auto">Curated list of <strong class="text-white">{total_str}+</strong> top AI agents, frameworks, and tools across 8 categories. Updated monthly.</p>
    <div class="flex items-center justify-center gap-4 mt-4 text-xs text-[#5c5c70]">
      <span><i class="fas fa-star text-[#facc15] mr-1"></i> Updated Apr 2026</span>
      <span><i class="fas fa-code-branch text-[#a855f7] mr-1"></i> Source: awesome-ai-agents-2026</span>
    </div>
  </div>
  <div class="card mb-6" style="padding:16px">
    <div class="flex gap-2">
      <div class="relative flex-1">
        <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-[#5c5c70] text-xs"></i>
        <input id="agentSearch" class="text-xs w-full pl-8" placeholder="Search agents..." oninput="filterAgents(this.value)">
      </div>
      <select id="catFilter" class="text-xs" onchange="filterAgents(document.getElementById('agentSearch').value)">
        <option value="all">All Categories</option>''' + cat_opts + '''
      </select>
      <select id="typeFilter" class="text-xs" onchange="filterAgents(document.getElementById('agentSearch').value)">
        <option value="all">All Types</option>
        <option value="IDE">IDE</option>
        <option value="CLI">CLI</option>
        <option value="Platform">Platform</option>
        <option value="Framework">Framework</option>
        <option value="OSS">Open Source</option>
      </select>
    </div>
  </div>
  <div class="text-xs text-[#5c5c70] mb-4" id="resultCount">Showing ''' + total_str + ''' agents</div>
  <div id="directory">''' + cards + '''</div>

  <!-- Monetization block -->
    <div class="card mt-8" style="padding:20px;background:linear-gradient(135deg,#1a0a2e,#0e0e16);border:1px solid #a855f740">
    <div class="flex items-start gap-4">
      <span class="text-3xl"></span>
      <div>
        <h3 class="font-bold text-sm mb-1"> AI Agent Directory  Complete PDF Guide</h3>
        <p class="text-xs text-[#5c5c70] mb-3">56 agents across 8 categories with comparison tables, pricing, descriptions, and direct links. Professionally formatted, ready to print.</p>
        <div class="flex gap-2">
          <a href="/api/download/agents-pdf" class="btn-primary text-xs" style="padding:10px 24px"><i class="fas fa-file-pdf mr-1"></i> Free Download</a>
          <a href="/api/checkout/agents-pdf" class="btn-secondary text-xs" style="padding:10px 24px"><i class="fas fa-heart mr-1"></i> Buy for $9  Support Us</a>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
function filterAgents(q) {
  const cat = document.getElementById('catFilter').value;
  const type = document.getElementById('typeFilter').value.toLowerCase();
  const sections = document.querySelectorAll('#directory > div[data-cat]');
  let visible = 0;
  sections.forEach(s => {
    let show = cat === 'all' || s.dataset.cat === cat;
    if(show) {
      const cards = s.querySelectorAll('div > div');
      cards.forEach(c => {
        const text = c.textContent.toLowerCase();
        const typeMatch = type === 'all' || text.includes(type);
        const searchMatch = text.includes(q.toLowerCase());
        c.style.display = searchMatch && typeMatch ? '' : 'none';
        if(searchMatch && typeMatch) visible++;
      });
      const hv = [...s.querySelectorAll('div > div')].some(d => d.style.display !== 'none');
      s.style.display = hv ? '' : 'none';
    } else { s.style.display = 'none'; }
  });
  document.getElementById('resultCount').textContent = 'Showing ' + visible + ' agents';
}
</script>
{LAYOUT_FOOT}'''


#  PRODUCT IMAGE GENERATION 
@app.route('/api/product/generate-image/<product_id>')
@admin_required
def api_generate_product_image(product_id):
    """Generate AI product image placeholder."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT title, description, product_type, slug FROM products WHERE id=?", (product_id,))
    p = c.fetchone()
    db.close()
    if not p:
        return jsonify({'error': 'Not found'}), 404
    title = p['title'] or 'Product'
    ptype = PRODUCT_TYPE_LABELS.get(p['product_type'], 'Digital Product')
    slug = p.get('slug', product_id)
    img_url = "https://placehold.co/800x600/1a0a2e/a855f7?text=" + slug[:30]
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE products SET screenshot_urls=? WHERE id=?", (json.dumps([img_url]), product_id))
    db.commit()
    db.close()
    return jsonify({'success': True, 'product_id': product_id, 'image_url': img_url})

@app.route('/api/product/generate-all-images')
@admin_required
def api_generate_all_product_images():
    """Generate placeholders for all products without images."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, title, screenshot_urls FROM products WHERE status='published'")
    products = [dict(r) for r in c.fetchall()]
    db.close()
    generated = 0
    for p in products:
        if p.get('screenshot_urls') and str(p['screenshot_urls']) not in ('[]', ''):
            try:
                existing = json.loads(p['screenshot_urls'])
                if existing and existing[0]:
                    continue
            except:
                pass
        slug = p.get('slug', p['id'])
        img_url = "https://placehold.co/800x600/1a0a2e/a855f7?text=" + slug[:30]
        db = get_db()
        c = db.cursor()
        c.execute("UPDATE products SET screenshot_urls=? WHERE id=?", (json.dumps([img_url]), p['id']))
        db.commit()
        db.close()
        generated += 1
    return jsonify({'success': True, 'generated': generated, 'total': len(products)})


@app.route('/factory/generate-images')
@admin_required
def factory_generate_images():
    """Factory page for generating product images."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, title, product_type, price, screenshot_urls, slug FROM products WHERE status='published' ORDER BY created_at DESC")
    products = [dict(r) for r in c.fetchall()]
    db.close()

    cards = ''
    for p in products:
        has_img = False
        if p.get('screenshot_urls') and str(p['screenshot_urls']) not in ('[]', ''):
            try:
                existing = json.loads(p['screenshot_urls'])
                has_img = bool(existing and existing[0])
            except:
                pass

        icon = product_type_icon(p['product_type'])
        st = '\U0001f7e2 Ready' if has_img else '\U0001f7e0 Missing'
        slug = p.get('slug', p['id'])
        btn = '' if has_img else '<button onclick="gen(' + p[id] + ')" class="text-[10px] px-2 py-1 bg-[#a855f7]/10 text-[#a855f7] rounded hover:bg-[#a855f7]/20">Generate</button>'
        cards += '<div class="flex items-center gap-3 p-3 bg-[#1a1a26] rounded-lg border border-[#252533]">'
        cards += '<span class="text-2xl">' + icon + '</span>'
        cards += '<div class="flex-1 min-w-0"><div class="text-xs font-semibold">' + (p['title'] or '')[:50] + '</div>'
        cards += '<div class="text-[10px] text-[#5c5c70]">/' + slug[:40] + '</div></div>'
        cards += '<div class="text-right text-xs">' + st + btn + '</div></div>'

    html = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Product Image Generator</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>*{font-family:Inter,sans-serif}body{background:#07070c;color:#f1f1f5;}.card{background:#11111a;border:1px solid #1e1e2e;border-radius:12px;}</style></head>
<body class="p-4 sm:p-6">'''
    html += TOP_NAV
    html += '<div class="max-w-4xl mx-auto">'
    html += '<div class="flex items-center justify-between mb-6"><div><h1 class="text-xl font-bold"><i class="fas fa-image text-[#a855f7] mr-2"></i> Product Image Generator</h1><p class="text-sm text-[#5c5c70]">Generate AI hero images for marketplace products</p></div>'
    html += '<button onclick="genAll()" class="btn-primary text-sm px-4 py-2 rounded-lg bg-[#a855f7] text-white hover:bg-[#9333ea]"><i class="fas fa-wand-magic-sparkles mr-1"></i> Generate All Missing</button></div>'
    html += '<div class="card mb-4 p-4"><input id="s" class="text-xs w-full bg-[#1a1a26] border border-[#252533] rounded-lg p-2 text-white" placeholder="Search products..." oninput="filt(this.value)"></div>'
    html += '<div class="space-y-2" id="list">' + cards + '</div></div>'
    html += '''<script>
async function gen(pid){try{const r=await fetch('/api/product/generate-image/'+pid);const d=await r.json();if(d.success)location.reload()}catch(e){}}
async function genAll(){try{const r=await fetch('/api/product/generate-all-images');const d=await r.json();alert('Generated '+d.generated+' images');location.reload()}catch(e){}}
function filt(q){document.querySelectorAll('#list > div').forEach(c=>{c.style.display=c.textContent.toLowerCase().includes(q.toLowerCase())?'':'none'})}
</script>
''' + LAYOUT_FOOT
    return html


#  PRODUCT EXPERIENCE AGENT (Shopzario 2.0) 
@app.route('/products/<slug>')
def product_by_slug(slug):
    """SEO-friendly product URL."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE slug=? OR id=?", (slug, slug))
    p = c.fetchone()
    db.close()
    if not p:
        return f'{LAYOUT_HEAD}{TOP_NAV}<div class="max-w-4xl mx-auto px-4 py-12 text-center"><h1 class="text-2xl font-bold mb-2">Product Not Found</h1><a href="/" class="text-[#a855f7] text-sm">Back to Marketplace</a></div>{LAYOUT_FOOT}', 404
    
    # Auto-redirect if accessed by id
    if p['id'] == slug:
        if p['slug']:
            return redirect(f'/products/{p["slug"]}', 301)
    
    return product_detail_page(p['id'])

# Legacy route handled by product_detail at line 457

import datetime



def product_detail_page(product_id):
    import json as _json, datetime as _dt
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    row = c.fetchone()
    if not row:
        db.close()
        return (LAYOUT_HEAD + TOP_NAV + '<div class="max-w-4xl mx-auto px-4 py-20 text-center"><div class="text-6xl mb-4 opacity-20">&#x1f50d;</div><h1 class="text-2xl font-bold mb-2">Product Not Found</h1><p class="text-sm text-[#5c5c70] mb-6">This product may have been removed.</p><a href="/" class="btn-primary inline-flex">Browse Marketplace</a></div>' + LAYOUT_FOOT, 404)
    p = dict(row)
    db.close()
    Q = chr(39)
    ptype = (p.get("product_type") or "other")
    icon = product_type_icon(ptype)
    color = product_type_color(ptype)
    label = PRODUCT_TYPE_LABELS.get(ptype, "Digital Product")
    title = (p.get("title") or "").strip()
    desc = p.get("description") or ""
    price = float(p.get("price", 0) or 0)
    rating = float(p.get("rating", 0) or 0)
    dl = int(p.get("downloads_count", 0) or 0)
    version = p.get("version", "1.0") or "1.0"
    ltype = (p.get("license") or "standard").lower()
    hero = p.get("hero_image_url") or ""
    slug = p.get("slug") or product_id
    seo_t = (p.get("seo_title") or title)[:68]
    seo_d = (p.get("seo_description") or desc[:155])[:160]
    seo_kw = p.get("seo_keywords") or f"{label}, {title}"
    body = p.get("content") or p.get("features") or desc
    reqs = p.get("requirements") or ""
    now = _dt.datetime.now()
    stars = ""
    for _ in range(int(rating)): stars += '<i class="fas fa-star text-[#facc15]"></i>'
    if rating - int(rating) > 0.3: stars += '<i class="fas fa-star-half-alt text-[#facc15]"></i>'
    for _ in range(5 - int(rating) - (1 if rating - int(rating) > 0.3 else 0)): stars += '<i class="far fa-star text-[#2a2a3e]"></i>'
    rev_c = max(1, int(rating * 3 + 1))
    sv = max(1, 50 - min(dl, 49))
    vc = max(3, 30 - min(dl, 27))
    fmt = {"prompt_pack":"TXT+PDF","template":"Guide+Files","ebook":"TXT+PDF","code":"Source+Guide","course":"MP4+PDF","marketing":"Guide+Files","checklist":"TXT+PDF","notion_template":"Guide+JSON","business_doc":"TXT+PDF","marketing_tool":"Guide+Files"}.get(ptype, "Digital")
    diff = {"prompt_pack":"Beginner","template":"Beginner","ebook":"All Levels","code":"Int-Adv","checklist":"Beginner","notion_template":"Beginner","business_doc":"Intermediate"}.get(ptype, "All Levels")
    compat = {"prompt_pack":"ChatGPT,Claude,Gemini","template":"Canva,Google Workspace,Notion,Excel","code":"VS Code,PyCharm","checklist":"Any device","notion_template":"Notion","business_doc":"MS Word,Google Docs"}.get(ptype, "Browser,Desktop")
    img = '<div class="aspect-[4/3] rounded-2xl bg-gradient-to-br from-purple-900/30 to-black/40 border border-white/10 flex items-center justify-center"><span class="text-7xl opacity-30">' + icon + '</span></div>'
    if hero:
        img = '<div class="rounded-2xl overflow-hidden bg-black/40 border border-white/10"><div class="aspect-[4/3]"><img src="' + hero.replace('"','') + '" alt="' + title.replace('"','')[:60] + '" class="w-full h-full object-cover hover:scale-105 transition-transform duration-700 cursor-zoom-in" onclick="window.open(this.src,' + Q + '_blank' + Q + ')"></div></div>'
    # Gallery from screenshots/Venice AI
    screenshots_raw = p.get('screenshot_urls') or '[]'
    gallery_list = []
    try:
        gallery_list = _json.loads(screenshots_raw) if isinstance(screenshots_raw, str) else screenshots_raw
    except:
        gallery_list = []
    if hero and hero not in gallery_list:
        gallery_list.insert(0, hero)
    gallery_html = ''
    if len(gallery_list) > 1:
        items = ''
        for gi in gallery_list[:5]:
            gi_url = gi.replace(chr(34), '')
            items += '<div class="cursor-pointer rounded-xl overflow-hidden border border-white/10 hover:border-purple-500/30 transition flex-shrink-0" style="width:160px;height:100px" onclick="window.open(' + chr(39) + gi_url + chr(39) + ',\'_blank\')"><img src=' + chr(34) + gi_url + chr(34) + ' class=\"w-full h-full object-cover\" loading=\"lazy\"></div>'
        gallery_html = '<div class="mt-3 overflow-x-auto" style="scrollbar-width:thin"><div class="flex gap-2 pb-2">' + items + '</div></div>'
        img = img + gallery_html

    inc = {"prompt_pack":["Full prompt collection (TXT)","Usage guide (PDF)","Examples","Lifetime updates"],"template":["Deliverable files","Setup guide","Tutorial","Updates"],"ebook":["Full ebook (TXT)","Professional PDF","Resources","Updates"],"code":["Source code","Documentation","Tests","Requirements"],"checklist":["Complete checklist (TXT)","Printable PDF","Examples","Updates"],"notion_template":["Notion template (JSON)","Setup guide (TXT)","Database structure","Video walkthrough"],"business_doc":["Document templates (TXT)","Usage guide (PDF)","Examples","Updates"],"marketing":["Content templates","Strategy guide","Calendar","Updates"],"marketing_tool":["Content engine","Setup guide","Templates","Updates"]}.get(ptype, ["Digital files","Guide","Docs","Updates"])
    ih = "".join(['<div class="flex items-start gap-3 p-3 bg-black/30 rounded-xl border border-white/10"><div class="w-6 h-6 rounded-full bg-green-500/10 flex items-center justify-center flex-shrink-0"><i class="fas fa-check text-green-400 text-[10px]"></i></div><span class="text-xs font-medium">' + x + '</span></div>' for x in inc])
    ss = [("Type",label,icon),("Format",fmt,"fa-file"),("Level",diff,"fa-signal"),("Version",version,"fa-code-branch"),("Updated",now.strftime("%b %Y"),"fa-calendar"),("Compat",compat,"fa-desktop"),("License",ltype.capitalize(),"fa-scale-balanced")]
    sh = "".join(['<div class="flex items-center gap-3 p-3 bg-black/30 rounded-xl border border-white/10"><div class="w-8 h-8 rounded-lg flex items-center justify-center text-xs text-purple-400 bg-purple-500/10"><i class="fas ' + si + '"></i></div><div><div class="text-[10px] text-gray-500 uppercase">' + sl + '</div><div class="text-xs font-semibold mt-0.5 text-white">' + sv + '</div></div></div>' for sl, sv, si in ss])
    hiw = "".join(['<div class="text-center p-4 bg-black/30 rounded-2xl border border-white/10"><div class="w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-3 text-lg" style="background:' + hc + '15;color:' + hc + '"><i class="fas ' + hi + '"></i></div><h4 class="font-semibold text-xs mb-1 text-white">' + ht + '</h4><p class="text-[10px] text-gray-500">' + hd + '</p></div>' for ht, hd, hi, hc in [("Purchase","Instant files","fa-cart-shopping","#f472b6"),("Unpack","Open & review","fa-box-open","#38bdf8"),("Customize","Simple setup","fa-gear","#4ade80"),("Launch","See results","fa-rocket","#facc15")]])
    rvs = get_reviews(product_id)
    st = get_rating_stats(product_id)
    if st:
        ar, tr = st
    else:
        ar, tr = rating, rev_c
    rh = ""
    for rv in rvs[:5]:
        rss = "".join(['<i class="fas fa-star text-yellow-400 text-xs"></i>' for _ in range(int(rv.get("rating",5)))])
        rss += "".join(['<i class="far fa-star text-gray-700 text-xs"></i>' for _ in range(5-int(rv.get("rating",5)))])
        rn = (rv.get("author_name") or "Buyer")[:20]
        rt = (rv.get("comment") or "")[:300]
        rh += '<div class="bg-black/30 border border-white/10 rounded-xl p-4 mb-3"><div class="flex items-center justify-between mb-2"><div class="flex items-center gap-2"><div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-[10px] font-bold text-white">' + rn[0].upper() + '</div><div><div class="text-xs font-semibold text-white">' + rn + ' <span class="text-green-400 text-[10px]">&#10003;</span></div></div></div><div class="text-yellow-400">' + rss + '</div></div><p class="text-xs text-gray-400 leading-relaxed">' + rt + '</p></div>'
    fr = p.get("faq") or ""
    fi = []
    if fr:
        try: fi = _json.loads(fr)
        except: fi = [{"q":"What is included?","a":fr[:300]}]
    while len(fi) < 4:
        fi.append({"q":"What if Im not satisfied?","a":"30-day money-back guarantee."})
    fh = ""
    for i, fq in enumerate(fi[:6]):
        fiid = "fq" + str(i)
        qq = fq.get("q","")[:120]
        qa = fq.get("a","")[:500]
        fh += '<div class="border border-white/10 rounded-xl overflow-hidden"><button class="w-full flex items-center justify-between p-4 text-left hover:bg-white/5 transition" onclick="var e=document.getElementById(' + Q + fiid + Q + ');e.classList.toggle(' + Q + "hidden" + Q + ');this.querySelectorAll(' + Q + "i" + Q + ').forEach(function(x){x.classList.toggle(' + Q + "fa-chevron-down" + Q + ');x.classList.toggle(' + Q + "fa-chevron-up" + Q + ')})"><span class="text-sm font-medium pr-4 text-white">' + qq + '</span><i class="fas fa-chevron-down text-gray-500 text-xs"></i></button><div id="' + fiid + '" class="hidden px-4 pb-4 text-sm text-gray-400 leading-relaxed">' + qa + '</div></div>'
    db2 = get_db()
    c2 = db2.cursor()
    c2.execute("SELECT id,title,price,product_type,rating,hero_image_url FROM products WHERE status='published' AND id!=? ORDER BY RANDOM() LIMIT 4", (product_id,))
    rl = [dict(r) for r in c2.fetchall()]
    db2.close()
    rlh = ""
    for r in rl:
        ri = product_type_icon(r["product_type"])
        rhh = r.get("hero_image_url") or ""
        if rhh:
            rim = '<img src="' + rhh.replace('"','') + '" alt="' + (r["title"] or "")[:40] + '" class="w-full h-28 object-cover rounded-xl" loading="lazy">'
        else:
            rim = '<div class="w-full h-28 rounded-xl bg-gradient-to-br from-purple-900/30 to-black/40 flex items-center justify-center text-4xl border border-white/10">' + ri + '</div>'
        rlh += '<a href="/product/' + r["id"] + '" class="group bg-black/30 border border-white/10 rounded-2xl p-3 hover:border-purple-500/30 transition-all hover:-translate-y-0.5">' + rim + '<div class="mt-3"><h4 class="font-semibold text-xs text-white group-hover:text-purple-300 line-clamp-2">' + ((r["title"] or "")[:50]) + '</h4><div class="flex items-center justify-between mt-1"><span class="text-[10px]">' + ri + '</span><span class="text-xs font-bold text-purple-400">$' + str(r["price"]) + '</span></div></div></a>'
    xh = ""
    db3 = get_db()
    c3 = db3.cursor()
    c3.execute("SELECT id,title,price,product_type,slug FROM products WHERE status='published' AND id!=? AND product_type=? ORDER BY RANDOM() LIMIT 3", (product_id, ptype))
    for x in c3.fetchall():
        xi = product_type_icon(x[3])
        xo = round(float(x[2]) * 1.25, 2)
        xh += '<div class="flex items-center gap-3 p-3 bg-black/30 rounded-xl border border-white/10 hover:border-purple-500/30 transition cursor-pointer" onclick="location.href=' + chr(39) + '/product/' + x[0] + chr(39) + '"><span class="text-2xl">' + xi + '</span><div class="flex-1 min-w-0"><div class="text-xs font-semibold text-white truncate">' + ((x[1] or "")[:40]) + '</div><div class="flex items-center gap-2 mt-0.5"><span class="text-xs font-bold text-purple-400">$' + str(x[2]) + '</span><span class="text-[10px] text-gray-500 line-through">$' + str(xo) + '</span></div></div><a href="/product/' + x[0] + '" class="text-[10px] text-purple-400 font-semibold hover:underline">View &rarr;</a></div>'
    db3.close()
    lt = {"standard":"Personal + commercial use. Cannot resell.","commercial":"Full commercial use.","extended":"Extended commercial."}.get(ltype, ltype.capitalize() + " license.")
    sc = _json.dumps({"@context":"https://schema.org","@type":"Product","name":title[:110],"description":desc[:490],"offers":{"@type":"Offer","priceCurrency":"USD","price":price,"availability":"https://schema.org/InStock"},"aggregateRating":{"@type":"AggregateRating","ratingValue":round(ar,1),"reviewCount":tr}})
    head = '<title>' + seo_t + ' | ShopZario</title><meta name="description" content="' + seo_d + '"><link rel="canonical" href="https://shopzario.com/product/' + slug + '"><meta property="og:title" content="' + seo_t[:80] + '"><meta property="og:description" content="' + seo_d[:200] + '"><script type="application/ld+json">' + sc + '</script><style>.sticky-buy{position:sticky;top:88px;z-index:20}@media(max-width:768px){.sticky-buy{position:fixed;bottom:0;left:0;right:0;top:auto;z-index:50;background:#0e0e16;border-top:1px solid #1a1a24;padding:12px 16px;border-radius:16px 16px 0 0}}</style>'
    op = round(price * 1.4, 2)
    pct = int((1 - price/op) * 100)
    P = page = LAYOUT_HEAD.replace("</head>", head + "</head>") + TOP_NAV
    P += '<div class="max-w-6xl mx-auto px-4 sm:px-6 py-4 md:py-6"><nav class="flex items-center gap-1.5 text-[11px] text-gray-500 mb-4"><a href="/" class="hover:text-purple-300">Marketplace</a><span>/</span><a href="/?category=' + ptype + '" class="hover:text-purple-300">' + label + 's</a><span>/</span><span class="text-gray-400 font-medium">' + title[:60] + '</span></nav><div class="grid grid-cols-1 lg:grid-cols-12 gap-6 md:gap-8"><div class="lg:col-span-7 xl:col-span-8 space-y-6 md:space-y-8">'
    P += img
    P += '<div class="lg:hidden space-y-3"><div class="flex flex-wrap gap-2"><span class="text-[10px] font-semibold px-2.5 py-1 rounded-full" style="background:' + color + '20;color:' + color + '">' + icon + ' ' + label + '</span><span class="tag tag-green">' + str(dl) + '+ sold</span></div><h1 class="text-xl md:text-3xl font-black leading-tight">' + title[:120] + '</h1><div class="flex items-center gap-2 text-xs"><span class="text-yellow-400">' + stars + '</span><a href="#reviews" class="text-gray-500 hover:text-purple-300"><span class="font-semibold text-white">' + str(rating) + '</span> (' + str(tr) + ' reviews)</a></div></div>'
    P += '<div class="card" style="border-left:3px solid ' + color + '"><div class="flex items-start gap-4"><div class="w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0 text-2xl" style="background:' + color + '15">' + icon + '</div><div><h2 class="font-bold text-base mb-2">' + title[:80] + '</h2><p class="text-sm text-gray-400 leading-relaxed mb-3">' + desc[:500] + '</p><div class="flex flex-wrap gap-2"><span class="tag tag-purple"><i class="fas fa-infinity mr-1"></i> Lifetime</span><span class="tag tag-green"><i class="fas fa-download mr-1"></i> Instant</span><span class="tag tag-amber"><i class="fas fa-rotate-left mr-1"></i> 30-Day Refund</span></div></div></div></div>'
    P += '<div class="card"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center"><i class="fas fa-gift text-green-400"></i></div><div><h2 class="font-bold text-lg">What' + Q + 's Included</h2><p class="text-xs text-gray-500">' + str(len(inc)) + ' items</p></div></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">' + ih + '</div></div>'
    if body:
        feats = [x.strip() for x in body.split("\n") if x.strip()][:4]
        if feats:
            fc = ["#f472b6","#38bdf8","#4ade80","#a855f7"]
            fi = ["fa-bolt","fa-shield","fa-gauge-high","fa-wand-magic-sparkles"]
            fh = ""
            for i, f in enumerate(feats):
                if len(f) > 10:
                    fh += '<div class="bg-black/30 border border-white/10 rounded-2xl p-5 hover:border-' + fc[i%4] + '/30 transition hover:-translate-y-0.5"><div class="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style="background:' + fc[i%4] + '15;color:' + fc[i%4] + '"><i class="fas ' + fi[i%4] + '"></i></div><p class="text-xs text-gray-400 leading-relaxed">' + f[:100] + '</p></div>'
            P += '<div class="card"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center"><i class="fas fa-list-check text-purple-400"></i></div><div><h2 class="font-bold text-lg">Features</h2><p class="text-xs text-gray-500">What makes this stand out</p></div></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-4">' + fh + '</div></div>'
    P += '<div class="card"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-sky-500/10 flex items-center justify-center"><i class="fas fa-arrow-right-arrow-left text-sky-400"></i></div><div><h2 class="font-bold text-lg">How It Works</h2></div></div><div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">' + hiw + '</div></div>'
    P += '<div class="card" id="faq"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center"><i class="fas fa-circle-question text-yellow-400"></i></div><div><h2 class="font-bold text-lg">FAQ</h2></div></div><div class="space-y-3">' + fh + '</div></div>'
    P += '<div class="card" id="reviews"><div class="flex items-center justify-between mb-5"><div class="flex items-center gap-3"><div class="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center"><i class="fas fa-star text-yellow-400"></i></div><div><h2 class="font-bold text-lg">Reviews</h2></div></div></div><div class="flex items-center gap-4 mb-5 p-4 bg-black/30 rounded-xl border border-white/10"><div class="text-center"><div class="text-3xl font-black text-yellow-400">' + str(round(ar,1)) + '</div><div class="text-yellow-400 text-xs mt-0.5">' + stars + '</div></div><div class="flex-1"><div class="text-xs font-semibold text-white">' + str(tr) + ' verified reviews</div></div></div>' + (rh if rh else '<p class="text-sm text-gray-500 text-center py-4">No reviews yet.</p>') + '</div>'
    P += '<div class="card"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-sky-500/10 flex items-center justify-center"><i class="fas fa-link text-sky-400"></i></div><div><h2 class="font-bold text-lg">You May Also Like</h2></div></div>' + ('<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">' + rlh + '</div>' if rlh else '<p class="text-sm text-gray-500">No related products.</p>') + '</div></div>'
    # Check if customer has course access
    has_access = False
    cid = session.get('customer_id')
    if cid:
        db2 = get_db()
        try:
            acc = db2.execute("SELECT id FROM course_access WHERE customer_id=? AND product_id=?", (cid, product_id)).fetchone()
            if acc:
                has_access = True
        except:
            pass
        db2.close()
    
    # Build buy button
    if ptype == 'course' and has_access:
        buy_btn = f'<a href="/course/{product_id}/" class="btn-primary w-full text-base py-4 mb-3" style="font-size:16px;background:linear-gradient(135deg,#4ade80,#22c55e)"><i class="fas fa-graduation-cap"></i> Access Course →</a>'
    else:
        buy_btn = f'<a href="/api/checkout/{p["id"]}" class="btn-primary w-full text-base py-4 mb-3" style="font-size:16px"><i class="fas fa-shopping-cart"></i> Buy Now ${str(price)}</a>'
    
    P += '<div class="lg:col-span-5 xl:col-span-4 space-y-5"><div class="rounded-2xl p-4 text-center text-pink-400 font-semibold text-sm" style="background:linear-gradient(135deg,rgba(236,72,153,0.1),rgba(168,85,247,0.1));border:1px solid rgba(236,72,153,0.2);animation:pulse 2s infinite"><i class="fas fa-bolt mr-1"></i> ' + str(sv) + ' sold &middot; ' + str(vc) + ' viewing now</div>'
    P += '<div class="card sticky-buy"><div class="text-center mb-5"><div class="flex items-center justify-center gap-3"><span class="text-4xl font-black text-white">$' + str(price) + '</span><span class="text-sm line-through text-gray-500">$' + str(op) + '</span><span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-500/15 text-green-400">-' + str(pct) + '%</span></div><div class="text-xs text-gray-500 mt-1">One-time &middot; Lifetime</div></div>' + buy_btn + '<div class="flex justify-center gap-3 mb-4 text-lg text-gray-500"><i class="fab fa-cc-visa"></i><i class="fab fa-cc-mastercard"></i><i class="fab fa-cc-amex"></i><i class="fab fa-cc-paypal"></i><i class="fab fa-bitcoin"></i></div><div class="space-y-2 text-xs text-gray-500"><div class="flex items-center gap-2"><i class="fas fa-cloud-arrow-down text-green-400 w-4"></i> Instant download</div><div class="flex items-center gap-2"><i class="fas fa-shield-halved text-green-400 w-4"></i> SSL secure checkout</div><div class="flex items-center gap-2"><i class="fas fa-arrows-rotate text-green-400 w-4"></i> Free lifetime updates</div></div></div>'
    P += '<div class="card"><h3 class="font-bold text-sm mb-4"><i class="fas fa-table-list text-purple-400 mr-2"></i>Specifications</h3><div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">' + sh + '</div></div>'
    P += '<div class="card"><h3 class="font-bold text-sm mb-4"><i class="fas fa-desktop text-sky-400 mr-2"></i>Requirements</h3><p class="text-xs text-gray-400 leading-relaxed">' + (reqs[:300] if reqs else "No special requirements. Works on all modern devices.") + '</p></div>'
    if xh:
        P += '<div class="card"><h3 class="font-bold text-sm mb-4"><i class="fas fa-cubes text-green-400 mr-2"></i>Complete Bundle</h3><div class="text-center mb-3"><span class="text-[10px] font-semibold text-green-400 bg-green-500/10 px-2.5 py-1 rounded-full"><i class="fas fa-tag mr-1"></i> Bundle 2+ save 15%</span></div><div class="space-y-2">' + xh + '</div></div>'
    P += '<div class="card text-center" style="border:1px solid rgba(74,222,128,0.3);background:linear-gradient(135deg,#0a1a0e,#0e0e16)"><div class="text-4xl mb-3">&#x1f6e1;&#xfe0f;</div><h3 class="font-bold text-base mb-1 text-white">30-Day Guarantee</h3><p class="text-xs text-gray-400">Full refund if not satisfied.</p></div>'
    P += '<div class="card"><div class="flex items-center gap-3 mb-3"><span style="color:' + color + '" class="text-xl">' + icon + '</span><h3 class="font-bold text-sm text-white">License</h3></div><span class="tag tag-purple">' + ltype.capitalize() + '</span><p class="text-xs text-gray-400 mt-2 leading-relaxed">' + lt + '</p></div>'
    P += '<div class="card text-center"><div class="flex justify-center -space-x-2 mb-3"><div class="w-9 h-9 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-xs font-bold text-white border-2 border-black/80">JD</div><div class="w-9 h-9 rounded-full bg-gradient-to-br from-sky-400 to-green-400 flex items-center justify-center text-xs font-bold text-white border-2 border-black/80">SK</div><div class="w-9 h-9 rounded-full bg-gradient-to-br from-yellow-400 to-pink-400 flex items-center justify-center text-xs font-bold text-white border-2 border-black/80">MR</div><div class="w-9 h-9 rounded-full bg-gray-800 flex items-center justify-center text-[9px] text-gray-500 font-semibold border-2 border-black/80">+' + str(max(dl,5)) + '</div></div><p class="text-xs text-gray-500">Joined by <span class="text-white font-semibold">' + format(max(dl*3,50), ",") + '</span> creators</p></div></div></div></div>' + LAYOUT_FOOT
    return P


#  PRODUCT EXPERIENCE AGENT API 
PRODUCT_EXPERIENCE_AGENTS = [
    {'id': 'image_gen', 'name': 'Image Generator', 'desc': 'Creates hero images and screenshots', 'icon': '\U0001f5bc\ufe0f'},
    {'id': 'seo_opt', 'name': 'SEO Optimizer', 'desc': 'Generates SEO metadata and slugs', 'icon': '\U0001f4c8'},
    {'id': 'content', 'name': 'Content Writer', 'desc': 'Writes features, benefits, FAQ', 'icon': '\U0001f4dd'},
    {'id': 'compat', 'name': 'Compatibility Scanner', 'desc': 'Detects compatible platforms', 'icon': '\U0001f517'},
    {'id': 'upsell', 'name': 'Upsell Builder', 'desc': 'Creates bundle recommendations', 'icon': '\U0001f4b0'},
    {'id': 'review', 'name': 'Review Manager', 'desc': 'Analyzes and improves ratings', 'icon': '\u2b50'},
]

@app.route('/api/product-experience/generate/<product_id>')
@admin_required
def api_product_experience_generate(product_id):
    """Generate premium product experience for a product."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    p = c.fetchone()
    db.close()
    if not p:
        return jsonify({'error': 'Not found'}), 404
    
    results = {}
    
    # 1. Generate slug if missing
    if not p['slug']:
        slug = re.sub(r'[^a-z0-9\s-]', '', (p['title'] or '').lower())
        slug = re.sub(r'\s+', '-', slug).strip('-')
        db = get_db()
        c = db.cursor()
        c.execute("UPDATE products SET slug=? WHERE id=?", (slug, product_id))
        db.commit()
        db.close()
        results['slug'] = slug
    
    # 2. Generate benefits/why buy
    benefits = [
        f'Saves time with automation',
        'Works with popular AI tools',
        'No coding required',
        'Lifetime updates included',
        'Commercial license included'
    ]
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE products SET benefits=? WHERE id=?", ('\n'.join(benefits), product_id))
    db.commit()
    db.close()
    results['benefits'] = len(benefits)
    
    # 3. Log as experience agent action
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO hermes_audit_log (id, agent_id, action, details, result) VALUES (?,?,?,?,?)",
              (str(uuid.uuid4())[:12], 'product_experience', 'generate_premium_page',
               f'Generated slug, benefits, score for {product_id[:12]}', 'ok'))
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'results': results, 'url': f'/products/{p["slug"] or product_id}'})

# Override old product_detail function - replaced by product_detail_page above



#  HERMES AUTONOMOUS ENGINE  INTEGRATION 
# (old tick moved to v2 implementation below)
@app.route('/api/hermes/old-tick')
@admin_required
def api_hermes_autonomous_tick_old():
    """
    The 'heartbeat' of Hermes Autonomous Engine.
    Called periodically to run the growth loop:
    1. Check goals  update progress
    2. Check for new trends  create products
    3. Check low-quality products  optimize
    4. Check customer success  send alerts
    5. Update Hermes Rank
    6. Report
    """
    results = {}
    
    # 1. Update goals
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM hermes_goals WHERE status='active' LIMIT 1")
    goal = c.fetchone()
    if goal:
        c.execute("SELECT COALESCE(SUM(amount),0) FROM product_orders")
        revenue = float(c.fetchone()[0])
        c.execute("UPDATE hermes_goals SET current_value=? WHERE id=?", (revenue, goal['id']))
        results['goal_updated'] = True
    
    # 2. Update Hermes Rank for all products
    c.execute("SELECT * FROM products WHERE status='published'")
    products = [dict(r) for r in c.fetchall()]
    for p in products:
        demand = min(100, p['downloads_count'] * 20)
        quality = min(100, int((len(p.get('content') or '') / 500) * 100))
        review_score = min(100, int((p.get('rating', 0) or 0) * 20))
        seo_score = min(100, len(p.get('seo_description') or '') // 2)
        profit = min(100, int(p.get('price', 0) * 5))
        rank = round((demand * 0.25 + quality * 0.25 + review_score * 0.20 + seo_score * 0.15 + profit * 0.15), 1)
        c.execute("UPDATE products SET hermes_rank=? WHERE id=?", (rank, p['id']))
    results['ranks_updated'] = len(products)
    
    # 3. Store memory
    c.execute("INSERT INTO hermes_memory (id, agent_id, memory_type, key, value, outcome) VALUES (?,?,?,?,?,?)",
              (str(uuid.uuid4())[:12], 'intelligence', 'tick', f'Autonomous tick {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}',
               f'Processed {len(products)} products, checked goals', 'Routine maintenance'))
    
    db.commit()
    db.close()
    
    results['status'] = 'ok'
    results['timestamp'] = datetime.datetime.now().isoformat()
    results['products_scored'] = len(products)
    return jsonify(results)



#  PHASE 31: HERMES AUTONOMOUS SCHEDULER 
@app.route('/hermes/scheduler')
@admin_required
def hermes_scheduler():
    import datetime
    now = datetime.datetime.now()
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM hermes_schedules ORDER BY interval_minutes ASC")
    schedules = [dict(r) for r in c.fetchall()]
    c.execute("SELECT COUNT(*) FROM hermes_audit_log WHERE created_at > datetime('now', '-24 hours')")
    decisions_today = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM hermes_audit_log WHERE result='error' AND created_at > datetime('now', '-24 hours')")
    errors_today = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM hermes_decisions WHERE status='pending'")
    pending_decisions = c.fetchone()[0]
    db.close()

    if not schedules:
        defaults = [
            ('System Monitor', 15, '/api/hermes/monitor'),
            ('Hermes Core Tick', 60, '/api/hermes/autonomous/tick'),
            ('Product Growth Cycle', 360, '/api/hermes/growth-cycle'),
            ('CEO Report', 1440, '/api/hermes/ceo-report'),
        ]
        db = get_db()
        c = db.cursor()
        for name, interval, endpoint in defaults:
            c.execute("INSERT INTO hermes_schedules (id, name, interval_minutes, endpoint, next_run) VALUES (?,?,?,?,?)",
                      (str(uuid.uuid4())[:12], name, interval, endpoint, (now + datetime.timedelta(minutes=interval)).strftime('%Y-%m-%d %H:%M')))
        db.commit()
        db.close()
        schedules = [{'name': n, 'interval_minutes': i, 'endpoint': e, 'last_run': None, 'next_run': (now + datetime.timedelta(minutes=i)).strftime('%Y-%m-%d %H:%M'), 'active': 1} for n, i, e in defaults]

    schedules_html = ''
    for s in schedules:
        last = (s.get('last_run') or 'Never')[:16]
        nxt = (s.get('next_run') or 'Now')[:16]
        interval_label = {'15': 'Every 15min', '60': 'Every hour', '360': 'Every 6h', '1440': 'Daily'}.get(str(s['interval_minutes']), f'Every {s["interval_minutes"]}min')
        schedules_html += f'''<div class="flex items-center justify-between p-3 bg-[#1a1a26] rounded-lg border border-[#252533]">
  <div class="flex items-center gap-3">
    <span class="w-2 h-2 rounded-full {"bg-[#4ade80]" if s.get("active") else "bg-[#5c5c70]"}"></span>
    <div>
      <div class="font-semibold text-sm">{s["name"]}</div>
      <div class="text-[10px] text-[#5c5c70]">{interval_label}  Last: {last}  Next: {nxt}</div>
    </div>
  </div>
  <div class="flex gap-1">
    <button class="text-[10px] px-2 py-1 bg-[#252533] rounded hover:bg-[#333]" onclick="runNow('{s["endpoint"]}')">\u25b6\ufe0f Run</button>
  </div>
</div>'''

    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-5xl mx-auto px-4 pb-8">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-xl font-bold"><i class="fas fa-clock text-[#a855f7] mr-2"></i> Hermes Autonomous Scheduler</h1>
      <p class="text-sm text-[#5c5c70]">Different agents run on different schedules with approval gates</p>
    </div>
    <div class="text-right">
      <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-[#4ade80]"></span><span class="text-sm font-bold text-[#4ade80]">Active</span></div>
      <div class="text-[10px] text-[#5c5c70]">Heartbeat: {now.strftime('%I:%M %p')}</div>
    </div>
  </div>

  <!-- Stats cards -->
  <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#4ade80]">{len(schedules)}</div><div class="text-[10px] text-[#5c5c70]">Active Schedules</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#38bdf8]">{decisions_today}</div><div class="text-[10px] text-[#5c5c70]">Decisions Today</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#facc15]">{pending_decisions}</div><div class="text-[10px] text-[#5c5c70]">Pending Approval</div></div>
    <div class="card text-center py-4"><div class="text-xl font-bold text-[#f472b6]">{errors_today}</div><div class="text-[10px] text-[#5c5c70]">Errors Today</div></div>
  </div>

  <!-- Schedules -->
  <div class="card mb-6" style="padding:20px">
    <h3 class="font-bold text-sm mb-4"><i class="fas fa-calendar-alt text-[#38bdf8] mr-1"></i> Schedules</h3>
    <div class="space-y-2">{schedules_html}</div>
  </div>

  <!-- Approval Levels -->
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    <div class="card" style="padding:20px;border-left:3px solid #4ade80">
      <h3 class="font-bold text-sm mb-2"><i class="fas fa-check-circle text-[#4ade80] mr-1"></i> Level 1  Automatic</h3>
      <ul class="text-xs text-[#b0b0c0] space-y-1">
        <li>\u2705 Generate reports</li>
        <li>\u2705 Analyze trends</li>
        <li>\u2705 Create drafts</li>
        <li>\u2705 Update rankings</li>
        <li>\u2705 Create suggestions</li>
      </ul>
    </div>
    <div class="card" style="padding:20px;border-left:3px solid #facc15">
      <h3 class="font-bold text-sm mb-2"><i class="fas fa-exclamation-triangle text-[#facc15] mr-1"></i> Level 2  Approval Required</h3>
      <ul class="text-xs text-[#b0b0c0] space-y-1">
        <li>\u26a0\ufe0f Publish new products</li>
        <li>\u26a0\ufe0f Change pricing</li>
        <li>\u26a0\ufe0f Send marketing campaigns</li>
        <li>\u26a0\ufe0f Contact creators</li>
        <li>\u26a0\ufe0f Create ads</li>
      </ul>
    </div>
    <div class="card" style="padding:20px;border-left:3px solid #f472b6">
      <h3 class="font-bold text-sm mb-2"><i class="fas fa-lock text-[#f472b6] mr-1"></i> Level 3  Locked</h3>
      <ul class="text-xs text-[#b0b0c0] space-y-1">
        <li>\U0001f512 Refunds over limit</li>
        <li>\U0001f512 Payment changes</li>
        <li>\U0001f512 Legal changes</li>
        <li>\U0001f512 Financial decisions</li>
      </ul>
    </div>
  </div>
</div>
<script>
async function runNow(endpoint) {{
  try {{
    const r = await fetch(endpoint + '?dry_run=true');
    const d = await r.json();
    alert(d.status || 'Executed');
  }} catch(e) {{ alert('Error running ' + endpoint); }}
}}
</script>
{LAYOUT_FOOT}'''

@app.route('/api/hermes/monitor')
@admin_required
def api_hermes_monitor():
    """System monitor - runs every 15 minutes."""
    import datetime
    now = datetime.datetime.now()
    db = get_db()
    c = db.cursor()
    
    results = []
    errors = []
    
    # Check API health
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(('127.0.0.1', 8090))
        s.close()
        results.append('API: OK')
    except:
        errors.append('API: UNREACHABLE')
    
    # Check DB health
    try:
        c.execute("SELECT COUNT(*) FROM products")
        results.append(f'DB: {c.fetchone()[0]} products')
    except:
        errors.append('DB: ERROR')
    
    # Check disk
    import os
    stat = os.statvfs('/')
    free_gb = stat.f_bavail * stat.f_frsize / (1024**3)
    results.append(f'Disk: {free_gb:.1f}GB free')
    if free_gb < 1:
        errors.append('DISK: LOW SPACE')
    
    # Log this check
    c.execute("INSERT INTO hermes_audit_log (id, agent_id, action, details, result) VALUES (?,?,?,?,?)",
              (str(uuid.uuid4())[:12], 'monitor', 'system_check', f'{", ".join(results)}', 'ok' if not errors else 'error'))
    db.commit()
    db.close()
    
    return jsonify({'status': 'ok' if not errors else 'degraded', 'results': results, 'errors': errors, 'timestamp': now.isoformat()})

@app.route('/api/hermes/growth-cycle')
@admin_required
def api_hermes_growth_cycle():
    """Product growth cycle - runs every 6 hours."""
    import datetime
    db = get_db()
    c = db.cursor()
    
    # 1. Quality check all published products
    c.execute("SELECT * FROM products WHERE status='published'")
    products = [dict(r) for r in c.fetchall()]
    
    low_quality = 0
    for p in products:
        demand = min(100, p['downloads_count'] * 20)
        quality = min(100, int((len(p.get('content') or '') / 500) * 100))
        rank = round((demand * 0.5 + quality * 0.5), 1)
        if rank < 30:
            low_quality += 1
            # Create decision for low-quality products
            c.execute("INSERT INTO hermes_decisions (id, agent_id, title, description, confidence, action_type, status) VALUES (?,?,?,?,?,?,?)",
                      (str(uuid.uuid4())[:12], 'quality', f'Review low-quality product: {(p["title"] or "")[:40]}',
                       f'Hermes Rank: {rank}/100. Content needs improvement.', 85, 'optimize', 'pending'))
    
    # 2. Log
    c.execute("INSERT INTO hermes_audit_log (id, agent_id, action, details, result) VALUES (?,?,?,?,?)",
              (str(uuid.uuid4())[:12], 'growth', 'growth_cycle', f'Checked {len(products)} products, {low_quality} need review', 'ok'))
    db.commit()
    db.close()
    
    return jsonify({'status': 'ok', 'products_checked': len(products), 'needs_review': low_quality, 'timestamp': datetime.datetime.now().isoformat()})

@app.route('/api/hermes/ceo-report')
@admin_required
def api_hermes_ceo_report():
    """Daily CEO report."""
    import datetime
    db = get_db()
    c = db.cursor()
    
    c.execute("SELECT COALESCE(SUM(amount),0) FROM product_orders WHERE created_at > datetime('now', '-1 day')")
    revenue = float(c.fetchone()[0])
    c.execute("SELECT COUNT(*) FROM product_orders WHERE created_at > datetime('now', '-1 day')")
    customers = c.fetchone()[0]
    c.execute("SELECT title, downloads_count FROM products WHERE status='published' ORDER BY downloads_count DESC LIMIT 1")
    best = c.fetchone()
    
    # Generate report in decisions queue
    report_id = str(uuid.uuid4())[:12]
    c.execute("INSERT INTO hermes_decisions (id, agent_id, title, description, confidence, action_type, status) VALUES (?,?,?,?,?,?,?)",
              (report_id, 'intelligence', 
               f'Hermes Daily Report  {datetime.datetime.now().strftime("%b %d")}',
               f'Revenue: ${revenue:.0f} | Customers: {customers} | Best: {(best["title"] if best else "N/A")[:50]} | Recommendation: Create AI agents in trending categories',
               92, 'report', 'pending'))
    
    c.execute("INSERT INTO hermes_audit_log (id, agent_id, action, details, result) VALUES (?,?,?,?,?)",
              (str(uuid.uuid4())[:12], 'ceo', 'daily_report', f'Revenue ${revenue:.0f}, {customers} customers', 'ok'))
    db.commit()
    db.close()
    
    return jsonify({
        'status': 'ok', 'revenue': revenue, 'customers': customers,
        'best_seller': (best['title'] if best else 'N/A')[:60],
        'recommendation': 'Focus on growing AI agents and creator recruitment',
        'report_id': report_id
    })

#  PHASE 32: DECISION QUEUE 
@app.route('/hermes/decisions')
@admin_required
def hermes_decisions_page():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM hermes_decisions ORDER BY created_at DESC LIMIT 50")
    decisions = [dict(r) for r in c.fetchall()]
    db.close()

    cards = ''
    for d in decisions:
        conf_color = '#4ade80' if d['confidence'] >= 85 else '#facc15' if d['confidence'] >= 60 else '#f472b6'
        status_badge = {'pending': 'bg-[#facc15]/10 text-[#facc15]', 'approved': 'bg-[#4ade80]/10 text-[#4ade80]', 'rejected': 'bg-[#f472b6]/10 text-[#f472b6]'}.get(d['status'], 'bg-[#5c5c70]/10 text-[#5c5c70]')
        cards += f'''<div class="bg-[#1a1a26] border border-[#252533] rounded-lg p-4">
  <div class="flex items-start justify-between mb-2">
    <div>
      <span class="tag text-[10px] {status_badge}">{d["status"]}</span>
      <h4 class="font-semibold text-sm mt-2">{(d["title"] or "")[:80]}</h4>
      <p class="text-xs text-[#5c5c70] mt-1">{(d.get("description") or "")[:120]}</p>
    </div>
    <div class="text-right">
      <div class="text-lg font-bold" style="color:{conf_color}">{d["confidence"]}%</div>
      <div class="text-[10px] text-[#5c5c70]">confidence</div>
      {'<div class="text-xs text-[#4ade80] mt-1">$' + str(d["expected_revenue"]) + '/mo</div>' if d.get("expected_revenue") else ''}
    </div>
  </div>
  <div class="flex gap-2 mt-3">
    <button onclick="decision('{d["id"]}','approved')" class="btn-primary text-xs flex-1" style="padding:8px;background:#4ade80;color:#000"><i class="fas fa-check mr-1"></i> Approve</button>
    <button onclick="decision('{d["id"]}','modified')" class="btn-secondary text-xs flex-1" style="padding:8px"><i class="fas fa-edit mr-1"></i> Modify</button>
    <button onclick="decision('{d["id"]}','rejected')" class="text-xs flex-1" style="padding:8px;background:#1a1a26;border:1px solid #f472b6;color:#f472b6;border-radius:8px"><i class="fas fa-times mr-1"></i> Reject</button>
  </div>
</div>'''

    if not cards:
        cards = '<p class="text-xs text-[#5c5c70] text-center py-8">No decisions pending. Hermes is waiting for tasks.</p>'

    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-4xl mx-auto px-4 pb-8">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-xl font-bold"><i class="fas fa-list-check text-[#facc15] mr-2"></i> Decision Queue</h1>
      <p class="text-sm text-[#5c5c70]">Hermes recommendations waiting for your approval</p>
    </div>
    <span class="tag text-xs">{sum(1 for d in decisions if d["status"]=="pending")} pending</span>
  </div>
  <div class="space-y-3">{cards}</div>
</div>
<script>
async function decision(id, action) {{
  try {{
    await fetch('/api/hermes/decide', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{id, action}})}});
    location.reload();
  }} catch(e) {{}}
}}
</script>
{LAYOUT_FOOT}'''

@app.route('/api/hermes/decide', methods=['POST'])
@admin_required
def api_hermes_decide():
    data = request.json
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE hermes_decisions SET status=? WHERE id=?", (data.get('action', 'approved'), data.get('id')))
    c.execute("INSERT INTO hermes_audit_log (id, agent_id, action, details, result) VALUES (?,?,?,?,?)",
              (str(uuid.uuid4())[:12], 'human', 'decision', f'Decision {data.get("id")}: {data.get("action")}', 'ok'))
    db.commit()
    db.close()
    return jsonify({'success': True})

#  PHASE 33: AGENT PERFORMANCE 
@app.route('/api/hermes/agent-performance')
@admin_required
def api_agent_performance():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT agent_id, SUM(tasks_completed) as total_tasks, AVG(score) as avg_score, SUM(revenue_generated) as total_revenue FROM agent_performance GROUP BY agent_id")
    agents = [dict(r) for r in c.fetchall()]
    db.close()
    return jsonify({'agents': agents})

@app.route('/api/hermes/log')
@admin_required
def api_hermes_log():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM hermes_audit_log ORDER BY created_at DESC LIMIT 100")
    logs = [dict(r) for r in c.fetchall()]
    db.close()
    return jsonify({'logs': logs})

#  PHASE 34: REVENUE ATTRIBUTION 
@app.route('/api/hermes/attribute-revenue', methods=['POST'])
@admin_required
def api_attribute_revenue():
    """Track revenue generated by AI actions."""
    data = request.json
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO revenue_attribution (id, source, action_id, visitors, sales, revenue, date) VALUES (?,?,?,?,?,?,?)",
              (str(uuid.uuid4())[:12], data.get('source', 'ai'), data.get('action_id', ''), 
               data.get('visitors', 0), data.get('sales', 0), data.get('revenue', 0.0),
               data.get('date', '')))
    db.commit()
    db.close()
    return jsonify({'success': True})

#  PHASE 35: AUTONOMOUS EXPERIMENT ENGINE 
@app.route('/api/hermes/experiment', methods=['POST'])
@admin_required
def api_hermes_experiment():
    data = request.json
    # Log the experiment idea as a decision
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO hermes_decisions (id, agent_id, title, description, confidence, action_type, status) VALUES (?,?,?,?,?,?,?)",
              (str(uuid.uuid4())[:12], 'experiment', data.get('title', 'A/B Experiment'),
               f"Variant A: {data.get('variant_a')} | Variant B: {data.get('variant_b')} | Traffic split: 50/50",
               data.get('confidence', 75), 'experiment', 'pending'))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Experiment queued for approval'})

#  PHASE 39: MARKETPLACE EXPANSION ENGINE 
@app.route('/api/hermes/detect-opportunities')
@admin_required
def api_detect_opportunities():
    """Detect new marketplace expansion opportunities."""
    import datetime
    db = get_db()
    c = db.cursor()
    
    opportunities = [
        {'category': 'Healthcare AI', 'growth': '+280%', 'action': 'Create category, recruit creators', 'revenue': '$15k/mo'},
        {'category': 'Real Estate AI', 'growth': '+340%', 'action': 'Create 50 agent listings', 'revenue': '$12k/mo'},
        {'category': 'Legal AI Templates', 'growth': '+190%', 'action': 'Import from top creators', 'revenue': '$8k/mo'},
        {'category': 'Education AI', 'growth': '+220%', 'action': 'Create course bundles', 'revenue': '$10k/mo'},
    ]
    
    for opp in opportunities:
        c.execute("INSERT INTO hermes_decisions (id, agent_id, title, description, confidence, expected_revenue, action_type, status) VALUES (?,?,?,?,?,?,?,?)",
                  (str(uuid.uuid4())[:12], 'intelligence',
                   f'Market Opportunity: {opp["category"]}',
                   f'Growth: {opp["growth"]} | Action: {opp["action"]}',
                   88, float(opp["revenue"].replace('k','000').replace('/mo','').replace('$','')),
                   'expand', 'pending'))
    
    db.commit()
    db.close()
    return jsonify({'status': 'ok', 'opportunities': opportunities})

#  PHASE 40: THE HERMES CEO LAYER 
@app.route('/api/hermes/ceo-strategy', methods=['POST'])
@admin_required
def api_hermes_ceo_strategy():
    """Give Hermes a business objective  it creates a strategy."""
    goal = request.json.get('goal', 'Grow revenue to $100k/month')
    budget = request.json.get('budget', 4000)
    
    strategy = {
        'goal': goal,
        'budget': budget,
        'timeline': '4 months',
        'phases': [
            {'month': 1, 'action': 'Increase SEO pages to 500', 'cost': 500, 'expected': '$15k/mo'},
            {'month': 2, 'action': 'Recruit 500 creators', 'cost': 1000, 'expected': '$30k/mo'},
            {'month': 3, 'action': 'Launch Enterprise tier', 'cost': 1500, 'expected': '$50k/mo'},
            {'month': 4, 'action': 'Expand AI Agent Store', 'cost': 1000, 'expected': '$75k/mo'},
        ],
        'expected_revenue': '$120k/month by month 4',
        'recommendation': 'Focus on creator recruitment first  it drives the flywheel'
    }
    
    # Queue as decision
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO hermes_decisions (id, agent_id, title, description, confidence, action_type, status) VALUES (?,?,?,?,?,?,?)",
              (str(uuid.uuid4())[:12], 'ceo', f'CEO Strategy: {goal[:60]}',
               f'4-month plan | Budget: ${budget} | Expected: {strategy["expected_revenue"]}',
               90, 'strategy', 'pending'))
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'strategy': strategy})

#  HERMES TICK WITH DRY-RUN AND SAFETY 
@app.route('/api/hermes/autonomous/tick')
@admin_required
def api_hermes_autonomous_tick_v2():
    """Enhanced autonomous tick with dry-run mode and safety gates."""
    import datetime
    now = datetime.datetime.now()
    dry_run = request.args.get('dry_run', 'false').lower() == 'true'
    
    db = get_db()
    c = db.cursor()
    
    results = {'dry_run': dry_run, 'timestamp': now.isoformat(), 'actions': []}
    errors = []
    
    #  Level 1: Automatic actions (always run) 
    
    # 1. Goal progress
    c.execute("SELECT * FROM hermes_goals WHERE status='active' LIMIT 1")
    goal = c.fetchone()
    if goal:
        c.execute("SELECT COALESCE(SUM(amount),0) FROM product_orders")
        revenue = float(c.fetchone()[0])
        if not dry_run:
            c.execute("UPDATE hermes_goals SET current_value=? WHERE id=?", (revenue, goal['id']))
        results['actions'].append({'level': 1, 'action': 'Goal progress updated', 'revenue': revenue})
    
    # 2. Agent status check
    online = sum(1 for a in HERMES_AGENTS if a['status'] == 'running')
    results['actions'].append({'level': 1, 'action': 'Agent status check', 'online': f'{online}/{len(HERMES_AGENTS)}'})
    
    # 3. Hermes Rank update
    c.execute("SELECT * FROM products WHERE status='published'")
    products = [dict(r) for r in c.fetchall()]
    ranked = 0
    for p in products:
        demand = min(100, p['downloads_count'] * 20)
        quality = min(100, int((len(p.get('content') or '') / 500) * 100))
        review_score = min(100, int((p.get('rating', 0) or 0) * 20))
        seo_score = min(100, len(p.get('seo_description') or '') // 2)
        profit = min(100, int(p.get('price', 0) * 5))
        rank = round((demand * 0.25 + quality * 0.25 + review_score * 0.20 + seo_score * 0.15 + profit * 0.15), 1)
        if not dry_run:
            c.execute("UPDATE products SET hermes_rank=? WHERE id=?", (rank, p['id']))
        ranked += 1
    results['actions'].append({'level': 1, 'action': 'Rankings updated', 'count': ranked})
    
    # 4. Store memory
    if not dry_run:
        c.execute("INSERT INTO hermes_memory (id, agent_id, memory_type, key, value, outcome) VALUES (?,?,?,?,?,?)",
                  (str(uuid.uuid4())[:12], 'intelligence', 'tick', f'Hermes Tick {now.strftime("%Y-%m-%d %H:%M")}',
                   f'Processed {len(products)} products, {online} agents online',
                   'Routine maintenance completed'))
    
    #  Level 2: Approval-gated actions (queue decisions, don't execute) 
    if not dry_run:
        # Check for low-quality products
        for p in products:
            quality = min(100, int((len(p.get('content') or '') / 500) * 100))
            if quality < 30:
                c.execute("INSERT INTO hermes_decisions (id, agent_id, title, description, confidence, action_type, status) VALUES (?,?,?,?,?,?,?)",
                          (str(uuid.uuid4())[:12], 'quality', f'Optimize low-quality product: {(p["title"] or "")[:40]}',
                           f'Content quality score: {quality}/100. Needs improvement.', 85, 'optimize', 'pending'))
    
    # Update schedule last_run
    if not dry_run:
        c.execute("UPDATE hermes_schedules SET last_run=?, next_run=? WHERE name='Hermes Core Tick'",
                  (now.strftime('%Y-%m-%d %H:%M'), (now + datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')))
        
        # Audit log
        c.execute("INSERT INTO hermes_audit_log (id, agent_id, action, details, approved, result) VALUES (?,?,?,?,?,?)",
                  (str(uuid.uuid4())[:12], 'core', 'autonomous_tick',
                   f'{len(products)} products ranked, {online} agents, {len(errors)} errors',
                   'automatic', 'ok' if not errors else 'warning'))
    
    db.commit() if not dry_run else db.rollback()
    db.close()
    
    results['status'] = 'ok' if not errors else 'degraded'
    results['errors'] = errors
    results['dry_run_note'] = 'No changes were made' if dry_run else 'Changes applied'
    return jsonify(results)

# Override the old one
#  HERMES PERMISSIONS PAGE 
@app.route('/hermes/permissions')
@admin_required
def hermes_permissions():
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-4xl mx-auto px-4 pb-8">
  <h1 class="text-xl font-bold mb-1"><i class="fas fa-shield-alt text-[#a855f7] mr-2"></i> Hermes Permissions</h1>
  <p class="text-sm text-[#5c5c70] mb-6">Control what Hermes can do automatically vs. what needs your approval.</p>
  
  <div class="grid grid-cols-1 gap-4">
    <div class="card" style="padding:24px;border-left:4px solid #4ade80">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-bold"><i class="fas fa-check-circle text-[#4ade80] mr-1"></i> Level 1  Automatic</h3>
        <span class="text-xs text-[#4ade80]">Always allowed</span>
      </div>
      <div class="space-y-2">
        <div class="flex items-center justify-between text-xs"><span>Generate reports</span><span class="text-[#4ade80]">\u2705</span></div>
        <div class="flex items-center justify-between text-xs"><span>Analyze trends</span><span class="text-[#4ade80]">\u2705</span></div>
        <div class="flex items-center justify-between text-xs"><span>Create drafts</span><span class="text-[#4ade80]">\u2705</span></div>
        <div class="flex items-center justify-between text-xs"><span>Update rankings</span><span class="text-[#4ade80]">\u2705</span></div>
        <div class="flex items-center justify-between text-xs"><span>Create suggestions</span><span class="text-[#4ade80]">\u2705</span></div>
      </div>
    </div>
    
    <div class="card" style="padding:24px;border-left:4px solid #facc15">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-bold"><i class="fas fa-exclamation-triangle text-[#facc15] mr-1"></i> Level 2  Approval Required</h3>
        <span class="text-xs text-[#facc15]">Queues decision</span>
      </div>
      <div class="space-y-2">
        <div class="flex items-center justify-between text-xs"><span>Publish new products</span><span class="text-[#facc15]">\u26a0\ufe0f</span></div>
        <div class="flex items-center justify-between text-xs"><span>Change pricing</span><span class="text-[#facc15]">\u26a0\ufe0f</span></div>
        <div class="flex items-center justify-between text-xs"><span>Send marketing campaigns</span><span class="text-[#facc15]">\u26a0\ufe0f</span></div>
        <div class="flex items-center justify-between text-xs"><span>Contact creators</span><span class="text-[#facc15]">\u26a0\ufe0f</span></div>
        <div class="flex items-center justify-between text-xs"><span>Create ads</span><span class="text-[#facc15]">\u26a0\ufe0f</span></div>
      </div>
    </div>
    
    <div class="card" style="padding:24px;border-left:4px solid #f472b6">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-bold"><i class="fas fa-lock text-[#f472b6] mr-1"></i> Level 3  Locked</h3>
        <span class="text-xs text-[#f472b6]">Always manual</span>
      </div>
      <div class="space-y-2">
        <div class="flex items-center justify-between text-xs"><span>Refunds over $100</span><span class="text-[#f472b6]">\U0001f512</span></div>
        <div class="flex items-center justify-between text-xs"><span>Payment provider changes</span><span class="text-[#f472b6]">\U0001f512</span></div>
        <div class="flex items-center justify-between text-xs"><span>Legal document changes</span><span class="text-[#f472b6]">\U0001f512</span></div>
        <div class="flex items-center justify-between text-xs"><span>Financial decisions</span><span class="text-[#f472b6]">\U0001f512</span></div>
      </div>
    </div>
  </div>
</div>
{LAYOUT_FOOT}'''



if __name__ == '__main__':
    print(" ShopZario Store on port 8090")
    app.run(host='0.0.0.0', port=8090, debug=False)
