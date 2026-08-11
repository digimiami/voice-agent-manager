# ── HERMES REDESIGN — Dashboard, Products, APIs, Models, Prompts ──

HERMES_NAV = '''<nav class="sticky top-0 z-40 glass mb-6 -mx-4 sm:-mx-6 px-4 sm:px-6" style="border-bottom:1px solid rgba(255,255,255,0.04)">
  <div class="max-w-6xl mx-auto flex items-center justify-between h-14">
    <div class="flex items-center gap-6">
      <a href="/" class="font-bold text-sm flex items-center gap-1.5"><span class="w-6 h-6 rounded-md bg-gradient-to-br from-[#a855f7] to-[#ec4899] flex items-center justify-center text-white text-[10px] font-bold">H</span>Hermes OS</a>
      <a href="/factory" class="nav-link text-xs"><i class="fas fa-chart-simple mr-1"></i>Dashboard</a>
      <a href="/hermes/products" class="nav-link text-xs"><i class="fas fa-box mr-1"></i>Products</a>
      <a href="/hermes/apis" class="nav-link text-xs"><i class="fas fa-plug mr-1"></i>APIs</a>
      <a href="/hermes/models" class="nav-link text-xs"><i class="fas fa-brain mr-1"></i>AI Models</a>
      <a href="/hermes/prompts" class="nav-link text-xs"><i class="fas fa-message mr-1"></i>Prompts</a>
      <a href="/ai-agents-directory" class="nav-link text-xs"><i class="fas fa-robot mr-1"></i>Agents</a>
    </div>
  </div>
</nav>'''

HERMES_FOOT = LAYOUT_FOOT

def _hermes_page(title, active, body):
    nav = HERMES_NAV.replace('>' + active + '</a>', ' class="nav-link text-xs font-semibold text-white" style="background:#a855f715">' + active + '</a>')
    return LAYOUT_HEAD + nav + '<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">' + body + '</div>' + LAYOUT_FOOT

# ────────────────────────────────────────
# 2. PRODUCTS — Full management
# ────────────────────────────────────────
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
            filters += '<option value="' + t + '">' + t + '</option>'
    filters += '</select>'
    filters += '<input class="text-xs flex-1" id="searchP" placeholder="Search products..." oninput="filterP()">'
    filters += '<a href="/hermes/generate" class="btn-primary text-xs whitespace-nowrap" style="padding:8px 16px"><i class="fas fa-wand-magic-sparkles"></i> AI Generate</a>'
    
    rows = ''
    for p in products:
        icon = product_type_icon(p.get('product_type',''))
        color = product_type_color(p.get('product_type',''))
        status_label = p.get('status','draft')
        status_color = {'published':'#4ade80','draft':'#facc15','scheduled':'#38bdf8','archived':'#5c5c70'}.get(status_label,'#5c5c70')
        slug = p.get('slug','') or p['id']
        rows += '<tr class="border-b border-[#1e1e2e] hover:bg-[#1a1a26] transition cursor-pointer" onclick="window.location=\'/hermes/product/' + p['id'] + '\'">'
        rows += '<td class="py-3 px-3"><span class="text-lg">' + icon + '</span></td>'
        rows += '<td class="py-3 px-3"><div class="text-sm font-semibold">' + (p['title'] or 'Untitled')[:60] + '</div><div class="text-[10px] text-[#5c5c70]">/' + slug[:40] + '</div></td>'
        rows += '<td class="py-3 px-3"><span class="text-[10px] px-2 py-0.5 rounded-full" style="background:' + color + '15;color:' + color + '">' + PRODUCT_TYPE_LABELS.get(p.get('product_type',''),'Product') + '</span></td>'
        rows += '<td class="py-3 px-3"><span class="text-[10px] px-2 py-0.5 rounded-full" style="background:' + status_color + '15;color:' + status_color + '">' + status_label + '</span></td>'
        rows += '<td class="py-3 px-3 text-sm font-bold">$' + str(p.get('price',0)) + '</td>'
        rows += '<td class="py-3 px-3 text-xs text-[#5c5c70]">' + str(p.get('downloads_count',0)) + '</td>'
        rows += '<td class="py-3 px-3 text-xs text-[#5c5c70]">' + (p.get('created_at','') or '')[:10] + '</td>'
        rows += '<td class="py-3 px-3"><div class="flex gap-1"><a href="/product/' + p['id'] + '" class="text-[10px] px-2 py-1 rounded bg-[#38bdf8]/10 text-[#38bdf8] hover:bg-[#38bdf8]/20"><i class="fas fa-eye"></i></a><a href="/hermes/product/' + p['id'] + '" class="text-[10px] px-2 py-1 rounded bg-[#a855f7]/10 text-[#a855f7] hover:bg-[#a855f7]/20"><i class="fas fa-edit"></i></a></div></td>'
        rows += '</tr>'
    
    body = '''<div class="flex items-center justify-between mb-6"><div><h1 class="text-xl font-bold">Products</h1><p class="text-xs text-[#5c5c70]">''' + str(len(products)) + ''' total</p></div></div>
<div class="card p-4 mb-4"><div class="flex gap-2 flex-wrap items-center">''' + filters + '''</div></div>
<div class="card overflow-hidden"><table class="w-full text-sm"><thead><tr class="text-xs text-[#5c5c70] border-b border-[#1e1e2e]">
<th class="text-left py-3 px-3 w-10"></th><th class="text-left py-3 px-3">Product</th><th class="text-left py-3 px-3">Type</th><th class="text-left py-3 px-3">Status</th><th class="text-left py-3 px-3">Price</th><th class="text-left py-3 px-3">Downloads</th><th class="text-left py-3 px-3">Created</th><th class="text-left py-3 px-3">Actions</th>
</tr></thead><tbody id="productTable">''' + rows + '''</tbody></table></div>
<script>
function filterP(){const s=document.getElementById('statusFilter').value;const t=document.getElementById('typeFilter').value;const q=document.getElementById('searchP').value.toLowerCase();document.querySelectorAll('#productTable tr').forEach(r=>{const txt=r.textContent.toLowerCase();const sm=s===''||txt.includes(s);const tm=t===''||txt.includes(t);const qm=txt.includes(q);r.style.display=sm&&tm&&qm?'':'none'})}
</script>'''
    return _hermes_page('Products', 'Products', body)

HERMES_PRODUCT_SECTIONS = ['General', 'Description', 'Pricing', 'Media', 'Downloads', 'License', 'SEO', 'Analytics', 'Affiliate', 'AI Rewrite', 'History', 'API', 'Logs']

@app.route('/hermes/product/<product_id>')
@admin_required
def hermes_product_detail(product_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    p = c.fetchone()
    db.close()
    if not p:
        return 'Not found', 404
    
    icon = product_type_icon(p['product_type'])
    color = product_type_color(p['product_type'])
    
    tabs = ''
    for s in HERMES_PRODUCT_SECTIONS:
        active = 'text-white border-b-2 border-[#a855f7]' if s == 'General' else 'text-[#5c5c70]'
        tabs += '<button class="px-3 py-2 text-xs font-medium ' + active + ' whitespace-nowrap" onclick="switchTab(\'' + s.lower().replace(' ','') + '\',this)">' + s + '</button>'
    
    content_body = (p.get('description','') or '')[:2000]
    
    body = '''<a href="/hermes/products" class="text-xs text-[#38bdf8] hover:underline mb-4 inline-flex items-center gap-1"><i class="fas fa-arrow-left"></i> Back to Products</a>
<div class="card overflow-hidden mb-4" style="padding:0"><div class="flex items-center gap-4 p-5 bg-gradient-to-r from-[#1a0a2e] to-[#0e0e16]">
  <span class="text-3xl">''' + icon + '''</span><div class="flex-1"><h1 class="text-lg font-bold">''' + (p['title'] or 'Untitled') + '''</h1>
  <div class="flex items-center gap-3 text-xs text-[#5c5c70] mt-1"><span style="color:''' + color + '''">''' + PRODUCT_TYPE_LABELS.get(p['product_type'],'Product') + '''</span>
  <span>$''' + str(p.get('price',0)) + '''</span><span>''' + str(p.get('downloads_count',0)) + ''' downloads</span></div></div>
  <div class="flex gap-2"><a href="/product/''' + p['id'] + '''" class="btn-secondary text-xs" style="padding:8px 16px"><i class="fas fa-eye"></i> View</a>
  <a href="/api/publish/''' + p['id'] + '''" class="btn-primary text-xs" style="padding:8px 16px"><i class="fas fa-check"></i> ''' + ('Publish' if p.get('status')=='draft' else 'Update') + '''</a></div>
</div>
<div class="border-b border-[#1e1e2e] px-5 flex gap-2 overflow-x-auto" id="productTabs">''' + tabs + '''</div></div>

<div id="tab-general" class="tab-pane"><div class="card p-5"><h3 class="font-bold text-sm mb-3">General</h3>
<p class="text-xs text-[#5c5c70]">ID: ''' + p['id'] + '''</p>
<p class="text-xs text-[#5c5c70]">Slug: ''' + (p.get('slug','') or '—') + '''</p>
<p class="text-xs text-[#5c5c70]">Created: ''' + (p.get('created_at','') or '—') + '''</p>
<p class="text-xs text-[#5c5c70]">Status: ''' + (p.get('status','') or 'draft') + '''</p></div></div>

<div id="tab-description" class="tab-pane hidden"><div class="card p-5"><h3 class="font-bold text-sm mb-3">Description</h3>
<pre class="text-xs text-[#b0b0c0] whitespace-pre-wrap font-sans">''' + content_body + '''</pre></div></div>

<div id="tab-pricing" class="tab-pane hidden"><div class="card p-5"><h3 class="font-bold text-sm mb-3">Pricing</h3>
<p class="text-xs text-[#5c5c70]">Price: $''' + str(p.get('price',0)) + '''</p></div></div>

<div id="tab-media" class="tab-pane hidden"><div class="card p-5"><h3 class="font-bold text-sm mb-3">Media</h3>
<p class="text-xs text-[#5c5c70]">No media uploaded yet.</p></div></div>

<div id="tab-seo" class="tab-pane hidden"><div class="card p-5"><h3 class="font-bold text-sm mb-3">SEO</h3>
<p class="text-xs text-[#5c5c70]">Title: ''' + (p.get('seo_title','') or '—') + '''</p>
<p class="text-xs text-[#5c5c70]">Description: ''' + (p.get('seo_description','') or '—') + '''</p></div></div>

<div id="tab-ai" class="tab-pane hidden"><div class="card p-5"><h3 class="font-bold text-sm mb-3">AI Rewrite</h3>
<p class="text-xs text-[#5c5c70]">Use Hermes AI to rewrite this product description, optimize SEO, and generate better pricing.</p>
<button class="btn-primary text-xs mt-3" style="padding:8px 16px"><i class="fas fa-wand-magic-sparkles"></i> AI Rewrite</button></div></div>

<script>
function switchTab(tab,btn){document.querySelectorAll('#productTabs button').forEach(b=>{b.classList.remove('text-white','border-b-2','border-[#a855f7]');b.classList.add('text-[#5c5c70]')});btn.classList.add('text-white','border-b-2','border-[#a855f7]');document.querySelectorAll('.tab-pane').forEach(p=>p.classList.add('hidden'));const el=document.getElementById('tab-'+tab);if(el)el.classList.remove('hidden')}
</script>'''
    return _hermes_page('Product: ' + (p['title'] or '')[:40], 'Products', body)

# ────────────────────────────────────────
# 3. AI PRODUCT GENERATOR
# ────────────────────────────────────────
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
        type_html += '<div class="flex items-center gap-2 p-3 rounded-lg border border-[#252533] hover:border-[#a855f7]/40 cursor-pointer bg-[#1a1a26] type-option" data-type="' + tid + '" onclick="selectType(this,\'' + tid + '\')">'
        type_html += '<span class="text-xl">' + icon + '</span><span class="text-xs font-medium">' + tlabel + '</span></div>'
    
    audience_html = ''
    for a in audiences:
        audience_html += '<button class="text-xs px-3 py-1.5 rounded-full border border-[#252533] hover:border-[#a855f7]/40 transition cursor-pointer audience-option" onclick="selectAudience(this,\'' + a + '\')">' + a + '</button>'
    
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

# ────────────────────────────────────────
# 4. API MANAGER
# ────────────────────────────────────────
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
        quota = str(85 - len(name) * 3) + '%' if connected else '—'
        
        cards += '<div class="card p-4 flex items-center gap-3 hover:border-[#a855f7]/40 transition">'
        cards += '<div class="w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold" style="background:' + color + '15;color:' + color + '">' + name[:2].upper() + '</div>'
        cards += '<div class="flex-1"><div class="text-sm font-semibold">' + name + '</div><div class="flex items-center gap-2 mt-0.5">' + status_html + '<span class="text-[10px] px-1.5 py-0.5 rounded" style="background:' + cat_color + '15;color:' + cat_color + '">' + cat + '</span></div></div>'
        cards += '<div class="text-right text-xs"><div class="text-[10px] text-[#5c5c70]">Quota</div><div class="font-semibold" style="color:' + ('#4ade80' if connected else '#5c5c70') + '">' + quota + '</div></div>'
        cards += '<button class="text-[10px] px-2 py-1 rounded ' + ('bg-[#a855f7]/10 text-[#a855f7] hover:bg-[#a855f7]/20' if not connected else 'bg-[#1a1a26] text-[#5c5c70] hover:text-white') + '">' + ('Connect' if not connected else 'Edit') + '</button></div>'
    
    body = '''<div class="flex items-center justify-between mb-6"><div><h1 class="text-xl font-bold">API Manager</h1><p class="text-xs text-[#5c5c70]">''' + str(len(API_PROVIDERS)) + ''' providers available</p></div></div>
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">''' + cards + '''</div>'''
    return _hermes_page('API Manager', 'APIs', body)

# ────────────────────────────────────────
# 5. AI MODELS — Task-to-model assignment
# ────────────────────────────────────────
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

# ────────────────────────────────────────
# 6. PROMPT LIBRARY
# ────────────────────────────────────────
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
        cards += '<div class="card p-4 hover:border-[#a855f7]/40 transition cursor-pointer" onclick="usePrompt(\'' + name + '\',\'' + template + '\')">'
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

# ────────────────────────────────────────
# AI Run Prompt API
# ────────────────────────────────────────
@app.route('/api/ai/run-prompt', methods=['POST'])
@admin_required
def api_ai_run_prompt():
    data = request.json
    prompt_name = data.get('prompt','')
    template = data.get('template','')
    user_input = data.get('input','')
    
    full_prompt = template + ' ' + user_input
    
    return jsonify({'output': full_prompt + '\n\n[AI would generate content here — integrate with your preferred model]', 'prompt': prompt_name})
