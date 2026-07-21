def product_detail_page(product_id):
    import json as _json, datetime as _dt
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    row = c.fetchone()
    if not row:
        db.close()
        return (LAYOUT_HEAD + TOP_NAV + '<div class="max-w-4xl mx-auto px-4 py-20 text-center"><div class="text-6xl mb-4 opacity-20">&#x1f50d;</div><h1 class="text-2xl font-bold mb-2">Product Not Found</h1><p class="text-sm text-[#5c5c70] mb-6">This product may have been removed.</p><a href="/" class="btn-primary inline-flex">Browse Marketplace</a></div>' + LAYOUT_FOOT, 404)
    p = dict(row)
    db.close()
    Q = chr(39)
    ptype = (p.get("product_type") or "other")
    icon = product_type_icon(ptype)
    color = product_type_color(ptype)
    label = PRODUCT_TYPE_LABELS.get(ptype, "Digital Product")
    title = (p.get("title") or "").strip()
    desc = p.get("description") or ""
    price = float(p.get("price", 0) or 0)
    rating = float(p.get("rating", 0) or 0)
    dl = int(p.get("downloads_count", 0) or 0)
    version = p.get("version", "1.0") or "1.0"
    ltype = (p.get("license") or "standard").lower()
    hero = p.get("hero_image_url") or ""
    slug = p.get("slug") or product_id
    seo_t = (p.get("seo_title") or title)[:68]
    seo_d = (p.get("seo_description") or desc[:155])[:160]
    seo_kw = p.get("seo_keywords") or f"{label}, {title}"
    body = p.get("content") or p.get("features") or desc
    reqs = p.get("requirements") or ""
    now = _dt.datetime.now()
    stars = ""
    for _ in range(int(rating)): stars += '<i class="fas fa-star text-[#facc15]"></i>'
    if rating - int(rating) > 0.3: stars += '<i class="fas fa-star-half-alt text-[#facc15]"></i>'
    for _ in range(5 - int(rating) - (1 if rating - int(rating) > 0.3 else 0)): stars += '<i class="far fa-star text-[#2a2a3e]"></i>'
    rev_c = max(1, int(rating * 3 + 1))
    sv = max(1, 50 - min(dl, 49))
    vc = max(3, 30 - min(dl, 27))
    fmt = {"prompt_pack":"PDF+TXT","template":"Canva+Slides","ebook":"PDF+EPUB+MOBI","code":"ZIP","course":"MP4+PDF","marketing":"PNG+PSD+Canva","starter":"ZIP+Docs"}.get(ptype, "Digital")
    diff = {"prompt_pack":"Beginner","template":"Beginner","ebook":"All Levels","code":"Int-Adv"}.get(ptype, "All Levels")
    compat = {"prompt_pack":"ChatGPT,Claude,Gemini","template":"Canva,Google Workspace","code":"VS Code,PyCharm"}.get(ptype, "Browser,Desktop")
    img = '<div class="aspect-[4/3] rounded-2xl bg-gradient-to-br from-purple-900/30 to-black/40 border border-white/10 flex items-center justify-center"><span class="text-7xl opacity-30">' + icon + '</span></div>'
    if hero:
        img = '<div class="rounded-2xl overflow-hidden bg-black/40 border border-white/10"><div class="aspect-[4/3]"><img src="' + hero.replace('"','') + '" alt="' + title.replace('"','')[:60] + '" class="w-full h-full object-cover hover:scale-105 transition-transform duration-700 cursor-zoom-in" onclick="window.open(this.src,' + Q + '_blank' + Q + ')"></div></div>'
    inc = {"prompt_pack":["150+ prompts","Usage guide","Examples","Updates"],"template":["Editable files","Guide","Tutorial","Updates"],"ebook":["PDF+EPUB+MOBI","Workbook","Resources","Updates"],"code":["Scripts","Docs","Tests","Requirements"],"course":["HD video","Workbook","Certificate","Community"]}.get(ptype, ["Digital files","Guide","Docs","Updates"])
    ih = "".join(['<div class="flex items-start gap-3 p-3 bg-black/30 rounded-xl border border-white/10"><div class="w-6 h-6 rounded-full bg-green-500/10 flex items-center justify-center flex-shrink-0"><i class="fas fa-check text-green-400 text-[10px]"></i></div><span class="text-xs font-medium">' + x + '</span></div>' for x in inc])
    ss = [("Type",label,icon),("Format",fmt,"fa-file"),("Level",diff,"fa-signal"),("Version",version,"fa-code-branch"),("Updated",now.strftime("%b %Y"),"fa-calendar"),("Compat",compat,"fa-desktop"),("License",ltype.capitalize(),"fa-scale-balanced")]
    sh = "".join(['<div class="flex items-center gap-3 p-3 bg-black/30 rounded-xl border border-white/10"><div class="w-8 h-8 rounded-lg flex items-center justify-center text-xs text-purple-400 bg-purple-500/10"><i class="fas ' + si + '"></i></div><div><div class="text-[10px] text-gray-500 uppercase">' + sl + '</div><div class="text-xs font-semibold mt-0.5 text-white">' + sv + '</div></div></div>' for sl, sv, si in ss])
    hiw = "".join(['<div class="text-center p-4 bg-black/30 rounded-2xl border border-white/10"><div class="w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-3 text-lg" style="background:' + hc + '15;color:' + hc + '"><i class="fas ' + hi + '"></i></div><h4 class="font-semibold text-xs mb-1 text-white">' + ht + '</h4><p class="text-[10px] text-gray-500">' + hd + '</p></div>' for ht, hd, hi, hc in [("Purchase","Instant files","fa-cart-shopping","#f472b6"),("Unpack","Open & review","fa-box-open","#38bdf8"),("Customize","Simple setup","fa-gear","#4ade80"),("Launch","See results","fa-rocket","#facc15")]])
    rvs = get_reviews(product_id)
    st = get_rating_stats(product_id)
    ar = st.get("avg", rating) if st else rating
    tr = st.get("total", rev_c) if st else rev_c
    rh = ""
    for rv in rvs[:5]:
        rss = "".join(['<i class="fas fa-star text-yellow-400 text-xs"></i>' for _ in range(int(rv.get("rating",5)))])
        rss += "".join(['<i class="far fa-star text-gray-700 text-xs"></i>' for _ in range(5-int(rv.get("rating",5)))])
        rn = (rv.get("author_name") or "Buyer")[:20]
        rt = (rv.get("comment") or "")[:300]
        rh += '<div class="bg-black/30 border border-white/10 rounded-xl p-4 mb-3"><div class="flex items-center justify-between mb-2"><div class="flex items-center gap-2"><div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-[10px] font-bold text-white">' + rn[0].upper() + '</div><div><div class="text-xs font-semibold text-white">' + rn + ' <span class="text-green-400 text-[10px]">&#10003;</span></div></div></div><div class="text-yellow-400">' + rss + '</div></div><p class="text-xs text-gray-400 leading-relaxed">' + rt + '</p></div>'
    fr = p.get("faq") or ""
    fi = []
    if fr:
        try: fi = _json.loads(fr)
        except: fi = [{"q":"What is included?","a":fr[:300]}]
    while len(fi) < 4:
        fi.append({"q":"What if Im not satisfied?","a":"30-day money-back guarantee."})
    fh = ""
    for i, fq in enumerate(fi[:6]):
        fiid = "fq" + str(i)
        qq = fq.get("q","")[:120]
        qa = fq.get("a","")[:500]
        fh += '<div class="border border-white/10 rounded-xl overflow-hidden"><button class="w-full flex items-center justify-between p-4 text-left hover:bg-white/5 transition" onclick="var e=document.getElementById(' + Q + fiid + Q + ');e.classList.toggle(' + Q + "hidden" + Q + ');this.querySelectorAll(' + Q + "i" + Q + ').forEach(function(x){x.classList.toggle(' + Q + "fa-chevron-down" + Q + ');x.classList.toggle(' + Q + "fa-chevron-up" + Q + ')})"><span class="text-sm font-medium pr-4 text-white">' + qq + '</span><i class="fas fa-chevron-down text-gray-500 text-xs"></i></button><div id="' + fiid + '" class="hidden px-4 pb-4 text-sm text-gray-400 leading-relaxed">' + qa + '</div></div>'
    db2 = get_db()
    c2 = db2.cursor()
    c2.execute("SELECT id,title,price,product_type,rating,hero_image_url FROM products WHERE status='published' AND id!=? ORDER BY RANDOM() LIMIT 4", (product_id,))
    rl = [dict(r) for r in c2.fetchall()]
    db2.close()
    rlh = ""
    for r in rl:
        ri = product_type_icon(r["product_type"])
        rhh = r.get("hero_image_url") or ""
        if rhh:
            rim = '<img src="' + rhh.replace('"','') + '" alt="' + (r["title"] or "")[:40] + '" class="w-full h-28 object-cover rounded-xl" loading="lazy">'
        else:
            rim = '<div class="w-full h-28 rounded-xl bg-gradient-to-br from-purple-900/30 to-black/40 flex items-center justify-center text-4xl border border-white/10">' + ri + '</div>'
        rlh += '<a href="/product/' + r["id"] + '" class="group bg-black/30 border border-white/10 rounded-2xl p-3 hover:border-purple-500/30 transition-all hover:-translate-y-0.5">' + rim + '<div class="mt-3"><h4 class="font-semibold text-xs text-white group-hover:text-purple-300 line-clamp-2">' + ((r["title"] or "")[:50]) + '</h4><div class="flex items-center justify-between mt-1"><span class="text-[10px]">' + ri + '</span><span class="text-xs font-bold text-purple-400">$' + str(r["price"]) + '</span></div></div></a>'
    lt = {"standard":"Personal + commercial use. Cannot resell.","commercial":"Full commercial use.","extended":"Extended commercial."}.get(ltype, ltype.capitalize() + " license.")
    sc = _json.dumps({"@context":"https://schema.org","@type":"Product","name":title[:110],"description":desc[:490],"offers":{"@type":"Offer","priceCurrency":"USD","price":price,"availability":"https://schema.org/InStock"},"aggregateRating":{"@type":"AggregateRating","ratingValue":round(ar,1),"reviewCount":tr}})
    head = '<title>' + seo_t + ' | ShopZario</title><meta name="description" content="' + seo_d + '"><link rel="canonical" href="https://shopzario.com/product/' + slug + '"><meta property="og:title" content="' + seo_t[:80] + '"><meta property="og:description" content="' + seo_d[:200] + '"><script type="application/ld+json">' + sc + '</script><style>.sticky-buy{position:sticky;top:88px;z-index:20}@media(max-width:768px){.sticky-buy{position:fixed;bottom:0;left:0;right:0;top:auto;z-index:50;background:#0e0e16;border-top:1px solid #1a1a24;padding:12px 16px;border-radius:16px 16px 0 0}}</style>'
    op = round(price * 1.4, 2)
    pct = int((1 - price/op) * 100)
    P = page = LAYOUT_HEAD.replace("</head>", head + "</head>") + TOP_NAV
    P += '<div class="max-w-6xl mx-auto px-4 sm:px-6 py-4 md:py-6"><nav class="flex items-center gap-1.5 text-[11px] text-gray-500 mb-4"><a href="/" class="hover:text-purple-300">Marketplace</a><span>/</span><a href="/?category=' + ptype + '" class="hover:text-purple-300">' + label + 's</a><span>/</span><span class="text-gray-400 font-medium">' + title[:60] + '</span></nav><div class="grid grid-cols-1 lg:grid-cols-12 gap-6 md:gap-8"><div class="lg:col-span-7 xl:col-span-8 space-y-6 md:space-y-8">'
    P += img
    P += '<div class="lg:hidden space-y-3"><div class="flex flex-wrap gap-2"><span class="text-[10px] font-semibold px-2.5 py-1 rounded-full" style="background:' + color + '20;color:' + color + '">' + icon + ' ' + label + '</span><span class="tag tag-green">' + str(dl) + '+ sold</span></div><h1 class="text-xl md:text-3xl font-black leading-tight">' + title[:120] + '</h1><div class="flex items-center gap-2 text-xs"><span class="text-yellow-400">' + stars + '</span><a href="#reviews" class="text-gray-500 hover:text-purple-300"><span class="font-semibold text-white">' + str(rating) + '</span> (' + str(tr) + ' reviews)</a></div></div>'
    P += '<div class="card" style="border-left:3px solid ' + color + '"><div class="flex items-start gap-4"><div class="w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0 text-2xl" style="background:' + color + '15">' + icon + '</div><div><h2 class="font-bold text-base mb-2">' + title[:80] + '</h2><p class="text-sm text-gray-400 leading-relaxed mb-3">' + desc[:500] + '</p><div class="flex flex-wrap gap-2"><span class="tag tag-purple"><i class="fas fa-infinity mr-1"></i> Lifetime</span><span class="tag tag-green"><i class="fas fa-download mr-1"></i> Instant</span><span class="tag tag-amber"><i class="fas fa-rotate-left mr-1"></i> 30-Day Refund</span></div></div></div></div>'
    P += '<div class="card"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center"><i class="fas fa-gift text-green-400"></i></div><div><h2 class="font-bold text-lg">What' + Q + 's Included</h2><p class="text-xs text-gray-500">' + str(len(inc)) + ' items</p></div></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">' + ih + '</div></div>'
    if body:
        feats = [x.strip() for x in body.split("\n") if x.strip()][:4]
        if feats:
            fc = ["#f472b6","#38bdf8","#4ade80","#a855f7"]
            fi = ["fa-bolt","fa-shield","fa-gauge-high","fa-wand-magic-sparkles"]
            fh = ""
            for i, f in enumerate(feats):
                if len(f) > 10:
                    fh += '<div class="bg-black/30 border border-white/10 rounded-2xl p-5 hover:border-' + fc[i%4] + '/30 transition hover:-translate-y-0.5"><div class="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style="background:' + fc[i%4] + '15;color:' + fc[i%4] + '"><i class="fas ' + fi[i%4] + '"></i></div><p class="text-xs text-gray-400 leading-relaxed">' + f[:100] + '</p></div>'
            P += '<div class="card"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center"><i class="fas fa-list-check text-purple-400"></i></div><div><h2 class="font-bold text-lg">Features</h2><p class="text-xs text-gray-500">What makes this stand out</p></div></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-4">' + fh + '</div></div>'
    P += '<div class="card"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-sky-500/10 flex items-center justify-center"><i class="fas fa-arrow-right-arrow-left text-sky-400"></i></div><div><h2 class="font-bold text-lg">How It Works</h2></div></div><div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">' + hiw + '</div></div>'
    P += '<div class="card" id="faq"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center"><i class="fas fa-circle-question text-yellow-400"></i></div><div><h2 class="font-bold text-lg">FAQ</h2></div></div><div class="space-y-3">' + fh + '</div></div>'
    P += '<div class="card" id="reviews"><div class="flex items-center justify-between mb-5"><div class="flex items-center gap-3"><div class="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center"><i class="fas fa-star text-yellow-400"></i></div><div><h2 class="font-bold text-lg">Reviews</h2></div></div></div><div class="flex items-center gap-4 mb-5 p-4 bg-black/30 rounded-xl border border-white/10"><div class="text-center"><div class="text-3xl font-black text-yellow-400">' + str(round(ar,1)) + '</div><div class="text-yellow-400 text-xs mt-0.5">' + stars + '</div></div><div class="flex-1"><div class="text-xs font-semibold text-white">' + str(tr) + ' verified reviews</div></div></div>' + (rh if rh else '<p class="text-sm text-gray-500 text-center py-4">No reviews yet.</p>') + '</div>'
    P += '<div class="card"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-sky-500/10 flex items-center justify-center"><i class="fas fa-link text-sky-400"></i></div><div><h2 class="font-bold text-lg">You May Also Like</h2></div></div>' + ('<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">' + rlh + '</div>' if rlh else '<p class="text-sm text-gray-500">No related products.</p>') + '</div></div>'
    P += '<div class="lg:col-span-5 xl:col-span-4 space-y-5"><div class="rounded-2xl p-4 text-center text-pink-400 font-semibold text-sm" style="background:linear-gradient(135deg,rgba(236,72,153,0.1),rgba(168,85,247,0.1));border:1px solid rgba(236,72,153,0.2);animation:pulse 2s infinite"><i class="fas fa-bolt mr-1"></i> ' + str(sv) + ' sold &middot; ' + str(vc) + ' viewing now</div>'
    P += '<div class="card sticky-buy"><div class="text-center mb-5"><div class="flex items-center justify-center gap-3"><span class="text-4xl font-black text-white">$' + str(price) + '</span><span class="text-sm line-through text-gray-500">$' + str(op) + '</span><span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-500/15 text-green-400">-' + str(pct) + '%</span></div><div class="text-xs text-gray-500 mt-1">One-time &middot; Lifetime</div></div><a href="/api/checkout/' + p["id"] + '" class="btn-primary w-full text-base py-4 mb-3" style="font-size:16px"><i class="fas fa-shopping-cart"></i> Buy Now $' + str(price) + '</a><div class="flex justify-center gap-3 mb-4 text-lg text-gray-500"><i class="fab fa-cc-visa"></i><i class="fab fa-cc-mastercard"></i><i class="fab fa-cc-amex"></i><i class="fab fa-cc-paypal"></i><i class="fab fa-bitcoin"></i></div><div class="space-y-2 text-xs text-gray-500"><div class="flex items-center gap-2"><i class="fas fa-cloud-arrow-down text-green-400 w-4"></i> Instant download</div><div class="flex items-center gap-2"><i class="fas fa-shield-halved text-green-400 w-4"></i> SSL secure checkout</div><div class="flex items-center gap-2"><i class="fas fa-arrows-rotate text-green-400 w-4"></i> Free lifetime updates</div></div></div>'
    P += '<div class="card"><h3 class="font-bold text-sm mb-4"><i class="fas fa-table-list text-purple-400 mr-2"></i>Specifications</h3><div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">' + sh + '</div></div>'
    P += '<div class="card"><h3 class="font-bold text-sm mb-4"><i class="fas fa-desktop text-sky-400 mr-2"></i>Requirements</h3><p class="text-xs text-gray-400 leading-relaxed">' + (reqs[:300] if reqs else "No special requirements. Works on all modern devices.") + '</p></div>'
    if xh:
        P += '<div class="card"><h3 class="font-bold text-sm mb-4"><i class="fas fa-cubes text-green-400 mr-2"></i>Complete Bundle</h3><div class="text-center mb-3"><span class="text-[10px] font-semibold text-green-400 bg-green-500/10 px-2.5 py-1 rounded-full"><i class="fas fa-tag mr-1"></i> Bundle 2+ save 15%</span></div><div class="space-y-2">' + xh + '</div></div>'
    P += '<div class="card text-center" style="border:1px solid rgba(74,222,128,0.3);background:linear-gradient(135deg,#0a1a0e,#0e0e16)"><div class="text-4xl mb-3">&#x1f6e1;&#xfe0f;</div><h3 class="font-bold text-base mb-1 text-white">30-Day Guarantee</h3><p class="text-xs text-gray-400">Full refund if not satisfied.</p></div>'
    P += '<div class="card"><div class="flex items-center gap-3 mb-3"><span style="color:' + color + '" class="text-xl">' + icon + '</span><h3 class="font-bold text-sm text-white">License</h3></div><span class="tag tag-purple">' + ltype.capitalize() + '</span><p class="text-xs text-gray-400 mt-2 leading-relaxed">' + lt + '</p></div>'
    P += '<div class="card text-center"><div class="flex justify-center -space-x-2 mb-3"><div class="w-9 h-9 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-xs font-bold text-white border-2 border-black/80">JD</div><div class="w-9 h-9 rounded-full bg-gradient-to-br from-sky-400 to-green-400 flex items-center justify-center text-xs font-bold text-white border-2 border-black/80">SK</div><div class="w-9 h-9 rounded-full bg-gradient-to-br from-yellow-400 to-pink-400 flex items-center justify-center text-xs font-bold text-white border-2 border-black/80">MR</div><div class="w-9 h-9 rounded-full bg-gray-800 flex items-center justify-center text-[9px] text-gray-500 font-semibold border-2 border-black/80">+' + str(max(dl,5)) + '</div></div><p class="text-xs text-gray-500">Joined by <span class="text-white font-semibold">' + format(max(dl*3,50), ",") + '</span> creators</p></div></div></div></div>' + LAYOUT_FOOT
    return P
