"""OpenAI Ads Campaign Manager for ShopZario"""
import json, os, requests, time, datetime

API_BASE = "https://api.ads.openai.com/v1"
API_KEY = os.environ.get("OPENAI_ADS_API_KEY", "")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# ── CAMPAIGNS ──

def list_campaigns():
    """List all campaigns."""
    r = requests.get(f"{API_BASE}/campaigns", headers=HEADERS)
    if r.status_code == 200:
        return r.json().get("data", [])
    return {"error": r.text[:300]}

def get_campaign(campaign_id):
    """Get one campaign by ID."""
    r = requests.get(f"{API_BASE}/campaigns/{campaign_id}", headers=HEADERS)
    if r.status_code == 200:
        return r.json()
    return {"error": r.text[:300]}

def create_campaign(name, description, budget_micros=50000000, billing="clicks", days=30):
    """Create a campaign (paused by default)."""
    now = int(time.time())
    data = {
        "name": name[:255],
        "description": description[:500],
        "start_time": now,
        "end_time": now + days * 86400,
        "status": "paused",
        "budget": {"lifetime_spend_limit_micros": budget_micros},
        "bidding_type": billing,
        "targeting": {}
    }
    r = requests.post(f"{API_BASE}/campaigns", headers=HEADERS, json=data)
    if r.status_code == 200:
        return r.json()
    return {"error": r.text[:500]}

def update_campaign(campaign_id, updates):
    """Update campaign fields."""
    r = requests.post(f"{API_BASE}/campaigns/{campaign_id}", headers=HEADERS, json=updates)
    if r.status_code == 200:
        return r.json()
    return {"error": r.text[:500]}

def activate_campaign(campaign_id):
    return update_campaign(campaign_id, {"status": "active"})

def pause_campaign(campaign_id):
    return update_campaign(campaign_id, {"status": "paused"})

# ── AD GROUPS ──

def list_ad_groups(campaign_id=None):
    params = {}
    if campaign_id:
        params["campaign_id"] = campaign_id
    r = requests.get(f"{API_BASE}/ad_groups", headers=HEADERS, params=params)
    if r.status_code == 200:
        return r.json().get("data", [])
    return {"error": r.text[:300]}

def create_ad_group(campaign_id, name, context_hints=None, max_bid_micros=50000, billing_event="impression"):
    """Create an ad group inside a campaign."""
    data = {
        "campaign_id": campaign_id,
        "name": name[:255],
        "status": "paused",
        "context_hints": context_hints or ["digital products", "ai tools"],
        "bidding_config": {
            "billing_event_type": billing_event,
            "max_bid_micros": max_bid_micros
        }
    }
    r = requests.post(f"{API_BASE}/ad_groups", headers=HEADERS, json=data)
    if r.status_code == 200:
        return r.json()
    return {"error": r.text[:500]}

def activate_ad_group(ad_group_id):
    r = requests.post(f"{API_BASE}/ad_groups/{ad_group_id}", headers=HEADERS, json={"status": "active"})
    return r.json() if r.status_code == 200 else {"error": r.text[:300]}

# ── ADS (Creatives) ──

def list_ads(ad_group_id=None):
    params = {}
    if ad_group_id:
        params["ad_group_id"] = ad_group_id
    r = requests.get(f"{API_BASE}/ads", headers=HEADERS, params=params)
    if r.status_code == 200:
        return r.json().get("data", [])
    return {"error": r.text[:300]}

def create_ad(ad_group_id, name, headline, description, product_url):
    """Create an ad with text creative."""
    data = {
        "ad_group_id": ad_group_id,
        "name": name[:255],
        "status": "paused",
        "creative": {
            "type": "text",
            "text": {
                "headline": headline[:60],
                "description": description[:120],
                "call_to_action": "Learn More",
                "display_url": product_url[:200],
                "destination_url": f"https://shopzario.com{product_url}"
            }
        }
    }
    r = requests.post(f"{API_BASE}/ads", headers=HEADERS, json=data)
    if r.status_code == 200:
        return r.json()
    return {"error": r.text[:500]}

# ── INSIGHTS ──

def get_insights(campaign_id, since=None, until=None):
    """Get campaign performance data."""
    params = {
        "time_granularity": "daily",
        "fields[]": ["readable_time", "clicks", "impressions", "spend", "ctr", "cpc", "cpm"]
    }
    since = since or (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    until = until or datetime.date.today().isoformat()
    params["time_ranges[]"] = json.dumps([{"type": "date_range", "since": since, "until": until}])
    
    r = requests.get(f"{API_BASE}/campaigns/{campaign_id}/insights", headers=HEADERS, params=params)
    if r.status_code == 200:
        return r.json().get("data", [])
    return {"error": r.text[:300]}

# ── HIGH-LEVEL: Create full campaign from product ──

def create_campaign_from_product(product, budget_dollars=50, days=30):
    """Create a complete campaign (campaign + ad group + ad) from a product."""
    slug = product.get("slug") or product.get("id", "")
    product_url = f"/product/{slug}"
    
    # Step 1: Create campaign
    campaign = create_campaign(
        name=f"ShopZario - {product['title'][:40]}",
        description=f"Promote {product['title']} on ChatGPT | ${product.get('price',0)}",
        budget_micros=budget_dollars * 1000000,
        days=days
    )
    if "error" in campaign:
        return {"error": campaign["error"], "step": "campaign"}
    
    campaign_id = campaign["id"]
    
    # Step 2: Create ad group
    context_hints = [product.get("type", "digital"), "shopzario marketplace", product["title"][:30]]
    billing = campaign.get("bidding_type", "clicks")
    billing_event = "click" if billing == "clicks" else "impression"
    ad_group = create_ad_group(
        campaign_id=campaign_id,
        name=f"{product['title'][:30]} - English",
        context_hints=context_hints,
        billing_event=billing_event
    )
    if "error" in ad_group:
        return {"campaign": campaign, "error": ad_group["error"], "step": "ad_group"}
    
    ad_group_id = ad_group["id"]
    
    # Step 3: Create AI-generated ad copy
    from ads_generator import generate_ad_copy
    
    # Generate for Google format (best for ChatGPT ads)
    copy = generate_ad_copy(product, "google_search")
    
    ads_created = []
    if copy and copy.get("headlines"):
        headlines = copy["headlines"]
        descriptions = copy.get("descriptions", [])
        
        for i, (hl, desc) in enumerate(zip(headlines, descriptions or [""] * len(headlines))):
            ad = create_ad(
                ad_group_id=ad_group_id,
                name=f"{product['title'][:30]} - Ad {i+1}",
                headline=hl,
                description=desc or hl,
                product_url=product_url
            )
            if "error" not in ad:
                ads_created.append(ad["id"])
    
    # Fallback: create generic ad if AI failed
    if not ads_created:
        ad = create_ad(
            ad_group_id=ad_group_id,
            name=f"{product['title'][:30]}",
            headline=product["title"][:60],
            description=f"Get {product['title'][:50]} - Only ${product.get('price',0)}",
            product_url=product_url
        )
        if "error" not in ad:
            ads_created.append(ad["id"])
    
    return {
        "campaign": campaign,
        "ad_group": ad_group,
        "ads_created": len(ads_created),
        "ad_ids": ads_created,
        "product_url": product_url
    }

# ── CAMPAIGNS DASHBOARD HTML ──

def campaigns_dashboard_html():
    """Admin dashboard for campaign management."""
    campaigns = list_campaigns()
    if isinstance(campaigns, dict) and "error" in campaigns:
        return f'<div class="card p-5 text-red-400 text-sm">{campaigns["error"]}</div>'
    
    rows = ""
    for c in campaigns:
        cid = c.get("id", "")
        name = c.get("name", "Unnamed")
        status = c.get("status", "unknown")
        budget = c.get("budget", {})
        lifetime = budget.get("lifetime_spend_limit_micros", 0) / 1_000_000
        daily = budget.get("daily_spend_limit_micros", 0) / 1_000_000
        bidding = c.get("bidding_type", "?")
        created = datetime.datetime.fromtimestamp(c.get("created_at", 0)).strftime("%b %d")
        
        status_color = {"active": "#4ade80", "paused": "#facc15", "archived": "#6b7280"}.get(status, "#6b7280")
        status_dot = f'<span class="inline-block w-2 h-2 rounded-full" style="background:{status_color}"></span>'
        
        rows += f'''<tr class="border-b border-white/5 hover:bg-white/[0.02]">
            <td class="py-3 px-3 text-xs font-medium">{name[:60]}</td>
            <td class="py-3 px-3 text-xs">{status_dot} {status.title()}</td>
            <td class="py-3 px-3 text-xs text-gray-400">${lifetime:.0f}</td>
            <td class="py-3 px-3 text-xs text-gray-400">${daily:.0f}</td>
            <td class="py-3 px-3 text-xs text-gray-400">{bidding}</td>
            <td class="py-3 px-3 text-xs text-gray-500">{created}</td>
            <td class="py-3 px-3 text-xs">
                <a href="/factory/campaigns/{cid}" class="text-purple-400 hover:text-purple-300">View</a>
                <button onclick="toggleCampaign('{cid}')" class="ml-2 text-xs {"text-yellow-400" if status=="active" else "text-green-400"} hover:underline">{("Pause" if status=="active" else "Activate")}</button>
            </td>
        </tr>'''
    
    return f'''<div class="max-w-6xl mx-auto px-4 py-8">
    <div class="flex items-center justify-between mb-6">
        <div>
            <h1 class="text-xl font-black mb-1">📢 ChatGPT Ad Campaigns</h1>
            <p class="text-xs text-gray-500">Manage your OpenAI Ads campaigns — created automatically from products</p>
        </div>
        <div class="flex gap-2">
            <a href="/factory/ads" class="btn-outline text-xs" style="padding:8px 16px"><i class="fas fa-wand-magic-sparkles mr-1"></i> Generate Copy</a>
            <a href="/factory/campaigns/create?all=1" class="btn-primary text-xs" style="padding:8px 16px"><i class="fas fa-plus mr-1"></i> New Campaign</a>
        </div>
    </div>
    
    <div class="card overflow-hidden">
        <table class="w-full">
            <thead><tr class="border-b border-white/10 text-[10px] text-gray-500 uppercase tracking-wider">
                <th class="text-left py-3 px-3 font-semibold">Campaign</th>
                <th class="text-left py-3 px-3 font-semibold">Status</th>
                <th class="text-left py-3 px-3 font-semibold">Budget</th>
                <th class="text-left py-3 px-3 font-semibold">Daily</th>
                <th class="text-left py-3 px-3 font-semibold">Bidding</th>
                <th class="text-left py-3 px-3 font-semibold">Created</th>
                <th class="text-left py-3 px-3 font-semibold">Actions</th>
            </tr></thead>
            <tbody>
                {rows or '<tr><td colspan="7" class="py-8 text-center text-xs text-gray-500">No campaigns yet</td></tr>'}
            </tbody>
        </table>
    </div>
    
    <div class="card p-5 mt-4">
        <h3 class="font-semibold text-sm mb-3">Quick Stats</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="border border-white/10 rounded-xl p-3 text-center">
                <div class="text-2xl font-black text-purple-400">{len(campaigns)}</div>
                <div class="text-[10px] text-gray-500">Total Campaigns</div>
            </div>
            <div class="border border-white/10 rounded-xl p-3 text-center">
                <div class="text-2xl font-black text-green-400">{sum(1 for c in campaigns if c.get("status")=="active")}</div>
                <div class="text-[10px] text-gray-500">Active</div>
            </div>
            <div class="border border-white/10 rounded-xl p-3 text-center">
                <div class="text-2xl font-black text-yellow-400">{sum(1 for c in campaigns if c.get("status")=="paused")}</div>
                <div class="text-[10px] text-gray-500">Paused</div>
            </div>
            <div class="border border-white/10 rounded-xl p-3 text-center">
                <div class="text-2xl font-black text-pink-400">${sum(c.get("budget",{}).get("lifetime_spend_limit_micros",0) for c in campaigns if c.get("budget"))/1_000_000:.0f}</div>
                <div class="text-[10px] text-gray-500">Total Budget</div>
            </div>
        </div>
    </div>
    
    <script>
    function toggleCampaign(id) {{
        fetch('/api/ads/toggle-campaign', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{campaign_id: id}})
        }}).then(r => r.json()).then(d => {{
            if(d.success) location.reload();
        }});
    }}
    </script>
</div>'''

def campaign_detail_html(campaign_id):
    """Single campaign detail page."""
    c = get_campaign(campaign_id)
    if isinstance(c, dict) and "error" in c:
        return f'<div class="card p-5 text-red-400">{c["error"]}</div>'
    
    # Get ad groups
    ad_groups = list_ad_groups(campaign_id)
    if isinstance(ad_groups, dict):
        ad_groups = []
    
    # Get insights
    insights = get_insights(campaign_id)
    if isinstance(insights, dict):
        insights = []
    
    name = c.get("name", "Unnamed")
    status = c.get("status", "unknown")
    budget = c.get("budget", {})
    lifetime = budget.get("lifetime_spend_limit_micros", 0) / 1_000_000
    
    # Build insights table
    insight_rows = ""
    for row in insights[-14:]:
        date = row.get("readable_time", row.get("date", ""))
        clicks = row.get("clicks", 0)
        imps = row.get("impressions", 0)
        spend = row.get("spend", 0)
        ctr = row.get("ctr", 0)
        insight_rows += f'<tr><td class="py-1 px-2 text-xs text-gray-500">{date}</td><td class="py-1 px-2 text-xs">{clicks}</td><td class="py-1 px-2 text-xs">{imps}</td><td class="py-1 px-2 text-xs">${float(spend):.2f}</td><td class="py-1 px-2 text-xs">{float(ctr):.1f}%</td></tr>'
    
    ag_rows = ""
    for ag in ad_groups:
        ag_rows += f'<tr class="border-b border-white/5"><td class="py-2 px-3 text-xs">{ag.get("name","")[:50]}</td><td class="py-2 px-3 text-xs">{ag.get("status","")}</td><td class="py-2 px-3 text-xs text-gray-500">{ag.get("context_hints",[])[:2]}</td></tr>'
    
    return f'''<div class="max-w-4xl mx-auto px-4 py-8">
    <a href="/factory/campaigns" class="text-xs text-purple-400 hover:text-purple-300 mb-4 inline-block">&larr; Back to Campaigns</a>
    
    <div class="card p-5 mb-6">
        <div class="flex items-start justify-between">
            <div>
                <h1 class="text-lg font-bold">{name}</h1>
                <p class="text-xs text-gray-500 mt-1">{c.get("description","")[:150]}</p>
            </div>
            <div class="flex gap-2">
                <button onclick="toggleCampaign('{campaign_id}')" class="btn-{"outline" if status=="active" else "primary"} text-xs" style="padding:8px 16px">{("Pause" if status=="active" else "Activate")}</button>
            </div>
        </div>
        <div class="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-white/10">
            <div><span class="text-[10px] text-gray-500 block">Status</span><span class="text-sm font-semibold">{status.title()}</span></div>
            <div><span class="text-[10px] text-gray-500 block">Budget</span><span class="text-sm font-semibold">${lifetime:.0f}</span></div>
            <div><span class="text-[10px] text-gray-500 block">Bidding</span><span class="text-sm font-semibold">{c.get("bidding_type","")}</span></div>
        </div>
    </div>
    
    <div class="card p-5 mb-6">
        <h3 class="font-semibold text-sm mb-3">Performance</h3>
        <div class="max-h-60 overflow-y-auto">
            <table class="w-full">
                <thead><tr class="text-[10px] text-gray-500 uppercase"><th class="text-left py-1 px-2">Date</th><th class="text-left py-1 px-2">Clicks</th><th class="text-left py-1 px-2">Impressions</th><th class="text-left py-1 px-2">Spend</th><th class="text-left py-1 px-2">CTR</th></tr></thead>
                <tbody>{insight_rows or '<tr><td colspan="5" class="py-4 text-center text-xs text-gray-600">No data yet</td></tr>'}</tbody>
            </table>
        </div>
    </div>
    
    <div class="card p-5">
        <h3 class="font-semibold text-sm mb-3">Ad Groups ({len(ad_groups)})</h3>
        <table class="w-full">
            <thead><tr class="text-[10px] text-gray-500 uppercase"><th class="text-left py-2 px-3">Name</th><th class="text-left py-2 px-3">Status</th><th class="text-left py-2 px-3">Context Hints</th></tr></thead>
            <tbody>{ag_rows or '<tr><td colspan="3" class="py-4 text-center text-xs text-gray-600">No ad groups</td></tr>'}</tbody>
        </table>
    </div>
    
    <script>
    function toggleCampaign(id) {{
        fetch('/api/ads/toggle-campaign', {{
            method: 'POST', headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{campaign_id: id}})
        }}).then(r=>r.json()).then(d=>{{if(d.success) location.reload()}});
    }}
    </script>
</div>'''

def create_campaign_from_products_html(products):
    """Form to create campaign from a product."""
    prod_options = "".join([f'<option value="{p[0]}">{p[1][:60]} - ${p[2]}</option>' for p in products])
    return f'''<div class="max-w-4xl mx-auto px-4 py-8">
    <a href="/factory/campaigns" class="text-xs text-purple-400 hover:text-purple-300 mb-4 inline-block">&larr; Back to Campaigns</a>
    <div class="card p-5">
        <h1 class="text-lg font-bold mb-1">New Campaign</h1>
        <p class="text-xs text-gray-500 mb-6">Create a ChatGPT ad campaign from a product</p>
        
        <form method="POST" class="space-y-4">
            <div>
                <label class="text-xs text-gray-400 font-semibold block mb-1">Select Product</label>
                <select name="product_id" class="w-full h-10 rounded-xl bg-white/5 border border-white/10 text-sm px-3 text-white" required>
                    <option value="">Choose a product...</option>
                    {prod_options}
                </select>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="text-xs text-gray-400 font-semibold block mb-1">Budget ($)</label>
                    <input type="number" name="budget" value="50" min="10" step="1" class="w-full h-10 rounded-xl bg-white/5 border border-white/10 text-sm px-3 text-white">
                </div>
                <div>
                    <label class="text-xs text-gray-400 font-semibold block mb-1">Duration (days)</label>
                    <input type="number" name="days" value="30" min="1" max="365" step="1" class="w-full h-10 rounded-xl bg-white/5 border border-white/10 text-sm px-3 text-white">
                </div>
            </div>
            <button type="submit" class="btn-primary text-sm" style="padding:12px 32px"><i class="fas fa-rocket mr-2"></i> Launch Campaign</button>
        </form>
    </div>
</div>'''

def bulk_create_campaigns(products, budget=50, days=30):
    """Create campaigns for multiple products at once."""
    results = []
    for p in products:
        try:
            result = create_campaign_from_product(
                {"id": p[0], "title": p[1], "price": p[2], "slug": p[3] if len(p) > 3 else p[0], "type": p[4] if len(p) > 4 else "digital"},
                budget_dollars=budget, days=days
            )
            results.append({"product": p[1], "success": "error" not in result, "campaign_id": result.get("campaign", {}).get("id", ""), "error": result.get("error", "")})
        except Exception as e:
            results.append({"product": p[1], "success": False, "error": str(e)})
    return results
