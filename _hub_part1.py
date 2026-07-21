"""Product Experience Hub - complete destination for every product."""
import json as _json, datetime as _dt, random, math

def product_detail_page(product_id):
    """Render a complete Product Experience Hub."""
    db = get_db()
    c = db.cursor()
    row = c.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not row:
        db.close()
        return (LAYOUT_HEAD + TOP_NAV + '<div class="max-w-4xl mx-auto px-4 py-20 text-center"><div class="text-6xl mb-4 opacity-20">&#x1f50d;</div><h1 class="text-2xl font-bold mb-2">Not Found</h1><a href="/" class="btn-primary">Browse Marketplace</a></div>' + LAYOUT_FOOT, 404)
    
    # [CONTINUED IN _hub_part2.py]
