"""Ad Generator for ShopZario — AI-powered ad copy using Venice API"""
import json, os, sqlite3, re, datetime

VENICE_KEY = os.environ.get('VENICE_API_KEY', '')
VENICE_MODEL = 'z-ai-glm-5-turbo'
DB = '/root/voice-agent-businesses.db'

AD_TEMPLATES = {
    "google_search": {
        "name": "Google Search Ads",
        "platform": "Google",
        "headlines": 3,
        "descriptions": 2,
        "icon": "🔍"
    },
    "facebook": {
        "name": "Facebook/Instagram Feed",
        "platform": "Meta",
        "headlines": 2,
        "descriptions": 2,
        "icon": "📘"
    },
    "instagram_story": {
        "name": "Instagram Story",
        "platform": "Meta",
        "headlines": 1,
        "descriptions": 1,
        "icon": "📸"
    },
    "twitter": {
        "name": "X/Twitter Post",
        "platform": "X",
        "headlines": 1,
        "descriptions": 1,
        "icon": "🐦"
    },
    "linkedin": {
        "name": "LinkedIn Ad",
        "platform": "LinkedIn",
        "headlines": 2,
        "descriptions": 2,
        "icon": "💼"
    },
    "email": {
        "name": "Email Marketing",
        "platform": "Email",
        "headlines": 1,
        "descriptions": 1,
        "icon": "📧"
    },
}

def get_product(product_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, title, description, price, product_type, slug FROM products WHERE id=? OR slug=?", (product_id, product_id))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "title": row[1], "description": row[2], "price": row[3], "type": row[4], "slug": row[5]}

def generate_ad_copy(product, ad_type="google_search"):
    """Generate ad copy for a product using Venice AI."""
    template = AD_TEMPLATES.get(ad_type, AD_TEMPLATES["google_search"])
    
    prompt = f"""Generate {template['name']} ad copy.

Product: {product['title']}
Price: ${product['price']}
Category: {product['type']}

Return ONLY a JSON object:
{{"headlines": ["h1", "h2"], "descriptions": ["d1", "d2"]}}
Headlines: {template['headlines']}x, max 30 chars each
Descriptions: {template['descriptions']}x, max 90 chars each
Match {template['platform']} ad best practices. Highlight benefits."""
    
    try:
        import requests, json, re
        r = requests.post("https://api.venice.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {VENICE_KEY}", "Content-Type": "application/json"},
            json={"model": VENICE_MODEL, "messages": [
                {"role": "system", "content": "Return ONLY valid JSON object. No markdown, no code blocks."},
                {"role": "user", "content": prompt}
            ], "max_tokens": 500, "temperature": 0.7},
            timeout=45)
        
        if r.status_code == 200:
            text = r.json()['choices'][0]['message']['content'].strip()
            # Remove markdown code blocks if present
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            # Extract JSON object
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                data = json.loads(json_match.group(0))
                # Normalize format
                return {
                    "headlines": data.get("headlines", data.get("headline", [])),
                    "descriptions": data.get("descriptions", data.get("description", data.get("descs", [])))
                }
    except Exception as e:
        return {"error": str(e), "headlines": [], "descriptions": []}
    return {"headlines": [], "descriptions": []}

def generate_all_ads(product_id):
    """Generate ads for all platforms."""
    product = get_product(product_id)
    if not product:
        return {"error": "Product not found"}
    
    results = {}
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        fut = {ad_type: executor.submit(generate_ad_copy, product, ad_type) for ad_type in AD_TEMPLATES}
        for ad_type, f in fut.items():
            try:
                result = f.result(timeout=30)
                if result and result.get("headlines") and len(result["headlines"]) > 0:
                    results[ad_type] = result
                else:
                    results[ad_type] = {"headlines": [], "descriptions": [], "error": result.get("error", "empty") if result else "failed"}
            except Exception as e:
                results[ad_type] = {"headlines": [], "descriptions": [], "error": str(e)}
    
    return {"product": product, "ads": results}

def ads_manager_html(products, ads_data=None):
    """Admin page HTML for ad management."""
    # Product selector dropdown
    prod_options = "".join([f'<option value="{p[0]}">{p[1][:50]}</option>' for p in products])
    
    ad_results = ""
    if ads_data:
        prod = ads_data.get("product", {})
        ad_results = f'<div class="card p-5 mb-6"><h2 class="font-bold text-lg mb-1">Ads for: {prod.get("title","")}</h2><p class="text-xs text-gray-500 mb-4">${prod.get("price",0)} | {prod.get("type","")}</p><div class="grid gap-4">'
        for ad_type, ad in ads_data.get("ads", {}).items():
            template = AD_TEMPLATES.get(ad_type, {})
            headlines = ad.get("headlines", [])
            descs = ad.get("descriptions", [])
            if headlines or descs:
                ad_results += f'<div class="border border-white/10 rounded-xl p-4"><h3 class="font-semibold text-sm mb-2">{template.get("icon","")} {template.get("name",ad_type)}</h3>'
                if headlines:
                    ad_results += '<div class="space-y-1 mb-2">'
                    for h in headlines:
                        ad_results += f'<div class="flex items-center gap-2"><span class="text-[10px] text-purple-400 font-mono bg-purple-400/10 px-1.5 py-0.5 rounded">H</span><span class="text-xs">{h}</span></div>'
                    ad_results += '</div>'
                if descs:
                    ad_results += '<div class="space-y-1">'
                    for d in descs:
                        ad_results += f'<div class="flex items-center gap-2"><span class="text-[10px] text-green-400 font-mono bg-green-400/10 px-1.5 py-0.5 rounded">D</span><span class="text-xs text-gray-400">{d}</span></div>'
                    ad_results += '</div>'
                ad_results += '</div>'
        ad_results += '</div></div>'
    
    return f'''<div class="max-w-4xl mx-auto px-4 py-8">
    <div class="card mb-6"><h1 class="text-xl font-black mb-1">📢 Ad Generator</h1><p class="text-xs text-gray-500">Generate AI-powered ad copy for any product</p></div>
    
    <div class="card p-5 mb-6">
        <form method="GET" class="flex items-end gap-3">
            <div class="flex-1">
                <label class="text-[10px] text-gray-500 uppercase font-semibold mb-1 block">Select Product</label>
                <select name="product_id" class="w-full h-10 rounded-xl bg-white/5 border border-white/10 text-sm px-3 text-white">
                    {prod_options}
                </select>
            </div>
            <button type="submit" class="btn-primary text-xs" style="padding:10px 24px"><i class="fas fa-wand-magic-sparkles mr-1"></i> Generate Ads</button>
        </form>
    </div>
    
    {ad_results}
    
    <div class="card p-5">
        <h3 class="font-semibold text-sm mb-3">Supported Ad Formats</h3>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {"".join([f'<div class="border border-white/10 rounded-xl p-3 text-center"><div class="text-xl mb-1">{t["icon"]}</div><div class="text-xs font-semibold">{t["name"]}</div><div class="text-[10px] text-gray-500">{t["platform"]}</div></div>' for t in AD_TEMPLATES.values()])}
        </div>
    </div>
    
    <script>
    document.querySelector('select[name="product_id"]').addEventListener('change', function() {{
        if(this.value) this.form.submit();
    }});
    </script>
</div>'''
