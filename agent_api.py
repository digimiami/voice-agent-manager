#!/usr/bin/env python3
"""
# Diazites Agent API
=========================
RESTful API for AI agents to connect to the Diazites system.
- API key authentication (Bearer tokens)
- Full CRUD on businesses, leads, campaigns
- Reports & analytics
- System settings

Base URL: http://localhost:8086/api/v1
"""

import os, sys, json, sqlite3, uuid, hashlib, time, io, csv
from datetime import datetime, date
from flask import Flask, Blueprint, jsonify, request, render_template_string
from functools import wraps

DB_PATH = "/root/voice-agent-businesses.db"

# ── API Key Management ──

def init_api_keys_table():
    """Ensure the api_keys table exists."""
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            key_hash TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            permissions TEXT DEFAULT 'read,write,admin',
            created_at TEXT DEFAULT (datetime('now')),
            last_used_at TEXT,
            expires_at TEXT,
            active INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'admin'
        )
    """)
    db.commit()
    db.close()

def generate_api_key(name, description="", permissions="read,write", created_by="admin", expires_at=None):
    """Generate a new API key. Returns (key_id, raw_key, key_data)."""
    raw_key = f"dz_{uuid.uuid4().hex}_{uuid.uuid4().hex[:16]}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_id = f"key_{uuid.uuid4().hex[:12]}"

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("""
        INSERT INTO api_keys (id, key_hash, name, description, permissions, created_by, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (key_id, key_hash, name, description, permissions, created_by, expires_at))
    db.commit()
    db.close()

    return key_id, raw_key, {
        'id': key_id,
        'name': name,
        'description': description,
        'permissions': permissions,
        'created_by': created_by,
        'expires_at': expires_at,
        'active': 1
    }

def validate_api_key(raw_key):
    """Validate an API key. Returns key data dict or None."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("SELECT * FROM api_keys WHERE key_hash = ? AND active = 1", (key_hash,))
    row = c.fetchone()
    if not row:
        db.close()
        return None
    # Check expiry
    expires_at = row['expires_at']
    if expires_at and expires_at < datetime.now().isoformat():
        db.close()
        return None
    # Update last_used_at
    c.execute("UPDATE api_keys SET last_used_at = datetime('now') WHERE id = ?", (row['id'],))
    db.commit()
    db.close()
    return dict(row)

def require_api_key(f):
    """Decorator: require a valid API key in Authorization header, OR admin session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        
        # Check admin session first (for admin UI frontend calls)
        from flask import session as flask_session
        if flask_session.get('admin_logged_in'):
            kwargs['api_key'] = {
                'permissions': 'read,write,admin',
                'name': 'Admin UI Session',
                'id': 'admin-session'
            }
            return f(*args, **kwargs)
        
        # Fall back to API key auth
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header. Use: Bearer <your_api_key>'}), 401
        raw_key = auth[7:]
        key_data = validate_api_key(raw_key)
        if not key_data:
            return jsonify({'error': 'Invalid, expired, or revoked API key'}), 401
        kwargs['api_key'] = key_data
        return f(*args, **kwargs)
    return decorated

# ── API Blueprint ──

agent_api = Blueprint('agent_api', __name__, url_prefix='/api/v1')

# ── AUTH ENDPOINTS ──

@agent_api.route('/auth/generate', methods=['POST'])
@require_api_key
def api_generate_key(api_key):
    """Generate a new API key (admin only)."""
    if 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Only admin keys can generate new keys'}), 403

    data = request.get_json(silent=True) or {}
    name = data.get('name', 'Unnamed Key').strip()
    description = data.get('description', '')
    permissions = data.get('permissions', 'read,write')
    expires_in_days = data.get('expires_in_days', 365)

    # Validate permissions
    valid_perms = ['read', 'write', 'admin']
    for p in permissions.split(','):
        if p.strip() not in valid_perms:
            return jsonify({'error': f'Invalid permission: {p}. Valid: read, write, admin'}), 400

    expires_at = None
    if expires_in_days > 0:
        from datetime import timedelta
        expires_at = (datetime.now() + timedelta(days=expires_in_days)).isoformat()

    key_id, raw_key, key_data = generate_api_key(
        name=name,
        description=description,
        permissions=permissions,
        created_by=api_key.get('name', 'admin'),
        expires_at=expires_at
    )

    return jsonify({
        'success': True,
        'key_id': key_id,
        'api_key': raw_key,
        'name': name,
        'permissions': permissions,
        'expires_at': expires_at,
        'warning': 'Save this key now — it will not be shown again!'
    })

@agent_api.route('/auth/keys', methods=['GET'])
@require_api_key
def api_list_keys(api_key):
    """List all API keys (admin only)."""
    if 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Admin permission required'}), 403

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    c.execute("SELECT id, name, description, permissions, created_at, last_used_at, expires_at, active, created_by FROM api_keys ORDER BY created_at DESC")
    keys = [dict(r) for r in c.fetchall()]
    db.close()

    return jsonify({'keys': keys, 'total': len(keys)})

@agent_api.route('/auth/keys/<key_id>', methods=['DELETE', 'POST'])
@require_api_key
def api_revoke_key(api_key, key_id):
    """Revoke an API key (admin only)."""
    if 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Admin permission required'}), 403

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    if request.method == 'POST' and request.args.get('reactivate') == 'true':
        c.execute("UPDATE api_keys SET active = 1 WHERE id = ?", (key_id,))
        msg = 'reactivated'
    else:
        c.execute("UPDATE api_keys SET active = 0 WHERE id = ?", (key_id,))
        msg = 'revoked'

    db.commit()
    affected = c.rowcount
    db.close()

    if affected == 0:
        return jsonify({'error': 'Key not found'}), 404
    return jsonify({'success': True, 'message': f'Key {msg} successfully', 'key_id': key_id})

# ── BUSINESS ENDPOINTS ──

@agent_api.route('/businesses', methods=['GET'])
@require_api_key
def api_list_businesses(api_key):
    """List all businesses with stats."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    c.execute("""
        SELECT b.*, 
               COALESCE(c.calls_made,0) as calls_made, 
               COALESCE(c.appointments_booked,0) as appointments_booked,
               COALESCE(c.total_cost,0) as total_cost,
               COALESCE(c.leads_imported,0) as leads_imported,
               c.status as campaign_status,
               (SELECT COUNT(*) FROM leads WHERE business_id = b.id) as leads_count,
               (SELECT COUNT(*) FROM leads WHERE business_id = b.id AND state = 'NEW') as new_leads_count
        FROM businesses b
        LEFT JOIN campaigns c ON b.id = c.business_id
        ORDER BY b.created_at DESC
    """)
    businesses = [dict(r) for r in c.fetchall()]
    db.close()

    return jsonify({
        'businesses': businesses,
        'total': len(businesses)
    })

@agent_api.route('/businesses/<bid>', methods=['GET'])
@require_api_key
def api_get_business(api_key, bid):
    """Get a single business with full details."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if not biz:
        db.close()
        return jsonify({'error': 'Business not found'}), 404
    biz = dict(biz)

    # Stats
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ?", (bid,))
    biz['leads_count'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ? AND state = 'NEW'", (bid,))
    biz['new_leads_count'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM call_log WHERE business_id = ?", (bid,))
    biz['calls_count'] = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(cost),0) FROM call_log WHERE business_id = ?", (bid,))
    biz['total_cost'] = c.fetchone()[0]
    c.execute("SELECT status FROM campaigns WHERE business_id = ?", (bid,))
    camp = c.fetchone()
    biz['campaign_status'] = camp['status'] if camp else 'idle'

    # Recent calls
    c.execute("SELECT * FROM call_log WHERE business_id = ? ORDER BY created_at DESC LIMIT 10", (bid,))
    biz['recent_calls'] = [dict(r) for r in c.fetchall()]

    db.close()
    return jsonify({'business': biz})

@agent_api.route('/businesses', methods=['POST'])
@require_api_key
def api_create_business(api_key):
    """Create a new business."""
    if 'write' not in api_key.get('permissions', '').split(',') and 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Write permission required'}), 403

    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Business name is required'}), 400

    bid = str(uuid.uuid4())[:12]
    cid = 'camp-' + bid
    industry = data.get('industry', 'general')
    plan = data.get('plan', 'starter')
    monthly_price = int(data.get('monthly_price', 299))
    email = data.get('email', '')
    phone = data.get('phone_number', '')

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    c.execute("""
        INSERT INTO businesses 
        (id, name, industry, phone_number, email, 
         script_template, knowledge_base, plan, monthly_price, status,
         max_tokens, voice_speed, concurrency, calls_included, features_desc, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 200, '1.0', 5, 500, ?, datetime('now'))
    """, (bid, name, industry, phone, email,
          data.get('script_template', f"You are an AI assistant for {name}. Help them book more clients."),
          data.get('knowledge_base', f"Industry: {industry}. Business: {name}."),
          plan, monthly_price,
          data.get('features_desc', f'{plan.title()} plan')))

    c.execute("INSERT INTO campaigns (id, business_id, status) VALUES (?, ?, 'idle')", (cid, bid))
    db.commit()
    db.close()

    return jsonify({
        'success': True,
        'business_id': bid,
        'name': name,
        'message': f'Business "{name}" created successfully'
    }), 201

@agent_api.route('/businesses/<bid>', methods=['PUT'])
@require_api_key
def api_update_business(api_key, bid):
    """Update a business."""
    if 'write' not in api_key.get('permissions', '').split(',') and 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Write permission required'}), 403

    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({'error': 'No fields to update'}), 400

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    allowed_fields = ['name', 'industry', 'phone_number', 'email', 'plan', 'monthly_price',
                      'script_template', 'knowledge_base', 'agent_prompt', 'status',
                      'max_tokens', 'voice_speed', 'concurrency']
    updates = []
    values = []
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])

    if not updates:
        db.close()
        return jsonify({'error': 'No valid fields to update'}), 400

    values.append(bid)
    c.execute(f"UPDATE businesses SET {', '.join(updates)} WHERE id = ?", values)
    db.commit()
    affected = c.rowcount
    db.close()

    if affected == 0:
        return jsonify({'error': 'Business not found'}), 404

    return jsonify({'success': True, 'message': 'Business updated', 'updated_fields': [u.split(' =')[0] for u in updates]})

@agent_api.route('/businesses/<bid>', methods=['DELETE'])
@require_api_key
def api_delete_business(api_key, bid):
    """Delete a business and all its data."""
    if 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Admin permission required to delete businesses'}), 403

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("SELECT name FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if not biz:
        db.close()
        return jsonify({'error': 'Business not found'}), 404

    name = biz[0]
    c.execute("DELETE FROM call_log WHERE business_id = ?", (bid,))
    c.execute("DELETE FROM leads WHERE business_id = ?", (bid,))
    c.execute("DELETE FROM campaigns WHERE business_id = ?", (bid,))
    c.execute("DELETE FROM businesses WHERE id = ?", (bid,))
    db.commit()
    db.close()

    return jsonify({'success': True, 'message': f'Business "{name}" and all associated data deleted'})

# ── LEADS ENDPOINTS ──

@agent_api.route('/leads', methods=['GET'])
@require_api_key
def api_list_leads(api_key):
    """List all leads with optional filters."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    business_id = request.args.get('business_id', '')
    state = request.args.get('state', '')
    limit = min(int(request.args.get('limit', 100)), 1000)
    offset = int(request.args.get('offset', 0))

    query = "SELECT l.*, b.name as business_name FROM leads l LEFT JOIN businesses b ON l.business_id = b.id WHERE 1=1"
    params = []

    if business_id:
        query += " AND l.business_id = ?"
        params.append(business_id)
    if state:
        query += " AND l.state = ?"
        params.append(state)

    # Count total
    count_query = query.replace("SELECT l.*, b.name as business_name", "SELECT COUNT(*)")
    c.execute(count_query, params)
    total = c.fetchone()[0]

    query += " ORDER BY l.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    c.execute(query, params)
    leads = [dict(r) for r in c.fetchall()]
    db.close()

    return jsonify({
        'leads': leads,
        'total': total,
        'limit': limit,
        'offset': offset
    })

@agent_api.route('/leads', methods=['POST'])
@require_api_key
def api_add_leads(api_key):
    """Add leads to a business."""
    if 'write' not in api_key.get('permissions', '').split(',') and 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Write permission required'}), 403

    data = request.get_json(silent=True) or {}
    business_id = data.get('business_id', '').strip()
    leads_data = data.get('leads', [])

    if not business_id:
        return jsonify({'error': 'business_id is required'}), 400
    if not leads_data or not isinstance(leads_data, list):
        return jsonify({'error': 'leads must be a non-empty array'}), 400

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    # Verify business exists
    c.execute("SELECT id FROM businesses WHERE id = ?", (business_id,))
    if not c.fetchone():
        db.close()
        return jsonify({'error': 'Business not found'}), 404

    added = 0
    errors = []
    for item in leads_data:
        if isinstance(item, str):
            phone = item.strip()
            name = ''
            biz_name = ''
        elif isinstance(item, dict):
            phone = item.get('phone', '').strip()
            name = item.get('name', '').strip()
            biz_name = item.get('business_name', '').strip()
        else:
            errors.append({'item': item, 'error': 'Invalid format'})
            continue

        # Clean phone
        phone = phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        if not phone.startswith('+'):
            phone = '+1' + phone.lstrip('1')
        if len(phone) < 10:
            errors.append({'item': item, 'error': f'Invalid phone: {phone}'})
            continue

        lid = f"lead_{uuid.uuid4().hex[:12]}"
        try:
            c.execute("INSERT OR IGNORE INTO leads (id, business_id, phone, name, business_name, state) VALUES (?,?,?,?,?,'NEW')",
                      (lid, business_id, phone, name, biz_name))
            if c.rowcount > 0:
                added += 1
            else:
                errors.append({'item': item, 'error': 'Duplicate lead (phone already exists)'})
        except Exception as e:
            errors.append({'item': item, 'error': str(e)})

    db.commit()
    db.close()

    return jsonify({
        'success': True,
        'business_id': business_id,
        'leads_added': added,
        'errors': errors if errors else None,
        'message': f'{added} lead(s) added'
    }), 201 if added > 0 else 200

# ── REPORTS ENDPOINTS ──

@agent_api.route('/reports/overview', methods=['GET'])
@require_api_key
def api_report_overview(api_key):
    """System overview report with key metrics."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    c.execute("SELECT COUNT(*) FROM businesses")
    total_businesses = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'running'")
    active_campaigns = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM leads")
    total_leads = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(cost),0) FROM call_log")
    total_ai_cost = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM leads WHERE state = 'NEW'")
    new_leads = c.fetchone()[0]

    # Active vs inactive businesses
    c.execute("SELECT status, COUNT(*) as cnt FROM businesses GROUP BY status")
    status_counts = {r['status']: r['cnt'] for r in c.fetchall()}

    # Plan breakdown
    c.execute("SELECT plan, COUNT(*) as cnt FROM businesses GROUP BY plan")
    plan_counts = {r['plan']: r['cnt'] for r in c.fetchall()}

    # Revenue estimation
    c.execute("SELECT COALESCE(SUM(monthly_price),0) FROM businesses WHERE status = 'active'")
    total_mrr = c.fetchone()[0]

    db.close()

    return jsonify({
        'report_type': 'overview',
        'generated_at': datetime.now().isoformat(),
        'total_businesses': total_businesses,
        'active_campaigns': active_campaigns,
        'total_leads': total_leads,
        'new_leads': new_leads,
        'total_ai_cost': round(total_ai_cost, 2),
        'estimated_mrr': total_mrr,
        'business_statuses': status_counts,
        'plan_breakdown': plan_counts
    })

@agent_api.route('/reports/billing', methods=['GET'])
@require_api_key
def api_report_billing(api_key):
    """Billing report per business."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    c.execute("""
        SELECT b.id, b.name, b.plan, b.monthly_price, b.status,
               COALESCE(c.calls_made,0) as calls_made,
               COALESCE(c.total_cost,0) as ai_cost,
               COALESCE((SELECT COUNT(*) FROM leads WHERE business_id = b.id),0) as leads_count
        FROM businesses b
        LEFT JOIN campaigns c ON b.id = c.business_id
        ORDER BY b.monthly_price DESC
    """)
    businesses = []
    for r in c.fetchall():
        biz = dict(r)
        price = int(biz.get('monthly_price') or 0)
        ai_cost = float(biz.get('ai_cost') or 0)
        biz['profit'] = round(price - ai_cost, 2)
        biz['margin'] = round((biz['profit'] / price * 100), 1) if price > 0 else 0
        businesses.append(biz)
    db.close()

    total_revenue = sum(b.get('monthly_price', 0) or 0 for b in businesses if b.get('status') == 'active')
    total_costs = sum(b.get('ai_cost', 0) or 0 for b in businesses)
    total_profit = round(total_revenue - total_costs, 2)

    return jsonify({
        'report_type': 'billing',
        'generated_at': datetime.now().isoformat(),
        'total_revenue': total_revenue,
        'total_costs': round(total_costs, 2),
        'total_profit': total_profit,
        'overall_margin': round((total_profit / total_revenue * 100), 1) if total_revenue > 0 else 0,
        'businesses': businesses
    })

@agent_api.route('/reports/calls', methods=['GET'])
@require_api_key
def api_report_calls(api_key):
    """Call log report with filters."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    business_id = request.args.get('business_id', '')
    limit = min(int(request.args.get('limit', 50)), 500)
    offset = int(request.args.get('offset', 0))

    query = """SELECT cl.*, b.name as business_name 
               FROM call_log cl 
               LEFT JOIN businesses b ON cl.business_id = b.id 
               WHERE 1=1"""
    params = []

    if business_id:
        query += " AND cl.business_id = ?"
        params.append(business_id)

    # Count
    c.execute(query.replace("SELECT cl.*, b.name as business_name", "SELECT COUNT(*)"), params)
    total = c.fetchone()[0]

    query += " ORDER BY cl.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    c.execute(query, params)
    calls = [dict(r) for r in c.fetchall()]
    db.close()

    return jsonify({
        'calls': calls,
        'total': total,
        'limit': limit,
        'offset': offset
    })

# ── CAMPAIGN ENDPOINTS ──

@agent_api.route('/campaigns/status', methods=['GET'])
@require_api_key
def api_campaign_status(api_key):
    """Get all campaign statuses."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    c.execute("""
        SELECT b.id, b.name, c.status, c.calls_made, c.appointments_booked, 
               c.total_cost, c.started_at, c.leads_imported,
               (SELECT COUNT(*) FROM leads WHERE business_id = b.id AND state = 'NEW') as pending_leads
        FROM businesses b
        JOIN campaigns c ON b.id = c.business_id
        ORDER BY c.status, b.name
    """)
    campaigns = [dict(r) for r in c.fetchall()]
    db.close()

    running = [c for c in campaigns if c['status'] == 'running']
    idle = [c for c in campaigns if c['status'] != 'running']

    return jsonify({
        'running': running,
        'idle': idle,
        'total': len(campaigns)
    })

@agent_api.route('/campaigns/<bid>/start', methods=['POST'])
@require_api_key
def api_campaign_start(api_key, bid):
    """Start a campaign for a business."""
    if 'write' not in api_key.get('permissions', '').split(',') and 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Write permission required'}), 403

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ? AND state = 'NEW'", (bid,))
    count = c.fetchone()[0]
    if count == 0:
        db.close()
        return jsonify({'error': 'No pending leads for this business. Add leads first.'}), 400

    c.execute("UPDATE campaigns SET status='running', started_at=datetime('now') WHERE business_id=?", (bid,))
    db.commit()
    db.close()

    return jsonify({
        'success': True,
        'message': f'Campaign started for {count} leads',
        'business_id': bid,
        'leads_count': count
    })

@agent_api.route('/campaigns/<bid>/stop', methods=['POST'])
@require_api_key
def api_campaign_stop(api_key, bid):
    """Stop a campaign."""
    if 'write' not in api_key.get('permissions', '').split(',') and 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Write permission required'}), 403

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("UPDATE campaigns SET status='stopped' WHERE business_id=?", (bid,))
    db.commit()
    db.close()

    return jsonify({'success': True, 'message': 'Campaign stopped', 'business_id': bid})

# ── SETTINGS / INFO ENDPOINTS ──

@agent_api.route('/settings', methods=['GET'])
@require_api_key
def api_settings(api_key):
    """Get system settings (industries, tiers, config)."""
    return jsonify({
        'industries': {
            'dentist': 'Reduce no-shows with automated booking',
            'plumber': 'Never miss emergency calls',
            'roofer': 'Capture storm season leads',
            'hvac': 'Handle after-hours emergencies',
            'lawyer': 'Qualify leads automatically',
            'real_estate': 'Capture buyer/seller leads 24/7',
            'auto_mechanic': 'Book service appointments overnight',
            'cleaning': 'Recurring client pipeline automation',
            'pest_control': 'Emergency response automation',
            'landscaper': 'Book estimates while on the job',
            'general': 'General business lead generation'
        },
        'pricing_tiers': {
            'starter': {'name': 'Starter', 'price': 299, 'calls_included': 500},
            'pro': {'name': 'Pro', 'price': 599, 'calls_included': 2000},
            'premium': {'name': 'Premium', 'price': 999, 'calls_included': 5000},
            'enterprise': {'name': 'Enterprise', 'price': 1999, 'calls_included': 15000},
            'custom': {'name': 'Custom', 'price': 0, 'calls_included': 0}
        },
        'api_version': 'v1',
        'docs_url': '/admin?tab=agent-api'
    })

@agent_api.route('/health', methods=['GET'])
def api_health():
    """Health check endpoint (no auth required)."""
    db_ok = False
    try:
        db = sqlite3.connect(DB_PATH)
        c = db.cursor()
        c.execute("SELECT COUNT(*) FROM businesses")
        biz_count = c.fetchone()[0]
        db.close()
        db_ok = True
    except:
        biz_count = 0

    return jsonify({
        'status': 'healthy' if db_ok else 'degraded',
        'service': 'Diazites Agent API',
        'version': 'v1',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected' if db_ok else 'error',
        'businesses_count': biz_count
    })

# ── EXPORT ENDPOINTS ──

@agent_api.route('/export/businesses', methods=['GET'])
@require_api_key
def api_export_businesses(api_key):
    """Export businesses as CSV."""
    if 'read' not in api_key.get('permissions', '').split(',') and 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Read permission required'}), 403

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    c.execute("""
        SELECT b.id, b.name, b.industry, b.plan, b.monthly_price, b.status, b.email, b.phone_number,
               b.calls_included, b.created_at,
               COALESCE(c.calls_made,0) as calls_made,
               COALESCE(c.appointments_booked,0) as appointments_booked,
               COALESCE(c.total_cost,0) as total_cost,
               (SELECT COUNT(*) FROM leads WHERE business_id = b.id) as total_leads
        FROM businesses b
        LEFT JOIN campaigns c ON b.id = c.business_id
        ORDER BY b.name
    """)
    rows = c.fetchall()
    db.close()

    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows([dict(r) for r in rows])

    return jsonify({
        'csv': output.getvalue(),
        'count': len(rows),
        'filename': f'diazites_businesses_export_{date.today().isoformat()}.csv'
    })


# ── Helpers for auth middleware ──

def api_key_required(permission='read'):
    """Decorator factory for requiring API key with specific permission."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                return jsonify({'error': 'Missing Authorization header. Use: Bearer <key>'}), 401
            key_data = validate_api_key(auth[7:])
            if not key_data:
                return jsonify({'error': 'Invalid or expired API key'}), 401
            perms = key_data.get('permissions', '').split(',')
            if 'admin' not in perms and permission not in perms:
                return jsonify({'error': f'Insufficient permissions. Required: {permission}'}), 403
            kwargs['api_key'] = key_data
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── Initialize on import ──
init_api_keys_table()
