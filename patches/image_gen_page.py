@app.route('/factory/generate-images')
@admin_required
def factory_generate_images():
    """Factory page for generating product images."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, title, product_type, price, screenshot_urls, slug FROM products WHERE status='published' ORDER BY created_at DESC")
    products = [dict(r) for r in c.fetchall()]
    db.close()

    cards = ''
    for p in products:
        has_img = False
        if p.get('screenshot_urls') and str(p['screenshot_urls']) not in ('[]', ''):
            try:
                existing = json.loads(p['screenshot_urls'])
                has_img = bool(existing and existing[0])
            except:
                pass

        icon = product_type_icon(p['product_type'])
        st = '\ud83d\udfe2 Ready' if has_img else '\ud83d\udfe0 Missing'
        slug = p.get('slug', p['id'])
        btn = '' if has_img else '<button onclick="gen(\'' + p['id'] + '\')" class="text-[10px] px-2 py-1 bg-[#a855f7]/10 text-[#a855f7] rounded hover:bg-[#a855f7]/20">Generate</button>'
        cards += '<div class="flex items-center gap-3 p-3 bg-[#1a1a26] rounded-lg border border-[#252533]">'
        cards += '<span class="text-2xl">' + icon + '</span>'
        cards += '<div class="flex-1 min-w-0"><div class="text-xs font-semibold">' + (p['title'] or '')[:50] + '</div>'
        cards += '<div class="text-[10px] text-[#5c5c70]">/' + slug[:40] + '</div></div>'
        cards += '<div class="text-right text-xs">' + st + btn + '</div></div>'

    html = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Product Image Generator</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>*{font-family:Inter,sans-serif}body{background:#07070c;color:#f1f1f5;}.card{background:#11111a;border:1px solid #1e1e2e;border-radius:12px;}</style></head>
<body class="p-4 sm:p-6">'''
    html += LAYOUT_TOP_NAV if 'LAYOUT_TOP_NAV' in dir() else TOP_NAV
    html += '<div class="max-w-4xl mx-auto">'
    html += '<div class="flex items-center justify-between mb-6"><div><h1 class="text-xl font-bold"><i class="fas fa-image text-[#a855f7] mr-2"></i> Product Image Generator</h1><p class="text-sm text-[#5c5c70]">Generate AI hero images for marketplace products</p></div>'
    html += '<button onclick="genAll()" class="btn-primary text-sm px-4 py-2 rounded-lg bg-[#a855f7] text-white hover:bg-[#9333ea]"><i class="fas fa-wand-magic-sparkles mr-1"></i> Generate All Missing</button></div>'
    html += '<div class="card mb-4 p-4"><input id="s" class="text-xs w-full bg-[#1a1a26] border border-[#252533] rounded-lg p-2 text-white" placeholder="Search products..." oninput="filt(this.value)"></div>'
    html += '<div class="space-y-2" id="list">' + cards + '</div></div>'
    html += '''<script>
async function gen(pid){try{const r=await fetch('/api/product/generate-image/'+pid);const d=await r.json();if(d.success)location.reload()}catch(e){}}
async function genAll(){try{const r=await fetch('/api/product/generate-all-images');const d=await r.json();alert('Generated '+d.generated+' images');location.reload()}catch(e){}}
function filt(q){document.querySelectorAll('#list > div').forEach(c=>{c.style.display=c.textContent.toLowerCase().includes(q.toLowerCase())?'':'none'})}
</script>
''' + LAYOUT_FOOT
    return html
