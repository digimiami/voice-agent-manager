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
from diazites_prompt import build_diazites_prompt

DB_PATH = "/root/voice-agent-businesses.db"

# ── VAPI Configuration ──
VAPI_BASE = "https://api.vapi.ai"

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

# ── Git auto-commit helper ──
def git_auto_commit(message):
    """Auto-commit and push changes to GitHub."""
    import subprocess
    try:
        subprocess.run(["git", "-C", "/root/voice-agent-manager", "add", "-A"],
                       capture_output=True, timeout=10)
        subprocess.run(["git", "-C", "/root/voice-agent-manager", "commit",
                       "-m", f"api: {message[:80]}"],
                       capture_output=True, timeout=10)
        subprocess.run(["git", "-C", "/root/voice-agent-manager", "push", "origin", "main"],
                       capture_output=True, timeout=30)
    except:
        pass  # don't break the API if git fails

# ── API Key Management ──

def init_api_keys_table():
    """Ensure the api_keys table exists."""
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_api_keys (
            id TEXT PRIMARY KEY,
            key_hash TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            permissions TEXT DEFAULT 'read,write,admin',
            created_at TEXT DEFAULT (datetime('now')),
            last_used_at TEXT,
            expires_at TEXT,
            active INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'admin',
            business_id TEXT DEFAULT ''
        )
    """)
    db.commit()
    # Add business_id column if missing (migration)
    try:
        c.execute("ALTER TABLE agent_api_keys ADD COLUMN business_id TEXT DEFAULT ''")
        db.commit()
    except:
        pass
    db.close()

def generate_api_key(name, description="", permissions="read,write", created_by="admin", expires_at=None, business_id=""):
    """Generate a new API key. Returns (key_id, raw_key, key_data)."""
    raw_key = f"dz_{uuid.uuid4().hex}_{uuid.uuid4().hex[:16]}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_id = f"key_{uuid.uuid4().hex[:12]}"

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("""
        INSERT INTO agent_api_keys (id, key_hash, name, description, permissions, created_by, expires_at, business_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (key_id, key_hash, name, description, permissions, created_by, expires_at, business_id))
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
    db.row_factory = sqlite3.Row
    c = db.cursor()
    # Check admin-generated keys first
    c.execute("SELECT * FROM agent_api_keys WHERE key_hash = ? AND active = 1", (key_hash,))
    row = c.fetchone()
    if not row:
        # Check user-generated keys (from dashboard)
        c.execute("SELECT * FROM user_api_keys WHERE key_hash = ? AND active = 1", (key_hash,))
        row = c.fetchone()
        if row:
            # Update last_used_at in user_api_keys
            c.execute("UPDATE user_api_keys SET last_used_at = datetime('now') WHERE id = ?", (row['id'],))
            db.commit()
            data = dict(row)
            db.close()
            return data
        db.close()
        return None
    # Check expiry
    expires_at = row['expires_at']
    if expires_at and expires_at < datetime.now().isoformat():
        db.close()
        return None
    # Update last_used_at for admin keys
    c.execute("UPDATE agent_api_keys SET last_used_at = datetime('now') WHERE id = ?", (row['id'],))
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

    git_auto_commit(f'generated API key {name}')
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
    c.execute("SELECT id, name, description, permissions, created_at, last_used_at, expires_at, active, created_by FROM agent_api_keys ORDER BY created_at DESC")
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
        c.execute("UPDATE agent_api_keys SET active = 1 WHERE id = ?", (key_id,))
        msg = 'reactivated'
    else:
        c.execute("UPDATE agent_api_keys SET active = 0 WHERE id = ?", (key_id,))
        msg = 'revoked'

    db.commit()
    affected = c.rowcount
    db.close()

    if affected == 0:
        return jsonify({'error': 'Key not found'}), 404
    git_auto_commit(f'{msg} API key {key_id}')
    return jsonify({'success': True, 'message': f'Key {msg} successfully', 'key_id': key_id})


@agent_api.route('/auth/keys/<key_id>/delete', methods=['DELETE'])
@require_api_key
def api_delete_key(api_key, key_id):
    """Permanently delete an API key from the database (admin only)."""
    if 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Admin permission required'}), 403
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("DELETE FROM agent_api_keys WHERE id = ?", (key_id,))
    db.commit()
    affected = c.rowcount
    db.close()
    if affected == 0:
        return jsonify({'error': 'Key not found'}), 404
    git_auto_commit(f'deleted API key {key_id}')
    return jsonify({'success': True, 'message': 'Key permanently deleted', 'key_id': key_id})


# ── Generate USER-level API key (scoped to a business) ──

@agent_api.route('/auth/generate-user-key', methods=['POST'])
@require_api_key
def api_generate_user_key(api_key):
    """Generate an API key scoped to a specific business (admin creates it for the user)."""
    if 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Admin permission required'}), 403

    data = request.get_json(silent=True) or {}
    name = data.get('name', 'User API Key').strip()
    business_id = data.get('business_id', '').strip()

    if not business_id:
        return jsonify({'error': 'business_id is required'}), 400

    # Verify business exists
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("SELECT name FROM businesses WHERE id = ?", (business_id,))
    biz = c.fetchone()
    db.close()
    if not biz:
        return jsonify({'error': 'Business not found'}), 404

    key_id, raw_key, key_data = generate_api_key(
        name=name, description=f"User key for {biz[0]}",
        permissions='read,write', created_by=api_key.get('name', 'admin'),
        expires_at=None, business_id=business_id
    )

    git_auto_commit(f'generated user API key for {biz[0]}')
    return jsonify({
        'success': True, 'key_id': key_id, 'api_key': raw_key,
        'name': name, 'business_id': business_id,
        'permissions': 'read,write',
        'warning': 'Save this key now — it will not be shown again!'
    })


# ── USER / ME ENDPOINTS (scoped to the key's business) ──

@agent_api.route('/me/business', methods=['GET'])
@require_api_key
def api_me_get_business(api_key):
    """Get the user's own business info (scoped by API key's business_id)."""
    bid = api_key.get('business_id', '')
    if not bid:
        return jsonify({'error': 'This API key is not scoped to a business'}), 403

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    db.close()
    if not biz:
        return jsonify({'error': 'Business not found'}), 404

    return jsonify({'success': True, 'business': dict(biz)})


@agent_api.route('/me/business', methods=['PUT'])
@require_api_key
def api_me_update_business(api_key):
    """Update the user's own business settings."""
    bid = api_key.get('business_id', '')
    if not bid:
        return jsonify({'error': 'This API key is not scoped to a business'}), 403

    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({'error': 'No fields to update'}), 400

    allowed = ['name', 'industry', 'phone_number', 'email', 'script_template',
               'knowledge_base', 'agent_prompt', 'voice_id', 'voice_speed',
               'temperature', 'max_tokens', 'timezone', 'call_window_start', 'call_window_end']
    updates = []
    values = []
    for field in allowed:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])
    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    values.append(bid)
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute(f"UPDATE businesses SET {', '.join(updates)} WHERE id = ?", values)
    db.commit()
    db.close()

    git_auto_commit(f'user updated business {bid}')
    return jsonify({'success': True, 'message': 'Business updated', 'updated_fields': [u.split(' =')[0] for u in updates]})


@agent_api.route('/me/leads', methods=['GET'])
@require_api_key
def api_me_list_leads(api_key):
    """Get the user's own leads."""
    bid = api_key.get('business_id', '')
    if not bid:
        return jsonify({'error': 'This API key is not scoped to a business'}), 403

    limit = min(int(request.args.get('limit', 50)), 500)
    state = request.args.get('state', '')

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    query = "SELECT * FROM leads WHERE business_id = ?"
    params = [bid]
    if state:
        query += " AND state = ?"
        params.append(state)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    c.execute(query, params)
    leads = [dict(r) for r in c.fetchall()]
    db.close()
    return jsonify({'success': True, 'leads': leads, 'total': len(leads)})


@agent_api.route('/me/calls', methods=['GET'])
@require_api_key
def api_me_list_calls(api_key):
    """Get the user's own call history."""
    bid = api_key.get('business_id', '')
    if not bid:
        return jsonify({'error': 'This API key is not scoped to a business'}), 403

    limit = min(int(request.args.get('limit', 20)), 100)

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    c.execute("""
        SELECT cl.*, l.phone as lead_phone, l.name as lead_name
        FROM call_log cl
        LEFT JOIN leads l ON cl.lead_id = l.id
        WHERE cl.business_id = ?
        ORDER BY cl.created_at DESC LIMIT ?
    """, (bid, limit))
    calls = [dict(r) for r in c.fetchall()]
    db.close()
    return jsonify({'success': True, 'calls': calls, 'total': len(calls)})


@agent_api.route('/me/settings', methods=['GET'])
@require_api_key
def api_me_get_settings(api_key):
    """Get the user's own settings (plan, minutes, usage)."""
    bid = api_key.get('business_id', '')
    if not bid:
        return jsonify({'error': 'This API key is not scoped to a business'}), 403

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    c.execute("SELECT plan, monthly_price, vapi_assistant_id, vapi_phone_id, phone_number, name, email FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if not biz:
        db.close()
        return jsonify({'error': 'Business not found'}), 404

    # extra_minutes column may not exist on older DBs
    try:
        c.execute("SELECT extra_minutes FROM businesses WHERE id = ?", (bid,))
        extra = (c.fetchone() or [0])[0] or 0
    except:
        extra = 0

    c.execute("SELECT COALESCE(SUM(duration),0) FROM call_log WHERE business_id = ?", (bid,))
    total_duration = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(cost),0) FROM call_log WHERE business_id = ?", (bid,))
    total_cost = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ?", (bid,))
    leads_count = c.fetchone()[0]
    db.close()

    pricing_tiers = {
        "starter": {"name": "Starter", "minutes": 250, "price": 97},
        "pro": {"name": "Professional", "minutes": 1000, "price": 197},
        "premium": {"name": "Premium", "minutes": 2500, "price": 297},
        "enterprise": {"name": "Enterprise", "minutes": 7500, "price": 497},
    }
    plan_key = (biz['plan'] or 'starter').lower()
    tier = pricing_tiers.get(plan_key, pricing_tiers['starter'])
    extra = biz['extra_minutes'] or 0
    limit_min = tier['minutes'] + extra
    used_min = total_duration // 60

    return jsonify({
        'success': True,
        'settings': {
            'plan': tier['name'], 'plan_key': plan_key,
            'price_monthly': tier['price'],
            'phone': biz['phone_number'] or '',
            'email': biz['email'] or '',
            'minutes_used': used_min,
            'minutes_limit': limit_min,
            'minutes_remaining': max(0, limit_min - used_min),
            'total_spent': round(total_cost, 2),
            'total_leads': leads_count,
            'has_assistant': bool(biz['vapi_assistant_id']),
            'has_phone': bool(biz['vapi_phone_id'])
        }
    })


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
          data.get('script_template', f"You are a professional employee of {name}. Help them book more clients. You are a real person — never mention being AI, a robot, or software."),
          data.get('knowledge_base', f"Industry: {industry}. Business: {name}."),
          plan, monthly_price,
          data.get('features_desc', f'{plan.title()} plan')))

    c.execute("INSERT INTO campaigns (id, business_id, status) VALUES (?, ?, 'idle')", (cid, bid))
    db.commit()
    db.close()

    git_auto_commit(f'created business {name} ({bid})')
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

    git_auto_commit(f'updated business {bid}: {",".join(u.split(" =")[0] for u in updates)}')
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

    git_auto_commit(f'deleted business {name} ({bid})')
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

    git_auto_commit(f'added {added} lead(s) to business {business_id}')
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


# ── PROVISION PHONE NUMBER ──

@agent_api.route('/businesses/<bid>/phone', methods=['POST'])
@require_api_key
def api_provision_phone(api_key, bid):
    """Provision a phone number for a business: create Vapi assistant, buy number, assign."""
    if 'admin' not in api_key.get('permissions', '').split(',') and 'write' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Write or admin permission required'}), 403

    import subprocess, json as py_json
    from twilio_helper import search_available_numbers, buy_twilio_number, register_with_vapi, buy_and_assign_number

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    # 1. Look up business
    c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if not biz:
        db.close()
        return jsonify({'error': 'Business not found'}), 404

    name = biz['name']
    industry = biz['industry'] or 'general'
    script = biz['script_template'] or ''
    kb = biz['knowledge_base'] or ''
    voice_id = biz['voice_id'] or 'burt'
    voice_speed = float(biz['voice_speed'] or 1.0)
    temperature = float(biz['temperature'] or 0.3)
    max_tokens = int(biz['max_tokens'] or 200)
    timezone = biz['timezone'] or 'America/New_York'
    call_start = biz['call_window_start'] or '09:00'
    call_end = biz['call_window_end'] or '17:00'
    area_code = request.args.get('area_code') or (request.get_json(silent=True) or {}).get('area_code')

    # 2. Create VAPI assistant if missing
    assistant_id = biz['vapi_assistant_id']
    assistant_created = False
    if not assistant_id:
        full_script = build_diazites_prompt(
            business_name=name,
            industry=industry,
            script=script,
            knowledge_base=kb
        )
        # Multilingual by default: auto-detect caller language & respond in it
        full_script += "\n\nIMPORTANT: You are a MULTI-LINGUAL assistant. Detect the caller's language and respond in that same language. You speak: English, Spanish, French, German, Portuguese, Chinese, Arabic, Hindi, Korean, Japanese. Switch languages naturally when the caller switches."
        body = {
            "name": f"{name} Voice Agent",
            "model": {
                "provider": "xai",
                "model": "grok-4.3",
                "temperature": temperature,
                "maxTokens": max_tokens,
                "systemPrompt": full_script
            },
            "transcriber": {"provider": "openai", "model": "gpt-4o-transcribe"},
            "voice": {"provider": "11labs", "voiceId": voice_id, "model": "eleven_v3"},
            "firstMessage": f"Hi, this is {name}'s assistant. I'm calling because we help {industry} businesses. Am I catching you at a good time?",
            "firstMessageMode": "assistant-speaks-first",
            "silenceTimeoutSeconds": 40,
            "maxDurationSeconds": 300,
            "backgroundSound": "off",
            # CRITICAL: 8083 webhook (vapi_webhook_server.py) does the email/SMS/calendar
            # confirmations. The /api/v1/vapi-webhook route on 8086 only logs calls.
            "serverUrl": "https://diazites.online/api/vapi/webhook",
            "serverMessages": ["end-of-call-report", "status-update", "hang", "transcript", "conversation-update"],
            "analysisPlan": {
                "summaryPlan": {"enabled": True},
                "successEvaluationPlan": {"enabled": True},
                "structuredDataPlan": {
                    "enabled": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "notes": {"type": "string"},
                            "interested": {"type": "boolean"},
                            "prospect_name": {"type": "string"},
                            "appointment_time": {"type": "string"},
                            "appointment_booked": {"type": "boolean"}
                        }
                    }
                }
            }
        }
        result = subprocess.run([
            "curl", "-s", "-X", "POST", f"{VAPI_BASE}/assistant",
            "-H", f"Authorization: Bearer {VAPI_API_KEY}",
            "-H", "Content-Type: application/json",
            "-d", py_json.dumps(body)
        ], capture_output=True, text=True, timeout=30)
        try:
            assistant = py_json.loads(result.stdout)
            assistant_id = assistant.get('id')
            if not assistant_id:
                db.close()
                return jsonify({'error': f'Voice agent setup failed: {result.stdout[:300]}'}), 500
        except Exception as e:
            db.close()
            return jsonify({'error': f'Voice agent API error: {str(e)}'}), 500
        assistant_created = True
        c.execute("UPDATE businesses SET vapi_assistant_id=? WHERE id=?", (assistant_id, bid))
        db.commit()

    # 3. Check for existing phone number
    if biz['vapi_phone_id']:
        db.close()
        return jsonify({
            'success': True, 'message': f'{name} already has a phone number',
            'vapi_assistant_id': assistant_id,
            'vapi_phone_id': biz['vapi_phone_id'],
            'phone_number': biz.get('phone_number', ''),
            'assistant_created': assistant_created,
            'source': 'existing',
            'cost': 0
        })

    # 4. Try to reuse an unassigned Vapi number
    vapi_phone_id = None
    phone_number = None
    result = subprocess.run([
        "curl", "-s", f"{VAPI_BASE}/phone-number",
        "-H", f"Authorization: Bearer {VAPI_API_KEY}"
    ], capture_output=True, text=True, timeout=30)
    try:
        all_phones = py_json.loads(result.stdout)
        if isinstance(all_phones, list):
            c.execute("SELECT vapi_phone_id FROM businesses WHERE vapi_phone_id IS NOT NULL AND id != ?", (bid,))
            used_ids = set(r[0] for r in c.fetchall() if r[0])
            for p in all_phones:
                if p.get('id') not in used_ids and not p.get('assistantId'):
                    vapi_phone_id = p['id']
                    phone_number = p.get('number', '')
                    # Assign to assistant
                    subprocess.run([
                        "curl", "-s", "-X", "PATCH", f"{VAPI_BASE}/phone-number/{vapi_phone_id}",
                        "-H", f"Authorization: Bearer {VAPI_API_KEY}",
                        "-H", "Content-Type: application/json",
                        "-d", py_json.dumps({"assistantId": assistant_id})
                    ], capture_output=True, text=True, timeout=30)
                    source = 'reused'
                    cost = 0
                    break
    except:
        pass

    # 5. If no unassigned number, buy from Twilio
    if not vapi_phone_id:
        vapi_data, twilio_number, error = buy_and_assign_number(assistant_id, area_code or None)
        if error:
            db.close()
            return jsonify({'error': error}), 500
        vapi_phone_id = vapi_data['id'] if isinstance(vapi_data, dict) else vapi_data
        phone_number = twilio_number
        source = 'bought'
        cost = 1.50  # Twilio monthly fee for a phone number

    # 6. Update business record
    c.execute("UPDATE businesses SET phone_number=?, vapi_phone_id=? WHERE id=?", (phone_number, vapi_phone_id, bid))
    db.commit()
    db.close()

    git_auto_commit(f'provisioned phone {phone_number} for {name} ({bid})')
    return jsonify({
        'success': True,
        'message': f'Phone {phone_number} assigned to {name}',
        'business_id': bid,
        'phone_number': phone_number,
        'vapi_assistant_id': assistant_id,
        'vapi_phone_id': vapi_phone_id,
        'assistant_created': assistant_created,
        'source': source,
        'cost': cost
    })


# ── OUTBOUND CALL ──

@agent_api.route('/businesses/<bid>/call', methods=['POST'])
@require_api_key
def api_outbound_call(api_key, bid):
    """Place an outbound call via Vapi to a prospect."""
    if 'write' not in api_key.get('permissions', '').split(',') and 'admin' not in api_key.get('permissions', '').split(','):
        return jsonify({'error': 'Write or admin permission required'}), 403

    import subprocess, json as py_json

    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    lead_name = (data.get('lead_name') or 'Prospect').strip()

    if not phone:
        return jsonify({'error': 'phone is required'}), 400

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("SELECT name, vapi_assistant_id, vapi_phone_id FROM businesses WHERE id=?", (bid,))
    biz = c.fetchone()
    db.close()

    if not biz:
        return jsonify({'error': 'Business not found'}), 404

    name = biz[0]
    assistant_id = biz[1]
    phone_id = biz[2]

    if not assistant_id:
        return jsonify({'error': 'No voice agent configured. Assign a phone number first.'}), 400
    if not phone_id:
        return jsonify({'error': 'No phone number assigned. Assign a phone number first.'}), 400

    body = {
        "assistantId": assistant_id,
        "phoneNumberId": phone_id,
        "customer": {
            "number": phone,
            "name": lead_name
        }
    }

    result = subprocess.run([
        "curl", "-s", "-X", "POST", f"{VAPI_BASE}/call",
        "-H", f"Authorization: Bearer {VAPI_API_KEY}",
        "-H", "Content-Type: application/json",
        "-d", py_json.dumps(body)
    ], capture_output=True, text=True, timeout=30)

    try:
        vapi_resp = py_json.loads(result.stdout)
        call_id = vapi_resp.get('id')
        if not call_id:
            return jsonify({'error': f'Call failed: {result.stdout[:300]}'}), 500
        status = vapi_resp.get('status', 'queued')
    except Exception as e:
        return jsonify({'error': f'Voice agent API error: {str(e)}'}), 500

    return jsonify({
        'success': True,
        'call_id': call_id,
        'status': status,
        'message': f'Calling {phone} from {name}'
    })


# ── GET CALL DETAILS / TRANSCRIPT ──

@agent_api.route('/calls/<call_id>', methods=['GET'])
@require_api_key
def api_get_call(api_key, call_id):
    """Get call details, transcript, and status from call_log."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    # Try by vapi_call_id first, then by call_log id
    c.execute("""
        SELECT cl.*, l.name as lead_name, l.phone as lead_phone,
               l.business_name as lead_business, l.notes as lead_notes,
               l.state as lead_state
        FROM call_log cl
        LEFT JOIN leads l ON cl.lead_id = l.id
        WHERE cl.vapi_call_id = ? OR cl.id = ?
        LIMIT 1
    """, (call_id, call_id))
    row = c.fetchone()
    db.close()

    if not row:
        return jsonify({'error': 'Call not found'}), 404

    dur = row['duration'] or 0
    row = dict(row)
    started = row.get('created_at', '')
    ended = ''
    if dur > 0 and started:
        from datetime import datetime as dt
        try:
            start_dt = dt.fromisoformat(started)
            end_dt = start_dt.replace(second=start_dt.second + (dur % 60),
                                       minute=start_dt.minute + (dur // 60))
            ended = end_dt.isoformat()
        except:
            pass

    return jsonify({
        'success': True,
        'call': {
            'id': row.get('vapi_call_id') or row.get('id'),
            'business_id': row.get('business_id', ''),
            'phone': row.get('lead_phone') or '',
            'status': row.get('status', 'unknown'),
            'duration_seconds': dur,
            'transcript': row.get('transcript', '') or '',
            'appointment_booked': row.get('outcome') == 'appointment_booked',
            'appointment_time': row.get('appointment_time', '') or '',
            'lead_notes': row.get('lead_notes', '') or row.get('notes', '') or '',
            'started_at': started,
            'ended_at': ended,
            'recording_url': row.get('recording_url', '') or '',
            'cost': row.get('cost', 0) or 0
        }
    })


# ── VAPI WEBHOOK (receive call-end events) ──

@agent_api.route('/vapi-webhook', methods=['POST'])
def vapi_webhook():
    """Receive call-end webhook from Vapi and store transcript/details."""
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({'error': 'No data'}), 400

    # Vapi may send {message:{type,call:{...}}} or a flat call payload — handle both
    msg = data.get('message') or {}
    call = data.get('call') or msg.get('call') or {}
    vapi_call_id = call.get('id') or data.get('callId') or msg.get('callId') or ''
    if not vapi_call_id:
        return jsonify({'error': 'Missing call ID'}), 400

    status = data.get('status') or call.get('status') or msg.get('type', 'completed')
    duration = data.get('durationSeconds') or call.get('durationSeconds', 0) or 0
    transcript = data.get('transcript') or call.get('transcript', '') or ''
    cost = data.get('cost') or call.get('cost', 0) or 0
    recording_url = data.get('recordingUrl') or call.get('recordingUrl', '') or ''
    outcome = data.get('endedReason') or call.get('endedReason', 'unknown')
    appointment_time = data.get('artifact', {}).get('appointmentTime') or call.get('artifact', {}).get('appointmentTime', '') or ''

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    # Check if it exists
    c.execute("SELECT id FROM call_log WHERE vapi_call_id = ?", (vapi_call_id,))
    existing = c.fetchone()

    if existing:
        c.execute("""UPDATE call_log SET
            status=?, duration=?, transcript=?, cost=?,
            recording_url=?, outcome=?, appointment_time=?
            WHERE vapi_call_id=?""",
            (status, duration, transcript, cost,
             recording_url, outcome, appointment_time, vapi_call_id))
    else:
        c.execute("""INSERT OR IGNORE INTO call_log
            (id, vapi_call_id, status, duration, transcript, cost,
             recording_url, outcome, appointment_time, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (vapi_call_id, vapi_call_id, status, duration, transcript, cost,
             recording_url, outcome, appointment_time))

    db.commit()
    db.close()

    git_auto_commit(f'vapi webhook: call {vapi_call_id} {status}')

    # Real-time Review-AI outcome sync → auto demo/package SMS+email on 'interested'
    if status in ('ended', 'completed') or 'ended' in str(status) or call.get('status') in ('ended', 'completed'):
        try:
            import threading
            def _ra_sync():
                try:
                    import sys
                    sys.path.insert(0, '/root/voice-agent-manager')
                    import review_ai
                    review_ai.sync_call_outcomes()
                except Exception:
                    pass
            threading.Thread(target=_ra_sync, daemon=True).start()
        except Exception:
            pass

    return jsonify({'success': True, 'call_id': vapi_call_id})


# ── Helpers for auth middleware ──

def api_key_required(permission='read'):
    """Decorator factory for requiring API key with specific permission (or admin session)."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get('Authorization', '')
            
            # Check admin session first
            from flask import session as flask_session
            if flask_session.get('admin_logged_in'):
                kwargs['api_key'] = {'permissions': 'read,write,admin', 'name': 'Admin UI Session', 'id': 'admin-session'}
                return f(*args, **kwargs)
            
            # Fall back to API key
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
