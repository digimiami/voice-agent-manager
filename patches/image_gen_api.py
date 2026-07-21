# ── PRODUCT IMAGE GENERATION ──
@app.route('/api/product/generate-image/<product_id>')
@admin_required
def api_generate_product_image(product_id):
    """Generate AI product image placeholder."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT title, description, product_type, slug FROM products WHERE id=?", (product_id,))
    p = c.fetchone()
    db.close()
    if not p:
        return jsonify({'error': 'Not found'}), 404
    title = p['title'] or 'Product'
    ptype = PRODUCT_TYPE_LABELS.get(p['product_type'], 'Digital Product')
    slug = p.get('slug', product_id)
    img_url = "https://placehold.co/800x600/1a0a2e/a855f7?text=" + slug[:30]
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE products SET screenshot_urls=? WHERE id=?", (json.dumps([img_url]), product_id))
    db.commit()
    db.close()
    return jsonify({'success': True, 'product_id': product_id, 'image_url': img_url})

@app.route('/api/product/generate-all-images')
@admin_required
def api_generate_all_product_images():
    """Generate placeholders for all products without images."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, title, screenshot_urls FROM products WHERE status='published'")
    products = [dict(r) for r in c.fetchall()]
    db.close()
    generated = 0
    for p in products:
        if p.get('screenshot_urls') and str(p['screenshot_urls']) not in ('[]', ''):
            try:
                existing = json.loads(p['screenshot_urls'])
                if existing and existing[0]:
                    continue
            except:
                pass
        slug = p.get('slug', p['id'])
        img_url = "https://placehold.co/800x600/1a0a2e/a855f7?text=" + slug[:30]
        db = get_db()
        c = db.cursor()
        c.execute("UPDATE products SET screenshot_urls=? WHERE id=?", (json.dumps([img_url]), p['id']))
        db.commit()
        db.close()
        generated += 1
    return jsonify({'success': True, 'generated': generated, 'total': len(products)})
