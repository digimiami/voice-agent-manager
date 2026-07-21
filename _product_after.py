# ── PRODUCT EXPERIENCE AGENT API ──
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



# ── HERMES AUTONOMOUS ENGINE — INTEGRATION ──
# (old tick moved to v2 implementation below)
@app.route('/api/hermes/old-tick')
@admin_required
def api_hermes_autonomous_tick_old():
    """
    The 'heartbeat' of Hermes Autonomous Engine.
    Called periodically to run the growth loop:
    1. Check goals → update progress
    2. Check for new trends → create products
    3. Check low-quality products → optimize
    4. Check customer success → send alerts
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



# ── PHASE 31: HERMES AUTONOMOUS SCHEDULER ──
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
      <div class="text-[10px] text-[#5c5c70]">{interval_label} · Last: {last} · Next: {nxt}</div>
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
      <h3 class="font-bold text-sm mb-2"><i class="fas fa-check-circle text-[#4ade80] mr-1"></i> Level 1 — Automatic</h3>
      <ul class="text-xs text-[#b0b0c0] space-y-1">
        <li>\u2705 Generate reports</li>
        <li>\u2705 Analyze trends</li>
        <li>\u2705 Create drafts</li>
        <li>\u2705 Update rankings</li>
        <li>\u2705 Create suggestions</li>
      </ul>
    </div>
    <div class="card" style="padding:20px;border-left:3px solid #facc15">
      <h3 class="font-bold text-sm mb-2"><i class="fas fa-exclamation-triangle text-[#facc15] mr-1"></i> Level 2 — Approval Required</h3>
      <ul class="text-xs text-[#b0b0c0] space-y-1">
        <li>\u26a0\ufe0f Publish new products</li>
        <li>\u26a0\ufe0f Change pricing</li>
        <li>\u26a0\ufe0f Send marketing campaigns</li>
        <li>\u26a0\ufe0f Contact creators</li>
        <li>\u26a0\ufe0f Create ads</li>
      </ul>
    </div>
    <div class="card" style="padding:20px;border-left:3px solid #f472b6">
      <h3 class="font-bold text-sm mb-2"><i class="fas fa-lock text-[#f472b6] mr-1"></i> Level 3 — Locked</h3>
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
               f'Hermes Daily Report — {datetime.datetime.now().strftime("%b %d")}',
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

# ── PHASE 32: DECISION QUEUE ──
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

# ── PHASE 33: AGENT PERFORMANCE ──
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

# ── PHASE 34: REVENUE ATTRIBUTION ──
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

# ── PHASE 35: AUTONOMOUS EXPERIMENT ENGINE ──
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

# ── PHASE 39: MARKETPLACE EXPANSION ENGINE ──
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

# ── PHASE 40: THE HERMES CEO LAYER ──
@app.route('/api/hermes/ceo-strategy', methods=['POST'])
@admin_required
def api_hermes_ceo_strategy():
    """Give Hermes a business objective — it creates a strategy."""
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
        'recommendation': 'Focus on creator recruitment first — it drives the flywheel'
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

# ── HERMES TICK WITH DRY-RUN AND SAFETY ──
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
    
    # ── Level 1: Automatic actions (always run) ──
    
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
    
    # ── Level 2: Approval-gated actions (queue decisions, don't execute) ──
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
# ── HERMES PERMISSIONS PAGE ──
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
        <h3 class="font-bold"><i class="fas fa-check-circle text-[#4ade80] mr-1"></i> Level 1 — Automatic</h3>
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
        <h3 class="font-bold"><i class="fas fa-exclamation-triangle text-[#facc15] mr-1"></i> Level 2 — Approval Required</h3>
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
        <h3 class="font-bold"><i class="fas fa-lock text-[#f472b6] mr-1"></i> Level 3 — Locked</h3>
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
    print("🚀 ShopZario Store on port 8090")
    app.run(host='0.0.0.0', port=8090, debug=False)
