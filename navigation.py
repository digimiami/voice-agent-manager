"""ShopZario Navigation System - Mega menu, search, footer, mobile nav"""
import json, datetime, sqlite3

DB = '/root/voice-agent-businesses.db'

def get_categories():
    """Get product categories from DB with counts."""
    conn = sqlite3.connect(DB)
    rows = conn.execute("""
        SELECT product_type, COUNT(*) as cnt, ROUND(AVG(price),2) as avg_price
        FROM products WHERE status='published' GROUP BY product_type ORDER BY cnt DESC
    """).fetchall()
    conn.close()
    return rows

def get_trending(limit=5):
    """Get trending products."""
    conn = sqlite3.connect(DB)
    rows = conn.execute("""
        SELECT id, title, slug, price, product_type FROM products 
        WHERE status='published' ORDER BY downloads_count DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows

def get_new_products(limit=5):
    """Get newest products."""
    conn = sqlite3.connect(DB)
    rows = conn.execute("""
        SELECT id, title, slug, price, product_type FROM products 
        WHERE status='published' ORDER BY created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows

# ── Config ──
NAV_CONFIG = {
    "announcement": {
        "enabled": True,
        "text": "🔥 AI-Powered Marketplace — Instant Delivery — 30-Day Guarantee",
        "bg": "linear-gradient(90deg, #7c3aed, #ec4899)",
        "link": "/new",
        "link_text": "Shop Now →"
    },
    "categories": {
        "AI Products": {
            "icon": "🤖",
            "color": "#a855f7",
            "items": [
                ("ChatGPT Prompts", "/?category=prompt_pack", "💬"),
                ("Claude Prompts", "/?category=prompt_pack", "🧠"),
                ("Gemini Prompts", "/?category=prompt_pack", "✨"),
                ("AI Automations", "/?category=code", "⚡"),
                ("AI Voice Agents", "/?category=code", "🎙️"),
                ("AI Images", "/factory/generate-images", "🎨"),
            ]
        },
        "Business": {
            "icon": "💼",
            "color": "#38bdf8",
            "items": [
                ("Contracts & Legal", "/?category=business_doc", "⚖️"),
                ("Finance & Accounting", "/?category=template", "💰"),
                ("Marketing Templates", "/?category=marketing", "📢"),
                ("Checklists", "/?category=checklist", "✅"),
                ("eBooks & Guides", "/?category=ebook", "📚"),
            ]
        },
        "Templates": {
            "icon": "📋",
            "color": "#4ade80",
            "items": [
                ("Notion Templates", "/?category=template", "📓"),
                ("Canva Templates", "/?category=template", "🎨"),
                ("Excel/Sheets", "/?category=template", "📊"),
                ("PowerPoint", "/?category=template", "📽️"),
                ("Social Media", "/?category=marketing", "📱"),
            ]
        },
        "Development": {
            "icon": "⚙️",
            "color": "#f472b6",
            "items": [
                ("React Components", "/?category=code", "⚛️"),
                ("Python Scripts", "/?category=code", "🐍"),
                ("TailwindCSS", "/?category=code", "🎨"),
                ("Full-Stack Starter", "/?category=code", "🚀"),
            ]
        },
    }
}

def top_bar():
    """Top announcement bar."""
    cfg = NAV_CONFIG["announcement"]
    if not cfg["enabled"]:
        return ""
    link = cfg.get("link", "")
    link_html = f'<a href="{link}" class="ml-3 text-xs font-semibold underline underline-offset-2 hover:no-underline whitespace-nowrap">{cfg["link_text"]}</a>' if link else ""
    return f'''<div class="top-bar" style="background:{cfg["bg"]}">
    <div class="max-w-6xl mx-auto px-4 flex items-center justify-center h-9 text-[11px] font-medium text-white/90">
      <span>{cfg["text"]}</span>
      {link_html}
      <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white/60 hover:text-white transition" aria-label="Dismiss">✕</button>
    </div>
  </div>'''

def mega_nav():
    """Full main navigation with mega menu."""
    cats = get_categories()
    cats_html = ""
    for ptype, cnt, avg_p in cats:
        icon_map = {"prompt_pack":"🤖","template":"📋","code":"⚙️","checklist":"✅","marketing":"📢","ebook":"📚","business_doc":"⚖️","marketing_tool":"📱"}
        lbl_map = {"prompt_pack":"Prompts","template":"Templates","code":"Code","checklist":"Checklists","marketing":"Marketing","ebook":"eBooks","business_doc":"Documents","marketing_tool":"Tools"}
        icon = icon_map.get(ptype, "📦")
        label = lbl_map.get(ptype, ptype.replace("_"," ").title())
        cats_html += f'<a href="/?category={ptype}" class="mega-link"><span class="text-lg">{icon}</span><div class="min-w-0"><div class="text-xs font-semibold text-white truncate">{label}</div><div class="text-[10px] text-gray-500">{cnt} products</div></div></a>'
    
    trending = get_trending(4)
    tr_html = ""
    for pid, title, slug, pr, pt in trending:
        icon = {"prompt_pack":"🤖","template":"📋","code":"⚙️","checklist":"✅","marketing":"📢","ebook":"📚","business_doc":"⚖️","marketing_tool":"📱"}.get(pt, "📦")
        tr_html += f'<a href="/product/{slug or pid}" class="flex items-center gap-3 p-2 rounded-xl hover:bg-white/5 transition"><span class="text-lg">{icon}</span><div class="min-w-0 flex-1"><div class="text-xs font-semibold text-white truncate">{title[:45]}</div><span class="text-[10px] text-purple-400">${pr}</span></div></a>'
    
    # Mega menu categories
    mm_cats = ""
    for cname, cdata in NAV_CONFIG["categories"].items():
        items = "".join([f'<a href="{url}" class="block text-xs text-gray-400 hover:text-white hover:bg-white/5 rounded-lg px-2.5 py-2 transition flex items-center gap-2"><span>{ic}</span><span>{name}</span></a>' for name, url, ic in cdata["items"]])
        mm_cats += f'''<div class="min-w-[200px]">
          <div class="flex items-center gap-2 px-2.5 mb-2"><span class="text-lg">{cdata["icon"]}</span><span class="text-xs font-bold text-white uppercase tracking-wider">{cname}</span></div>
          <div class="space-y-0.5">{items}</div>
        </div>'''
    
    return f'''<nav class="sticky top-0 z-40" style="background:#0a0a12;border-bottom:1px solid rgba(255,255,255,0.05)">
  
  <!-- Main Header -->
  <div class="max-w-6xl mx-auto px-4">
    <div class="flex items-center justify-between h-14">
      
      <!-- Left: Logo + Hamburger -->
      <div class="flex items-center gap-4">
        <button class="md:hidden w-9 h-9 flex items-center justify-center rounded-lg hover:bg-white/5 transition" onclick="toggleMegaMobile()" aria-label="Menu">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </button>
        <a href="/" class="flex items-center gap-2.5">
          <img src="/static/logo_small.png" alt="ShopZario" class="w-8 h-8 rounded-lg object-cover">
          <span class="font-bold text-base hidden sm:inline" style="background:linear-gradient(90deg,#c084fc,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent">ShopZario</span>
        </a>
      </div>
      
      <!-- Center: Search (desktop) -->
      <div class="hidden md:flex flex-1 max-w-2xl mx-6">
        <div class="relative w-full search-wrapper">
          <input type="text" id="navSearch" class="w-full h-10 pl-10 pr-4 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-purple-500/50 focus:bg-white/10 transition-all search-input" placeholder="Search 200+ products..." autocomplete="off" oninput="searchSuggest(this.value)" onfocus="searchSuggest(this.value)">
          <svg class="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <!-- Search dropdown -->
          <div id="searchDropdown" class="search-dropdown hidden absolute top-full left-0 right-0 mt-2 rounded-2xl bg-[#0e0e16] border border-white/10 shadow-2xl overflow-hidden z-50">
            <div class="p-4 space-y-3 max-h-[70vh] overflow-y-auto" id="searchResults">
              <div class="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">Popular Searches</div>
              <div class="flex flex-wrap gap-2">
                <a href="/?category=prompt_pack" class="tag tag-purple text-xs">🤖 Prompts</a>
                <a href="/?category=template" class="tag tag-green text-xs">📋 Templates</a>
                <a href="/?category=code" class="tag tag-pink text-xs">⚙️ Code</a>
                <a href="/?category=checklist" class="tag tag-amber text-xs">✅ Checklists</a>
              </div>
              <div class="text-[10px] text-gray-600 uppercase tracking-wider font-semibold pt-2">Trending</div>
              <div class="space-y-1">''' + tr_html + '''</div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Right: Nav Links + User -->
      <div class="flex items-center gap-2">
        <a href="/legals" class="hidden lg:flex items-center gap-1.5 text-xs font-medium text-gray-400 hover:text-white px-3 py-2 rounded-lg hover:bg-white/5 transition"><i class="fas fa-scale-balanced text-[10px]"></i> Legal</a>
        <a href="/account" class="hidden lg:flex items-center gap-1.5 text-xs font-medium text-gray-400 hover:text-white px-3 py-2 rounded-lg hover:bg-white/5 transition"><i class="fas fa-user text-[10px]"></i> My Account</a>
        <div class="flex items-center gap-1">
          <a href="/factory/campaigns" class="text-xs font-medium text-gray-400 hover:text-white px-2 py-1.5 rounded-lg hover:bg-white/5 transition"><i class="fas fa-rocket"></i></a>
          <a href="/factory" class="btn-primary text-xs" style="padding:8px 16px;font-size:11px"><i class="fas fa-wand-magic-sparkles mr-1"></i> Create</a>
        </div>
      </div>
    </div>
  </div>
  
  <!-- Category Bar (desktop) -->
  <div class="hidden md:block max-w-6xl mx-auto px-4 pb-1">
    <div class="flex items-center gap-0.5 overflow-x-auto scrollbar-none">
      <!-- Mega Menu Toggle -->
      <div class="relative mega-trigger" onmouseenter="openMega()" onmouseleave="closeMega()">
        <button class="flex items-center gap-2 text-xs font-semibold text-white px-3 py-2 rounded-lg hover:bg-white/5 transition whitespace-nowrap mega-btn" onclick="toggleMega()">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 4h12M2 8h12M2 12h8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
          Categories
        </button>
        <!-- Mega Dropdown -->
        <div id="megaMenu" class="mega-menu hidden absolute top-full left-0 mt-1 rounded-2xl bg-[#0e0e16] border border-white/10 shadow-2xl p-5 z-50" style="width:720px;max-height:80vh;overflow-y:auto">
          <div class="grid grid-cols-3 gap-6">''' + mm_cats + '''</div>
          <div class="mt-5 pt-4 border-t border-white/10">
            <a href="/?tab=trending" class="text-xs font-semibold text-purple-400 hover:text-purple-300 transition">View All Categories →</a>
          </div>
        </div>
      </div>
      
      <!-- Category Links -->
      <a href="/?category=prompt_pack" class="category-pill">🤖 Prompts</a>
      <a href="/?category=template" class="category-pill">📋 Templates</a>
      <a href="/?category=code" class="category-pill">⚙️ Code</a>
      <a href="/?category=checklist" class="category-pill">✅ Checklists</a>
      <a href="/?category=marketing" class="category-pill">📢 Marketing</a>
      <a href="/?category=ebook" class="category-pill">📚 eBooks</a>
      <a href="/new" class="category-pill category-pill-new"><i class="fas fa-bolt text-yellow-400 text-[9px]"></i> New</a>
    </div>
  </div>
  
  <!-- Mobile Overlay + Menu -->
  <div class="mobile-overlay" id="mbOverlay" onclick="closeMegaMobile()"></div>
  <div class="fixed top-0 left-0 bottom-0 w-[300px] bg-[#0a0a12] border-r border-white/10 z-50 transform -translate-x-full transition-transform duration-300 overflow-y-auto" id="mbMenu">
    <div class="p-4">
      <div class="flex items-center justify-between mb-6">
        <span class="font-bold text-sm" style="background:linear-gradient(90deg,#c084fc,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent">ShopZario</span>
        <button onclick="closeMegaMobile()" class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/5"><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></button>
      </div>
      <!-- Mobile Search -->
      <div class="relative mb-5">
        <input type="text" class="w-full h-10 pl-9 pr-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-600" placeholder="Search products...">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
      </div>
      <!-- Mobile Links -->
      <div class="space-y-1">
        <a href="/" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm font-medium"><i class="fas fa-store w-5 text-purple-400"></i>Home</a>
        <a href="/?tab=trending" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm font-medium"><i class="fas fa-fire w-5 text-pink-400"></i>Trending</a>
        <a href="/new" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm font-medium"><i class="fas fa-bolt w-5 text-yellow-400"></i>New Releases</a>
        <a href="/bundles" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm font-medium"><i class="fas fa-cubes w-5 text-green-400"></i>Bundles</a>
      </div>
      <div class="border-t border-white/10 my-3"></div>
      <div class="text-[10px] text-gray-600 uppercase tracking-wider px-3 mb-2 font-semibold">Categories</div>
      <div class="space-y-1">
        <a href="/?category=prompt_pack" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm font-medium">🤖 Prompts</a>
        <a href="/?category=template" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm font-medium">📋 Templates</a>
        <a href="/?category=code" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm font-medium">⚙️ Code</a>
        <a href="/?category=checklist" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm font-medium">✅ Checklists</a>
        <a href="/?category=marketing" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm font-medium">📢 Marketing</a>
        <a href="/?category=ebook" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm font-medium">📚 eBooks</a>
      </div>
      <div class="border-t border-white/10 my-3"></div>
      <div class="space-y-1">
        <a href="/legals" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm"><i class="fas fa-scale-balanced w-5 text-gray-500"></i>Legal</a>
        <a href="/account" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm"><i class="fas fa-user w-5 text-gray-500"></i>My Account</a>
        <a href="/factory" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm"><i class="fas fa-wand-magic-sparkles w-5 text-purple-400"></i>Create</a>
      <a href="/factory/ads" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm"><i class="fas fa-bullhorn w-5 text-pink-400"></i>Ad Generator</a>
      <a href="/factory/campaigns" class="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/5 text-sm"><i class="fas fa-rocket w-5 text-green-400"></i>Campaigns</a>
      </div>
    </div>
  </div>
  
  <style>
  .category-pill{display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:8px;font-size:11px;font-weight:600;color:#a0a0b0;white-space:nowrap;transition:all .2s}
  .category-pill:hover{background:rgba(255,255,255,0.05);color:#fff}
  .category-pill-new{background:rgba(250,204,21,0.08);color:#facc15}
  .category-pill-new:hover{background:rgba(250,204,21,0.15)}
  .mega-link{display:flex;align-items:center;gap:10px;padding:8px;border-radius:10px;font-size:12px;color:#a0a0b0;transition:all .2s}
  .mega-link:hover{background:rgba(255,255,255,0.05);color:#fff}
  .mega-menu{backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);background:rgba(10,10,18,0.97)}
  .search-dropdown{backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px)}
  .scrollbar-none::-webkit-scrollbar{display:none}
  .mobile-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:40}
  .mobile-overlay.show{display:block}
  #mbMenu.open{transform:translateX(0)}
  </style>
  
  <script>
  function openMega(){document.getElementById('megaMenu').classList.remove('hidden')}
  function closeMega(){document.getElementById('megaMenu').classList.add('hidden')}
  function toggleMega(){document.getElementById('megaMenu').classList.toggle('hidden')}
  function toggleMegaMobile(){document.getElementById('mbMenu').classList.toggle('open');document.getElementById('mbOverlay').classList.toggle('show')}
  function closeMegaMobile(){document.getElementById('mbMenu').classList.remove('open');document.getElementById('mbOverlay').classList.remove('show')}
  function searchSuggest(v){var d=document.getElementById('searchDropdown');if(v.length>0){d.classList.remove('hidden')}else{d.classList.add('hidden')}}
  document.addEventListener('click',function(e){var sw=document.querySelector('.search-wrapper');if(sw&&!sw.contains(e.target)){document.getElementById('searchDropdown').classList.add('hidden')}})
  document.addEventListener('keydown',function(e){if(e.key==='Escape'){document.getElementById('searchDropdown').classList.add('hidden')}})
  </script>
</nav>'''

def footer():
    """Comprehensive footer with all sections."""
    cats = get_categories()
    cat_links = "".join([f'<a href="/?category={r[0]}" class="text-xs text-gray-500 hover:text-purple-300 transition">{r[0].replace("_"," ").title()}</a>' for r in cats])
    trending = get_trending(5)
    tr_html = "".join([f'<a href="/product/{r[2] or r[0]}" class="flex items-center gap-2 py-2 border-b border-white/5 last:border-0"><span class="text-xs text-gray-400 truncate flex-1">{r[1][:40]}</span><span class="text-[10px] font-semibold text-purple-400">${r[3]}</span></a>' for r in trending])
    
    return f'''<footer class="border-t border-white/10 mt-12" style="background:#08080e">
  <div class="max-w-6xl mx-auto px-4 py-10">
    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-8 mb-10">
      
      <!-- Brand -->
      <div class="col-span-2 md:col-span-1 lg:col-span-1">
        <div class="flex items-center gap-2 mb-4">
          <img src="/static/logo_small.png" alt="ShopZario" class="w-8 h-8 rounded-lg object-cover">
          <span class="font-bold text-sm" style="background:linear-gradient(90deg,#c084fc,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent">ShopZario</span>
        </div>
        <p class="text-[11px] text-gray-600 leading-relaxed mb-4">Premium digital products marketplace. AI-powered, instant delivery, lifetime access.</p>
        <div class="flex gap-2">
          <a href="#" class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center hover:bg-white/10 transition"><i class="fab fa-twitter text-[11px] text-gray-500"></i></a>
          <a href="#" class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center hover:bg-white/10 transition"><i class="fab fa-discord text-[11px] text-gray-500"></i></a>
          <a href="#" class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center hover:bg-white/10 transition"><i class="fab fa-github text-[11px] text-gray-500"></i></a>
          <a href="#" class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center hover:bg-white/10 transition"><i class="fab fa-youtube text-[11px] text-gray-500"></i></a>
        </div>
      </div>
      
      <!-- Explore -->
      <div>
        <h4 class="text-xs font-bold text-white uppercase tracking-wider mb-4">Explore</h4>
        <div class="space-y-2.5">
          <a href="/?category=prompt_pack" class="block text-xs text-gray-500 hover:text-purple-300 transition">Prompt Pack</a>
          <a href="/?category=template" class="block text-xs text-gray-500 hover:text-purple-300 transition">Template</a>
          <a href="/?category=checklist" class="block text-xs text-gray-500 hover:text-purple-300 transition">Checklist</a>
          <a href="/?category=marketing" class="block text-xs text-gray-500 hover:text-purple-300 transition">Marketing</a>
          <a href="/?category=code" class="block text-xs text-gray-500 hover:text-purple-300 transition">Code</a>
          <a href="/?category=marketing_tool" class="block text-xs text-gray-500 hover:text-purple-300 transition">Marketing Tool</a>
          <a href="/?category=ebook" class="block text-xs text-gray-500 hover:text-purple-300 transition">eBook</a>
          <a href="/?category=business_doc" class="block text-xs text-gray-500 hover:text-purple-300 transition">Business Doc</a>
        </div>
      </div>
      
      <!-- Quick Links -->
      <div>
        <h4 class="text-xs font-bold text-white uppercase tracking-wider mb-4">Quick Links</h4>
        <div class="space-y-2.5">
          <a href="/new" class="block text-xs text-gray-500 hover:text-purple-300 transition">New Releases</a>
          <a href="/?tab=trending" class="block text-xs text-gray-500 hover:text-purple-300 transition">Best Sellers</a>
          <a href="/bundles" class="block text-xs text-gray-500 hover:text-purple-300 transition">Bundles</a>
          <a href="/factory" class="block text-xs text-gray-500 hover:text-purple-300 transition">Create Product</a>
          <a href="/ai-agents-directory" class="block text-xs text-gray-500 hover:text-purple-300 transition">AI Agents</a>
        </div>
      </div>
      
      <!-- Support -->
      <div>
        <h4 class="text-xs font-bold text-white uppercase tracking-wider mb-4">Support</h4>
        <div class="space-y-2.5">
          <a href="/legals#help" class="block text-xs text-gray-500 hover:text-purple-300 transition">Help Center</a>
          <a href="/legals#contact" class="block text-xs text-gray-500 hover:text-purple-300 transition">Contact Us</a>
          <a href="/legals#faq" class="block text-xs text-gray-500 hover:text-purple-300 transition">FAQ</a>
          <a href="/legals#refund" class="block text-xs text-gray-500 hover:text-purple-300 transition">Refund Policy</a>
          <a href="/legals#licensing" class="block text-xs text-gray-500 hover:text-purple-300 transition">Licensing</a>
        </div>
      </div>
      
      <!-- Company -->
      <div>
        <h4 class="text-xs font-bold text-white uppercase tracking-wider mb-4">Company</h4>
        <div class="space-y-2.5">
          <a href="#" class="block text-xs text-gray-500 hover:text-purple-300 transition">About</a>
          <a href="#" class="block text-xs text-gray-500 hover:text-purple-300 transition">Blog</a>
          <a href="#" class="block text-xs text-gray-500 hover:text-purple-300 transition">Press</a>
          <a href="#" class="block text-xs text-gray-500 hover:text-purple-300 transition">Affiliates</a>
          <a href="/legals" class="block text-xs text-gray-500 hover:text-purple-300 transition">Legal</a>
        </div>
      </div>
    </div>
    
    <!-- Trending Footer -->
    <div class="border-t border-white/5 pt-6 mb-6">
      <h4 class="text-xs font-bold text-white mb-3"><i class="fas fa-fire text-pink-400 mr-2"></i>Trending Products</h4>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">{tr_html}</div>
    </div>
    
    <!-- Bottom Bar -->
    <div class="border-t border-white/5 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
      <p class="text-[10px] text-gray-600">© {datetime.datetime.now().year} ShopZario — The Hermes Digital Marketplace. All products delivered instantly.</p>
      <div class="flex items-center gap-4 text-[10px] text-gray-600">
        <a href="/legals" class="hover:text-purple-300 transition">Privacy Policy</a>
        <a href="/legals" class="hover:text-purple-300 transition">Terms of Service</a>
        <a href="/legals" class="hover:text-purple-300 transition">Cookie Policy</a>
        <span>Made with ❤️ by Hermes AI</span>
      </div>
    </div>
  </div>
</footer>'''

def mobile_bottom_nav():
    return '''<div class="mobile-bottom-nav md:hidden fixed bottom-0 left-0 right-0 z-50 bg-[#0a0a12] border-t border-white/10 px-2 py-1 flex items-center justify-around">
  <a href="/" class="flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg text-[10px] font-medium" style="color:#c084fc"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg><span>Home</span></a>
  <button onclick="document.getElementById('navSearch')?.focus()" class="flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg text-[10px] font-medium text-gray-500"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg><span>Search</span></button>
  <a href="/?tab=trending" class="flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg text-[10px] font-medium text-gray-500"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg><span>Trending</span></a>
  <a href="/account" class="flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg text-[10px] font-medium text-gray-500"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg><span>Account</span></a>
</div>
<style>
.mobile-bottom-nav{backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
@media(min-width:768px){.mobile-bottom-nav{display:none!important}}
</style>'''

def generate():
    """Generate complete navigation HTML."""
    return top_bar() + mega_nav() + mobile_bottom_nav()
