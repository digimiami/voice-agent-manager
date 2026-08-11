# ── AI AGENT DIRECTORY ROUTE ──
@app.route('/ai-agents-directory')
def ai_agents_directory():
    """Curated directory of 50+ top AI agents, frameworks, and tools for 2026."""
    cat_icons = {'Coding Agents': '🖥️', 'Agent Frameworks': '🧱', 'Browser & Desktop Agents': '🌐',
                 'Voice Agents': '🎤', 'CRM & Sales Agents': '💼', 'Data & Research Agents': '📊',
                 'Self-Hosted & Local': '🏠', 'Platforms & Hubs': '🤖'}
    
    cards = ''
    total = 0
    for cat, agents in AGENTS_DIRECTORY.items():
        icon = cat_icons.get(cat, '📦')
        total += len(agents)
        agents_html = ''
        for a in agents:
            agents_html += f'''<div class="flex items-start gap-3 p-3 rounded-lg bg-[#1a1a26] border border-[#252533] hover:border-[#a855f7]/40 transition cursor-pointer" onclick="window.open('{a["url"]}','_blank')">
  <span class="text-lg mt-0.5 flex-shrink-0">{icon}</span>
  <div class="flex-1 min-w-0">
    <div class="flex items-center gap-2 mb-0.5">
      <span class="text-sm font-semibold">{a["name"]}</span>
      <span class="text-[10px] px-1.5 py-0.5 rounded bg-[#a855f7]/10 text-[#a855f7]">{a["type"]}</span>
    </div>
    <p class="text-xs text-[#5c5c70] leading-relaxed">{a["desc"][:120]}</p>
    <span class="text-[10px] text-[#38bdf8]">{a["price"]}</span>
  </div>
</div>'''
        
        cards += f'''<div class="mb-6" data-cat="{cat}">
  <div class="flex items-center gap-2 mb-3">
    <span class="text-xl">{icon}</span>
    <h3 class="font-bold text-sm">{cat} <span class="text-[10px] text-[#5c5c70] font-normal">({len(agents)})</span></h3>
  </div>
  <div class="space-y-2">{agents_html}</div>
</div>'''
    
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-4xl mx-auto px-4 sm:px-6 pb-8">

  <!-- Hero -->
  <div class="text-center py-10 mb-6">
    <span class="text-5xl mb-4 block">🤖</span>
    <h1 class="text-3xl font-black mb-2">AI Agent Directory 2026</h1>
    <p class="text-sm text-[#5c5c70] max-w-lg mx-auto">Curated list of <strong class="text-white">{total}+</strong> top AI agents, frameworks, and tools across 8 categories. Updated monthly.</p>
    <div class="flex items-center justify-center gap-4 mt-4 text-xs text-[#5c5c70]">
      <span><i class="fas fa-star text-[#facc15] mr-1"></i> Updated Apr 2026</span>
      <span><i class="fas fa-code-branch text-[#a855f7] mr-1"></i> Source: awesome-ai-agents-2026</span>
    </div>
  </div>

  <!-- Search + Filters -->
  <div class="card mb-6" style="padding:16px">
    <div class="flex gap-2">
      <div class="relative flex-1">
        <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-[#5c5c70] text-xs"></i>
        <input id="agentSearch" class="text-xs w-full pl-8" placeholder="Search agents by name, category, type..." oninput="filterAgents(this.value)">
      </div>
      <select id="catFilter" class="text-xs" onchange="filterAgents(document.getElementById('agentSearch').value)">
        <option value="all">All Categories</option>
        {''.join(f'<option value=\"{cat}\">{icon} {cat}</option>' for cat, icon in cat_icons.items())}
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

  <!-- Count -->
  <div class="text-xs text-[#5c5c70] mb-4" id="resultCount">Showing {total} agents</div>

  <!-- Directory -->
  <div id="directory">{cards}</div>

  <!-- Ad / Monetization -->
  <div class="card mt-8" style="padding:20px;background:linear-gradient(135deg,#1a0a2e,#0e0e16);border:1px solid #a855f740">
    <div class="flex items-start gap-4">
      <span class="text-3xl">📋</span>
      <div>
        <h3 class="font-bold text-sm mb-1">Want This as a Downloadable PDF?</h3>
        <p class="text-xs text-[#5c5c70] mb-3">Get the full 2026 AI Agent Directory as a printable PDF with comparison tables, pricing, and affiliate links. Updated quarterly.</p>
        <a href="/api/checkout/agents-pdf" class="btn-primary text-xs" style="padding:10px 24px"><i class="fas fa-file-pdf mr-1"></i> Get PDF — $9</a>
      </div>
    </div>
  </div>

</div>

<script>
function filterAgents(q) {{
  const cat = document.getElementById('catFilter').value;
  const type = document.getElementById('typeFilter').value.toLowerCase();
  const sections = document.querySelectorAll('#directory > div[data-cat]');
  let visible = 0;
  sections.forEach(s => {{
    let show = cat === 'all' || s.dataset.cat === cat;
    if(show) {{
      const cards = s.querySelectorAll('div > div');
      cards.forEach(c => {{
        const text = c.textContent.toLowerCase();
        const typeMatch = type === 'all' || text.includes(type);
        const searchMatch = text.includes(q.toLowerCase());
        c.style.display = searchMatch && typeMatch ? '' : 'none';
        if(searchMatch && typeMatch) visible++;
      }});
      const hasVisible = [...s.querySelectorAll('div > div')].some(d => d.style.display !== 'none');
      s.style.display = hasVisible ? '' : 'none';
    }} else {{
      s.style.display = 'none';
    }}
  }});
  document.getElementById('resultCount').textContent = 'Showing ' + visible + ' agents';
}}
</script>
{LAYOUT_FOOT}'''
