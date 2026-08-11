# ── PRODUCT EXPERIENCE AGENT (Shopzario 2.0) ──
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

@app.route('/product/<identifier>')
def product_redirect(identifier):
    """Legacy route — redirect to SEO slug."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT slug FROM products WHERE id=?", (identifier,))
    p = c.fetchone()
    db.close()
    if p and p['slug']:
        return redirect(f'/products/{p["slug"]}', 301)
    return product_detail_page(identifier)

import datetime

def product_detail_page(product_id):
    """Render premium product detail page."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    p = dict(c.fetchone())
    
    features = p.get('features', '') or p.get('content', '')
    now = datetime.datetime.now()
    
    # Hermes Score
    demand = min(100, p['downloads_count'] * 20)
    quality = min(100, int((len(p.get('content') or '') / 500) * 100))
    seo_score = min(100, len(p.get('seo_description') or '') // 2)
    review_score = min(100, int((p.get('rating', 0) or 0) * 20))
    hermes_score = round((demand * 0.25 + quality * 0.25 + seo_score * 0.30 + review_score * 0.20), 1)
    
    # Compatibility
    compat_items = (p.get('compatibility') or '').split(',') if p.get('compatibility') else []
    if not compat_items:
        compat_items = ['OpenAI', 'Claude', 'ChatGPT', 'n8n']
    
    # Benefits / Why Buy
    benefits = (p.get('benefits') or '').split('\n') if p.get('benefits') else []
    if not benefits:
        benefits = [f'Saves 20 hours/week', f'Works with ChatGPT', 'No coding required', 'Lifetime updates', 'Commercial license included']
    
    # Version
    version = p.get('version', '')
    changelog = p.get('changelog', '')
    
    # Creator
    creator_name = p.get('creator_name') or 'ShopZario Official'
    creator_products = 0
    c.execute("SELECT COUNT(*) FROM products WHERE creator_name=? AND id!=?", (creator_name, product_id))
    row = c.fetchone()
    if row:
        creator_products = row[0]
    
    # Related products
    c.execute("SELECT id, title, price, product_type, rating, downloads_count, slug FROM products WHERE status='published' AND id!=? ORDER BY RANDOM() LIMIT 4", (product_id,))
    related = [dict(r) for r in c.fetchall()]
    
    # Reviews
    c.execute("SELECT * FROM product_reviews WHERE product_id=? ORDER BY created_at DESC LIMIT 10", (product_id,))
    reviews = [dict(r) for r in c.fetchall()]
    
    c.execute("SELECT AVG(rating), COUNT(*) FROM product_reviews WHERE product_id=?", (product_id,))
    stats = c.fetchone()
    avg_rating = round(stats[0] or 0, 1)
    total_reviews = stats[1] or 0
    
    db.close()
    
    # Category-based slug prefix
    cat_slug = p.get('product_type', 'products').replace('_', '-')
    slug = p.get('slug', product_id)
    full_url = f'/products/{slug}'
    
    # Build stars
    stars = '★' * int(avg_rating) + '☆' * (5 - int(avg_rating))
    
    # Type icon
    type_icon = product_type_icon(p['product_type'])
    
    # Screenshots
    screenshots = []
    try:
        screenshots = json.loads(p.get('screenshot_urls') or '[]')
    except:
        pass
    if not screenshots:
        screenshots = ['', '', '']
    
    # Related products HTML
    related_html = ''
    for r in related:
        s = product_type_icon(r['product_type'])
        r_slug = r.get('slug', r['id'])
        related_html += f'''<a href="/products/{r_slug}" class="bg-[#1a1a26] border border-[#252533] rounded-lg p-3 hover:border-[#a855f7]/40 transition group">
  <span class="text-2xl">{s}</span>
  <h4 class="font-semibold text-xs mt-1 group-hover:text-[#c084fc]">{(r['title'] or '')[:50]}</h4>
  <div class="text-xs text-[#a855f7] font-bold mt-1">${r['price']}</div>
</a>'''
    
    # Reviews HTML
    reviews_html = ''
    for rev in reviews:
        rev_stars = '★' * int(rev['rating']) + '☆' * (5 - int(rev['rating']))
        reviews_html += f'''<div class="border-b border-[#1e1e2e] py-3 last:border-0">
  <div class="flex items-center gap-2 text-xs"><span class="text-[#facc15]">{rev_stars}</span><span class="font-semibold">{rev.get('author','Anonymous')[:30]}</span></div>
  <p class="text-xs text-[#b0b0c0] mt-1">{(rev.get('text','')[:200])}</p>
</div>'''
    if not reviews_html:
        reviews_html = '<p class="text-xs text-[#5c5c70] py-4">No reviews yet. Be the first!</p>'
    
    # Build upsells
    upsells_data = []
    try:
        upsells_data = json.loads(p.get('upsells') or '[]')
    except:
        pass
    upsells_html = ''
    for u in upsells_data:
        upsells_html += f'''<div class="flex items-center gap-3 p-3 bg-[#1a1a26] rounded-lg border border-[#252533]">
  <span class="text-xl">{u.get('icon','🤖')}</span>
  <div class="flex-1"><div class="text-xs font-semibold">{u.get('name','')}</div><div class="text-[10px] text-[#5c5c70]">{u.get('desc','')}</div></div>
  <span class="font-bold text-xs text-[#a855f7]">${u.get('price',0)}</span>
</div>'''
    if upsells_html:
        upsells_html = f'<div class="space-y-2">{upsells_html}</div><div class="flex items-center justify-center mt-3 text-xs text-[#4ade80] font-semibold">Save 35% — ${sum(u.get("price",0) for u in upsells_data)}</div>'
    
    # Hero image
    img_html = '<div class="text-center"><span class="text-6xl opacity-30">' + str(type_icon) + '</span><p class="text-xs text-[#5c5c70] mt-2">Premium ' + PRODUCT_TYPE_LABELS.get(p.get('product_type',''), 'Product') + '</p></div>'
    if p.get('screenshot_urls') and str(p.get('screenshot_urls','')) != '[]':
        try:
            ss = json.loads(p.get('screenshot_urls','[]'))
            if ss and ss[0]:
                img_html = '<img src="' + ss[0] + '" class="rounded-xl w-full max-h-[320px] object-cover">'
        except:
            pass
    upd_btn = '<button class="tab-btn px-3 py-2 text-[#5c5c70]" onclick="switchPTab(' + chr(39) + 'updates' + chr(39) + ',this)">Updates</button>'
    
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-6xl mx-auto px-4 sm:px-6 pb-8">

  <!-- Breadcrumb -->
  <div class="text-xs text-[#5c5c70] mb-4 mt-4 flex items-center gap-2">
    <a href="/" class="hover:text-white">Marketplace</a>
    <span>/</span>
    <a href="/?category={p['product_type']}" class="hover:text-white">{PRODUCT_TYPE_LABELS.get(p['product_type'], 'Products')}</a>
    <span>/</span>
    <span class="text-[#b0b0c0]">{(p['title'] or '')[:40]}</span>
  </div>

  <!-- HERO -->
  <div class="card overflow-hidden mb-6" style="padding:0;background:linear-gradient(135deg,#0f0a1e,#1a0a2e,#0e0e16)">
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-0">
      <!-- Left: Product Info -->
      <div class="p-6 sm:p-8 flex flex-col justify-center">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-2xl">{type_icon}</span>
          <span class="text-[10px] font-medium px-2 py-0.5 rounded-full" style="background:{product_type_color(p['product_type'])}20;color:{product_type_color(p['product_type'])}">{PRODUCT_TYPE_LABELS.get(p['product_type'], 'Product')}</span>
          {f'<span class="text-[10px] text-[#4ade80] bg-[#4ade80]/10 px-2 py-0.5 rounded-full">v{version}</span>' if version else ''}
        </div>
        <h1 class="text-2xl sm:text-3xl font-black mb-2 leading-tight">{(p['title'] or '')[:80]}</h1>
        <p class="text-sm text-[#b0b0c0] mb-4">{(p.get('seo_title') or p.get('description') or '')[:120]}</p>
        
        <div class="flex items-center gap-4 text-xs text-[#5c5c70] mb-5">
          <span class="text-[#facc15] text-sm">{stars}</span>
          <span><span class="text-white font-bold">{avg_rating}</span> ({total_reviews} reviews)</span>
          <span><i class="fas fa-download mr-1 text-[#38bdf8]"></i>{p['downloads_count']} users</span>
        </div>
        
        <div class="flex items-center gap-3 mb-6">
          <div class="text-3xl font-bold text-white">${p['price']}<span class="text-sm text-[#5c5c70] font-normal">/month</span></div>
          <a href="/api/checkout/{p['id']}" class="btn-primary text-sm px-8" style="padding:12px 28px;background:linear-gradient(135deg,#a855f7,#7c3aed)"><i class="fas fa-bolt mr-1"></i> Install Now</a>
          <a href="#demo" class="btn-secondary text-sm" style="padding:12px 20px"><i class="fas fa-play mr-1"></i> Demo</a>
        </div>
        
        <div class="text-[10px] text-[#5c5c70]">Trusted by 100+ businesses worldwide</div>
      </div>
      
      <!-- Right: Hero Image -->
      <div class="bg-gradient-to-br from-[#a855f7]/10 to-[#7c3aed]/5 p-6 sm:p-8 flex items-center justify-center min-h-[250px]">
        {img_html}
      </div>
    </div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <!-- Main Content -->
    <div class="lg:col-span-2 space-y-6">
      
      <!-- Quick Stats -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div class="card text-center py-4"><div class="text-lg font-bold text-[#a855f7]">{hermes_score}</div><div class="text-[10px] text-[#5c5c70]">Hermes Score</div></div>
        <div class="card text-center py-4"><div class="text-lg font-bold text-[#38bdf8]">{p['downloads_count']}</div><div class="text-[10px] text-[#5c5c70]">Downloads</div></div>
        <div class="card text-center py-4"><div class="text-lg font-bold text-[#facc15]">{avg_rating}</div><div class="text-[10px] text-[#5c5c70]">Rating</div></div>
        <div class="card text-center py-4"><div class="text-lg font-bold text-[#4ade80]">{p.get('version','1.0')}</div><div class="text-[10px] text-[#5c5c70]">Version</div></div>
      </div>
      
      <!-- Why Buy / Benefits -->
      <div class="card" style="padding:24px">
        <h3 class="font-bold text-sm mb-3"><i class="fas fa-heart text-[#f472b6] mr-1"></i> Why Customers Love This</h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {''.join(f'<div class="flex items-center gap-2 text-xs text-[#b0b0c0]"><i class="fas fa-check-circle text-[#4ade80]"></i>{b[:80]}</div>' for b in benefits)}
        </div>
      </div>
      
      <!-- Tabs -->
      <div class="card" style="padding:0">
        <div class="flex gap-1 border-b border-[#1e1e2e] px-4 pt-3 overflow-x-auto text-xs" id="productTabs">
          <button class="tab-btn active px-3 py-2 font-semibold text-white" onclick="switchPTab('overview',this)">Overview</button>
          <button class="tab-btn px-3 py-2 text-[#5c5c70]" onclick="switchPTab('features',this)">Features</button>
          <button class="tab-btn px-3 py-2 text-[#5c5c70]" onclick="switchPTab('installation',this)">Installation</button>
          <button class="tab-btn px-3 py-2 text-[#5c5c70]" onclick="switchPTab('reviews',this)">Reviews ({total_reviews})</button>
          {upd_btn if changelog else ''}
          <button class="tab-btn px-3 py-2 text-[#5c5c70]" onclick="switchPTab('faq',this)">FAQ</button>
        </div>
        
        <div id="tab-overview" class="tab-pane p-5 text-sm text-[#b0b0c0] leading-relaxed">{p.get('description','No description')[:2000]}</div>
        <div id="tab-features" class="tab-pane hidden p-5 text-sm text-[#b0b0c0] leading-relaxed whitespace-pre-wrap">{features[:2000] if features else p.get('description','')[:1000]}</div>
        <div id="tab-installation" class="tab-pane hidden p-5 text-sm text-[#b0b0c0] leading-relaxed">{f'<h4 class="font-bold mb-2">Installation Guide</h4><p>1. Download the product<br>2. Unzip the files<br>3. Follow the included documentation<br>4. Configure for your use case<br>5. Start using immediately!</p><p class="mt-2 text-[#5c5c70]">Requirements: {p.get("requirements","Internet connection")[:200]}</p>'}</div>
        <div id="tab-reviews" class="tab-pane hidden p-5">
          <div class="flex items-center justify-between mb-4">
            <div><span class="text-2xl font-bold">{avg_rating}</span><span class="text-[#facc15] text-sm ml-1">{stars}</span><span class="text-xs text-[#5c5c70] ml-2">({total_reviews} reviews)</span></div>
            <button onclick="document.getElementById('reviewForm').classList.toggle('hidden')" class="btn-secondary text-xs" style="padding:8px 14px">Write Review</button>
          </div>
          <div id="reviewForm" class="hidden bg-[#1a1a26] rounded-lg p-4 mb-4 space-y-2">
            <input id="reviewName" class="text-xs" placeholder="Your name">
            <select id="reviewRating" class="text-xs"><option value="5">⭐⭐⭐⭐⭐</option><option value="4">⭐⭐⭐⭐</option><option value="3">⭐⭐⭐</option><option value="2">⭐⭐</option><option value="1">⭐</option></select>
            <textarea id="reviewText" class="text-xs" placeholder="Your review..." rows="2"></textarea>
            <button onclick="submitReview('{product_id}')" class="btn-primary text-xs">Submit Review</button>
          </div>
          {reviews_html}
        </div>
        {'<div id="tab-updates" class="tab-pane hidden p-5 text-sm text-[#b0b0c0] whitespace-pre-wrap">' + changelog[:2000] + '</div>' if changelog else ''}
        <div id="tab-faq" class="tab-pane hidden p-5 text-sm text-[#b0b0c0]">
          <div class="space-y-3"><div class="p-3 bg-[#1a1a26] rounded-lg"><p class="font-semibold text-xs mb-1">What is this product?</p><p class="text-xs text-[#5c5c70]">{(p.get("description") or "")[:200]}</p></div>
          <div class="p-3 bg-[#1a1a26] rounded-lg"><p class="font-semibold text-xs mb-1">How do I install it?</p><p class="text-xs text-[#5c5c70]">Download the files and follow the included documentation. Most products require no technical skills.</p></div>
          <div class="p-3 bg-[#1a1a26] rounded-lg"><p class="font-semibold text-xs mb-1">Do I get updates?</p><p class="text-xs text-[#5c5c70]">Yes! All products include{' lifetime' if not version else ' '}updates{'' if not version else f' (currently v{version})'}.</p></div>
          <div class="p-3 bg-[#1a1a26] rounded-lg"><p class="font-semibold text-xs mb-1">What if I have issues?</p><p class="text-xs text-[#5c5c70]">Contact the creator directly or use the Ask Hermes feature for instant support.</p></div></div>
        </div>
      </div>
      
      <!-- Hermes AI Assistant -->
      <div class="card" style="padding:20px;border:1px solid #a855f740;background:linear-gradient(135deg,#1a0a2e,#0e0e16)">
        <div class="flex items-center gap-3 mb-3">
          <span class="w-10 h-10 rounded-full bg-[#a855f7]/20 flex items-center justify-center"><i class="fas fa-robot text-[#a855f7]"></i></span>
          <div><h3 class="font-bold text-sm">Ask Hermes About This Product</h3><p class="text-xs text-[#5c5c70]">AI-powered product assistant</p></div>
        </div>
        <div class="flex gap-2">
          <input id="hermesAsk" class="text-sm flex-1" placeholder="e.g. Is this good for my business?">
          <button onclick="askHermesAboutProduct('{product_id}')" class="btn-primary text-sm"><i class="fas fa-paper-plane"></i></button>
        </div>
        <div id="hermesProductAnswer" class="mt-3 text-sm text-[#b0b0c0] hidden"></div>
      </div>
      
      <!-- Related Products -->
      <div class="card" style="padding:20px">
        <h3 class="font-bold text-sm mb-3">Related Products</h3>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">{related_html}</div>
      </div>
      
    </div>
    
    <!-- Sidebar -->
    <div class="space-y-4">
      
      <!-- Score Card -->
      <div class="card" style="padding:20px;border:1px solid #a855f740">
        <h3 class="font-bold text-sm mb-3"><i class="fas fa-brain text-[#a855f7] mr-1"></i> Hermes Score</h3>
        <div class="text-center mb-4">
          <div class="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-[#a855f7] to-[#4ade80]">{hermes_score}</div>
          <div class="text-[10px] text-[#5c5c70]">/ 100</div>
        </div>
        <div class="space-y-2 text-xs">
          <div><div class="flex justify-between mb-0.5"><span>Quality</span><span>{quality}/100</span></div><div class="w-full bg-[#1a1a26] h-1.5 rounded-full"><div class="bg-[#4ade80] h-1.5 rounded-full" style="width:{quality}%"></div></div></div>
          <div><div class="flex justify-between mb-0.5"><span>SEO</span><span>{seo_score}/100</span></div><div class="w-full bg-[#1a1a26] h-1.5 rounded-full"><div class="bg-[#38bdf8] h-1.5 rounded-full" style="width:{seo_score}%"></div></div></div>
          <div><div class="flex justify-between mb-0.5"><span>Demand</span><span>{demand}/100</span></div><div class="w-full bg-[#1a1a26] h-1.5 rounded-full"><div class="bg-[#facc15] h-1.5 rounded-full" style="width:{demand}%"></div></div></div>
        </div>
        <div class="text-[10px] text-[#5c5c70] mt-3 text-center">Updated: {now.strftime('%b %d, %Y')}</div>
      </div>
      
      <!-- Price + Buy -->
      <div class="card sticky top-20" style="padding:24px">
        <div class="text-2xl font-bold mb-1">${p['price']}</div>
        <div class="text-xs text-[#5c5c70] mb-4">One-time payment · Lifetime access</div>
        <a href="/api/checkout/{p['id']}" class="btn-primary w-full text-sm mb-3" style="padding:14px;background:linear-gradient(135deg,#a855f7,#7c3aed)"><i class="fas fa-bolt mr-1"></i> Install Now</a>
        
        <!-- Compatibility -->
        <div class="mb-4">
          <h4 class="text-xs font-semibold mb-2 text-[#5c5c70]">Compatible With</h4>
          <div class="flex flex-wrap gap-1.5">{''.join(f'<span class="text-[10px] px-2 py-0.5 rounded-full bg-[#1a1a26] border border-[#252533]">{c.strip()[:20]}</span>' for c in compat_items)}</div>
        </div>
        
        <div class="text-xs text-[#5c5c70] space-y-1.5">
          <div><i class="fas fa-check text-[#4ade80] w-4"></i> Instant Download</div>
          <div><i class="fas fa-check text-[#4ade80] w-4"></i> Commercial License</div>
          <div><i class="fas fa-check text-[#4ade80] w-4"></i> Lifetime Updates</div>
          <div><i class="fas fa-check text-[#4ade80] w-4"></i> 30-Day Guarantee</div>
        </div>
      </div>
      
      <!-- Creator Card -->
      <div class="card" style="padding:16px">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-full bg-gradient-to-br from-[#a855f7] to-[#7c3aed] flex items-center justify-center text-white font-bold text-sm">{(creator_name[:2]).upper()}</div>
          <div>
            <h4 class="font-semibold text-sm">{creator_name[:30]}</h4>
            <div class="flex items-center gap-1 text-[10px] text-[#5c5c70]"><span>★★★★★</span><span>{creator_products} products</span></div>
          </div>
        </div>
      </div>
      
      <!-- Upsells -->
      {'<div class="card" style="padding:20px;border:1px solid #4ade8040"><h3 class="font-bold text-sm mb-3"><i class="fas fa-gem text-[#4ade80] mr-1"></i> Recommended Bundle</h3>' + upsells_html + '</div>' if upsells_html else ''}
      
    </div>
  </div>
  
  <!-- SEO Content Below -->
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6">
    <a href="/products?q=best" class="card text-center py-3 hover:border-[#a855f7]/40"><span class="text-xs font-semibold">Best {PRODUCT_TYPE_LABELS.get(p['product_type'],'Products')}</span><span class="text-[10px] text-[#5c5c70] block mt-0.5">See top rated</span></a>
    <a href="/products?q=trending" class="card text-center py-3 hover:border-[#a855f7]/40"><span class="text-xs font-semibold">Trending {PRODUCT_TYPE_LABELS.get(p['product_type'],'Products')}</span><span class="text-[10px] text-[#5c5c70] block mt-0.5">What's popular now</span></a>
    <a href="/products?q=bundles" class="card text-center py-3 hover:border-[#a855f7]/40"><span class="text-xs font-semibold">{PRODUCT_TYPE_LABELS.get(p['product_type'],'Product')} Bundles</span><span class="text-[10px] text-[#5c5c70] block mt-0.5">Save with bundles</span></a>
  </div>
  
</div>

<script>
function switchPTab(tab,btn) {{
  document.querySelectorAll('#productTabs .tab-btn').forEach(b=>b.classList.remove('active','text-white'));
  btn.classList.add('active','text-white');
  document.querySelectorAll('.tab-pane').forEach(p=>p.classList.add('hidden'));
  const el = document.getElementById('tab-'+tab);
  if(el) el.classList.remove('hidden');
}}

async function submitReview(pid) {{
  const name = document.getElementById('reviewName').value || 'Anonymous';
  const rating = document.getElementById('reviewRating').value;
  const text = document.getElementById('reviewText').value;
  if(!text) return alert('Please write a review');
  try {{
    const r = await fetch('/api/review', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{product_id:pid, author:name, rating:parseInt(rating), text}})}});
    const d = await r.json();
    if(d.success) location.reload(); else alert('Error');
  }} catch(e) {{ alert('Error submitting review'); }}
}}

async function askHermesAboutProduct(pid) {{
  const q = document.getElementById('hermesAsk').value;
  if(!q) return;
  const ans = document.getElementById('hermesProductAnswer');
  ans.classList.remove('hidden');
  ans.innerHTML = '<i class=\"fas fa-spinner fa-spin text-[#a855f7]\"></i>';
  try {{
    const r = await fetch('/api/customer/ask', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({question: q + " (product: " + pid + ")"})}});
    const d = await r.json();
    ans.innerHTML = '<div class=\\"flex gap-2\\"><i class=\\"fas fa-robot text-[#a855f7]\\"></i><p>' + (d.answer || 'No answer') + '</p></div>';
  }} catch(e) {{ ans.innerHTML = 'Error'; }}
}}
</script>
{LAYOUT_FOOT}'''

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

