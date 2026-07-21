#!/usr/bin/env python3
"""Generate professional product content PDF sheets for all Shopzario products."""

import sqlite3
import os
import re
from weasyprint import HTML
from pathlib import Path

DB_PATH = "/root/voice-agent-businesses.db"
OUTPUT_DIR = "/root/voice-agent-manager/static/product_pdfs"
IMAGE_DIR = "/root/voice-agent-manager/static/product_images"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_product_image_base64(product_id):
    """Read product image and return as base64 data URL."""
    img_path = os.path.join(IMAGE_DIR, f"product_{product_id}.png")
    if os.path.exists(img_path):
        import base64
        with open(img_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return data
    return None

def format_features_from_content(content):
    """Extract features/sections from the content field."""
    if not content:
        return []
    
    features = []
    lines = content.split('\n')
    current_section = None
    section_items = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if this is a section heading (## or **bold** headers)
        if line.startswith('## '):
            if current_section and section_items:
                features.append({"title": current_section, "items": section_items[:10]})
            current_section = line.lstrip('#').strip().strip('*')
            section_items = []
        elif line.startswith('**') and line.endswith('**'):
            if current_section and section_items:
                features.append({"title": current_section, "items": section_items[:10]})
            current_section = line.strip('*').strip()
            section_items = []
        elif re.match(r'^\d+[\.\)]', line):
            # Numbered item
            clean = re.sub(r'^\d+[\.\)]\s*', '', line)
            # Remove markdown links
            clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)
            if len(clean) > 10:  # meaningful items only
                section_items.append(clean)
        elif line.startswith('- ') or line.startswith('* '):
            clean = line[2:]
            clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)
            if len(clean) > 10:
                section_items.append(clean)
        elif len(line) > 20 and not line.startswith('#'):
            # Plain text that's substantial - could be a feature
            clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
            clean = re.sub(r'\*\*(.+?)\*\*', r'\1', clean)
            section_items.append(clean)
    
    if current_section and section_items:
        features.append({"title": current_section, "items": section_items[:10]})
    
    return features[:8]  # Limit to 8 sections max

def get_whats_included(product_type):
    """Infer 'what's included' from product type."""
    whats = {
        "template": [
            "Editable Canva/Notion/Google Sheets template",
            "Professional design with brand colors",
            "Pre-filled example data",
            "Setup instructions & usage guide",
            "Instant digital download"
        ],
        "prompt_pack": [
            "Curated, ready-to-use prompt collection",
            "PDF + text file formats",
            "Copy-paste ready prompts",
            "Bonus tips & best practices",
            "Instant digital download"
        ],
        "checklist": [
            "Comprehensive printable checklist",
            "Actionable step-by-step format",
            "Priority matrix & tracking tools",
            "Pro tips for each phase",
            "Instant digital download"
        ],
        "marketing_tool": [
            "Ready-made content calendar",
            "Strategy templates & frameworks",
            "Performance tracking sheets",
            "Proven hooks & swipe files",
            "Instant digital download"
        ],
        "marketing": [
            "Strategic content calendar",
            "Viral hook swipe file",
            "Hashtag research sheets",
            "Performance tracker template",
            "Instant digital download"
        ],
        "code": [
            "Complete source code files",
            "Fully commented & documented",
            "Requirements file included",
            "Setup & installation guide",
            "Instant digital download"
        ],
        "business_doc": [
            "Fill-in-the-blank templates",
            "Multiple format options",
            "Supporting clauses & addendums",
            "Usage guide & best practices",
            "Instant digital download"
        ],
        "ebook": [
            "Full-length digital book (PDF)",
            "Actionable templates & scripts",
            "Step-by-step framework",
            "Real-world examples",
            "Instant digital download"
        ],
        "starter": [
            "Pre-built automation workflows",
            "Ready-to-deploy configurations",
            "Setup guides & API templates",
            "Environment configuration files",
            "Instant digital download"
        ]
    }
    return whats.get(product_type, [
        "Professional digital product",
        "Instant digital download",
        "Detailed documentation",
        "Lifetime access & updates",
        "Personal & commercial use"
    ])

def get_specifications(product_type):
    """Get specifications based on product type."""
    specs = {
        "template": {
            "Format": "Digital Template (Editable)",
            "Difficulty": "Beginner-Friendly",
            "Compatibility": "Works with Free & Pro versions",
            "Delivery": "Instant Digital Download"
        },
        "prompt_pack": {
            "Format": "PDF / TXT",
            "Difficulty": "All Levels",
            "Compatibility": "Works with ChatGPT, Claude, Gemini & more",
            "Delivery": "Instant Digital Download"
        },
        "checklist": {
            "Format": "PDF (Printable & Digital)",
            "Difficulty": "All Levels",
            "Compatibility": "Any PDF reader or note-taking app",
            "Delivery": "Instant Digital Download"
        },
        "marketing_tool": {
            "Format": "Digital Planner / Templates",
            "Difficulty": "Beginner-Friendly",
            "Compatibility": "Canva, Google Apps, or PDF reader",
            "Delivery": "Instant Digital Download"
        },
        "marketing": {
            "Format": "Digital Planner (PDF)",
            "Difficulty": "All Levels",
            "Compatibility": "Any PDF reader or note-taking app",
            "Delivery": "Instant Digital Download"
        },
        "code": {
            "Format": "Source Code Files",
            "Difficulty": "Intermediate",
            "Compatibility": "Python 3.6+ / Node.js / Browser",
            "Delivery": "Instant Digital Download"
        },
        "business_doc": {
            "Format": "DOCX / PDF / TXT",
            "Difficulty": "Beginner-Friendly",
            "Compatibility": "Microsoft Word, Google Docs, or any text editor",
            "Delivery": "Instant Digital Download"
        },
        "ebook": {
            "Format": "PDF (Digital Book)",
            "Difficulty": "All Levels",
            "Compatibility": "Any PDF reader",
            "Delivery": "Instant Digital Download"
        },
        "starter": {
            "Format": "Workflow JSON / Config Files",
            "Difficulty": "Intermediate",
            "Compatibility": "n8n, Docker, or compatible platform",
            "Delivery": "Instant Digital Download"
        }
    }
    return specs.get(product_type, {
        "Format": "Digital Download",
        "Difficulty": "All Levels",
        "Compatibility": "Various platforms",
        "Delivery": "Instant Digital Download"
    })

def make_html(product):
    """Generate beautiful HTML page for product."""
    product_id = product[0]
    title = product[1] or "Untitled Product"
    description = product[2] or ""
    content = product[3] or ""
    product_type = product[4] or "digital"
    version = product[5] or "1.0.0"
    license_type = product[6] or "Standard"
    requirements = product[7] or ""
    price = product[8] or 0
    rating = product[9] or 0
    downloads = product[10] or 0
    hero_image_url = product[11] or ""
    
    # Get product image
    img_b64 = get_product_image_base64(product_id)
    
    features = format_features_from_content(content)
    whats_included = get_whats_included(product_type)
    specs = get_specifications(product_type)
    
    # Product type badge
    type_labels = {
        "template": "Template",
        "prompt_pack": "Prompt Pack",
        "checklist": "Checklist",
        "marketing_tool": "Marketing Tool",
        "marketing": "Marketing Pack",
        "code": "Code Library",
        "business_doc": "Business Document",
        "ebook": "eBook",
        "starter": "Starter Kit"
    }
    type_badge = type_labels.get(product_type, "Digital Product")
    
    # Build stars HTML
    stars_html = ""
    if rating > 0:
        full = int(rating)
        half = 1 if rating - full >= 0.5 else 0
        stars_html = "".join(['★' for _ in range(full)]) + ("½" if half else "") + "".join(['☆' for _ in range(5 - full - half)])
    
    # Image header
    header_style = ""
    header_overlay = ""
    if img_b64:
        header_style = f"background-image: url('data:image/png;base64,{img_b64}'); background-size: cover; background-position: center;"
        header_overlay = '<div class="header-overlay"></div>'
    
    # Features HTML
    features_html = ""
    for feat in features:
        items_html = "".join([f'<li>{item}</li>' for item in feat.get("items", [])])
        features_html += f'''
        <div class="feature-card">
            <h3 class="feature-title">{feat["title"]}</h3>
            <ul class="feature-list">{items_html}</ul>
        </div>'''
    
    if not features_html:
        # Fallback: show content in chunks
        content_paras = [p.strip() for p in content.split('\n') if p.strip() and len(p.strip()) > 20]
        content_chunks = content_paras[:20]
        for chunk in content_chunks:
            clean = re.sub(r'\*\*(.+?)\*\*', r'\1', chunk)
            clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)
            features_html += f'<p class="content-text">{clean}</p>'
    
    # What's included HTML
    included_html = "".join([f'<li class="included-item">✓ {item}</li>' for item in whats_included])
    
    # Specs HTML
    specs_html = "".join([f'<tr><td class="spec-label">{k}</td><td class="spec-value">{v}</td></tr>' for k, v in specs.items()])
    
    # Requirements
    req_text = requirements if requirements else "No special requirements. Instant digital download."
    
    # Price display
    price_display = f"${price:.2f}" if price > 0 else "Free"
    
    # Versions / Tags
    version_display = version if version else "1.0.0"
    
    # License
    license_display = license_type if license_type else "Standard License"
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
@page {{
    size: A4;
    margin: 0;
}}
@page {{
    @bottom-center {{
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9px;
        color: #6b7280;
        font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
    }}
}}
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}
body {{
    font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
    background: #0f0f13;
    color: #e2e8f0;
    line-height: 1.6;
}}

/* Header / Hero Section */
.hero {{
    position: relative;
    padding: 80px 60px 60px;
    {header_style}
    overflow: hidden;
}}
.hero .header-overlay {{
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: linear-gradient(135deg, rgba(15,15,19,0.92) 0%, rgba(15,15,19,0.75) 50%, rgba(15,15,19,0.6) 100%);
    z-index: 1;
}}
.hero-content {{
    position: relative;
    z-index: 2;
    max-width: 700px;
}}
.product-badge {{
    display: inline-block;
    background: linear-gradient(135deg, #a855f7, #7c3aed);
    color: white;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    padding: 5px 14px;
    border-radius: 20px;
    margin-bottom: 16px;
}}
.product-title {{
    font-size: 32px;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.2;
    margin-bottom: 8px;
}}
.product-version {{
    font-size: 14px;
    color: #a855f7;
    font-weight: 500;
    margin-bottom: 16px;
}}
.product-description {{
    font-size: 15px;
    color: #94a3b8;
    line-height: 1.7;
    max-width: 600px;
}}
.hero-meta {{
    margin-top: 24px;
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
}}
.meta-item {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #94a3b8;
}}
.meta-item .label {{
    color: #6b7280;
}}
.meta-item .value {{
    color: #a855f7;
    font-weight: 600;
}}

/* Price ribbon */
.price-ribbon {{
    position: absolute;
    top: 40px;
    right: 40px;
    z-index: 3;
    background: linear-gradient(135deg, #a855f7, #7c3aed);
    color: white;
    font-size: 28px;
    font-weight: 800;
    padding: 14px 24px;
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(168,85,247,0.3);
}}
.price-ribbon .label {{
    display: block;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    opacity: 0.8;
}}

/* Content container */
.container {{
    padding: 40px 60px 60px;
}}

/* Section titles */
.section-title {{
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 2px solid rgba(168,85,247,0.3);
    display: flex;
    align-items: center;
    gap: 10px;
}}
.section-title .icon {{
    color: #a855f7;
    font-size: 22px;
}}

/* Features grid */
.features-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 40px;
}}
.feature-card {{
    background: linear-gradient(135deg, rgba(31, 31, 41, 0.9), rgba(24, 24, 36, 0.9));
    border: 1px solid rgba(168,85,247,0.15);
    border-radius: 12px;
    padding: 18px 20px;
    page-break-inside: avoid;
}}
.feature-title {{
    font-size: 14px;
    font-weight: 700;
    color: #a855f7;
    margin-bottom: 10px;
}}
.feature-list {{
    list-style: none;
    padding: 0;
}}
.feature-list li {{
    font-size: 12px;
    color: #94a3b8;
    padding: 3px 0;
    padding-left: 12px;
    position: relative;
}}
.feature-list li::before {{
    content: "›";
    position: absolute;
    left: 0;
    color: #a855f7;
    font-weight: 700;
}}

.content-text {{
    font-size: 13px;
    color: #94a3b8;
    margin-bottom: 8px;
    line-height: 1.6;
}}

/* Two column layout */
.two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 40px;
}}
.info-card {{
    background: linear-gradient(135deg, rgba(31, 31, 41, 0.9), rgba(24, 24, 36, 0.9));
    border: 1px solid rgba(168,85,247,0.15);
    border-radius: 12px;
    padding: 20px;
    page-break-inside: avoid;
}}
.card-title {{
    font-size: 15px;
    font-weight: 700;
    color: #a855f7;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}}

/* Included list */
.included-list {{
    list-style: none;
    padding: 0;
}}
.included-item {{
    font-size: 13px;
    color: #94a3b8;
    padding: 4px 0;
}}

/* Specs table */
.specs-table {{
    width: 100%;
    border-collapse: collapse;
}}
.specs-table tr {{
    border-bottom: 1px solid rgba(168,85,247,0.1);
}}
.specs-table tr:last-child {{
    border-bottom: none;
}}
.spec-label {{
    font-size: 12px;
    color: #6b7280;
    padding: 6px 10px 6px 0;
    width: 40%;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.spec-value {{
    font-size: 13px;
    color: #e2e8f0;
    padding: 6px 0;
}}

/* Requirements box */
.requirements-box {{
    background: linear-gradient(135deg, rgba(31, 31, 41, 0.9), rgba(24, 24, 36, 0.9));
    border: 1px solid rgba(168,85,247,0.15);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 40px;
    page-break-inside: avoid;
}}
.requirements-box p {{
    font-size: 13px;
    color: #94a3b8;
    line-height: 1.7;
}}

/* Rating and downloads row */
.stats-row {{
    display: flex;
    gap: 30px;
    margin-bottom: 40px;
    padding: 16px 20px;
    background: linear-gradient(135deg, rgba(31, 31, 41, 0.9), rgba(24, 24, 36, 0.9));
    border: 1px solid rgba(168,85,247,0.15);
    border-radius: 12px;
}}
.stat-item {{
    display: flex;
    flex-direction: column;
}}
.stat-label {{
    font-size: 11px;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}}
.stat-value {{
    font-size: 16px;
    font-weight: 700;
    color: #e2e8f0;
    margin-top: 2px;
}}
.stat-value .stars {{
    color: #f59e0b;
}}

/* Full-width license bar */
.license-bar {{
    background: linear-gradient(135deg, rgba(168,85,247,0.1), rgba(124,58,237,0.05));
    border: 1px solid rgba(168,85,247,0.2);
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
    page-break-inside: avoid;
}}
.license-bar .lic-icon {{
    color: #a855f7;
    font-size: 18px;
    margin-right: 8px;
}}
.license-bar .lic-text {{
    font-size: 13px;
    color: #94a3b8;
}}
.license-bar .lic-name {{
    font-weight: 700;
    color: #a855f7;
}}

/* Footer */
.footer {{
    text-align: center;
    padding: 20px 60px 30px;
    font-size: 11px;
    color: #4b5563;
    border-top: 1px solid rgba(168,85,247,0.1);
    margin-top: 20px;
}}
.footer .brand {{
    color: #a855f7;
    font-weight: 600;
}}

/* Page break helpers */
.page-break {{
    page-break-before: always;
}}

@media print {{
    body {{
        background: #0f0f13;
    }}
    .feature-card, .info-card, .requirements-box, .stats-row, .license-bar {{
        break-inside: avoid;
    }}
}}
</style>
</head>
<body>
<div class="hero">
    {header_overlay}
    <div class="hero-content">
        <span class="product-badge">{type_badge}</span>
        <h1 class="product-title">{title}</h1>
        <div class="product-version">v{version_display}</div>
        <p class="product-description">{description}</p>
        <div class="hero-meta">
            <div class="meta-item">
                <span class="label">Type:</span>
                <span class="value">{type_badge}</span>
            </div>
            <div class="meta-item">
                <span class="label">Version:</span>
                <span class="value">{version_display}</span>
            </div>
            <div class="meta-item">
                <span class="label">Downloads:</span>
                <span class="value">{downloads:,}</span>
            </div>
        </div>
    </div>
    <div class="price-ribbon">
        <span class="label">Price</span>
        {price_display}
    </div>
</div>

<div class="container">
    <!-- Stats row -->
    <div class="stats-row">
        <div class="stat-item">
            <span class="stat-label">Price</span>
            <span class="stat-value">{price_display}</span>
        </div>
        <div class="stat-item">
            <span class="stat-label">Version</span>
            <span class="stat-value">{version_display}</span>
        </div>
        <div class="stat-item">
            <span class="stat-label">Downloads</span>
            <span class="stat-value">{downloads:,}</span>
        </div>
        <div class="stat-item">
            <span class="stat-label">Rating</span>
            <span class="stat-value"><span class="stars">{stars_html}</span>{' ' if stars_html else ''}{f'({rating})' if rating else '—'}</span>
        </div>
    </div>
    
    <!-- Features -->
    <h2 class="section-title"><span class="icon">✦</span> Key Features</h2>
    <div class="features-grid">
        {features_html}
    </div>
    
    <!-- Two column: What's Included + Specs -->
    <div class="two-col">
        <div class="info-card">
            <h3 class="card-title">📦 What's Included</h3>
            <ul class="included-list">
                {included_html}
            </ul>
        </div>
        <div class="info-card">
            <h3 class="card-title">⚙️ Specifications</h3>
            <table class="specs-table">
                {specs_html}
            </table>
        </div>
    </div>
    
    <!-- Requirements -->
    <h2 class="section-title"><span class="icon">📋</span> Requirements</h2>
    <div class="requirements-box">
        <p>{req_text}</p>
    </div>
    
    <!-- License -->
    <div class="license-bar">
        <span class="lic-icon">©</span>
        <span class="lic-text">Licensed under <span class="lic-name">{license_display}</span> — Personal & Commercial use permitted as per license terms.</span>
    </div>
</div>

<div class="footer">
    Generated by <span class="brand">Shopzario</span> — Premium Digital Products for Modern Creators &amp; Professionals
</div>
</body>
</html>'''
    return html


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, description, content, product_type, version, 
               COALESCE(license, 'Standard'), COALESCE(requirements, ''),
               COALESCE(price, 0), COALESCE(rating, 0), COALESCE(downloads_count, 0), 
               COALESCE(hero_image_url, '')
        FROM products
        ORDER BY id
    """)
    products = cursor.fetchall()
    conn.close()
    
    total = len(products)
    print(f"Found {total} products to generate PDFs for.")
    
    for i, product in enumerate(products, 1):
        product_id = product[0]
        title = product[1]
        output_path = os.path.join(OUTPUT_DIR, f"{product_id}.pdf")
        
        print(f"[{i}/{total}] Generating PDF for: {title} ({product_id})")
        
        html_content = make_html(product)
        
        try:
            HTML(string=html_content).write_pdf(output_path)
            size_kb = os.path.getsize(output_path) / 1024
            print(f"  ✓ Saved to {output_path} ({size_kb:.1f} KB)")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print(f"\nDone! Generated {total} PDFs in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
