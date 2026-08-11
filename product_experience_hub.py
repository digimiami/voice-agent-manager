"""Product Experience Hub - complete destination for every product."""
import json as _json
import datetime as _dt
import navigation


def experience_hub(product_id):
    """Complete Product Experience Hub - multi-tab destination."""
    import product_store as _ps
    
    db = _ps.get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    row = c.fetchone()
    if not row:
        db.close()
        return (_ps.LAYOUT_HEAD + _ps.TOP_NAV + 
                '<div class="max-w-4xl mx-auto px-4 py-20 text-center"><div class="text-6xl mb-4 opacity-20">&#x1f50d;</div><h1 class="text-2xl font-bold mb-2">Not Found</h1><a href="/" class="btn-primary">Back</a></div>' + 
                _ps.LAYOUT_FOOT)
    p = dict(row)
    db.close()
    Q = chr(39)
    ptype = (p.get("product_type") or "other")
    icon = _ps.product_type_icon(ptype)
    color = _ps.product_type_color(ptype)
    label = _ps.PRODUCT_TYPE_LABELS.get(ptype, "Digital Product")
    title = (p.get("title") or "").strip()
    desc = p.get("description") or ""
    price = float(p.get("price", 0) or 0)
    rating = float(p.get("rating", 0) or 0)
    dl = int(p.get("downloads_count", 0) or 0)
    ver = p.get("version", "1.0") or "1.0"
    ltype = (p.get("license") or "standard").lower()
    hero = p.get("hero_image_url") or ""
    slug = p.get("slug") or product_id
    seo_t = (p.get("seo_title") or title)[:68]
    seo_d = (p.get("seo_description") or desc[:155])[:160]
    body = p.get("content") or p.get("features") or desc
    reqs = p.get("requirements") or ""
    vid = p.get("video_url") or ""
    faq_raw = p.get("faq") or ""
    changelog = p.get("changelog") or ""
    creator = p.get("creator_name") or "AI Factory"
    now = _dt.datetime.now()
    sv = max(1, 50 - min(dl, 49))
    vc = max(3, 30 - min(dl, 27))
    
    # Stars
    stars = ""
    for _ in range(int(rating)): stars += '<i class="fas fa-star text-yellow-400"></i>'
    if rating - int(rating) > 0.3: stars += '<i class="fas fa-star-half-alt text-yellow-400"></i>'
    for _ in range(5 - int(rating) - (1 if rating - int(rating) > 0.3 else 0)): stars += '<i class="far fa-star text-gray-700"></i>'
    
    # Hero image
    img = '<div class="aspect-[4/3] rounded-2xl bg-gradient-to-br from-purple-900/30 to-black/40 border border-white/10 flex items-center justify-center"><span class="text-7xl opacity-30">' + icon + '</span></div>'
    if hero:
        img = '<div class="rounded-2xl overflow-hidden bg-black/40 border border-white/10 group"><div class="aspect-[4/3]"><img src="' + hero.replace('"','') + '" alt="' + title.replace('"','')[:60] + '" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105 cursor-zoom-in" onclick="window.open(this.src,' + Q + '_blank' + Q + ')"></div></div>'
    
    # Specs
    fmap = {"prompt_pack":{"f":"TXT+PDF","d":"Beginner","c":"ChatGPT,Claude,Gemini"},"template":{"f":"Guide+Files","d":"Beginner","c":"Notion,Excel,Canva,GSuite"},"ebook":{"f":"TXT+PDF","d":"All","c":"Any device"},"code":{"f":"Source+Guide","d":"Int-Adv","c":"VS Code,PyCharm"},"checklist":{"f":"TXT+PDF","d":"Beginner","c":"Any device"},"notion_template":{"f":"Guide+JSON","d":"Beginner","c":"Notion"},"business_doc":{"f":"TXT+PDF","d":"Intermediate","c":"MS Word,Google Docs"},"marketing":{"f":"Guide+Files","d":"Beginner","c":"Canva,Social Media"},"marketing_tool":{"f":"Guide+Files","d":"Beginner","c":"Canva,Social Media"}}
    fm = fmap.get(ptype, {}); fmt = fm.get("f","Digital"); diff = fm.get("d","All"); compat = fm.get("c","Browser")
    specs = [("Type",label,icon),("Format",fmt,"fa-file"),("Level",diff,"fa-signal"),("Version",ver,"fa-code-branch"),("Updated",now.strftime("%b %Y"),"fa-calendar"),("Compat",compat,"fa-desktop"),("License",ltype.capitalize(),"fa-scale-balanced"),("Author",creator[:20],"fa-user")]
    sh = "".join(['<div class="flex items-center gap-3 p-3 bg-black/30 rounded-xl border border-white/10"><div class="w-8 h-8 rounded-lg flex items-center justify-center text-xs text-purple-400 bg-purple-500/10"><i class="fas ' + si + '"></i></div><div><div class="text-[10px] text-gray-500 uppercase">' + sl + '</div><div class="text-xs font-semibold text-white">' + sv + '</div></div></div>' for sl,sv,si in specs])
    
    # Included
    inc_map = {"prompt_pack":["Full prompt collection (TXT)","Usage guide (PDF)","Examples","Lifetime updates"],"template":["Deliverable files","Setup guide","Tutorial","Updates"],"ebook":["Full ebook (TXT)","Professional PDF","Resources","Updates"],"code":["Source code","Documentation","Tests","Requirements"],"checklist":["Complete checklist (TXT)","Printable PDF","Examples","Updates"],"notion_template":["Notion template (JSON)","Setup guide (TXT)","Database structure","Video walkthrough"],"business_doc":["Document templates (TXT)","Usage guide (PDF)","Examples","Updates"],"marketing":["Content templates","Strategy guide","Calendar","Updates"],"marketing_tool":["Content engine","Setup guide","Templates","Updates"]}
    inc = inc_map.get(ptype, ["Digital files","Guide","Docs","Updates"])
    ih = "".join(['<div class="flex items-start gap-3 p-3 bg-black/30 rounded-xl border border-white/10"><div class="w-6 h-6 rounded-full bg-green-500/10 flex items-center justify-center shrink-0"><i class="fas fa-check text-green-400 text-[10px]"></i></div><span class="text-xs font-medium text-white">' + x + '</span></div>' for x in inc])
    
    # Reviews
    rvs = _ps.get_reviews(product_id)
    st = _ps.get_rating_stats(product_id)
    ar = st[0] if st else rating
    tr = st[1] if st else max(1, int(rating * 3 + 1))
    rh = ""
    for r in rvs[:5]:
        rss = "".join(['<i class="fas fa-star text-yellow-400 text-xs"></i>' for _ in range(int(r.get("rating",5)))])
        rss += "".join(['<i class="far fa-star text-gray-700 text-xs"></i>' for _ in range(5-int(r.get("rating",5)))])
        rn = (r.get("author_name") or "Buyer")[:20]; rt2 = (r.get("comment") or "Great!")[:300]
        rh += '<div class="bg-black/30 border border-white/10 rounded-xl p-4"><div class="flex items-center justify-between mb-2"><div class="flex items-center gap-2"><div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-[10px] font-bold text-white">' + rn[0].upper() + '</div><div><div class="text-xs font-semibold text-white">' + rn + ' <span class="text-green-400">&#10003;</span></div></div></div><div class="text-yellow-400">' + rss + '</div></div><p class="text-xs text-gray-400">' + rt2 + '</p></div>'
    if not rh: rh = '<p class="text-sm text-gray-500 text-center py-4">No reviews.</p>'
    
    # FAQ - generate type-specific content from product data
    try: fi = _json.loads(faq_raw) if isinstance(faq_raw,str) and faq_raw.startswith("[") else []
    except: fi = []
    
    # Build rich FAQ from product data and type
    faq_items = []
    inc_names = {"prompt_pack":"prompts","template":"templates","ebook":"ebook files","code":"Python scripts","course":"video lessons","marketing":"templates","checklist":"checklists","business_doc":"legal document templates","starter":"starter kits"}
    inc_name = inc_names.get(ptype, "digital files")
    
    faq_items.append({"q":"What exactly is included in this " + label.lower() + "?","a":"This " + label.lower() + " includes " + str(len(inc)) + " items: " + ", ".join(inc) + ". All files are professionally designed and ready for immediate use after purchase. You get lifetime access and free updates."})
    faq_items.append({"q":"Can I use this commercially?","a":"Yes! This comes with a " + ltype.capitalize() + " license, which allows personal and commercial use in your projects. You cannot resell the raw " + inc_name + " as-is, but you can use them in client work and commercial products."})
    faq_items.append({"q":"How do I access my files after purchase?","a":"Immediately after completing payment, you will be redirected to a download page. We also send a download link to your email. All files are available as a ZIP archive for easy downloading. Your downloads never expire."})
    faq_items.append({"q":"What format are the files in?","a":"Files are provided in " + fmt + " format" + (", fully compatible with " + compat + "." if compat else ".") + ' All files are professionally formatted, tested, and ready to use. No special software is required beyond what is listed in the requirements.'})
    faq_items.append({"q":"What software or tools do I need?","a":(reqs[:200] if reqs else "No special requirements. Works with standard free or commonly available tools.") + ' Most users already have everything they need.'})
    faq_items.append({"q":"Is this suitable for beginners?","a":"Yes. This ' + label.lower() + ' is suitable for everyone. The included guide walks through everything step by step."})
    faq_items.append({"q":"Do I get updates if the product is improved?","a":"Yes, absolutely! All ShopZario products include free lifetime updates. When we release new versions, features, or improvements, you get them at no additional cost. Check the Resources tab above for the changelog."})
    faq_items.append({"q":"What if I am not satisfied with my purchase?","a":"We offer a 30-day money-back guarantee. If you are not completely satisfied, contact support@shopzario.com within 30 days of purchase for a full refund. No questions asked, no hassle."})
    faq_items.append({"q":"Can I get support if I have questions?","a":"Absolutely! Email support@shopzario.com and we will respond within 24 hours. Include your order ID for the fastest service. We also have a knowledge base with 100+ guides and tutorials."})
    faq_items.append({"q":"How large are the files?","a":"The download is typically 1-50 MB depending on the product type. All files are compressed in ZIP format for fast downloading. Your internet connection should handle it easily."})
    
    # Merge DB faq with defaults
    fi = fi + faq_items
    # Deduplicate by question text
    seen = set()
    fi_deduped = []
    for f in fi:
        q = f.get("q","")[:50].lower()
        if q not in seen:
            seen.add(q)
            fi_deduped.append(f)
    fi = fi_deduped[:12]  # max 12 FAQ items
    fh = ""
    for i, fq in enumerate(fi):
        fid = "fq" + str(i)
        qq = fq.get("q","")[:120]; qa = fq.get("a","")[:500]
        fh += '<div class="border border-white/10 rounded-xl overflow-hidden"><button class="w-full flex items-center justify-between p-4 text-left hover:bg-white/5 transition" onclick="var e=document.getElementById(' + Q + fid + Q + ');e.classList.toggle(' + Q + "hidden" + Q + ');this.querySelectorAll(' + Q + "i" + Q + ').forEach(function(x){x.classList.toggle(' + Q + "fa-chevron-down" + Q + ');x.classList.toggle(' + Q + "fa-chevron-up" + Q + ')})"><span class="text-sm font-medium text-white">' + qq + '</span><i class="fas fa-chevron-down text-gray-500 text-xs transition shrink-0"></i></button><div id="' + fid + '" class="hidden px-4 pb-4 text-sm text-gray-400 leading-relaxed">' + qa + '</div></div>'
    
    # Related + Cross-sells + Trending
    db2 = _ps.get_db()
    c2 = db2.cursor()
    c2.execute("SELECT id,title,price,product_type,rating,hero_image_url,slug FROM products WHERE status='published' AND id!=? ORDER BY RANDOM() LIMIT 4", (product_id,))
    rl = [dict(r) for r in c2.fetchall()]
    rlh = ""
    for r in rl:
        ri = _ps.product_type_icon(r["product_type"]); rhh = r.get("hero_image_url") or ""
        rim = ('<img src="' + rhh.replace('"',"") + '" alt="' + (r["title"]or"")[:40] + '" class="w-full h-28 object-cover rounded-xl" loading="lazy">') if rhh else ('<div class="w-full h-28 rounded-xl bg-gradient-to-br from-purple-900/30 to-black/40 flex items-center justify-center text-4xl border border-white/10">' + ri + '</div>')
        rlh += '<a href="/product/' + r["id"] + '" class="group bg-black/30 border border-white/10 rounded-2xl p-3 hover:border-purple-500/30 transition-all hover:-translate-y-0.5">' + rim + '<div class="mt-3"><h4 class="font-semibold text-xs text-white group-hover:text-purple-300 line-clamp-2">' + ((r["title"] or "")[:50]) + '</h4><div class="flex items-center justify-between mt-1"><span class="text-[10px]">' + ri + '</span><span class="text-xs font-bold text-purple-400">$' + str(r["price"]) + '</span></div></div></a>'
    
    c2.execute("SELECT id,title,price,product_type,slug FROM products WHERE status='published' AND id!=? AND product_type=? ORDER BY RANDOM() LIMIT 3", (product_id, ptype))
    xh = ""
    for x in c2.fetchall():
        xi = _ps.product_type_icon(x[3]); xo = round(float(x[2]) * 1.25, 2)
        xh += '<div class="flex items-center gap-3 p-3 bg-black/30 rounded-xl border border-white/10 hover:border-purple-500/30 transition cursor-pointer" onclick="location.href=' + Q + '/product/' + (x[4] or x[0]) + Q + '"><span class="text-2xl">' + xi + '</span><div class="flex-1 min-w-0"><div class="text-xs font-semibold text-white truncate">' + (x[1] or "")[:40] + '</div><div class="flex items-center gap-2 mt-0.5"><span class="text-xs font-bold text-purple-400">$' + str(x[2]) + '</span><span class="text-[10px] text-gray-500 line-through">$' + str(xo) + '</span></div></div></div>'
    
    c2.execute("SELECT id,title,price,product_type,hero_image_url,slug FROM products WHERE status='published' AND id!=? AND product_type!=? ORDER BY downloads_count DESC LIMIT 4", (product_id, ptype))
    trh = ""
    for r in c2.fetchall():
        ri = _ps.product_type_icon(r[3])
        trh += '<a href="/product/' + r[0] + '" class="flex items-center gap-3 p-3 bg-black/30 rounded-xl border border-white/10 hover:border-purple-500/30 transition"><div class="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-900/30 to-black/40 flex items-center justify-center text-lg shrink-0">' + ri + '</div><div class="min-w-0"><div class="text-xs font-semibold text-white truncate">' + (r[1]or"")[:30] + '</div><span class="text-[10px] text-purple-400">$' + str(r[2]) + '</span></div></a>'
    db2.close()
    
    # Learning Center
    lc = ""
    for lt, ld in [("Getting Started","Download, extract, read the README. Most users are up in 5 min."),("Tips & Tricks","Customize templates, combine files, use bonus content. Power users see 3x results."),("Common Mistakes","Skipping the guide, forgetting backups, not testing on multiple devices."),("Best Practices","Follow the workflow, customize, test, iterate. Top creators follow this process."),("Troubleshooting","Check browser settings, update software, or email support@shopzario.com.")]:
        lc += '<div class="bg-black/30 border border-white/10 rounded-2xl p-5 hover:border-purple-500/20 transition"><h4 class="font-semibold text-sm text-white mb-2">' + lt + '</h4><p class="text-xs text-gray-400 leading-relaxed">' + ld + '</p></div>'
    
    # Blog
    blog = ""
    for bt, bd in [("1. Start with the template","Open and customize colors, fonts, layout to match your brand."),("2. Read the guide first","The included README has setup steps and pro tips."),("3. Customize for your audience","Tailor the content to resonate with your specific audience."),("4. Test on multiple devices","Preview on desktop, tablet, and mobile."),("5. Use bonus content","Leverage included extras to expand your project."),("6. Combine products","Bundle with similar items for a complete solution."),("7. Keep backups","Always save original files before making changes."),("8. Update regularly","Check for updates monthly. New features added regularly."),("9. Leave a review","Your feedback helps other buyers and improves the product.")]:
        blog += '<p class="text-sm text-white font-semibold mt-3 mb-1">' + bt + '</p><p class="text-xs text-gray-400 leading-relaxed">' + bd + '</p>'
    
    # Changelog
    try: cls = _json.loads(changelog) if changelog.startswith("[") else [changelog[:300]]
    except: cls = [changelog[:300]] if changelog else ["Initial release v" + ver]
    cl = "".join(["<li class='text-xs text-gray-400 py-1.5 border-b border-white/5 last:border-0'>" + c[:200] + "</li>" for c in cls])
    
    # Schema
    schema = _json.dumps({"@context":"https://schema.org","@type":"Product","name":title[:110],"description":desc[:490],"offers":{"@type":"Offer","priceCurrency":"USD","price":price},"aggregateRating":{"@type":"AggregateRating","ratingValue":round(ar,1),"reviewCount":tr}}, default=str)
    
    # Video
    vid_block = '<div class="aspect-video rounded-2xl bg-gradient-to-br from-purple-900/20 to-black/40 border border-white/10 flex items-center justify-center"><div class="text-center"><div class="text-5xl mb-3 opacity-30">&#x1f3ac;</div><p class="text-sm text-gray-500">Video coming soon</p></div></div>'
    if vid: vid_block = '<div class="aspect-video rounded-2xl overflow-hidden border border-white/10 bg-black"><video controls class="w-full h-full"><source src="' + vid + '" type="video/mp4"></video></div>'
    
    ltx = {"standard":"Personal + commercial use. Cannot resell.","commercial":"Full commercial use. Unlimited projects.","extended":"Extended commercial."}.get(ltype, ltype.capitalize() + " license.")
    op = round(price * 1.4, 2); pct = int((1 - price/op) * 100)
    hub_css = ".hub-tab{display:none}.hub-tab.active{display:block}.tab-btn{transition:all .2s}.tab-btn.active{color:#c084fc!important;background:rgba(168,85,247,0.1)!important}@media(max-width:768px){.hub-tabs{overflow-x:auto;white-space:nowrap;-webkit-overflow-scrolling:touch}.hub-tabs::-webkit-scrollbar{display:none}}"
    
    page = (_ps.LAYOUT_HEAD.replace("</head>",
        '<title>' + seo_t + ' | ShopZario Hub</title><meta name="description" content="' + seo_d + '">'
        '<link rel="canonical" href="https://shopzario.com/product/' + slug + '">'
        '<meta property="og:title" content="' + seo_t[:80] + '">'
        '<meta property="og:description" content="' + seo_d[:200] + '">'
        '<meta property="og:url" content="https://shopzario.com/product/' + slug + '">'
        '<meta property="og:image" content="' + (hero or "https://shopzario.com/static/og-image.png") + '">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<script type="application/ld+json">' + schema + '</script>'
        '<style>' + hub_css + '</style></head>')
        + _ps.TOP_NAV)
    
    page += '<div class="max-w-7xl mx-auto px-4 sm:px-6 py-4 md:py-6">'
    page += '<nav class="flex items-center gap-1.5 text-[11px] text-gray-500 mb-4"><a href="/" class="hover:text-purple-300">Marketplace</a><span>/</span><a href="/?category=' + ptype + '" class="hover:text-purple-300">' + label + 's</a><span>/</span><span class="text-gray-400 font-medium">' + title[:60] + '</span></nav>'
    
    # Tab nav
    tabs = [("overview","Overview","fa-store"),("learn","Learn","fa-graduation-cap"),("resources","Resources","fa-box-archive"),("video","Video","fa-video"),("reviews","Reviews","fa-star")]
    page += '<nav class="hub-tabs flex gap-1 md:gap-2 p-1 rounded-2xl bg-black/40 border border-white/10 mb-6 md:mb-8">'
    for i, (tid, tn, ti) in enumerate(tabs):
        a = "active" if i == 0 else ""
        page += '<button class="tab-btn ' + a + ' flex items-center gap-2 px-3 md:px-5 py-2.5 rounded-xl text-xs font-semibold text-gray-400 hover:text-white transition-all shrink-0" onclick="switchHub(' + Q + tid + Q + ',this)" data-tab="' + tid + '"><i class="fas ' + ti + '"></i><span class="hidden sm:inline"> ' + tn + '</span></button>'
    page += '</nav>'
    
    # ── OVERVIEW TAB ──
    page += '<div id="hub-overview" class="hub-tab active"><div class="grid grid-cols-1 lg:grid-cols-12 gap-6 md:gap-8"><div class="lg:col-span-7 xl:col-span-8 space-y-6">'
    page += img
    page += '<div class="lg:hidden space-y-3"><div class="flex gap-2"><span class="text-[10px] font-semibold px-2.5 py-1 rounded-full" style="background:' + color + '20;color:' + color + '">' + icon + ' ' + label + '</span><span class="tag tag-green">' + str(dl) + '+ sold</span></div><h1 class="text-xl md:text-3xl font-black text-white leading-tight">' + title[:120] + '</h1><div class="flex items-center gap-2 text-xs"><span class="text-yellow-400">' + stars + '</span><span class="text-gray-500"><span class="font-semibold text-white">' + str(rating) + '</span> reviews</span></div></div>'
    page += '<div class="card" style="border-left:3px solid ' + color + '"><div class="flex items-start gap-4"><div class="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 text-2xl" style="background:' + color + '15">' + icon + '</div><div><h2 class="font-bold text-base text-white mb-2">' + title[:80] + '</h2><p class="text-sm text-gray-400 leading-relaxed mb-3">' + desc[:600] + '</p><div class="flex flex-wrap gap-2"><span class="tag tag-purple">&#x221e; Lifetime</span><span class="tag tag-green"><i class="fas fa-download"></i> Instant</span><span class="tag tag-amber"><i class="fas fa-rotate-left"></i> 30-Day</span></div></div></div></div>'
    page += '<div class="card"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center"><i class="fas fa-gift text-green-400"></i></div><div><h2 class="font-bold text-lg text-white">What' + Q + 's Included</h2></div></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">' + ih + '</div></div>'
    
    hiw = ""
    for ht, hd, hi, hc in [("Purchase","Instant access","fa-cart-shopping","#f472b6"),("Download","Save to device","fa-download","#38bdf8"),("Customize","Edit for you","fa-pen","#4ade80"),("Launch","Get results","fa-rocket","#facc15")]:
        hiw += '<div class="text-center p-5 bg-black/30 rounded-2xl border border-white/10 hover:border-' + hc + '/30 transition"><div class="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-3 text-xl" style="background:' + hc + '15;color:' + hc + '"><i class="fas ' + hi + '"></i></div><h4 class="font-semibold text-sm text-white">' + ht + '</h4><p class="text-xs text-gray-500 mt-1">' + hd + '</p></div>'
    page += '<div class="card"><h2 class="font-bold text-lg text-white mb-5">How It Works</h2><div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">' + hiw + '</div></div>'
    
    # Faq
    page += '<div class="card" id="over-faq"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center"><i class="fas fa-circle-question text-yellow-400"></i></div><div><h2 class="font-bold text-lg text-white">FAQ</h2></div></div><div class="space-y-3">' + fh + '</div></div>'
    page += '<div class="card"><div class="flex items-center gap-3 mb-5"><div class="w-10 h-10 rounded-xl bg-sky-500/10 flex items-center justify-center"><i class="fas fa-link text-sky-400"></i></div><div><h2 class="font-bold text-lg text-white">You May Also Like</h2></div></div>' + ('<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">' + rlh + '</div>' if rlh else '<p class="text-sm text-gray-500">None.</p>') + '</div></div>'
    
    # ── RIGHT SIDEBAR ──
    page += '<div class="lg:col-span-5 xl:col-span-4 space-y-5">'
    page += '<div class="rounded-2xl p-4 text-center text-pink-400 font-semibold text-sm" style="background:linear-gradient(135deg,rgba(236,72,153,0.1),rgba(168,85,247,0.1));border:1px solid rgba(236,72,153,0.2)"><i class="fas fa-bolt"></i> ' + str(sv) + ' sold &middot; ' + str(vc) + ' viewing</div>'
    page += '<div class="card sticky-buy"><div class="text-center mb-4"><div class="flex items-center justify-center gap-3"><span class="text-4xl font-black text-white">$' + str(price) + '</span><span class="text-sm line-through text-gray-500">$' + str(op) + '</span><span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-500/15 text-green-400">-' + str(pct) + '%</span></div></div><a href="/api/checkout/' + p["id"] + '" class="btn-primary w-full text-base py-4 mb-3" style="font-size:16px"><i class="fas fa-shopping-cart"></i> Buy Now $' + str(price) + '</a><div class="flex justify-center gap-3 mb-3 text-lg text-gray-500"><i class="fab fa-cc-visa"></i><i class="fab fa-cc-mastercard"></i><i class="fab fa-cc-amex"></i><i class="fab fa-cc-paypal"></i><i class="fab fa-bitcoin"></i></div></div>'
    page += '<div class="card"><h3 class="font-bold text-sm text-white mb-4"><i class="fas fa-table-list text-purple-400 mr-2"></i>Specifications</h3><div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">' + sh + '</div></div>'
    page += '<div class="card"><h3 class="font-bold text-sm text-white mb-4"><i class="fas fa-desktop text-sky-400 mr-2"></i>Requirements</h3><p class="text-xs text-gray-400">' + (reqs[:300] or "No special requirements.") + '</p></div>'
    if xh: page += '<div class="card"><h3 class="font-bold text-sm text-white mb-4"><i class="fas fa-cubes text-green-400 mr-2"></i>Bundle</h3><div class="space-y-2">' + xh + '</div></div>'
    page += '<div class="card text-center" style="border:1px solid rgba(74,222,128,0.3);background:linear-gradient(135deg,#0a1a0e,#0e0e16)"><div class="text-4xl mb-3">&#x1f6e1;&#xfe0f;</div><h3 class="font-bold text-base text-white">30-Day Guarantee</h3><p class="text-xs text-gray-400">Full refund.</p></div>'
    page += '<div class="card"><div class="flex items-center gap-3 mb-3"><span style="color:' + color + '" class="text-xl">' + icon + '</span><h3 class="font-bold text-sm text-white">License: ' + ltype.capitalize() + '</h3></div><p class="text-xs text-gray-400">' + ltx + '</p></div>'
    page += '<div class="card text-center"><div class="flex justify-center -space-x-2 mb-3"><div class="w-9 h-9 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-xs font-bold text-white border-2 border-black/80">JD</div><div class="w-9 h-9 rounded-full bg-gradient-to-br from-sky-400 to-green-400 flex items-center justify-center text-xs font-bold text-white border-2 border-black/80">SK</div><div class="w-9 h-9 rounded-full bg-gradient-to-br from-yellow-400 to-pink-400 flex items-center justify-center text-xs font-bold text-white border-2 border-black/80">MR</div><div class="w-9 h-9 rounded-full bg-gray-800 flex items-center justify-center text-[9px] text-gray-500 font-semibold border-2 border-black/80">+' + str(max(dl,5)) + '</div></div><p class="text-xs text-gray-500">Joined by <span class="text-white font-semibold">' + format(max(dl*3,50),",") + '</span> creators</p></div></div></div></div>'
    
    # ── LEARN TAB ──
    page += '<div id="hub-learn" class="hub-tab space-y-6"><div class="card"><div class="flex items-center gap-3 mb-5"><i class="fas fa-graduation-cap text-purple-400 text-xl"></i><h2 class="font-bold text-xl text-white">Learning Center</h2></div><div class="grid grid-cols-1 md:grid-cols-2 gap-4">' + lc + '</div></div>'
    page += '<div class="card"><div class="flex items-center gap-3 mb-5"><i class="fas fa-newspaper text-blue-400 text-xl"></i><h2 class="font-bold text-xl text-white">10 Ways to Maximize Your Purchase</h2></div>' + blog + '<div class="mt-5 pt-4 border-t border-white/10"><p class="text-xs text-gray-500 italic">Guide for <strong>' + title[:50] + '</strong></p></div></div></div>'
    
    # ── RESOURCES TAB ──
    page += '<div id="hub-resources" class="hub-tab space-y-6"><div class="card"><div class="flex items-center gap-3 mb-5"><i class="fas fa-box-archive text-amber-400 text-xl"></i><h2 class="font-bold text-xl text-white">Resources</h2></div><div class="grid grid-cols-1 md:grid-cols-4 gap-4"><div class="bg-black/30 border border-white/10 rounded-2xl p-5"><h4 class="font-semibold text-sm text-white mb-2">&#x1f4cb; Quick Start</h4><p class="text-xs text-gray-400">Download, extract, follow the guide. Compatible with ' + compat + '.</p></div><div class="bg-black/30 border border-white/10 rounded-2xl p-5"><h4 class="font-semibold text-sm text-white mb-2">&#x1f4e9; Support</h4><p class="text-xs text-gray-400">support@shopzario.com. 24h response.</p></div><div class="bg-black/30 border border-white/10 rounded-2xl p-5"><h4 class="font-semibold text-sm text-white mb-2">&#x1f504; Updates</h4><p class="text-xs text-gray-400">v' + ver + ' current. Free lifetime updates.</p></div><a href="/static/product_pdfs/' + product_id + '.pdf" target="_blank" class="bg-black/30 border border-white/10 rounded-2xl p-5 hover:border-purple-500/30 transition block group"><h4 class="font-semibold text-sm text-white mb-2 group-hover:text-purple-300">&#x1f4d1; Product Sheet (PDF)</h4><p class="text-xs text-gray-400">Download features, specs &amp; details.</p></a></div></div>'
    page += '<div class="card"><div class="flex items-center gap-3 mb-5"><i class="fas fa-rotate text-green-400 text-xl"></i><h2 class="font-bold text-lg text-white">Changelog</h2></div><ul>' + cl + '</ul></div></div>'
    
    # ── VIDEO TAB ──
    page += '<div id="hub-video" class="hub-tab space-y-6"><div class="card"><div class="flex items-center gap-3 mb-5"><i class="fas fa-video text-pink-400 text-xl"></i><h2 class="font-bold text-xl text-white">Video Center</h2></div>' + vid_block + '</div>'
    page += '<div class="card"><div class="flex items-center gap-3 mb-5"><i class="fas fa-scroll text-purple-400 text-xl"></i><h2 class="font-bold text-lg text-white">Video Script</h2></div><div class="bg-black/30 rounded-xl p-5"><p class="text-xs text-gray-400">"Hey! In this video I' + Q + 'll show you ' + title[:50] + '. This ' + label.lower() + ' helps you solve [problem] in minutes. Walk through what you get, key features, and my honest review. Grab yours at shopzario.com!"</p></div></div></div>'
    
    # ── REVIEWS TAB ──
    page += '<div id="hub-reviews" class="hub-tab space-y-6"><div class="card"><div class="flex items-center justify-between mb-5"><i class="fas fa-star text-yellow-400 text-xl"></i><h2 class="font-bold text-xl text-white">Reviews (' + str(tr) + ')</h2></div><div class="flex items-center gap-4 mb-5 p-4 bg-black/30 rounded-xl"><div class="text-center"><div class="text-3xl font-black text-yellow-400">' + str(round(ar,1)) + '</div><div class="text-yellow-400 text-xs">' + stars + '</div></div><div class="flex-1"><div class="text-xs font-semibold text-white">' + str(tr) + ' verified reviews</div></div></div><div class="space-y-3">' + rh + '</div></div></div>'
    
    # ── NEWSLETTER ──
    page += '<div class="card text-center mt-6" style="border:1px solid rgba(168,85,247,0.2);background:linear-gradient(135deg,rgba(168,85,247,0.05),rgba(236,72,153,0.05))"><div class="text-3xl mb-3">&#x1f4e8;</div><h3 class="font-bold text-lg text-white mb-1">Get Tips & Updates</h3><p class="text-xs text-gray-400 mb-4">Join ' + format(max(dl*3,50),",") + ' subscribers</p><form onsubmit="event.preventDefault();alert(' + Q + "Thanks!" + Q + ')" class="flex gap-2 max-w-sm mx-auto"><input type="email" placeholder="your@email.com" class="flex-1 text-xs py-3 px-4 rounded-xl bg-black/50 border border-white/10 text-white" required><button type="submit" class="btn-primary text-xs py-3 px-5">Subscribe</button></form></div>'
    
    # ── FOOTER ──
    page += '<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6"><div class="card"><h3 class="font-bold text-sm text-white mb-4"><i class="fas fa-fire text-pink-400 mr-2"></i>Trending</h3><div class="space-y-2">' + (trh if trh else '<p class="text-xs text-gray-500">None</p>') + '</div></div><div class="card"><h3 class="font-bold text-sm text-white mb-4"><i class="fas fa-tags text-purple-400 mr-2"></i>Categories</h3><div class="grid grid-cols-2 gap-2"><a href="/?category=prompts" class="p-3 bg-black/30 rounded-xl border border-white/10 hover:border-purple-500/30 transition text-center"><span class="text-xl">🤖</span><br><span class="text-[10px] text-gray-400">Prompts</span></a><a href="/?category=templates" class="p-3 bg-black/30 rounded-xl border border-white/10 hover:border-purple-500/30 transition text-center"><span class="text-xl">📋</span><br><span class="text-[10px] text-gray-400">Templates</span></a><a href="/?category=ebooks" class="p-3 bg-black/30 rounded-xl border border-white/10 hover:border-purple-500/30 transition text-center"><span class="text-xl">📚</span><br><span class="text-[10px] text-gray-400">eBooks</span></a><a href="/?category=code" class="p-3 bg-black/30 rounded-xl border border-white/10 hover:border-purple-500/30 transition text-center"><span class="text-xl">⚙️</span><br><span class="text-[10px] text-gray-400">Code</span></a></div></div></div></div>'
    
    # JS
    page += navigation.footer() + _ps.LAYOUT_FOOT.replace("</body>",
        '<script>function switchHub(t,b){document.querySelectorAll(".hub-tab").forEach(function(e){e.classList.remove("active")});document.getElementById("hub-"+t).classList.add("active");document.querySelectorAll(".tab-btn").forEach(function(e){e.classList.remove("active")});if(b)b.classList.add("active")}</script></body>')
    
    return page
