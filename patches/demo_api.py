# ── AI DEMO GENERATOR ──
@app.route('/api/demo/generate/<product_id>')
@admin_required
def api_generate_demo(product_id):
    """Generate an AI demo script for a product."""
    import json as _json
    db = get_db()
    c = db.cursor()
    c.execute("SELECT title, description, product_type, features, version, requirements FROM products WHERE id=?", (product_id,))
    p = c.fetchone()
    db.close()
    if not p:
        return jsonify({'error': 'Not found'}), 404
    
    title = p['title'] or 'Product'
    desc = p['description'] or 'A premium digital product'
    ptype = PRODUCT_TYPE_LABELS.get(p['product_type'], 'Digital Product')
    features = p['features'] or 'Key features: solve problems, save time'
    
    demo_script = """=== {title} — Quick Demo ===

Product Type: {ptype}

{desc[:200]}

═══ DEMO OVERVIEW ═══

Step 1: Purchase & Download
→ Buy the product with one click
→ Instant download to your device
→ Includes all files and documentation

Step 2: Setup
→ Open the files in your preferred tool
→ Follow the included setup guide
→ No technical skills required
→ Works with ChatGPT, Claude, Gemini, and more

Step 3: Customize
{features[:300] if features else '→ Tailor to your specific needs\n→ Modify prompts/templates for your use case\n→ Integrate with your existing workflow'}

Step 4: Deploy & Profit
→ Launch your solution immediately
→ Save hours of manual work
→ Scale with included commercial license

═══ KEY BENEFITS ═══
✓ Instant access after purchase
✓ Lifetime updates included
✓ Works with all major AI platforms
✓ Commercial license included
✓ 30-day satisfaction guarantee

═══ IDEAL FOR ═══
→ Beginners and experts alike
→ Agencies and freelancers
→ Small business owners
→ Digital creators and marketers

═══ GET STARTED ═══
→ Click Buy Now above
→ Download your files
→ Transform your workflow today"""
    
    return jsonify({'success': False, 'script': demo_script, 'note': 'Demo preview (not a video)'})
