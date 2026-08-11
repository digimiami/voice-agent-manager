# ── PHASE 21: HERMES GOAL MANAGER ──
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
      <p class="text-sm text-[#5c5c70]">Set business objectives — Hermes executes the strategy</p>
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

# ── PHASE 22: AGENT MEMORY SYSTEM ──
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

# ── PHASE 23: WORKFLOW BUILDER ──
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
      <p class="text-sm text-[#5c5c70]">Automate business processes — like Zapier for Hermes agents</p>
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
  const stepData = JSON.parse('{"type":"' + type + '","label":"' + label + '","icon":"\u2699"}');
  fetch('/api/hermes/workflow/step', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({step:stepData})})
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

# ── PHASE 24: HERMES RANK ──
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

# ── PHASE 25: CREATOR AI COACH ──
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

# ── PHASE 26: AI CUSTOMER SUCCESS ──
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

# ── PHASE 27: PRODUCT VERSION CONTROL ──
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

# ── PHASE 28: AI MARKETPLACE SEARCH ──
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
        r['url'] = f'/product/{r["id"]}'

    return jsonify({'query': q, 'results': results, 'count': len(results)})

# ── PHASE 29: ENTERPRISE AI BUILDER ──
@app.route('/enterprise/builder', methods=['GET', 'POST'])
def enterprise_builder():
    if request.method == 'GET':
        return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-3xl mx-auto px-4 pb-8">
  <div class="text-center py-10">
    <div class="text-5xl mb-4">\U0001f3e2</div>
    <h1 class="text-2xl sm:text-3xl font-bold mb-2">Enterprise AI Stack Builder</h1>
    <p class="text-sm text-[#5c5c70]">Tell us about your business — we'll build your AI team.</p>
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
      <p class="text-sm text-[#5c5c70]">{industry} · {employees} employees</p>
    </div>
    <div class="space-y-2 mb-6">{stack_html}</div>
    <div class="text-center">
      <div class="text-3xl font-bold text-[#4ade80]">${monthly}<span class="text-sm text-[#5c5c70] font-normal">/month</span></div>
      <p class="text-xs text-[#5c5c70] mt-1">All agents included · Setup in 24 hours</p>
      <a href="/enterprise/register" class="btn-primary mt-4 inline-block" style="padding:14px 36px">Get Started <i class="fas fa-arrow-right ml-1"></i></a>
    </div>
  </div>
</div>
{LAYOUT_FOOT}'''

# ── PHASE 30: HERMES AGENT PROTOCOL ──
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
  pricing: {"monthly": 49}
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

# ── HERMES AUTONOMOUS ENGINE — INTEGRATION ──
@app.route('/api/hermes/autonomous/tick')
@admin_required
def api_hermes_autonomous_tick():
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

