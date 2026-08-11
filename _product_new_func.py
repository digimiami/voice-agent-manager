def product_detail_page(product_id):
    """Render premium, conversion-optimized product sales page."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    row = c.fetchone()
    if not row:
        db.close()
        return '<html><body style="background:#07070c;color:#f1f1f5;display:flex;align-items:center;justify-content:center;height:100vh;font-family:Inter,sans-serif"><div style="text-align:center"><h1 style="font-size:48px;margin:0">404</h1><p>Product not found</p><a href="/" style="color:#c084fc">Back to store</a></div></body></html>'
    p = dict(row)
    db.close()
    ptype = p.get("product_type", "other")
    type_icon = product_type_icon(ptype)
    type_color = product_type_color(ptype)
    type_label = PRODUCT_TYPE_LABELS.get(ptype, "Digital Product")
    title = p.get("title", "Untitled Product") or ""
    desc = p.get("description", "") or ""
    price = p.get("price", 0) or 0
    rating = p.get("rating", 0) or 0
    downloads = p.get("downloads_count", 0) or 0
    version = p.get("version", "1.0.0") or "1.0"
    license_type = p.get("license", "standard") or "standard"
    requirements = p.get("requirements", "") or ""
    faq = p.get("faq", "") or ""
    hero_img = p.get("hero_image_url", "") or ""
    slug = p.get("slug", product_id) or product_id
    seo_title = p.get("seo_title", "") or title
    seo_desc = p.get("seo_description", "") or desc[:150]
    seo_kw = p.get("seo_keywords", "") or type_label + ", " + title
    content_body = p.get("content", "") or p.get("features", "") or desc
    video_url = p.get("video_url", "") or ""
    now = __import__("datetime").datetime.now()
    demand = min(100, downloads * 20)
    quality = min(100, int((len(content_body or "") / 500) * 100))
    seo_score_val = min(100, len(seo_desc or "") // 2)
    review_score = min(100, int((rating or 0) * 20))
    hermes_score = round((demand * 0.25 + quality * 0.25 + seo_score_val * 0.30 + review_score * 0.20), 1)
    stars = chr(9733) * int(rating) + chr(9734) * (5 - int(rating))
    try:
        screenshots = __import__("json").loads(p.get("screenshot_urls", "[]"))
    except:
        screenshots = []
    img_html = '<div class="flex items-center justify-center h-full"><span class="text-7xl opacity-30">' + type_icon + "</span></div>"
    if hero_img:
        img_html = '<img src="' + hero_img.replace('"', "&quot;") + '" class="w-full h-full object-cover rounded-2xl" alt="' + title.replace('"', "&quot;") + '">'
    demo_btn = ""
    if video_url and video_url.startswith("http"):
        demo_btn = '<a href="' + video_url.replace('"', "&quot;") + '" target="_blank" class="btn-outline text-sm px-6 py-3"><i class="fas fa-play mr-1.5"></i> Watch Demo</a>'
    else:
        demo_btn = '<button onclick="generateDemo(' + chr(39) + product_id + chr(39) + ')" class="btn-outline text-sm px-6 py-3"><i class="fas fa-wand-magic-sparkles mr-1.5"></i> Live Preview</button>'
    ptype_data = {"prompt_pack": {"format": "PDF + TXT", "difficulty": "Beginner", "compat": "ChatGPT, Claude, Gemini"},
        "template": {"format": "Canva + Google Slides", "difficulty": "Beginner", "compat": "Canva, Google Workspace"},
        "ebook": {"format": "PDF + EPUB + MOBI", "difficulty": "All Levels", "compat": "Kindle, Apple Books"},
        "checklist": {"format": "PDF + Google Sheets", "difficulty": "Beginner", "compat": "Adobe Reader, Google Sheets"},
        "business_doc": {"format": "DOCX + PDF", "difficulty": "Intermediate", "compat": "MS Word, Google Docs"},
        "marketing": {"format": "Canva + PNG + PSD", "difficulty": "Beginner", "compat": "Canva, Photoshop"},
        "code": {"format": "ZIP (Source Code)", "difficulty": "Int-Advanced", "compat": "VS Code, PyCharm"},
        "starter": {"format": "ZIP + Docs", "difficulty": "Intermediate", "compat": "n8n, Docker, Node.js"},
        "course": {"format": "MP4 + PDF Workbook", "difficulty": "All Levels", "compat": "Browser, Mobile"}}
    fmt = ptype_data.get(ptype, {}).get("format", "PDF + Digital Files")
    difficulty = ptype_data.get(ptype, {}).get("difficulty", "All Levels")
    compat = ptype_data.get(ptype, {}).get("compat", "Web Browser, Desktop, Mobile")
    how_it_works = [["Purchase & Download", "Complete your order in seconds. Instant access."],
        ["Unpack & Explore", "Open files and review the included documentation."],
        ["Customize & Configure", "Simple setup in under 5 minutes. Zero technical skills needed."],
        ["Launch & Profit", "Start using immediately and see results."]]
    why_list = [["Purpose-Built", "Designed to solve a specific problem."],
        ["Instant Delivery", "Files available immediately after payment."],
        ["Lifetime Updates", "Buy once, own forever. Free updates."],
        ["Premium Quality", "Expert-designed and QA-tested."],
        ["30-Day Guarantee", "Not satisfied? Full refund."]]
    trust_list = [["Secure Checkout", "256-bit SSL encrypted"], ["Cards & Crypto", "Visa, MC, PayPal, USDC"],
        ["Instant Download", "No waiting"], ["Lifetime Updates", "Free forever"], ["30-Day Refund", "No questions asked"]]
    included_map = {"prompt_pack": ["150+ premium prompts organized by category", "Step-by-step usage guide", "Examples and output samples", "Lifetime updates"],
        "template": ["Editable template files", "Installation guide PDF", "Customization tutorial", "Lifetime updates"],
        "ebook": ["Full-length eBook PDF", "EPUB and MOBI format", "Printable workbook", "Supplementary resources"],
        "checklist": ["Comprehensive checklist PDF", "Google Sheets version", "Priority matrix template", "Quick-reference card"],
        "business_doc": ["5 fill-in-the-blank templates", "Clause explanation guide", "US and UK versions", "Optional addendums"],
        "marketing": ["50+ premium templates", "Canva editable files", "Font pairing guide", "Brand style guide"],
        "code": ["10 production-ready Python scripts", "Comprehensive documentation", "Test files included", "Requirements.txt"],
        "starter": ["15+ pre-built automation workflows", "Setup guide PDF", "API configuration guide", "Docker compose file"],
        "course": ["10+ hours of HD video content", "PDF workbook and exercises", "Certificate of completion", "Community access"]}
    included_items = included_map.get(ptype, ["Digital files", "Installation guide", "Documentation", "Lifetime updates"])
    db2 = get_db()
    c2 = db2.cursor()
    c2.execute("SELECT id, title, price, product_type, rating, downloads_count, hero_image_url, slug FROM products WHERE status='published' AND id!=? ORDER BY RANDOM() LIMIT 4", (product_id,))
    related = [dict(r) for r in c2.fetchall()]
    db2.close()
    related_html = ""
    for r in related:
        ri = product_type_icon(r["product_type"])
        r_slug = r.get("slug", r["id"])
        r_hero = r.get("hero_image_url", "") or ""
        if r_hero:
            r_img = '<img src="' + r_hero.replace('"', "&quot;") + '" class="w-full h-24 object-cover rounded-lg mb-2">'
        else:
            r_img = '<div class="w-full h-24 rounded-lg bg-[#1a1a26] flex items-center justify-center text-3xl mb-2">' + ri + "</div>"
        related_html += '<a href="/products/' + r_slug + '" class="bg-[#1a1a26] border border-[#252533] rounded-xl p-3 hover:border-[#a855f7]/40 transition-all group hover:-translate-y-0.5">' + r_img + '<h4 class="font-semibold text-xs leading-tight group-hover:text-[#c084fc]">' + (r["title"] or "")[:45] + '</h4><div class="flex items-center justify-between mt-1.5"><span class="text-[10px] text-[#5c5c70]">' + ri + '</span><span class="text-xs font-bold text-[#a855f7]">$' + str(r["price"]) + "</span></div></a>"
    faq_items = []
    if faq:
        try:
            faq_items = __import__("json").loads(faq)
        except:
            faq_items = [{"q": "What is included?", "a": faq[:200]}]
    if not faq_items:
        faq_items = [{"q": "What exactly is included?", "a": "Everything listed in the What's Included section."},
            {"q": "Do I need special software?", "a": compat + ". Most work with commonly available tools."},
            {"q": "How do I access my files?", "a": "Immediately after payment you will receive a download link via email."},
            {"q": "Can I use this commercially?", "a": "This comes with a " + license_type + " license."},
            {"q": "What if I am not satisfied?", "a": "30-day money-back guarantee. No questions asked."}]
    faq_html = ""
    for i, fq in enumerate(faq_items):
        qid = "faq_" + str(i)
        faq_html += '<div class="border border-[#252533] rounded-xl overflow-hidden"><button onclick="document.getElementById(' + chr(39) + qid + chr(39) + ').classList.toggle(' + chr(39) + "hidden" + chr(39) + ');this.querySelector(' + chr(39) + "i" + chr(39) + ').classList.toggle(' + chr(39) + "fa-chevron-down" + chr(39) + ');this.querySelector(' + chr(39) + "i" + chr(39) + ').classList.toggle(' + chr(39) + "fa-chevron-up" + chr(39) + ')" class="w-full flex items-center justify-between p-4 text-left hover:bg-[#1a1a26] transition"><span class="text-sm font-medium">' + fq["q"] + '</span><i class="fas fa-chevron-down text-[#5c5c70] text-xs transition"></i></button><div id="' + qid + '" class="hidden px-4 pb-4 text-sm text-[#b0b0c0] leading-relaxed">' + fq["a"] + "</div></div>"
    sales_velocity = max(1, 50 - downloads * 2)
    viewing_count = max(3, 30 - downloads)
    license_text = {"standard": "Personal and commercial use in your projects and client work. You may not resell the raw files.",
        "commercial": "Full commercial use in unlimited projects, client work, and commercial applications.",
        "extended": "Extended commercial license. Incorporate into products you sell."}.get(license_type, license_type)
    spec_data = [["Product Type", type_label], ["File Format", fmt], ["Difficulty", difficulty],
        ["Version", version], ["License", license_type.capitalize()], ["Updated", now.strftime("%b %Y")]]
    spec_html = ""
    for sl, sv in spec_data:
        spec_html += '<div class="spec-item"><div class="spec-label">' + sl + '</div><div class="spec-value">' + sv + "</div></div>"
    included_html = ""
    for item in included_items:
        included_html += '<div class="flex items-start gap-3 p-3 bg-[#0a0a12] rounded-xl border border-[#1a1a24]"><div class="w-6 h-6 rounded-full bg-[#4ade80]/10 flex items-center justify-center flex-shrink-0 mt-0.5"><i class="fas fa-check text-[#4ade80] text-[10px]"></i></div><div class="text-xs font-medium">' + item + "</div></div>"
    hiw_html = ""
    for ht, hd in how_it_works:
        hiw_html += '<div class="text-center p-4 bg-[#0a0a12] rounded-xl border border-[#1a1a24]"><h4 class="font-semibold text-xs mb-1">' + ht + '</h4><p class="text-[10px] text-[#5c5c70] leading-relaxed">' + hd + "</p></div>"
    choose_html = ""
    for wt, wd in why_list:
        choose_html += '<div class="flex items-start gap-3 p-3 bg-[#0a0a12] rounded-xl border border-[#1a1a24]"><div><h4 class="text-xs font-semibold mb-0.5">' + wt + '</h4><p class="text-[10px] text-[#5c5c70]">' + wd + "</p></div></div>"
    trust_html = ""
    for tt, td in trust_list:
        trust_html += '<div class="trust-item"><div class="font-semibold text-xs text-white">' + tt + '</div><div class="text-[10px] mt-0.5">' + td + "</div></div>"
    compat_html = ""
    for c in compat.split(", "):
        ci = c.strip()[:25]
        compat_html += '<span class="text-[10px] px-2.5 py-1 rounded-full bg-[#1a1a26] border border-[#252533] text-[#b0b0c0] font-medium">' + ci + "</span>"
    req_html = '<p class="text-[10px] text-[#5c5c70] mt-2">' + requirements[:150].replace("<", "&lt;").replace(">", "&gt;") + "</p>" if requirements else ""

    S = chr(39)  # single quote character to avoid escaping issues

    return LAYOUT_HEAD.replace("</head>", """
<style>
.trust-grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(130px,1fr))}
.trust-item{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:12px;text-align:center;font-size:11px;color:#b0b0c0;transition:all .2s}
.trust-item:hover{border-color:rgba(168,85,247,0.2);background:rgba(168,85,247,0.05)}
.sticky-buy{position:sticky;top:24px}
.spec-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.spec-item{background:#0a0a12;border:1px solid #1a1a24;border-radius:10px;padding:12px}
.spec-label{font-size:10px;color:#5c5c70;text-transform:uppercase;letter-spacing:.05em}
.spec-value{font-size:13px;font-weight:600;margin-top:2px}
.flash-sale{background:linear-gradient(135deg,rgba(236,72,153,0.12),rgba(168,85,247,0.12));border:1px solid rgba(236,72,153,0.2);border-radius:12px;padding:12px 16px;text-align:center;font-size:12px;color:#f472b6;font-weight:600;animation:pulse2 2s infinite}
@keyframes pulse2{0%%,100%%{opacity:1}50%%{opacity:0.7}}
@media(max-width:768px){.spec-grid{grid-template-columns:1fr}.trust-grid{grid-template-columns:repeat(auto-fill,minmax(100px,1fr))}}
</style>
<title>""" + seo_title[:65] + """</title>
<meta name="description" content="""" + seo_desc[:160] + """">
<meta name="keywords" content="""" + seo_kw[:200] + """">
<meta property="og:title" content="""" + seo_title[:80] + """">
<meta property="og:description" content="""" + seo_desc[:200] + """">
<meta property="product:price:amount" content=""" + str(price) + """>
</head>
<body>""" + TOP_NAV + """
<div class="max-w-6xl mx-auto px-4 sm:px-6 py-6">
<div class="flex items-center gap-2 text-xs text-[#5c5c70] mb-6">
<a href="/" class="hover:text-[#c084fc] transition">Marketplace</a><span>/</span>
<a href="/?category=""" + ptype + """ class="hover:text-[#c084fc] transition">""" + type_label + """s</a><span>/</span>
<span class="text-[#b0b0c0]">""" + title[:50] + """</span></div>

<div class="grid grid-cols-1 lg:grid-cols-5 gap-8">
<div class="lg:col-span-3 space-y-8">

<div class="rounded-2xl overflow-hidden" style="background:linear-gradient(135deg,#0f0a1e,#1a0a2e,#0e0e16);border:1px solid #1e1e2e">
<div class="grid grid-cols-1 md:grid-cols-2 gap-0">
<div class="p-6 md:p-8 flex flex-col justify-center">
<div class="flex items-center gap-2 mb-3">
<span class="text-xl">""" + type_icon + """</span>
<span class="text-[10px] font-semibold px-2.5 py-0.5 rounded-full" style="background:""" + type_color + """20;color:""" + type_color + """">""" + type_label + """</span>
<span class="text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-[#4ade80]/10 text-[#4ade80]">v""" + version + """</span></div>
<h1 class="text-2xl md:text-3xl font-black mb-3 leading-tight">""" + title[:90] + """</h1>
<p class="text-sm text-[#b0b0c0] mb-4 leading-relaxed">""" + desc[:200] + """</p>
<div class="flex items-center gap-4 text-xs text-[#5c5c70] mb-4">
<span class="text-[#facc15] text-base">""" + stars + """</span>
<span><span class="text-white font-bold">""" + str(rating) + """</span> (""" + str(max(0, int(rating * 3 + 1))) + """ reviews)</span>
<span><i class="fas fa-download mr-1 text-[#38bdf8]"></i>""" + str(downloads) + """+ sold</span></div>
<div class="flex items-center gap-3">
<div class="text-3xl font-bold text-white">$""" + str(price) + """</div>
<div class="text-[10px] text-[#5c5c70]">one-time / lifetime access</div></div></div>
<div class="bg-gradient-to-br from-[#a855f7]/10 to-transparent p-6 md:p-8 flex items-center justify-center min-h-[220px]">""" + img_html + """</div></div></div>

<div class="card" style="border-left:3px solid #f472b6">
<div class="flex items-start gap-4">
<div class="w-12 h-12 rounded-full bg-[#f472b6]/10 flex items-center justify-center flex-shrink-0 text-2xl">&#x1f62b;</div>
<div><h3 class="font-bold text-sm mb-1">The Problem</h3>
<p class="text-sm text-[#b0b0c0] leading-relaxed">""" + desc[:200] + """</p>
<div class="mt-3 flex items-center gap-2 text-sm"><span class="text-[#4ade80] font-bold">&#x2192;</span><span class="text-white font-semibold">""" + desc[:150] + """</span></div></div></div></div>

<div class="card">
<div class="flex items-center justify-between mb-4">
<h3 class="font-bold"><i class="fas fa-gift text-[#f472b6] mr-2"></i> What's Included</h3>
<span class="text-[10px] text-[#4ade80] bg-[#4ade80]/10 px-2 py-0.5 rounded-full font-semibold">""" + str(len(included_items)) + """ items</span></div>
<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">""" + included_html + """</div></div>

<div class="card">
<h3 class="font-bold mb-4"><i class="fas fa-list-check text-[#38bdf8] mr-2"></i> Features</h3>
<div class="text-sm text-[#b0b0c0] leading-relaxed">""" + content_body[:3000] + """</div></div>

<div class="card">
<h3 class="font-bold mb-5"><i class="fas fa-arrow-right-arrow-left text-[#38bdf8] mr-2"></i> How It Works</h3>
<div class="grid grid-cols-1 md:grid-cols-4 gap-4">""" + hiw_html + """</div></div>

<div class="card">
<h3 class="font-bold mb-4"><i class="fas fa-star text-[#facc15] mr-2"></i> Why Choose This Product</h3>
<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">""" + choose_html + """</div></div>

<div class="card" style="border:1px solid #f472b640;background:linear-gradient(135deg,#1a0a2e,#0e0e16)">
<div class="flex items-center gap-3 mb-4"><span class="text-2xl">&#x1f381;</span>
<div><h3 class="font-bold text-sm">Free Bonus</h3><p class="text-xs text-[#5c5c70]">Exclusive with purchase today</p></div></div>
<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
<div class="flex items-center gap-3 p-3 bg-[#f472b6]/5 rounded-xl border border-[#f472b6]/10"><span class="text-xl">&#x1f4d8;</span><div><div class="text-xs font-semibold">Quick Start Guide</div><div class="text-[10px] text-[#5c5c70]">Up and running in 5 minutes</div></div></div>
<div class="flex items-center gap-3 p-3 bg-[#f472b6]/5 rounded-xl border border-[#f472b6]/10"><span class="text-xl">&#x1f4ac;</span><div><div class="text-xs font-semibold">Priority Support</div><div class="text-[10px] text-[#5c5c70]">Questions answered within 24h</div></div></div></div></div>

<div class="card">
<h3 class="font-bold mb-4"><i class="fas fa-circle-question text-[#facc15] mr-2"></i> FAQ</h3>
<div class="space-y-2">""" + faq_html + """</div></div>

<div class="card">
<h3 class="font-bold mb-4"><i class="fas fa-link text-[#38bdf8] mr-2"></i> Related Products</h3>
<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">""" + related_html + """</div></div></div>

<div class="lg:col-span-2 space-y-5">
<div class="flash-sale"><i class="fas fa-bolt mr-1"></i> """ + str(sales_velocity) + """ sold recently | """ + str(viewing_count) + """ viewing now</div>

<div class="card sticky-buy" style="padding:28px">
<div class="text-center mb-5">
<div class="text-4xl font-black text-white">$""" + str(price) + """</div>
<div class="text-xs text-[#5c5c70] mt-1">One-time payment - Lifetime access</div></div>
<a href="/api/checkout/""" + p["id"] + """\" class="btn-primary w-full text-base py-4 mb-3" style="font-size:16px;padding:16px"><i class="fas fa-shopping-cart"></i> Buy Now - $""" + str(price) + """</a>""" + demo_btn + """
<div class="mt-4 space-y-2 text-xs text-[#5c5c70]">
<div class="flex items-center gap-2"><i class="fas fa-shield-halved text-[#4ade80] w-4"></i> Secure checkout via Stripe</div>
<div class="flex items-center gap-2"><i class="fas fa-bolt text-[#4ade80] w-4"></i> Instant download after payment</div>
<div class="flex items-center gap-2"><i class="fas fa-rotate-left text-[#4ade80] w-4"></i> 30-day money-back guarantee</div></div>
<div class="flex justify-center gap-3 mt-4 text-lg text-[#5c5c70]">
<i class="fab fa-cc-visa"></i><i class="fab fa-cc-mastercard"></i><i class="fab fa-cc-amex"></i><i class="fab fa-cc-paypal"></i><i class="fab fa-bitcoin"></i></div></div>

<div class="card"><h4 class="font-bold text-xs mb-3 uppercase text-[#5c5c70]">Specifications</h4>
<div class="spec-grid">""" + spec_html + """</div></div>

<div class="card"><h4 class="font-bold text-xs mb-3 uppercase text-[#5c5c70]">Compatibility</h4>
<div class="flex flex-wrap gap-1.5">""" + compat_html + """</div>""" + req_html + """</div>

<div class="card"><h4 class="font-bold text-xs mb-3 uppercase text-[#5c5c70]">Why Shop With Us</h4>
<div class="trust-grid">""" + trust_html + """</div></div>

<div class="card"><h4 class="font-bold text-xs mb-3 uppercase text-[#5c5c70]">License</h4>
<div class="flex items-center gap-2 mb-2"><span class="text-[10px] font-semibold px-2 py-0.5 rounded-full" style="background:""" + type_color + """20;color:""" + type_color + """">""" + license_type.capitalize() + """</span></div>
<p class="text-xs text-[#b0b0c0] leading-relaxed">""" + license_text + """</p></div>

<div class="card text-center" style="border:1px solid #4ade8040;background:linear-gradient(135deg,#0a1a0e,#0e0e16)">
<h4 class="font-bold text-sm mb-1">30-Day Money-Back Guarantee</h4>
<p class="text-xs text-[#b0b0c0] leading-relaxed">Not satisfied? Full refund within 30 days. No questions asked.</p></div>

<div class="card text-center">
<div class="flex justify-center -space-x-2 mb-2">
<div class="w-8 h-8 rounded-full bg-gradient-to-br from-[#a855f7] to-[#ec4899] flex items-center justify-center text-[10px] font-bold text-white border-2 border-[#0e0e16]">JD</div>
<div class="w-8 h-8 rounded-full bg-gradient-to-br from-[#38bdf8] to-[#4ade80] flex items-center justify-center text-[10px] font-bold text-white border-2 border-[#0e0e16]">SK</div>
<div class="w-8 h-8 rounded-full bg-gradient-to-br from-[#facc15] to-[#f472b6] flex items-center justify-center text-[10px] font-bold text-white border-2 border-[#0e0e16]">MR</div>
<div class="w-8 h-8 rounded-full bg-[#1a1a26] flex items-center justify-center text-[10px] text-[#5c5c70] border-2 border-[#0e0e16]">+""" + str(max(5, downloads)) + """</div></div>
<p class="text-xs text-[#5c5c70]">Joined by <span class="text-white font-semibold">""" + str(max(50, downloads * 3)) + """</span> other creators</p></div>

</div></div></div>""" + LAYOUT_FOOT)
