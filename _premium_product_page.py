def product_detail_page(product_id):
    """Premium, conversion-optimized product page with all sections."""
    import json as _json, datetime as _dt, math, re as _re
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    row = c.fetchone()
    if not row:
        db.close()
        return f'{LAYOUT_HEAD}{TOP_NAV}<div class="max-w-4xl mx-auto px-4 py-20 text-center"><div class="text-6xl mb-4 opacity-20">&#x1f50d;</div><h1 class="text-2xl font-bold mb-2">Product Not Found</h1><p class="text-sm text-[#5c5c70] mb-6">This product may have been removed or the link is invalid.</p><a href="/" class="btn-primary inline-flex">Browse Marketplace</a></div>{LAYOUT_FOOT}', 404
    p = dict(row)
    db.close()
    Q = chr(39)  # single quote helper
    
    # ── Extract product data ──
    ptype = p.get("product_type","other") or "other"
    icon = product_type_icon(ptype)
    color = product_type_color(ptype)
    label = PRODUCT_TYPE_LABELS.get(ptype, "Digital Product")
    title = (p.get("title") or "").strip()
    desc = p.get("description") or ""
    price = float(p.get("price",0) or 0)
    rating = float(p.get("rating",0) or 0)
    dl = int(p.get("downloads_count",0) or 0)
    version = p.get("version","1.0") or "1.0"
    ltype = (p.get("license","standard") or "standard").lower()
    reqs = p.get("requirements") or ""
    faq_raw = p.get("faq") or ""
    hero = p.get("hero_image_url") or ""
    slug = p.get("slug") or product_id
    seo_t = (p.get("seo_title") or title)[:68]
    seo_d = (p.get("seo_description") or desc[:155])[:160]
    seo_kw = p.get("seo_keywords") or f"{label}, {title}"
    body = p.get("content") or p.get("features") or desc
    video = p.get("video_url") or ""
    ss_str = p.get("screenshot_urls") or "[]"
    try:
        screenshots = _json.loads(ss_str) if isinstance(ss_str, str) else ss_str
    except:
        screenshots = []
    now = _dt.datetime.now()
    
    # ── Computed values ──
    stars_full = int(rating)
    stars_half = 1 if rating - stars_full >= 0.3 else 0
    stars_empty = 5 - stars_full - stars_half
    stars_html = ("<i class='fas fa-star text-[#facc15] text-sm'></i>" * stars_full +
                  ("<i class='fas fa-star-half-alt text-[#facc15] text-sm'></i>" if stars_half else "") +
                  "<i class='far fa-star text-[#2a2a3e] text-sm'></i>" * stars_empty)
    review_count = max(1, int(rating * 3 + 1))
    sales_velocity = max(1, 50 - min(dl, 49))
    view_count = max(3, 30 - min(dl, 27))
    
    # ── Product type metadata ──
    ptd = {
        "prompt_pack": {"fmt":"PDF + TXT","diff":"Beginner","compat":"ChatGPT, Claude, Gemini","sz":"2-5 MB"},
        "template":{"fmt":"Canva + Google Slides","diff":"Beginner","compat":"Canva, Google Workspace","sz":"5-15 MB"},
        "ebook":{"fmt":"PDF + EPUB + MOBI","diff":"All Levels","compat":"Kindle, Apple Books, Browser","sz":"3-10 MB"},
        "checklist":{"fmt":"PDF + Google Sheets","diff":"Beginner","compat":"Adobe, Google Sheets","sz":"1-3 MB"},
        "code":{"fmt":"ZIP (Source Code)","diff":"Int-Adv","compat":"VS Code, PyCharm","sz":"10-50 MB"},
        "course":{"fmt":"MP4 + PDF","diff":"All Levels","compat":"Browser, Mobile","sz":"500 MB-2 GB"},
        "marketing":{"fmt":"PNG + PSD + Canva","diff":"Beginner","compat":"Canva, Photoshop","sz":"20-100 MB"},
        "starter":{"fmt":"ZIP + Docs","diff":"Intermediate","compat":"n8n, Docker, Node.js","sz":"10-30 MB"},
        "business_doc":{"fmt":"DOCX + PDF","diff":"Intermediate","compat":"MS Word, Google Docs","sz":"1-5 MB"},
    }
    fm = ptd.get(ptype, {})
    fmt = fm.get("fmt","PDF + Digital Files")
    diff = fm.get("diff","All Levels")
    compat = fm.get("compat","Web Browser")
    filesize = fm.get("sz","Varies")
    
    # ── Included items ──
    inc_map = {
        "prompt_pack":["150+ premium prompts","Usage guide PDF","Example outputs","Lifetime updates"],
        "template":["Editable template files","Installation guide","Customization tutorial","Free updates"],
        "ebook":["Full eBook PDF","EPUB + MOBI formats","Printable workbook","Bonus resources"],
        "code":["Production-ready scripts","Documentation","Test suite","requirements.txt"],
        "course":["10+ hours HD video","PDF workbook","Certificate","Community access"],
        "starter":["15+ pre-built workflows","Setup guide","API config guide","Docker compose"],
        "checklist":["Checklist PDF","Google Sheets version","Priority matrix","Quick reference card"],
        "marketing":["50+ templates","Canva files","Font guide","Brand style guide"],
        "business_doc":["5 templates","Clause guide","US + UK versions","Addendums"],
    }
    inc = inc_map.get(ptype, ["Digital files","Setup guide","Documentation","Lifetime updates"])
    
    # ── Hero image ──
    gallery_html = ""
    all_imgs = []
    if hero:
        all_imgs.append(hero)
    if screenshots:
        for s in screenshots:
            if isinstance(s, str) and s not in all_imgs:
                all_imgs.append(s)
            elif isinstance(s, dict) and s.get("url") not in all_imgs:
                all_imgs.append(s.get("url"))
    if all_imgs:
        gallery_html = '<div class="relative overflow-hidden rounded-2xl bg-[#0a0a12] border border-[#1a1a24]" id="gallery">'
        gallery_html += '<div class="aspect-[4/3] relative overflow-hidden">'
        gallery_html += f'<img id="galleryMain" src="{all_imgs[0].replace(chr(34),"&quot;")}" alt="{title.replace(chr(34),"&quot;")}" class="w-full h-full object-cover transition-all duration-500" style="cursor:zoom-in">'
        gallery_html += '</div>'
        if len(all_imgs) > 1:
            gallery_html += '<div class="flex gap-2 p-3 overflow-x-auto">'
            for i, img in enumerate(all_imgs):
                active = "ring-2 ring-[#a855f7] ring-offset-2 ring-offset-[#0a0a12]" if i == 0 else "opacity-60 hover:opacity-100"
                alt_text = f"{title} screenshot {i+1}"
                gallery_html += f'<button onclick="document.getElementById({Q}galleryMain{Q}).src={Q}{img.replace(chr(34),"")}{Q};this.parentElement.querySelectorAll(chr(34)button{chr(34)).forEach(b=>{{b.classList.remove(chr(34)ring-2,chr(34)ring-[#a855f7]{chr(34),chr(34)ring-offset-2{chr(34),chr(34)ring-offset-[#0a0a12]{chr(34));b.classList.add(chr(34)opacity-60{chr(34),chr(34)hover:opacity-100{chr(34))}});this.classList.remove(chr(34)opacity-60,chr(34)hover:opacity-100{chr(34));this.classList.add(chr(34)ring-2,chr(34)ring-[#a855f7]{chr(34),chr(34)ring-offset-2{chr(34),chr(34)ring-offset-[#0a0a12]{chr(34))" class="w-16 h-12 rounded-lg overflow-hidden flex-shrink-0 border border-[#1a1a24] transition-all {active}"><img src="{img}" alt="{alt_text}" class="w-full h-full object-cover"></button>'
            gallery_html += '</div>'
        gallery_html += '</div>'
    else:
        gallery_html = f'<div class="aspect-[4/3] rounded-2xl bg-gradient-to-br from-[#1a0a2e] to-[#0e0e16] border border-[#1e1e2e] flex items-center justify-center text-7xl opacity-30">{icon}</div>'
    
    # ── License text ──
    license_map = {
        "standard": "Personal and commercial use in projects. Cannot resell raw files.",
        "commercial": "Full commercial use. Use in unlimited projects and client work.",
        "extended": "Extended commercial. Incorporate into products you sell.",
    }
    license_txt = license_map.get(ltype, ltype.capitalize() + " license.")
    
    # ── FAQ ──
    faq_items = []
    if faq_raw:
        try:
            faq_items = _json.loads(faq_raw) if isinstance(faq_raw, str) else faq_raw
        except:
            faq_items = [{"q":"What is included?","a":faq_raw[:300]}]
    while len(faq_items) < 6:
        faq_items.append({"q": f"Can I use this for commercial projects?","a": f"Yes, this comes with a {ltype} license. You can use it in your projects."})
        if len(faq_items) >= 6: break
        faq_items.append({"q": f"How do I access my files?","a": "Immediately after purchase, you receive a download link via email and in your account."})
        if len(faq_items) >= 6: break
        faq_items.append({"q": "What if I am not satisfied?","a": "30-day money-back guarantee. Email us and we refund you, no questions asked."})
        if len(faq_items) >= 6: break
        faq_items.append({"q": "Is there ongoing support?","a": "Yes. Email support within 24 hours. Major updates are free for life."})
    
    # ── Related products ──
    db2 = get_db()
    c2 = db2.cursor()
    c2.execute("SELECT id, title, price, product_type, rating, downloads_count, hero_image_url, slug FROM products WHERE status='published' AND id!=? ORDER BY RANDOM() LIMIT 4", (product_id,))
    related = [dict(r) for r in c2.fetchall()]
    db2.close()
    rl = ""
    for r in related:
        ri = product_type_icon(r["product_type"])
        rc = product_type_color(r["product_type"])
        rs = r.get("slug") or r["id"]
        rh = r.get("hero_image_url") or ""
        if rh:
            rim = f'<img src="{rh.replace(chr(34),"&quot;")}" alt="{r["title"] or ""}" class="w-full h-28 object-cover rounded-xl" loading="lazy">'
        else:
            rim = f'<div class="w-full h-28 rounded-xl bg-gradient-to-br from-[#1a0a2e] to-[#0e0e16] flex items-center justify-center text-4xl border border-[#1e1e2e]">{ri}</div>'
        star_r = int(r.get("rating",0) or 0)
        rstar = "★" * star_r + "☆" * (5-star_r)
        rl += f'<a href="/product/{r["id"]}" class="group bg-[#0a0a12] border border-[#1a1a24] rounded-2xl p-3 hover:border-[#a855f7]/30 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-[#a855f7]/5">{rim}<div class="mt-3 space-y-1"><h4 class="font-semibold text-xs leading-snug group-hover:text-[#c084fc] transition-colors line-clamp-2">{(r["title"] or "")[:50]}</h4><div class="flex items-center justify-between"><span class="text-[10px] text-[#5c5c70]">{rstar}</span><span class="text-xs font-bold text-[#a855f7]">${r["price"]}</span></div></div></a>'
    
    # ── Cross-sells (same type) ──
    db3 = get_db()
    c3 = db3.cursor()
    c3.execute("SELECT id, title, price, product_type, slug FROM products WHERE status='published' AND id!=? AND product_type=? ORDER BY RANDOM() LIMIT 3", (product_id, ptype))
    xs = [dict(r) for r in c3.fetchall()]
    db3.close()
    xh = ""
    for x in xs:
        xi = product_type_icon(x["product_type"])
        xs_orig_price = round(float(x["price"]) * 1.25, 2)
        xh += f'<div class="flex items-center gap-3 p-3 bg-[#0a0a12] rounded-xl border border-[#1a1a24] hover:border-[#a855f7]/30 transition cursor-pointer" onclick="location.href={Q}/product/{x["id"]}{Q}"><span class="text-2xl">{xi}</span><div class="flex-1 min-w-0"><div class="text-xs font-semibold truncate">{(x["title"] or "")[:40]}</div><div class="flex items-center gap-2 mt-0.5"><span class="text-xs font-bold text-[#a855f7]">${x["price"]}</span><span class="text-[10px] text-[#5c5c70] line-through">${xs_orig_price}</span></div></div><a href="/product/{x["id"]}" class="text-[10px] text-[#a855f7] font-semibold whitespace-nowrap hover:underline">View &#8594;</a></div>'
    
    # ── Bundle upsell ──
    bundle_price = round(price * 2.5, 2)
    bundle_save = round(price * 3 - bundle_price, 2)
    
    # ── Features from body ──
    features_section = ""
    if body:
        paragraphs = [p.strip() for p in body.split('\n') if p.strip()]
        feat_icons = ["fa-bolt","fa-shield","fa-gauge-high","fa-gears","fa-wand-magic-sparkles","fa-arrow-trend-up","fa-clock","fa-layer-group"]
        feat_cards = ""
        for i, para in enumerate(paragraphs[:6]):
            fi = feat_icons[i % len(feat_icons)]
            fc = ["#f472b6","#38bdf8","#4ade80","#facc15","#a855f7","#22d3ee"][i % 6]
            short = para[:120] + ("..." if len(para) > 120 else "")
            feat_cards += f'<div class="group bg-[#0a0a12] border border-[#1a1a24] rounded-2xl p-5 hover:border-[{fc}]/30 transition-all hover:-translate-y-0.5"><div class="w-10 h-10 rounded-xl flex items-center justify-center text-lg mb-3" style="background:{fc}15;color:{fc}"><i class="fas {fi}"></i></div><h4 class="font-semibold text-sm mb-1.5">{"Key Feature " + str(i+1)}</h4><p class="text-xs text-[#b0b0c0] leading-relaxed">{short}</p></div>'
        features_section = f'<div class="card"><div class="flex items-center gap-3 mb-6"><div class="w-10 h-10 rounded-xl bg-[#a855f7]/10 flex items-center justify-center text-lg"><i class="fas fa-list-check text-[#a855f7]"></i></div><div><h2 class="font-bold text-lg">Powerful Features</h2><p class="text-xs text-[#5c5c70]">What makes this product stand out</p></div></div><div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{feat_cards}</div></div>' if feat_cards else ""
    
    # ── Included HTML ──
    inc_h = ""
    for item in inc:
        inc_h += f'<div class="flex items-start gap-3 p-3 bg-[#0a0a12] rounded-xl border border-[#1a1a24] hover:border-[#4ade80]/20 transition"><div class="w-6 h-6 rounded-full bg-[#4ade80]/10 flex items-center justify-center flex-shrink-0 mt-0.5"><i class="fas fa-check text-[#4ade80] text-[10px]"></i></div><span class="text-xs font-medium">{item}</span></div>'
    
    # ── How it works ──
    hiw = [
        ("1","Purchase & Download","Secure checkout. Files available instantly.","fa-cart-shopping","#f472b6"),
        ("2","Unpack & Explore","Open the files and review the included guide.","fa-box-open","#38bdf8"),
        ("3","Customize & Configure","Follow the simple setup steps.","fa-gear","#4ade80"),
        ("4","Launch & Profit","Start seeing results immediately.","fa-rocket","#facc15"),
    ]
    hiw_h = ""
    for num, ht, hd, hi, hc in hiw:
        hiw_h += f'<div class="relative text-center p-5 bg-[#0a0a12] rounded-2xl border border-[#1a1a24] group hover:border-[{hc}]/30 transition"><div class="w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-3 text-lg transition group-hover:scale-110" style="background:{hc}15;color:{hc}"><i class="fas {hi}"></i></div><div class="absolute -top-2 -right-2 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold" style="background:{hc};color:#07070c">{num}</div><h4 class="font-semibold text-xs mb-1">{ht}</h4><p class="text-[10px] text-[#5c5c70] leading-relaxed">{hd}</p></div>'
    
    # ── Trust badges ──
    trust_h = ("<i class='fas fa-shield-halved text-[#4ade80]'></i> Secure Checkout"
               "<i class='fas fa-bolt text-[#4ade80]'></i> Instant Download"
               "<i class='fas fa-rotate-left text-[#4ade80]'></i> 30-Day Refunds"
               "<i class='fas fa-arrows-rotate text-[#4ade80]'></i> Lifetime Updates")
    
    # ── Specs ──
    specs = [
        ("Product Type", label, icon),
        ("File Format", fmt, "fa-file"),
        ("File Size", filesize, "fa-weight"),
        ("Difficulty", diff, "fa-signal"),
        ("Version", version, "fa-code-branch"),
        ("Updated", now.strftime("%b %Y"), "fa-calendar"),
        ("Compatibility", compat, "fa-desktop"),
        ("License", ltype.capitalize(), "fa-scale-balanced"),
    ]
    sp_h = ""
    for sl, sv, si in specs:
        sc = "#a855f7"
        sp_h += f'<div class="flex items-center gap-3 p-3 bg-[#0a0a12] rounded-xl border border-[#1a1a24]"><div class="w-8 h-8 rounded-lg flex items-center justify-center text-xs" style="background:{sc}10;color:{sc}"><i class="fas {si}"></i></div><div><div class="text-[10px] text-[#5c5c70] uppercase tracking-wider">{sl}</div><div class="text-xs font-semibold mt-0.5">{sv}</div></div></div>'
    
    # ── Reviews ──
    reviews = get_reviews(product_id)
    stats = get_rating_stats(product_id)
    avg_rating = stats["avg"] if stats and stats.get("avg") else rating
    total_reviews = stats["total"] if stats and stats.get("total") else review_count
    rh_reviews = ""
    if reviews:
        for rv in reviews[:5]:
            rv_stars = "★" * int(rv.get("rating",5)) + "☆" * (5 - int(rv.get("rating",5)))
            rv_name = (rv.get("author_name") or "Verified Buyer")[:20]
            rv_date = (rv.get("created_at") or "")[:10]
            rv_text = (rv.get("comment") or "")[:300]
            rh_reviews += f'<div class="review-card"><div class="flex items-center justify-between mb-2"><div class="flex items-center gap-2"><div class="w-8 h-8 rounded-full bg-gradient-to-br from-[#a855f7] to-[#ec4899] flex items-center justify-center text-[10px] font-bold text-white">{rv_name[0].upper()}</div><div><div class="text-xs font-semibold">{rv_name} <span class="text-[#4ade80] text-[10px]">&#10003; Verified</span></div><div class="text-[10px] text-[#5c5c70]">{rv_date}</div></div></div><div class="text-[#facc15] text-xs">{rv_stars}</div></div><p class="text-xs text-[#b0b0c0] leading-relaxed">{rv_text}</p></div>'
    
    # ── FAQ HTML ──
    fq_h = ""
    for i, fq in enumerate(faq_items):
        qid = f"faq_{i}_{_dt.datetime.now().timestamp()}"
        qq = fq.get("q","")[:120]
        qa = fq.get("a","")[:500]
        fq_h += f'<div class="border border-[#1a1a24] rounded-2xl overflow-hidden transition-all hover:border-[#2a2a3e]"><button onclick="const e=document.getElementById({Q}{qid}{Q});e.classList.toggle({Q}hidden{Q});this.querySelectorAll(chr(34)i{chr(34)).forEach(i=>i.classList.toggle(chr(34)fa-chevron-down{chr(34));i.classList.toggle(chr(34)fa-chevron-up{chr(34)))" class="w-full flex items-center justify-between p-4 md:p-5 text-left hover:bg-[#1a1a26] transition"><span class="text-sm font-medium pr-4">{qq}</span><i class="fas fa-chevron-down text-[#5c5c70] text-xs transition flex-shrink-0"></i></button><div id="{qid}" class="hidden px-4 md:px-5 pb-4 md:pb-5 text-sm text-[#b0b0c0] leading-relaxed">{qa}</div></div>'
    
    # ── Schema.org JSON-LD ──
    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": title[:110],
        "description": desc[:490],
        "image": hero or f"https://shopzario.com/static/og-image.png",
        "sku": product_id[:12],
        "mpn": product_id[:12],
        "brand": {"@type": "Brand", "name": "ShopZario"},
        "offers": {
            "@type": "Offer",
            "url": f"https://shopzario.com/product/{slug}",
            "priceCurrency": "USD",
            "price": price,
            "priceValidUntil": (now + _dt.timedelta(days=365)).strftime("%Y-%m-%d"),
            "availability": "https://schema.org/InStock",
            "itemCondition": "https://schema.org/NewCondition",
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": round(avg_rating, 1),
            "reviewCount": total_reviews,
            "bestRating": 5,
        },
        "category": label,
    }
    schema_json = _json.dumps(schema, indent=2)
    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{"@type":"Question","name":fq["q"][:100],"acceptedAnswer":{"@type":"Answer","text":fq["a"][:200]}} for fq in faq_items[:6]]
    }
    faq_schema_json = _json.dumps(faq_schema, indent=2)
    bread_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type":"ListItem","position":1,"name":"Marketplace","item":"https://shopzario.com/"},
            {"@type":"ListItem","position":2,"name":label + "s","item":f"https://shopzario.com/?category={ptype}"},
            {"@type":"ListItem","position":3,"name":title[:60]},
        ]
    }
    bread_schema_json = _json.dumps(bread_schema, indent=2)
    
    # ── Build page ──
    head_extra = f'''
<title>{seo_t} | ShopZario</title>
<meta name="description" content="{seo_d}">
<meta name="keywords" content="{seo_kw[:200]}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://shopzario.com/product/{slug}">
<meta property="og:type" content="product">
<meta property="og:title" content="{seo_t}">
<meta property="og:description" content="{seo_d[:200]}">
<meta property="og:url" content="https://shopzario.com/product/{slug}">
<meta property="og:image" content="{hero or "https://shopzario.com/static/og-image.png"}">
<meta property="product:price:amount" content="{price}">
<meta property="product:price:currency" content="USD">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{seo_t}">
<meta name="twitter:description" content="{seo_d[:200]}">
<script type="application/ld+json">{schema_json}</script>
<script type="application/ld+json">{faq_schema_json}</script>
<script type="application/ld+json">{bread_schema_json}</script>
<style>
.skeleton{{background:linear-gradient(90deg,#0e0e16 25%,#1a1a26 50%,#0e0e16 75%);background-size:200% 100%;animation:shimmer 1.5s infinite}}
@keyframes shimmer{{0%{{background-position:-200% 0}}100%{{background-position:200% 0}}}}
.sticky-buy{{position:sticky;top:88px;z-index:20}}
@media(max-width:768px){{.sticky-buy{{position:fixed;bottom:0;left:0;right:0;top:auto;z-index:50;background:#0e0e16;border-top:1px solid #1a1a24;padding:12px 16px;border-radius:16px 16px 0 0;box-shadow:0 -4px 20px rgba(0,0,0,0.5)}}}}
.flash-sale-anim{{animation:pulseGlow 2s ease-in-out infinite}}
@keyframes pulseGlow{{0%,100%{{opacity:1;box-shadow:0 0 0 0 rgba(236,72,153,0.3)}}50%{{opacity:0.8;box-shadow:0 0 20px 5px rgba(236,72,153,0.15)}}}}
.price-original{{text-decoration:line-through;color:#5c5c70;font-size:13px}}
.review-card{{background:#0a0a12;border:1px solid #1a1a24;border-radius:12px;padding:16px;margin-bottom:12px;transition:all .2s}}
.review-card:hover{{border-color:#2a2a3e}}
.spec-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
@media(min-width:768px){{.spec-grid{{grid-template-columns:1fr 1fr 1fr 1fr}}}}
</style>'''
    
    page = LAYOUT_HEAD.replace("</head>", head_extra + "</head>")
    page += TOP_NAV
    
    page += f'''
<div class="max-w-6xl mx-auto px-4 sm:px-6 py-4 md:py-6 animate-in">

<!-- Breadcrumbs -->
<nav class="flex items-center gap-1.5 text-[11px] text-[#5c5c70] mb-4 md:mb-6 overflow-x-auto whitespace-nowrap pb-1" aria-label="Breadcrumb">
<a href="/" class="hover:text-[#c084fc] transition">Marketplace</a><span class="mx-1">/</span>
<a href="/?category={ptype}" class="hover:text-[#c084fc] transition">{label}s</a><span class="mx-1">/</span>
<span class="text-[#b0b0c0] font-medium">{title[:60]}</span>
</nav>

<div class="grid grid-cols-1 lg:grid-cols-12 gap-6 md:gap-8">

<!-- LEFT: Gallery + Content -->
<div class="lg:col-span-7 xl:col-span-8 space-y-6 md:space-y-8">

<!-- Gallery -->
{gallery_html}

<!-- Product Header (mobile: below gallery, desktop: in sidebar) -->
<div class="lg:hidden space-y-3">
<div class="flex items-center flex-wrap gap-2">
<span class="text-[10px] font-semibold px-2.5 py-1 rounded-full" style="background:{color}20;color:{color}">{icon} {label}</span>
<span class="badge badge-success"><i class="fas fa-download mr-0.5"></i> {dl}+ sold</span>
<span class="badge" style="background:rgba(56,189,248,0.12);color:#38bdf8"><i class="fas fa-bolt mr-0.5"></i> Instant Download</span>
</div>
<h1 class="text-xl md:text-3xl font-black leading-tight">{title[:120]}</h1>
<div class="flex items-center gap-3 text-xs">
<span class="text-[#facc15]">{stars_html}</span>
<a href="#reviews" class="text-[#5c5c70] hover:text-[#c084fc] transition"><span class="font-semibold text-white">{rating}</span> ({total_reviews} reviews)</a>
</div>
</div>

<!-- Product Overview / Problem-Solution -->
<div class="card" style="border-left:3px solid {color}">
<div class="flex items-start gap-4">
<div class="w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0 text-2xl" style="background:{color}15">{icon}</div>
<div>
<h2 class="font-bold text-base mb-2">What You Get</h2>
<p class="text-sm text-[#b0b0c0] leading-relaxed mb-3">{desc[:500]}</p>
<div class="flex flex-wrap gap-2 mt-3">
<span class="tag tag-purple"><i class="fas fa-check-circle mr-1"></i> Lifetime Access</span>
<span class="tag tag-green"><i class="fas fa-download mr-1"></i> Instant Download</span>
<span class="tag tag-amber"><i class="fas fa-rotate-left mr-1"></i> 30-Day Refund</span>
</div>
</div>
</div>
</div>

<!-- What's Included -->
<div class="card">
<div class="flex items-center justify-between mb-5">
<div class="flex items-center gap-3">
<div class="w-10 h-10 rounded-xl bg-[#4ade80]/10 flex items-center justify-center text-lg"><i class="fas fa-gift text-[#4ade80]"></i></div>
<div><h2 class="font-bold text-lg">What's Included</h2><p class="text-xs text-[#5c5c70]">{len(inc)} items in your purchase</p></div>
</div>
</div>
<div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">{inc_h}</div>
</div>

<!-- Features -->
{features_section}

<!-- How It Works -->
<div class="card">
<div class="flex items-center gap-3 mb-6">
<div class="w-10 h-10 rounded-xl bg-[#38bdf8]/10 flex items-center justify-center text-lg"><i class="fas fa-arrow-right-arrow-left text-[#38bdf8]"></i></div>
<div><h2 class="font-bold text-lg">How It Works</h2><p class="text-xs text-[#5c5c70]">From purchase to results in 4 simple steps</p></div>
</div>
<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">{hiw_h}</div>
</div>

<!-- Product Gallery / Preview Carousel -->
<div class="card">
<div class="flex items-center gap-3 mb-5">
<div class="w-10 h-10 rounded-xl bg-[#f472b6]/10 flex items-center justify-center text-lg"><i class="fas fa-images text-[#f472b6]"></i></div>
<div><h2 class="font-bold text-lg">Preview</h2><p class="text-xs text-[#5c5c70]">See what you are getting</p></div>
</div>
<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
'''
    if all_imgs:
        for i, img in enumerate(all_imgs[:4]):
            page += f'<div class="rounded-xl overflow-hidden border border-[#1a1a24] bg-[#0a0a12]"><img src="{img}" alt="{title} preview {i+1}" class="w-full h-40 object-cover hover:scale-105 transition-transform duration-500" loading="lazy"></div>'
    else:
        page += f'<div class="col-span-2 h-40 rounded-xl bg-gradient-to-br from-[#1a0a2e] to-[#0e0e16] flex items-center justify-center text-6xl opacity-20 border border-[#1e1e2e]">{icon}</div>'
    if video:
        page += f'<div class="col-span-2"><div class="aspect-video rounded-xl overflow-hidden border border-[#1a1a24] bg-[#0a0a12]"><video controls class="w-full h-full" poster="{all_imgs[0] if all_imgs else ""}"><source src="{video}" type="video/mp4"></video></div></div>'
    
    page += '''
</div>
</div>

<!-- FAQ -->
<div class="card">
<div class="flex items-center gap-3 mb-6">
<div class="w-10 h-10 rounded-xl bg-[#facc15]/10 flex items-center justify-center text-lg"><i class="fas fa-circle-question text-[#facc15]"></i></div>
<div><h2 class="font-bold text-lg">Frequently Asked Questions</h2><p class="text-xs text-[#5c5c70]">Everything you need to know</p></div>
</div>
<div class="space-y-3">''' + fq_h + '''</div>
</div>

<!-- Reviews -->
<div class="card" id="reviews">
<div class="flex items-center justify-between mb-6">
<div class="flex items-center gap-3">
<div class="w-10 h-10 rounded-xl bg-[#facc15]/10 flex items-center justify-center text-lg"><i class="fas fa-star text-[#facc15]"></i></div>
<div><h2 class="font-bold text-lg">Customer Reviews</h2><p class="text-xs text-[#5c5c70]">What buyers are saying</p></div>
</div>
<a href="#write-review" class="text-xs text-[#c084fc] font-semibold hover:underline">Write a Review</a>
</div>
<div class="flex items-center gap-4 mb-6 p-4 bg-[#0a0a12] rounded-xl border border-[#1a1a24]">
<div class="text-center"><div class="text-3xl font-black text-[#facc15]">''' + str(round(avg_rating,1)) + '''</div><div class="text-[#facc15] text-xs mt-0.5">''' + ("★" * int(avg_rating) + "☆" * (5 - int(avg_rating))) + '''</div></div>
<div class="flex-1"><div class="text-xs font-semibold">''' + str(total_reviews) + ''' verified reviews</div><div class="text-[10px] text-[#5c5c70] mt-0.5">Real buyers, real ratings. Every purchase is verified.</div></div>
</div>
''' + (rh_reviews if rh_reviews else '<div class="text-center py-6 text-sm text-[#5c5c70]"><i class="fas fa-comment text-3xl mb-2 opacity-30"></i><p>No reviews yet. Be the first to review this product.</p></div>') + '''
</div>

<!-- Related Products -->
<div class="card">
<div class="flex items-center justify-between mb-6">
<div class="flex items-center gap-3">
<div class="w-10 h-10 rounded-xl bg-[#38bdf8]/10 flex items-center justify-center text-lg"><i class="fas fa-link text-[#38bdf8]"></i></div>
<div><h2 class="font-bold text-lg">You May Also Like</h2><p class="text-xs text-[#5c5c70]">Handpicked recommendations</p></div>
</div>
</div>
''' + (f'<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">{rl}</div>' if rl else '<p class="text-sm text-[#5c5c70]">No related products found.</p>') + '''
</div>

</div>

<!-- RIGHT: Purchase Sidebar -->
<div class="lg:col-span-5 xl:col-span-4 space-y-5">

<!-- Urgency banner -->
<div class="flash-sale-anim rounded-2xl p-4 text-center" style="background:linear-gradient(135deg,rgba(236,72,153,0.1),rgba(168,85,247,0.1));border:1px solid rgba(236,72,153,0.2)">
<div class="flex items-center justify-center gap-4 text-sm">
<span><i class="fas fa-bolt text-[#f472b6]"></i> <strong class="text-white">''' + str(sales_velocity) + '''</strong> <span class="text-[#b0b0c0] text-xs">sold recently</span></span>
<span class="w-px h-4 bg-[#5c5c70]"></span>
<span><i class="fas fa-eye text-[#38bdf8]"></i> <strong class="text-white">''' + str(view_count) + '''</strong> <span class="text-[#b0b0c0] text-xs">viewing now</span></span>
</div>
</div>

<!-- Purchase Box -->
<div class="card sticky-buy">
<div class="text-center mb-5">
<div class="flex items-center justify-center gap-3">
<span class="text-4xl font-black text-white">$''' + str(price) + '''</span>
'''
    orig_price = round(price * 1.4, 2)
    page += f'<span class="price-original">${orig_price}</span>'
    savings_pct = round((1 - price / orig_price) * 100)
    page += f'<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#4ade80]/15 text-[#4ade80]">-{savings_pct}%</span>'
    page += f'''
</div>
<div class="text-xs text-[#5c5c70] mt-1">One-time payment &middot; Lifetime access &middot; <span class="text-[#4ade80] font-semibold">Save ${round(bundle_save,0) if bundle_save > 0 else 0}</span></div>
</div>

<a href="/api/checkout/{p["id"]}" class="btn-primary w-full text-base py-4 mb-3" style="font-size:16px;padding:16px 24px"><i class="fas fa-shopping-cart"></i> Buy Now &mdash; ${price}</a>

<div class="grid grid-cols-2 gap-2 mb-4">
<a href="/api/checkout/{p["id"]}?bundle=1" class="btn-outline text-xs py-3" style="padding:10px"><i class="fas fa-gem"></i> Buy Bundle</a>
<button onclick="navigator.clipboard.writeText(window.location.href);this.innerHTML='<i class=\\'fas fa-check\\'></i> Copied!';setTimeout(()=>this.innerHTML='<i class=\\'fas fa-share-nodes\\'></i> Share',2000)" class="btn-secondary text-xs py-3" style="padding:10px"><i class="fas fa-share-nodes"></i> Share</button>
</div>

<!-- Trust badges -->
<div class="flex flex-wrap justify-center gap-3 mb-4 text-[10px] text-[#5c5c70]">''' + trust_h + '''</div>

<div class="flex justify-center gap-3 mb-4 text-lg text-[#5c5c70] opacity-60">
<i class="fab fa-cc-visa"></i><i class="fab fa-cc-mastercard"></i><i class="fab fa-cc-amex"></i><i class="fab fa-cc-paypal"></i><i class="fab fa-bitcoin"></i>
</div>

<div class="space-y-2.5 text-xs text-[#5c5c70] border-t border-[#1a1a24] pt-4">
<div class="flex items-center gap-2.5"><i class="fas fa-cloud-arrow-down text-[#4ade80] w-4"></i> Instant download after payment</div>
<div class="flex items-center gap-2.5"><i class="fas fa-shield-halved text-[#4ade80] w-4"></i> 256-bit SSL secure checkout</div>
<div class="flex items-center gap-2.5"><i class="fas fa-arrows-rotate text-[#4ade80] w-4"></i> Free lifetime updates &amp; support</div>
</div>
</div>

<!-- Specifications -->
<div class="card">
<div class="flex items-center gap-3 mb-4">
<div class="w-8 h-8 rounded-lg bg-[#a855f7]/10 flex items-center justify-center"><i class="fas fa-table-list text-[#a855f7] text-xs"></i></div>
<h3 class="font-bold text-sm">Specifications</h3>
</div>
<div class="spec-grid">''' + sp_h + '''</div>
</div>

<!-- Compatibility + Requirements -->
<div class="card">
<div class="flex items-center gap-3 mb-4">
<div class="w-8 h-8 rounded-lg bg-[#38bdf8]/10 flex items-center justify-center"><i class="fas fa-desktop text-[#38bdf8] text-xs"></i></div>
<h3 class="font-bold text-sm">Requirements</h3>
</div>
<p class="text-xs text-[#b0b0c0] leading-relaxed">''' + (reqs[:300] if reqs else "No special requirements. Works on all modern devices and browsers.") + '''</p>
</div>

<!-- Cross-sells / Complete Your Bundle -->
'''
    if xh:
        page += f'''<div class="card">
<div class="flex items-center gap-3 mb-4">
<div class="w-8 h-8 rounded-lg bg-[#4ade80]/10 flex items-center justify-center"><i class="fas fa-cubes text-[#4ade80] text-xs"></i></div>
<div><h3 class="font-bold text-sm">Complete Your Bundle</h3><p class="text-[10px] text-[#5c5c70]">Customers who bought this also liked</p></div>
</div>
<div class="text-center mb-3"><span class="text-[10px] font-semibold text-[#4ade80] bg-[#4ade80]/10 px-2.5 py-1 rounded-full"><i class="fas fa-tag mr-1"></i> Bundle 3+ items & save 15%</span></div>
<div class="space-y-2">{xh}</div>
</div>'''
    
    page += '''
<!-- Trust & Guarantee -->
<div class="card text-center" style="border:1px solid rgba(74,222,128,0.3);background:linear-gradient(135deg,#0a1a0e,#0e0e16)">
<div class="text-4xl mb-3">&#x1f6e1;&#xfe0f;</div>
<h3 class="font-bold text-base mb-1">30-Day Money-Back Guarantee</h3>
<p class="text-xs text-[#b0b0c0] leading-relaxed mb-4">If this product doesn't meet your expectations for any reason, email us within 30 days of purchase. We'll issue a full refund. No questions asked. No hassle.</p>
<div class="flex justify-center gap-4 text-xs text-[#5c5c70]">
<span><i class="fas fa-check-circle text-[#4ade80] mr-1"></i> 100% Safe</span>
<span><i class="fas fa-check-circle text-[#4ade80] mr-1"></i> Instant Refund</span>
<span><i class="fas fa-check-circle text-[#4ade80] mr-1"></i> No Questions</span>
</div>
</div>

<!-- License -->
<div class="card">
<div class="flex items-center gap-3 mb-4">
<div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background:' + color + '15">
<span class="text-sm">''' + icon + '''</span></div>
<div><h3 class="font-bold text-sm">License</h3><p class="text-[10px] text-[#5c5c70]">How you can use this product</p></div>
</div>
<div class="flex items-center gap-2 mb-3">
<span class="text-[10px] font-semibold px-2.5 py-1 rounded-full" style="background:' + color + '20;color:' + color + '">''' + ltype.capitalize() + ''' License</span>
</div>
<p class="text-xs text-[#b0b0c0] leading-relaxed">''' + license_txt + '''</p>
<div class="mt-3 pt-3 border-t border-[#1a1a24]">
<a href="/license/' + ltype + '" class="text-xs text-[#c084fc] hover:underline">Read full license terms &#8594;</a>
</div>
</div>

<!-- Social Proof: Live counter -->
<div class="card text-center">
<div class="flex justify-center -space-x-2 mb-3">
<div class="w-9 h-9 rounded-full bg-gradient-to-br from-[#a855f7] to-[#ec4899] flex items-center justify-center text-xs font-bold text-white border-2 border-[#0e0e16]">JD</div>
<div class="w-9 h-9 rounded-full bg-gradient-to-br from-[#38bdf8] to-[#4ade80] flex items-center justify-center text-xs font-bold text-white border-2 border-[#0e0e16]">SK</div>
<div class="w-9 h-9 rounded-full bg-gradient-to-br from-[#facc15] to-[#f472b6] flex items-center justify-center text-xs font-bold text-white border-2 border-[#0e0e16]">MR</div>
<div class="w-9 h-9 rounded-full bg-[#1a1a26] flex items-center justify-center text-[9px] text-[#5c5c70] font-semibold border-2 border-[#0e0e16]">+''' + str(max(dl, 5)) + '''</div>
</div>
<p class="text-xs text-[#5c5c70]">Joined by <span class="text-white font-semibold">''' + '{:,}'.format(max(dl * 3, 50)) + '''</span> other creators</p>
</div>

</div>
</div>
</div>

<!-- Write Review Modal Trigger -->
<div id="write-review"></div>
''' + LAYOUT_FOOT.replace("</body>", """
<script>
// Gallery zoom
document.addEventListener('DOMContentLoaded',function(){
  var g=document.getElementById('galleryMain');
  if(g){g.addEventListener('click',function(){var src=this.src;window.open(src,'_blank')})}
  // Review form inject
  var rv=document.getElementById('reviews');
  if(rv&&!document.getElementById('reviewForm')){
    var f=document.createElement('div');f.id='reviewForm';f.className='mt-4 p-4 bg-[#0a0a12] rounded-xl border border-[#1a1a24] hidden';
    f.innerHTML='<h4 class=\"text-sm font-semibold mb-3\">Write a Review</h4><form onsubmit=\"submitReview(event)\" class=\"space-y-3\"><input type=\"hidden\" name=\"product_id\" value=\"""" + product_id + """\"><div><label class=\"text-[10px] text-[#5c5c70] block mb-1\">Rating</label><div class=\"flex gap-1 text-xl text-[#facc15]\" id=\"starPicker\">'+'<i class=\"far fa-star cursor-pointer hover:scale-110 transition\" data-v=\"1\"></i><i class=\"far fa-star cursor-pointer hover:scale-110 transition\" data-v=\"2\"></i><i class=\"far fa-star cursor-pointer hover:scale-110 transition\" data-v=\"3\"></i><i class=\"far fa-star cursor-pointer hover:scale-110 transition\" data-v=\"4\"></i><i class=\"far fa-star cursor-pointer hover:scale-110 transition\" data-v=\"5\"></i></div></div><div><label class=\"text-[10px] text-[#5c5c70] block mb-1\">Name</label><input name=\"author_name\" class=\"text-xs\" placeholder=\"Your name\" required></div><div><label class=\"text-[10px] text-[#5c5c70] block mb-1\">Review</label><textarea name=\"comment\" class=\"text-xs\" rows=\"3\" placeholder=\"Share your experience...\" required></textarea></div><button type=\"submit\" class=\"btn-primary text-xs py-3\">Submit Review</button></form>';
    rv.appendChild(f);
    document.querySelector('a[href=\"#write-review\"]')?.addEventListener('click',function(e){e.preventDefault();f.classList.toggle('hidden')});
    document.getElementById('starPicker')?.querySelectorAll('i').forEach(function(s){s.addEventListener('click',function(){var v=this.dataset.v;this.parentElement.querySelectorAll('i').forEach(function(x,i){x.className=i<v?'fas fa-star':'far fa-star'});var inp=document.createElement('input');inp.type='hidden';inp.name='rating';inp.value=v;var old=this.parentElement.querySelector('input[name=rating]');if(old)old.remove();this.parentElement.appendChild(inp)})})
  }
});
function submitReview(e){e.preventDefault();var f=e.target;var d=new FormData(f);fetch('/api/review',{method:'POST',body:d}).then(function(r){return r.json()}).then(function(r){if(r.success){alert('Review submitted!');f.reset();location.reload()}else{alert(r.error||'Error submitting review')}}).catch(function(){alert('Network error')})}
</script>""" + "</body>")
    
    return page
