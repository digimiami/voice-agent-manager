"""Landing page HTML generator - industry-aware with SEO, audio, gallery, video support."""
import sys
sys.path.insert(0, '/root/voice-agent-manager')
from landing_page_route import INDUSTRY_DATA, get_industry_data, FALLBACK_FAQ, FALLBACK_TESTIMONIALS, FALLBACK_FEATURES
import os

def generate_landing_html(bid, biz_name, title, tagline, desc, features, hero_img, fc, sc,
                          seo_title, meta_desc, meta_kw, gallery, featured_video,
                          demo_audio, demo_audio_label, icon, hero_badge, trust_1, trust_2,
                          cta_text, cta_sub, display_phone, cal_username='pablo-d-i2xmhr', cal_event_slug='30min'):
    """Generate the full landing page HTML with all dynamic content."""
    feature_icons = ['🔍', '💰', '📋', '🤝', '🛡️', '✅']
    
    # Features
    feat_items = []
    for i, feat in enumerate(features[:6]):
        feat_items.append(f'''      <div class="feature-card" data-aos="fade-up" data-aos-delay="{i*100}">
        <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-[{fc}]30 to-[{sc}]30 flex items-center justify-center text-2xl mb-4">{feature_icons[i % 6]}</div>
        <h3 class="text-lg font-bold mb-2">{feat}</h3>
        <p class="text-sm text-[#7a7a8e]">Professional {feat.lower()} for our valued clients.</p>
      </div>''')
    features_html = '\n'.join(feat_items)
    
    # Gallery
    gallery_html = ''
    if gallery:
        gal_items = []
        for i, img in enumerate(gallery[:6]):
            gal_items.append(f'      <img src="{img}" alt="Gallery {i+1}" class="gallery-img" onerror="this.style.display=`none`">')
        gals = '\n'.join(gal_items)
        gallery_html = f'''<section class="py-16 px-4 bg-[#0a0a12]">
  <div class="max-w-6xl mx-auto">
    <div class="text-center mb-12" data-aos="fade-up">
      <h2 class="section-title">Our <span class="gradient-text">Work</span></h2>
      <p class="section-subtitle mt-3">See the quality and professionalism we bring to every project.</p>
    </div>
    <div class="grid md:grid-cols-3 gap-4">
{gals}
    </div>
  </div>
</section>'''
    
    # Video
    video_html = ''
    if featured_video:
        embed_url = featured_video.replace('watch?v=', 'embed/').split('&')[0]
        video_html = f'''<section class="py-16 px-4">
  <div class="max-w-4xl mx-auto">
    <div class="text-center mb-12" data-aos="fade-up">
      <h2 class="section-title">Watch <span class="gradient-text">Our Service</span></h2>
      <p class="section-subtitle mt-3">See how we help our clients.</p>
    </div>
    <div class="video-container" data-aos="fade-up">
      <iframe src="{embed_url}" title="Featured Video" allowfullscreen></iframe>
    </div>
  </div>
</section>'''
    
    # Audio
    audio_html = ''
    if demo_audio:
        audio_html = f'''<section id="demos" class="py-16 px-4 bg-[#0a0a12]">
  <div class="max-w-4xl mx-auto text-center">
    <h2 class="section-title mb-4">🎧 <span class="gradient-text">{demo_audio_label}</span></h2>
    <p class="text-[#7a7a8e] mb-10 max-w-xl mx-auto">Listen to our AI agent in action.</p>
    <div class="max-w-md mx-auto bg-[rgba(18,18,26,0.5)] border border-[rgba(37,37,51,0.4)] rounded-2xl p-6 hover:border-[{fc}40] transition-all">
      <div class="flex items-center gap-4 mb-4">
        <button class="play-btn" onclick="toggleAudioPlayer(this)"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></button>
        <div class="flex-1 text-left">
          <div class="font-semibold">{demo_audio_label}</div>
          <div class="text-xs text-[#7a7a8e]">AI Voice Agent Demo</div>
        </div>
      </div>
      <div class="flex items-center gap-1 justify-center" id="waveform-demo">
        {"".join(f'<div class="waveform-bar" style="height:{h}px"></div>' for h in [12,18,24,32,38,44,48,44,38,32,24,18,12])}
      </div>
      <div class="flex items-center justify-between mt-2 text-xs text-[#5c5c70]">
        <span id="audio-time">0:00</span>
        <span id="audio-status" class="text-[{fc}]">▶ Click to play</span>
      </div>
      <audio id="demo-player" src="{demo_audio}" preload="none"></audio>
    </div>
  </div>
</section>'''
    
    # About images
    about_imgs = gallery[:4] if len(gallery) >= 2 else [
        'https://images.unsplash.com/photo-1590674899484-d5640f00aec6?w=800&q=80',
        'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=800&q=80',
    ]
    about_items = []
    for i, img in enumerate(about_imgs[:4]):
        cls = 'rounded-2xl w-full h-40 object-cover' + (' mt-8' if i % 2 == 1 else '')
        about_items.append(f'      <img src="{img}" alt="Gallery" class="{cls}" onerror="this.style.display=`none`">')
    about_imgs_html = '\n'.join(about_items)
    
    # Testimonials
    test_items = []
    for i, (t, a) in enumerate(FALLBACK_TESTIMONIALS):
        test_items.append(f'''      <div class="review-card" data-aos="fade-up" data-aos-delay="{i*100}">
        <div class="text-yellow-400 mb-2">★★★★★</div>
        <p class="text-sm text-[#7a7a8e] mb-4 leading-relaxed">"{t}"</p>
        <div class="font-semibold text-sm">{a}</div>
      </div>''')
    testimonials_html = '\n'.join(test_items)
    
    # FAQ
    faq_items = []
    for q, a in FALLBACK_FAQ:
        faq_items.append(f'''      <div class="faq-item" onclick="this.querySelector('.faq-a').classList.toggle('hidden')">
        <div class="flex items-center justify-between">
          <h4 class="font-semibold">{q}</h4>
          <span class="text-[{fc}] text-xl">+</span>
        </div>
        <p class="faq-a hidden text-sm text-[#7a7a8e] mt-3 leading-relaxed">{a}</p>
      </div>''')
    faq_html = '\n'.join(faq_items)
    
    if not hero_img:
        hero_img = 'data:image/svg+xml,%3Csvg%20width%3D%22500%22%20height%3D%22500%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Crect%20width%3D%22500%22%20height%3D%22500%22%20fill%3D%22%23181824%22%2F%3E%3Ctext%20x%3D%22250%22%20y%3D%22250%22%20text-anchor%3D%22middle%22%20fill%3D%22%237a7a8e%22%20font-family%3D%22Inter%22%20font-size%3D%2220%22%3EAI-Powered%20Service%3C%2Ftext%3E%3C%2Fsvg%3E'
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{seo_title}</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{meta_kw}">
<meta property="og:title" content="{seo_title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="website">
<meta property="og:url" content="https://diazites.online/lp/{bid}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{seo_title}">
<meta name="twitter:description" content="{meta_desc}">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"LocalBusiness","name":"{biz_name}","description":"{meta_desc}","telephone":"{display_phone}","url":"https://diazites.online/lp/{bid}"}}</script>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://unpkg.com/aos@2.3.1/dist/aos.js"></script>
<link href="https://unpkg.com/aos@2.3.1/dist/aos.css" rel="stylesheet">
<style>
*{{font-family:'Inter',sans-serif;margin:0;padding:0;box-sizing:border-box}}
body{{background:#08080f;color:#f1f1f5;overflow-x:hidden}}
.gradient-text{{background:linear-gradient(135deg,{fc},{sc});-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
.hero-gradient{{background:radial-gradient(ellipse at 30% 20%,{fc}25 0%,transparent 50%),radial-gradient(ellipse at 70% 80%,{sc}20 0%,transparent 50%),#08080f}}
.glass{{background:rgba(18,18,26,0.7);backdrop-filter:blur(20px);border:1px solid rgba(37,37,51,0.5)}}
.btn-primary{{background:linear-gradient(135deg,{fc},{sc});color:white;padding:16px 40px;border-radius:14px;font-weight:700;font-size:1.125rem;display:inline-block;transition:all .3s;text-decoration:none}}
.btn-primary:hover{{transform:translateY(-3px);box-shadow:0 20px 60px rgba(0,0,0,.3)}}
.section-title{{font-size:2.5rem;font-weight:800;margin-bottom:0.5rem}}
.section-subtitle{{color:#7a7a8e;font-size:1.125rem;max-width:600px;margin:0 auto}}
.feature-card{{background:rgba(18,18,26,0.5);border:1px solid rgba(37,37,51,0.4);border-radius:20px;padding:28px;transition:all .3s}}
.feature-card:hover{{background:rgba(18,18,26,0.8);border-color:{fc}40;transform:translateY(-5px);box-shadow:0 10px 40px rgba(0,0,0,.2)}}
.step-number{{background:linear-gradient(135deg,{fc},{sc});width:48px;height:48px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1.25rem;color:white;flex-shrink:0}}
.floating-phone{{position:fixed;bottom:24px;right:24px;z-index:100;background:linear-gradient(135deg,{fc},{sc});color:white;border-radius:50%;width:60px;height:60px;display:flex;align-items:center;justify-content:center;font-size:1.5rem;box-shadow:0 4px 30px rgba(0,0,0,.4);transition:all .3s;text-decoration:none}}
.floating-phone:hover{{transform:scale(1.1);box-shadow:0 8px 40px {fc}60}}
.hero-image{{border-radius:20px;box-shadow:0 20px 60px rgba(0,0,0,.4);width:100%;height:auto;object-fit:cover}}
.faq-item{{background:rgba(18,18,26,0.5);border:1px solid rgba(37,37,51,0.4);border-radius:16px;padding:20px;cursor:pointer;transition:all .3s}}
.faq-item:hover{{border-color:{fc}30}}
.review-card{{background:rgba(18,18,26,0.5);border:1px solid rgba(37,37,51,0.4);border-radius:16px;padding:24px}}
.play-btn{{width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,{fc},{sc});border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:transform .2s}}
.play-btn:hover{{transform:scale(1.1)}}
.play-btn svg{{width:20px;height:20px;fill:white;margin-left:2px}}
.waveform-bar{{width:3px;border-radius:2px;background:{fc};transition:height .3s}}
.gallery-img{{border-radius:12px;width:100%;height:180px;object-fit:cover;transition:all .3s}}
.gallery-img:hover{{transform:scale(1.02);box-shadow:0 10px 40px rgba(0,0,0,.3)}}
.video-container{{position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:16px}}
.video-container iframe{{position:absolute;top:0;left:0;width:100%;height:100%}}
.hamburger{{display:none;flex-direction:column;cursor:pointer;gap:5px;padding:4px;z-index:60;background:none;border:none}}
.hamburger span{{display:block;width:24px;height:2px;background:#f1f1f5;border-radius:2px;transition:all .3s}}
.hamburger.active span:nth-child(1){{transform:rotate(45deg) translate(5px,5px)}}
.hamburger.active span:nth-child(2){{opacity:0}}
.hamburger.active span:nth-child(3){{transform:rotate(-45deg) translate(5px,-5px)}}
.mobile-nav{{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(8,8,15,0.98);backdrop-filter:blur(20px);z-index:55;flex-direction:column;align-items:center;justify-content:center;gap:28px}}
.mobile-nav.open{{display:flex}}
.mobile-nav a{{color:#f1f1f5;font-size:1.25rem;font-weight:600;text-decoration:none;transition:color .3s}}
.mobile-nav a:hover{{background:linear-gradient(135deg,{fc},{sc});-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.mobile-nav .btn-primary{{font-size:1rem;padding:14px 32px}}
@media (max-width:768px){{.hamburger{{display:flex}}.desktop-nav{{display:none}}.section-title{{font-size:1.75rem}}.hero-image{{margin-top:2rem}}.gallery-img{{height:120px}}}}
</style>
</head>
<body>
<nav class="glass fixed top-0 left-0 right-0 z-50 py-3 px-6">
  <div class="max-w-6xl mx-auto flex items-center justify-between">
    <div class="flex items-center gap-2">
      <span class="text-2xl">{icon}</span>
      <span class="font-bold text-lg">{biz_name}</span>
    </div>
    <div class="desktop-nav flex items-center gap-6 text-sm">
      <a href="#features" class="text-[#7a7a8e] hover:text-white transition">Services</a>
      <a href="#process" class="text-[#7a7a8e] hover:text-white transition">How It Works</a>
      <a href="#faq" class="text-[#7a7a8e] hover:text-white transition">FAQ</a>
      <a href="tel:{display_phone}" class="btn-primary text-sm py-2 px-5">{icon} {display_phone}</a>
    </div>
    <button class="hamburger" id="hamburger" onclick="toggleMobileMenu()" aria-label="Menu">
      <span></span><span></span><span></span>
    </button>
  </div>
</nav>
<div class="mobile-nav" id="mobileNav">
  <a href="#features" onclick="toggleMobileMenu()">Services</a>
  <a href="#process" onclick="toggleMobileMenu()">How It Works</a>
  <a href="#faq" onclick="toggleMobileMenu()">FAQ</a>
  <a href="tel:{display_phone}" class="btn-primary" onclick="toggleMobileMenu()">{icon} {display_phone}</a>
</div>
<section class="hero-gradient min-h-screen flex items-center pt-20 pb-20 px-4">
  <div class="max-w-6xl mx-auto w-full grid md:grid-cols-2 gap-12 items-center">
    <div data-aos="fade-right">
      <div class="inline-block px-4 py-2 rounded-full bg-[{fc}]20 border border-[{fc}]30 text-sm font-medium mb-6 text-[{fc}]">{icon} {hero_badge}</div>
      <h1 class="text-5xl md:text-6xl font-black mb-4 leading-tight">{title}</h1>
      <p class="text-xl md:text-2xl font-bold gradient-text mb-4">{tagline}</p>
      <p class="text-base md:text-lg text-[#7a7a8e] mb-8 leading-relaxed">{desc}</p>
      <div class="flex flex-wrap gap-4 items-center">
        <a href="tel:{display_phone}" class="btn-primary text-base px-8 py-4">{cta_text}</a>
        <a href="#features" class="text-sm text-[#7a7a8e] hover:text-white transition flex items-center gap-2">Learn More ↓</a>
      </div>
      <div class="flex items-center gap-4 mt-8 text-sm text-[#5c5c70]">
        <span>⭐ 4.9/5</span>
        <span>•</span>
        <span>{trust_1}</span>
        <span>•</span>
        <span>{trust_2}</span>
      </div>
    </div>
    <div data-aos="fade-left" class="relative">
      <img src="{hero_img}" alt="{biz_name}" class="hero-image rounded-2xl" onerror="this.style.display='none'">
    </div>
  </div>
</section>
<section class="py-10 border-y border-[#252533]/50 bg-[#0c0c14]">
  <div class="max-w-6xl mx-auto px-4 text-center">
    <p class="text-xs text-[#5c5c70] uppercase tracking-widest mb-6">Trusted by Our Clients</p>
    <div class="flex flex-wrap justify-center gap-8 items-center text-[#4a4a5e] text-sm font-medium opacity-50">
      <span>Licensed & Insured</span><span>•</span><span>5-Star Rated</span><span>•</span><span>100% Satisfaction</span><span>•</span><span>Free Consultation</span>
    </div>
  </div>
</section>
<section id="features" class="py-24 px-4">
  <div class="max-w-6xl mx-auto">
    <div class="text-center mb-16" data-aos="fade-up">
      <p class="text-sm font-semibold text-[{fc}] uppercase tracking-widest mb-3">Why Choose Us</p>
      <h2 class="section-title">Everything You Need, <span class="gradient-text">Handled by AI</span></h2>
      <p class="section-subtitle mt-3">From first call to completed service, our AI agent handles every step.</p>
    </div>
    <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
{features_html}
    </div>
  </div>
</section>
{gallery_html}
{video_html}
{audio_html}
<section id="process" class="py-24 px-4">
  <div class="max-w-6xl mx-auto">
    <div class="text-center mb-16" data-aos="fade-up">
      <p class="text-sm font-semibold text-[{fc}] uppercase tracking-widest mb-3">Simple Process</p>
      <h2 class="section-title">How It Works — <span class="gradient-text">3 Easy Steps</span></h2>
      <p class="section-subtitle mt-3">Get started today in minutes.</p>
    </div>
    <div class="grid md:grid-cols-3 gap-8">
      <div class="text-center" data-aos="fade-up">
        <div class="step-number mx-auto mb-4">1</div>
        <h3 class="text-xl font-bold mb-2">Call or Request Online</h3>
        <p class="text-sm text-[#7a7a8e]">Call us or fill out a quick form. We will ask about your needs and schedule a free consultation at your convenience.</p>
      </div>
      <div class="text-center" data-aos="fade-up" data-aos-delay="150">
        <div class="step-number mx-auto mb-4">2</div>
        <h3 class="text-xl font-bold mb-2">Free Consultation</h3>
        <p class="text-sm text-[#7a7a8e]">We discuss your needs, provide expert advice, and create a tailored solution that fits your budget.</p>
      </div>
      <div class="text-center" data-aos="fade-up" data-aos-delay="300">
        <div class="step-number mx-auto mb-4">3</div>
        <h3 class="text-xl font-bold mb-2">Service Delivered</h3>
        <p class="text-sm text-[#7a7a8e]">We deliver exceptional service with full satisfaction guaranteed.</p>
      </div>
    </div>
    <div class="text-center mt-12" data-aos="fade-up">
      <a href="tel:{display_phone}" class="btn-primary">{icon} Get Started Today</a>
    </div>
  </div>
</section>
<section class="py-24 px-4 bg-[#0a0a12]">
  <div class="max-w-6xl mx-auto grid md:grid-cols-2 gap-16 items-center">
    <div data-aos="fade-right">
      <p class="text-sm font-semibold text-[{fc}] uppercase tracking-widest mb-3">About {biz_name}</p>
      <h2 class="section-title mb-4">Your Trusted <span class="gradient-text">Local Service Provider</span></h2>
      <p class="text-[#7a7a8e] leading-relaxed mb-6">
        At {biz_name}, we combine professional expertise with cutting-edge AI technology to deliver exceptional service to our community.
      </p>
      <ul class="space-y-2 text-sm">
        <li class="flex items-center gap-3"><span style="color:{fc}">✅</span> Fast response — often same-day</li>
        <li class="flex items-center gap-3"><span style="color:{fc}">✅</span> Professional, licensed service</li>
        <li class="flex items-center gap-3"><span style="color:{fc}">✅</span> 100% satisfaction guaranteed</li>
      </ul>
    </div>
    <div class="grid grid-cols-2 gap-4" data-aos="fade-left">
{about_imgs_html}
    </div>
  </div>
</section>
<section class="py-24 px-4">
  <div class="max-w-6xl mx-auto">
    <div class="text-center mb-16" data-aos="fade-up">
      <p class="text-sm font-semibold text-[{fc}] uppercase tracking-widest mb-3">Testimonials</p>
      <h2 class="section-title">What Our Clients <span class="gradient-text">Are Saying</span></h2>
    </div>
    <div class="grid md:grid-cols-3 gap-6">
{testimonials_html}
    </div>
  </div>
</section>
<section id="faq" class="py-24 px-4 bg-[#0a0a12]">
  <div class="max-w-3xl mx-auto">
    <div class="text-center mb-16" data-aos="fade-up">
      <p class="text-sm font-semibold text-[{fc}] uppercase tracking-widest mb-3">FAQ</p>
      <h2 class="section-title">Frequently Asked <span class="gradient-text">Questions</span></h2>
    </div>
    <div class="space-y-4" data-aos="fade-up">
{faq_html}
    </div>
  </div>
</section>
<section class="py-24 px-4 hero-gradient">
  <div class="max-w-3xl mx-auto text-center" data-aos="fade-up">
    <div class="text-5xl mb-6">{icon}</div>
    <h2 class="section-title mb-4">Ready to Get <span class="gradient-text">Started?</span></h2>
    <p class="text-lg text-[#7a7a8e] mb-8 max-w-xl mx-auto">Call us today for your free consultation. Our AI agent is standing by 24/7.</p>
    <a href="tel:{display_phone}" class="btn-primary text-xl px-12 py-5 mb-4">{cta_text}</a>
    <div class="mt-4 text-sm text-[#5c5c70]">{cta_sub}</div>
    <div class="mt-6">
    <a href="https://cal.com/{cal_username}/{cal_event_slug}" target="_blank" class="btn-outline text-sm px-6 py-3 inline-flex items-center gap-2" onclick="return !window.Cal?true: (Cal('booking', {calLink:'{cal_username}/{cal_event_slug}'}), false)">
    📅 Book Appointment
    </a>
    </div>
  </div>
</section>
<footer class="py-12 px-4 border-t border-[#252533]">
  <div class="max-w-6xl mx-auto text-center text-sm text-[#5c5c70]">
    <p class="font-semibold text-[#7a7a8e] mb-1">{biz_name}</p>
    <p class="mt-1">{icon} <a href="tel:{display_phone}" class="hover:text-white transition">{display_phone}</a></p>
    <div class="mt-6 text-xs">Powered by Diazites AI Voice Agents</div>
  </div>
</footer>
<a href="tel:{display_phone}" class="floating-phone">{icon}</a>
<script>
AOS.init({{duration:800,once:true}});
function toggleMobileMenu(){{
  document.getElementById('mobileNav').classList.toggle('open');
  document.getElementById('hamburger').classList.toggle('active');
  document.body.style.overflow=document.getElementById('mobileNav').classList.contains('open')?'hidden':'';
}}
var da = document.getElementById('demo-player');
var dp = document.querySelector('.play-btn');
if(da){{
  da.addEventListener('timeupdate',function(){{
    var m=Math.floor(this.currentTime/60),s=Math.floor(this.currentTime%60);
    var t=document.getElementById('audio-time');
    if(t)t.textContent=m+':'+(s<10?'0':'')+s;
  }});
  da.addEventListener('ended',function(){{
    var s=document.getElementById('audio-status');
    if(s)s.textContent='\u25b6 Listen Again';
    if(dp)dp.innerHTML='<svg viewBox=\"0 0 24 24\"><polygon points=\"5,3 19,12 5,21\"/></svg>';
  }});
}}
function toggleAudioPlayer(btn){{
  if(!da)return;
  if(da.paused){{
    da.play();
    btn.innerHTML='<svg viewBox=\"0 0 24 24\"><rect x=\"6\" y=\"4\" width=\"4\" height=\"16\"/><rect x=\"14\" y=\"4\" width=\"4\" height=\"16\"/></svg>';
    var s=document.getElementById('audio-status');
    if(s)s.textContent='\U0001f50a Playing...';
  }}else{{
    da.pause();
    btn.innerHTML='<svg viewBox=\"0 0 24 24\"><polygon points=\"5,3 19,12 5,21\"/></svg>';
    var s=document.getElementById('audio-status');
    if(s)s.textContent='\u23f8 Paused';
  }}
}}
</script>
</body>
</html>'''
