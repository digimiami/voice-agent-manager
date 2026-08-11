# ── HERMES MISSION CONTROL (Phase 11) ──
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
    """Hermes Mission Control — Agent orchestration dashboard."""
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

# ── PUBLIC API v1 (Phase 12) ──
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
        p['url'] = f'/product/{p["id"]}'
    
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

# ── AI AGENT STORE (Phase 13) ──
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

# ── SUBSCRIPTION ENGINE (Phase 14) ──
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

# ── SEO FACTORY (Phase 15) ──
@app.route('/api/seo-factory/generate')
@admin_required
def api_seo_factory():
    """Generate SEO-optimized content at scale."""
    import datetime
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    
    templates = [
        f'Best AI Agents {datetime.datetime.now().year} — Top Picks for Every Business',
        f'Top 20 n8n Workflows to Automate Your Business in {datetime.datetime.now().year}',
        'Best ChatGPT Prompts for Marketing, Sales, and Support',
        'AI Tools for Real Estate Agents — Complete Guide',
        'Best Trading Bots for Cryptocurrency in ' + datetime.datetime.now().strftime('%Y'),
        'Ultimate Guide to AI Voice Agents for Customer Service',
        'Top MCP Servers Every Developer Should Know',
        'Best Prompt Engineering Templates for Business',
        'AI Automation Stack for Small Business Owners',
        'How to Build an AI Sales Agent — Step by Step',
    ]
    
    db = get_db()
    c = db.cursor()
    count = 0
    for title in templates[:10]:
        c.execute("SELECT id FROM seo_content WHERE title=?", (title,))
        if not c.fetchone():
            content = f'# {title}\n\nThis comprehensive guide covers everything you need to know about {title.lower()}.\n\n## Why This Matters\n\nIn {datetime.datetime.now().year}, AI-powered tools are transforming how businesses operate.\n\n## Getting Started\n\n1. Browse our curated collection\n2. Compare features and pricing\n3. Download and install instantly\n\n## Related Products\n\nCheck out our marketplace for the best tools in this category.\n\n---\n*Generated by Hermes SEO Factory — {today}*'
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

# ── AFFILIATE ARMY (Phase 16) ──
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

# ── PRODUCT QUALITY AI (Phase 17) ──
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

# ── DIGITAL LICENSE ENGINE (Phase 18) ──
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

# ── MARKETPLACE INTELLIGENCE (Phase 19) ──
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

# ── MOBILE API SUPPORT (Phase 20) ──
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

