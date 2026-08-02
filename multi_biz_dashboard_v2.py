#!/usr/bin/env python3
"""
# Diazites Dashboard
========================================
Full-featured dashboard for business clients:
  - Campaign start/stop/pause controls
  - Lead CSV upload + manual add + bulk
  - Buy/rent additional phone numbers
  - Call forwarding to business line
  - Voicemail greeting customization
  - Call scheduling (set business hours)
  - Analytics & call recordings
  - Script & knowledge base editor

Run: python3 multi_biz_dashboard_v2.py
Port: 8085


"""

# Extra minutes pricing (cents)
PRICES = {500: 15000, 1000: 29000, 5000: 49000}

import os, sys, json, sqlite3, csv, io, hashlib, time, threading, subprocess, hmac, uuid
import requests
from werkzeug.middleware.proxy_fix import ProxyFix
import urllib.request
from datetime import datetime, date, timedelta
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, redirect, session, url_for, send_file, flash, make_response
from functools import wraps
import secrets
from diazites_prompt import build_diazites_prompt
from landing_page_route import INDUSTRY_DATA, get_industry_data, FALLBACK_FAQ, FALLBACK_TESTIMONIALS, FALLBACK_FEATURES

# ── Helper: Git auto-commit ──
def git_auto_commit(message):
    """Auto-commit and push changes to GitHub."""
    try:
        subprocess.run(["git", "-C", "/root/voice-agent-manager", "add", "-A"],
                       capture_output=True, timeout=10)
        subprocess.run(["git", "-C", "/root/voice-agent-manager", "commit",
                       "-m", f"api: {message[:80]}"],
                       capture_output=True, timeout=10)
        subprocess.run(["git", "-C", "/root/voice-agent-manager", "push", "origin", "main"],
                       capture_output=True, timeout=30)
    except:
        pass  # don't break if git fails

DB_PATH = "/root/voice-agent-businesses.db"
CAL_COM_API_KEY = os.environ.get("CAL_COM_API_KEY", "")
CAL_COM_USERNAME = os.environ.get("CAL_COM_USERNAME", "pablo-d-i2xmhr")
# Calling key (d948...) — admin key is only for the admin panel on 8086.
# Env wins; literal is a last-resort fallback so calls never silently break.
VAPI_API_KEY = os.environ.get("VAPI_API_KEY") or "d9486ec8-b862-460b-97ba-64bbb639f234"
VAPI_BASE = "https://api.vapi.ai"
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
# Accept both /affiliate and /affiliate/ (trailing-slash tolerant)
app.url_map.strict_slashes = False
app.secret_key = os.environ.get("DIAZITES_SECRET_KEY") or secrets.token_hex(32)

GA_CONFIG_PATH = "/root/voice-agent-manager/ga_config.json"

@app.route('/api/ga-config')
def api_ga_config():
    try:
        with open(GA_CONFIG_PATH) as f:
            cfg = json.load(f)
        return jsonify({'ga_id': cfg.get('ga_id', ''), 'sc_key': cfg.get('sc_key', '')})
    except Exception:
        return jsonify({'ga_id': '', 'sc_key': ''})

def gsc_meta_tag():
    """Server-side Google Search Console verification meta tag (no JS needed)."""
    try:
        with open(GA_CONFIG_PATH) as f:
            cfg = json.load(f)
        key = cfg.get('sc_key', '').strip()
        if key:
            return f'<meta name="google-site-verification" content="{key}" />'
    except Exception:
        pass
    return ''

# Track active campaign threads so we can detect stale ones
campaign_threads = {}
campaign_status_cache = {}

from premium_features2 import LANGUAGES
from agentmail_email import send_appointment_confirmation

INDUSTRY_LIST = [
    {"id": "plumber", "name": "Plumber", "icon": "🔧", "desc": "Never miss emergency calls"},
    {"id": "dentist", "name": "Dentist", "icon": "🦷", "desc": "Reduce no-shows with automated booking"},
    {"id": "roofer", "name": "Roofer", "icon": "🏠", "desc": "Capture storm season leads"},
    {"id": "hvac", "name": "HVAC", "icon": "❄️", "desc": "Handle after-hours emergencies"},
    {"id": "lawyer", "name": "Lawyer", "icon": "⚖️", "desc": "Qualify leads automatically"},
    {"id": "real_estate", "name": "Real Estate", "icon": "🏡", "desc": "Capture buyer/seller leads 24/7"},
    {"id": "auto_mechanic", "name": "Auto Mechanic", "icon": "🚗", "desc": "Book service appointments overnight"},
    {"id": "cleaning", "name": "Cleaning Service", "icon": "🧹", "desc": "Recurring client pipeline automation"},
    {"id": "pest_control", "name": "Pest Control", "icon": "🐜", "desc": "Emergency response automation"},
    {"id": "landscaper", "name": "Landscaper", "icon": "🌿", "desc": "Book estimates while on the job"},
]

SIGNUP_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diazites — AI Voice Agents for Your Business</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/@phosphor-icons/web"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{font-family:'Inter',sans-serif;margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{background:#08080f;color:#f1f1f5;overflow-x:hidden}
.gradient-text{background:linear-gradient(135deg,#a855f7,#ec4899,#06b6d4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-size:200% 200%;animation:gradientShift 4s ease infinite}
@keyframes gradientShift{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-20px)}}
@keyframes pulseGlow{0%,100%{opacity:0.4;transform:scale(1)}50%{opacity:0.8;transform:scale(1.05)}}
@keyframes slideUp{from{opacity:0;transform:translateY(40px)}to{opacity:1;transform:translateY(0)}}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.animate-float{animation:float 6s ease-in-out infinite}
.animate-pulse-glow{animation:pulseGlow 3s ease-in-out infinite}
.animate-slide-up{animation:slideUp 0.8s ease-out forwards}
.animate-slide-up-1{animation:slideUp 0.8s ease-out 0.1s forwards;opacity:0}
.animate-slide-up-2{animation:slideUp 0.8s ease-out 0.2s forwards;opacity:0}
.animate-slide-up-3{animation:slideUp 0.8s ease-out 0.3s forwards;opacity:0}
.animate-slide-up-4{animation:slideUp 0.8s ease-out 0.4s forwards;opacity:0}
.hero-gradient{background:radial-gradient(ellipse at 30% 20%,rgba(168,85,247,0.15) 0%,transparent 50%),radial-gradient(ellipse at 70% 80%,rgba(6,182,212,0.1) 0%,transparent 50%),radial-gradient(ellipse at 50% 50%,rgba(236,72,153,0.05) 0%,transparent 50%)}
.glass{background:rgba(18,18,26,0.6);backdrop-filter:blur(20px);border:1px solid rgba(37,37,51,0.5)}
.glass-hover:hover{background:rgba(30,30,50,0.8);border-color:rgba(168,85,247,0.3);transform:translateY(-4px)}
.card-gradient{background:linear-gradient(135deg,rgba(18,18,26,0.8),rgba(26,10,46,0.8));border:1px solid rgba(37,37,51,0.5);border-radius:16px;transition:all 0.3s ease}
.card-gradient:hover{border-color:rgba(168,85,247,0.3);transform:translateY(-4px);box-shadow:0 20px 40px rgba(168,85,247,0.1)}
.glow-border{position:relative}
.glow-border::before{content:'';position:absolute;inset:-1px;border-radius:17px;background:linear-gradient(135deg,#a855f7,#ec4899,#06b6d4);opacity:0;transition:opacity 0.3s;z-index:-1}
.glow-border:hover::before{opacity:0.5}
.step-circle{width:48px;height:48px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.2rem;background:linear-gradient(135deg,#a855f7,#ec4899);flex-shrink:0}
.feature-icon{width:56px;height:56px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:1.5rem}
.marquee-track{display:flex;animation:marquee 30s linear infinite;gap:2rem;width:max-content}
@keyframes marquee{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
/* ── MOBILE RESPONSIVE ── */
@media(max-width:768px){
  nav.glass{flex-wrap:wrap;gap:8px;padding:10px 16px !important}
  nav.glass>div:first-child{flex:1}
  nav.glass .flex.items-center.gap-4{display:none}
  nav.glass .flex.items-center.gap-4.open{display:flex;flex-direction:column;position:fixed;top:60px;left:0;right:0;background:rgba(10,10,15,.98);border-bottom:1px solid #252533;padding:16px;gap:12px;z-index:100}
  section{overflow-x:hidden}
  h1.text-5xl{font-size:1.8rem !important;line-height:1.2 !important}
  h1.md\:text-6xl{font-size:2rem !important}
  p.text-lg{font-size:0.9rem !important;max-width:100% !important}
  .max-w-6xl,.max-w-4xl,.max-w-2xl{max-width:100% !important;padding-left:16px !important;padding-right:16px !important}
  .flex.items-center.justify-center.gap-4{flex-direction:column;width:100%}
  .flex.items-center.justify-center.gap-4 a{width:100%;text-align:center;box-sizing:border-box;padding-left:16px !important;padding-right:16px !important}
  .grid.md\:grid-cols-2,.grid.md\:grid-cols-3,.grid.md\:grid-cols-4,.grid.lg\:grid-cols-2,.grid.lg\:grid-cols-3,.grid.lg\:grid-cols-4{grid-template-columns:1fr !important}
  .grid.grid-cols-3,.grid.grid-cols-4{grid-template-columns:1fr 1fr !important}
  .gap-12{gap:24px !important}
  .card,.audio-card{padding:16px !important}
  .p-8{padding:16px !important}
  .px-8{padding-left:16px !important;padding-right:16px !important}
  .play-btn{width:40px;height:40px}
  .grid.md\:grid-cols-3.gap-8{gap:16px !important}
  .grid.md\:grid-cols-4{gap:16px !important;grid-template-columns:1fr 1fr !important}
}
@media(max-width:480px){
  h1.text-5xl{font-size:1.5rem !important}
  .grid.grid-cols-2,.grid.grid-cols-3{grid-template-columns:1fr !important}
  .grid.md\:grid-cols-4{grid-template-columns:1fr !important}
}</head><body>

</style>
</head>
<body>

<!-- NAVBAR -->
<nav class="fixed top-0 w-full z-50 glass">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <span class="text-2xl">🎙️</span>
      <span class="font-bold text-lg gradient-text">Diazites</span>
    </div>
    <div class="hidden md:flex items-center gap-8 text-sm text-[#7a7a8e]">
      <a href="#features" class="hover:text-[#a855f7] transition-colors">Features</a>
      <a href="#how-it-works" class="hover:text-[#a855f7] transition-colors">How It Works</a>
      <a href="#benefits" class="hover:text-[#a855f7] transition-colors">Benefits</a>
      <a href="#pricing" class="hover:text-[#a855f7] transition-colors">Pricing</a>
    </div>
    <div class="flex items-center gap-3">
      <a href="/login" class="text-sm text-[#7a7a8e] hover:text-white transition-colors">Log In</a>
      <a href="/login" class="text-sm font-semibold bg-gradient-to-r from-[#a855f7] to-[#ec4899] text-white px-5 py-2 rounded-lg hover:shadow-lg hover:shadow-purple-500/20 transition-all">Get Started</a>
    </div>
  </div>
</nav>

<!-- HERO -->
<section class="hero-gradient min-h-screen flex items-center pt-20 pb-16 px-4 relative overflow-hidden">
  <!-- Background particles -->
  <div class="absolute inset-0 overflow-hidden pointer-events-none">
    <div class="absolute w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse-glow" style="top:10%;left:10%"></div>
    <div class="absolute w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl animate-pulse-glow" style="bottom:20%;right:15%;animation-delay:1.5s"></div>
    <div class="absolute w-48 h-48 bg-pink-500/10 rounded-full blur-3xl animate-pulse-glow" style="top:40%;right:30%;animation-delay:3s"></div>
  </div>
  
  <div class="max-w-7xl mx-auto relative z-10">
    <div class="grid lg:grid-cols-2 gap-12 items-center">
      <div class="space-y-8">
        <div class="animate-slide-up-1 inline-flex items-center gap-2 bg-purple-500/10 border border-purple-500/20 rounded-full px-4 py-1.5 text-sm">
          <span class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
          <span class="text-purple-300">AI Voice Agents — Now Available</span>
        </div>
        <h1 class="text-5xl md:text-6xl lg:text-7xl font-black leading-tight animate-slide-up-2">
          Your Business<br>
          <span class="gradient-text">Never Miss a Call</span><br>
          Again
        </h1>
        <p class="text-lg text-[#7a7a8e] max-w-lg animate-slide-up-3 leading-relaxed">
          Diazites AI voice agents answer every call 24/7, book appointments automatically, 
          follow up with leads, and handle conversations in multiple languages — 
          just like a real receptionist.
        </p>
        <div class="flex flex-wrap gap-4 animate-slide-up-4">
          <a href="/login" class="bg-gradient-to-r from-[#a855f7] to-[#ec4899] text-white px-8 py-3.5 rounded-xl font-semibold text-base hover:shadow-xl hover:shadow-purple-500/25 transition-all flex items-center gap-2">
            Start Your Free Trial <span>→</span>
          </a>
          <a href="#how-it-works" class="glass px-8 py-3.5 rounded-xl font-semibold text-base hover:bg-white/5 transition-all flex items-center gap-2">
            <span>▶</span> See How It Works
          </a>
        </div>
        <div class="flex items-center gap-6 text-sm text-[#5c5c70] animate-slide-up-4 pt-4">
          <div class="flex items-center gap-2">
            <span class="text-green-400">✓</span> No setup fees
          </div>
          <div class="flex items-center gap-2">
            <span class="text-green-400">✓</span> Cancel anytime
          </div>
          <div class="flex items-center gap-2">
            <span class="text-green-400">✓</span> 14-day free trial
          </div>
        </div>
      </div>
      
      <!-- Hero visual with video -->
      <div class="relative lg:block">
        <div class="relative rounded-2xl overflow-hidden shadow-2xl shadow-purple-500/20">
          <video autoplay muted loop playsinline class="w-full max-w-lg mx-auto rounded-2xl" style="max-height:500px;object-fit:cover">
            <source src="/static/product_images/promo_main.mp4" type="video/mp4">
          </video>
          <!-- Floating feature badges -->
          <div class="absolute -top-4 -right-4 glass rounded-xl px-4 py-3 text-xs font-medium shadow-xl border border-green-500/20">
            <span class="text-green-400">●</span> 24/7 Automated
          </div>
          <div class="absolute -bottom-4 -left-4 glass rounded-xl px-4 py-3 text-xs font-medium shadow-xl border border-cyan-500/20">
            <span class="text-cyan-400">●</span> Multi-Language
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- SOCIAL PROOF / STATS -->
<section class="py-16 border-y border-[#1a1a2e]">
  <div class="max-w-7xl mx-auto px-4">
    <div class="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
      <div>
        <div class="text-3xl font-bold gradient-text">350+</div>
        <div class="text-sm text-[#5c5c70] mt-1">Leads Processed</div>
      </div>
      <div>
        <div class="text-3xl font-bold gradient-text">24/7</div>
        <div class="text-sm text-[#5c5c70] mt-1">Call Coverage</div>
      </div>
      <div>
        <div class="text-3xl font-bold gradient-text">5+</div>
        <div class="text-sm text-[#5c5c70] mt-1">Languages</div>
      </div>
      <div>
        <div class="text-3xl font-bold gradient-text">$0</div>
        <div class="text-sm text-[#5c5c70] mt-1">Setup Cost</div>
      </div>
    </div>
  </div>
</section>

<!-- FEATURES -->
<section id="features" class="py-24 px-4">
  <div class="max-w-7xl mx-auto">
    <div class="text-center mb-16">
      <span class="text-sm font-semibold text-purple-400 tracking-widest uppercase">Features</span>
      <h2 class="text-4xl md:text-5xl font-bold mt-4">AI Receptionists for<br><span class="gradient-text">Any Industry</span></h2>
      <p class="text-[#7a7a8e] mt-4 max-w-3xl mx-auto">Whether you're a small business, growing company, or enterprise, your AI receptionist is trained specifically for your operations.</p>
    </div>
    
    <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
      <!-- Feature 1 -->
      <div class="card-gradient p-6 glow-border">
        <div class="feature-icon bg-gradient-to-br from-purple-500/20 to-purple-500/5 mb-4">
          <span class="text-2xl">🏢</span>
        </div>
        <h3 class="font-bold text-lg mb-2">Customized for Your Business</h3>
        <p class="text-sm text-[#7a7a8e] leading-relaxed">Your AI receptionist is trained on your services, pricing, FAQs, policies, and workflows—so every caller gets accurate, professional answers.</p>
      </div>
      
      <!-- Feature 2 -->
      <div class="card-gradient p-6 glow-border">
        <div class="feature-icon bg-gradient-to-br from-pink-500/20 to-pink-500/5 mb-4">
          <span class="text-2xl">📞</span>
        </div>
        <h3 class="font-bold text-lg mb-2">Never Miss Another Call</h3>
        <p class="text-sm text-[#7a7a8e] leading-relaxed">Answer every call 24/7, qualify leads, schedule appointments, transfer urgent calls, and capture every opportunity.</p>
      </div>
      
      <!-- Feature 3 -->
      <div class="card-gradient p-6 glow-border">
        <div class="feature-icon bg-gradient-to-br from-cyan-500/20 to-cyan-500/5 mb-4">
          <span class="text-2xl">📅</span>
        </div>
        <h3 class="font-bold text-lg mb-2">Smart Scheduling</h3>
        <p class="text-sm text-[#7a7a8e] leading-relaxed">Connect with your calendar to book appointments, meetings, consultations, demos, estimates, or service calls automatically.</p>
      </div>
      
      <!-- Feature 4 -->
      <div class="card-gradient p-6 glow-border">
        <div class="feature-icon bg-gradient-to-br from-green-500/20 to-green-500/5 mb-4">
          <span class="text-2xl">💬</span>
        </div>
        <h3 class="font-bold text-lg mb-2">Instant Customer Support</h3>
        <p class="text-sm text-[#7a7a8e] leading-relaxed">Answer common questions, provide updates, collect information, and route customers to the right department.</p>
      </div>
      
      <!-- Feature 5 -->
      <div class="card-gradient p-6 glow-border">
        <div class="feature-icon bg-gradient-to-br from-amber-500/20 to-amber-500/5 mb-4">
          <span class="text-2xl">🚀</span>
        </div>
        <h3 class="font-bold text-lg mb-2">Lead Qualification & Sales</h3>
        <p class="text-sm text-[#7a7a8e] leading-relaxed">Qualify prospects, collect contact information, answer objections, and move leads through your sales process automatically.</p>
      </div>
      
      <!-- Feature 6 -->
      <div class="card-gradient p-6 glow-border">
        <div class="feature-icon bg-gradient-to-br from-red-500/20 to-red-500/5 mb-4">
          <span class="text-2xl">⚙️</span>
        </div>
        <h3 class="font-bold text-lg mb-2">Built Around Your Workflow</h3>
        <p class="text-sm text-[#7a7a8e] leading-relaxed">Every AI receptionist is customized for your business processes, CRM, scheduling software, and communication tools.</p>
      </div>
    </div>
  </div>
</section>

<!-- TRUSTED BY -->
<section class="max-w-5xl mx-auto px-6 pb-8 text-center">
<p class="text-sm text-[#5c5c70] mb-6 tracking-wider uppercase font-semibold">Trusted By Local Businesses</p>
<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
<div class="card py-5 text-center"><div class="text-lg mb-1">🔧</div><div class="text-sm font-medium">Plumbing Companies</div></div>
<div class="card py-5 text-center"><div class="text-lg mb-1">🦷</div><div class="text-sm font-medium">Dental Offices</div></div>
<div class="card py-5 text-center"><div class="text-lg mb-1">🏡</div><div class="text-sm font-medium">Real Estate Teams</div></div>
<div class="card py-5 text-center"><div class="text-lg mb-1">❄️</div><div class="text-sm font-medium">HVAC Companies</div></div>
</div>
<p class="text-xs text-[#5c5c70] mt-5">Built for: Home Services ✓  Healthcare ✓  Real Estate ✓  Professional Services ✓</p>
</section>

<!-- LIVE VOICE DEMOS -->
<section id="demos" class="max-w-5xl mx-auto px-6 pb-16">
<h2 class="text-3xl font-bold text-center mb-3">🎧 Hear It In <span class="gradient-text">Action</span></h2>
<p class="text-[#7a7a8e] text-center mb-2 max-w-xl mx-auto">Listen to a real customer call handled by Diazites AI — hear how natural, professional, and instant it sounds.</p>
<p class="text-sm text-[#a855f7] text-center mb-10 font-semibold">Click any demo to play</p>

<div class="grid md:grid-cols-3 gap-5">
<!-- Plumber Demo -->
<div class="audio-card" data-demo="plumber" onclick="toggleAudio(this,'/static/audio/demo-plumber.mp3')">
<div class="flex items-start gap-4 mb-3">
<button class="play-btn" id="play-plumber"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></button>
<div class="flex-1">
<div class="flex items-center gap-2 mb-1"><span class="text-lg">🔧</span><span class="font-semibold">Plumber</span><span class="text-[10px] px-2 py-0.5 rounded-full" style="background:#a855f722;color:#c084fc">Emergency</span></div>
<p class="text-xs text-[#7a7a8e]">Burst pipe call — AI triages urgency, captures address, dispatches plumber</p>
</div>
</div>
<div class="flex items-center gap-1" id="waveform-plumber">
<div class="waveform-bar" style="height:12px"></div><div class="waveform-bar" style="height:18px"></div><div class="waveform-bar" style="height:24px"></div><div class="waveform-bar" style="height:32px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:48px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:32px"></div><div class="waveform-bar" style="height:24px"></div><div class="waveform-bar" style="height:18px"></div><div class="waveform-bar" style="height:12px"></div>
</div>
<div class="flex items-center justify-between mt-2">
<span class="text-[10px] text-[#5c5c70]" id="time-plumber">0:00 / 0:20</span>
<span class="text-[10px] text-[#c084fc]" id="status-plumber">▶ Click to play</span>
</div>
</div>

<!-- Dentist Demo -->
<div class="audio-card" data-demo="dentist" onclick="toggleAudio(this,'/static/audio/demo-dentist.mp3')">
<div class="flex items-start gap-4 mb-3">
<button class="play-btn" id="play-dentist"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></button>
<div class="flex-1">
<div class="flex items-center gap-2 mb-1"><span class="text-lg">🦷</span><span class="font-semibold">Dentist</span><span class="text-[10px] px-2 py-0.5 rounded-full" style="background:#22c55e22;color:#4ade80">Booking</span></div>
<p class="text-xs text-[#7a7a8e]">Patient calls — AI checks availability, schedules appointment, sets reminder</p>
</div>
</div>
<div class="flex items-center gap-1" id="waveform-dentist">
<div class="waveform-bar" style="height:14px"></div><div class="waveform-bar" style="height:20px"></div><div class="waveform-bar" style="height:28px"></div><div class="waveform-bar" style="height:36px"></div><div class="waveform-bar" style="height:42px"></div><div class="waveform-bar" style="height:46px"></div><div class="waveform-bar" style="height:48px"></div><div class="waveform-bar" style="height:42px"></div><div class="waveform-bar" style="height:36px"></div><div class="waveform-bar" style="height:28px"></div><div class="waveform-bar" style="height:20px"></div><div class="waveform-bar" style="height:14px"></div>
</div>
<div class="flex items-center justify-between mt-2">
<span class="text-[10px] text-[#5c5c70]" id="time-dentist">0:00 / 0:23</span>
<span class="text-[10px] text-[#c084fc]" id="status-dentist">▶ Click to play</span>
</div>
</div>

<!-- Real Estate Demo -->
<div class="audio-card" data-demo="realestate" onclick="toggleAudio(this,'/static/audio/demo-realestate.mp3')">
<div class="flex items-start gap-4 mb-3">
<button class="play-btn" id="play-realestate"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></button>
<div class="flex-1">
<div class="flex items-center gap-2 mb-1"><span class="text-lg">🏡</span><span class="font-semibold">Real Estate</span><span class="text-[10px] px-2 py-0.5 rounded-full" style="background:#f59e0b22;color:#fbbf24">Qualification</span></div>
<p class="text-xs text-[#7a7a8e]">Property inquiry — AI qualifies buyer, schedules showing, confirms by text</p>
</div>
</div>
<div class="flex items-center gap-1" id="waveform-realestate">
<div class="waveform-bar" style="height:10px"></div><div class="waveform-bar" style="height:16px"></div><div class="waveform-bar" style="height:22px"></div><div class="waveform-bar" style="height:30px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:48px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:30px"></div><div class="waveform-bar" style="height:22px"></div><div class="waveform-bar" style="height:16px"></div><div class="waveform-bar" style="height:10px"></div>
</div>
<div class="flex items-center justify-between mt-2">
<span class="text-[10px] text-[#5c5c70]" id="time-realestate">0:00 / 0:21</span>
<span class="text-[10px] text-[#c084fc]" id="status-realestate">▶ Click to play</span>
</div>
</div>
</div>
</section>

<!-- HOW IT WORKS -->
<section id="how-it-works" class="py-24 px-4 bg-[#0c0c18]">
  <div class="max-w-7xl mx-auto">
    <div class="text-center mb-16">
      <span class="text-sm font-semibold text-purple-400 tracking-widest uppercase">How It Works</span>
      <h2 class="text-4xl md:text-5xl font-bold mt-4">Three Simple Steps<br><span class="gradient-text">to Get Started</span></h2>
    </div>
    
    <div class="grid md:grid-cols-3 gap-8">
      <div class="text-center animate-slide-up-1">
        <div class="step-circle mx-auto mb-6 text-white">1</div>
        <div class="glass rounded-2xl p-8 h-full">
          <div class="text-5xl mb-4">🎯</div>
          <h3 class="font-bold text-xl mb-3">Set Up Your Agent</h3>
          <p class="text-sm text-[#7a7a8e] leading-relaxed">Enter your business details, choose your industry, and customize how your AI answers calls. Takes 5 minutes.</p>
        </div>
      </div>
      
      <div class="text-center animate-slide-up-2">
        <div class="step-circle mx-auto mb-6 text-white">2</div>
        <div class="glass rounded-2xl p-8 h-full">
          <div class="text-5xl mb-4">📱</div>
          <h3 class="font-bold text-xl mb-3">Get a Phone Number</h3>
          <p class="text-sm text-[#7a7a8e] leading-relaxed">Pick your area code and we'll assign a local number. Forward your existing number or get a new one.</p>
        </div>
      </div>
      
      <div class="text-center animate-slide-up-3">
        <div class="step-circle mx-auto mb-6 text-white">3</div>
        <div class="glass rounded-2xl p-8 h-full">
          <div class="text-5xl mb-4">🚀</div>
          <h3 class="font-bold text-xl mb-3">Go Live</h3>
          <p class="text-sm text-[#7a7a8e] leading-relaxed">Your AI starts answering calls immediately. Import leads, schedule campaigns, and monitor everything from your dashboard.</p>
        </div>
      </div>
    </div>
    
    <!-- Visual walkthrough images -->
    <div class="grid md:grid-cols-3 gap-6 mt-16">
      <div class="rounded-xl overflow-hidden glass">
        <img src="/static/product_images/feature_247.png" alt="24/7 AI Assistant" class="w-full h-48 object-cover">
        <div class="p-4">
          <h4 class="font-semibold text-sm">24/7 AI Call Answering</h4>
          <p class="text-xs text-[#7a7a8e] mt-1">Never miss a call — day or night</p>
        </div>
      </div>
      <div class="rounded-xl overflow-hidden glass">
        <img src="/static/product_images/feature_calendar.png" alt="Calendar Booking" class="w-full h-48 object-cover">
        <div class="p-4">
          <h4 class="font-semibold text-sm">Auto Appointment Booking</h4>
          <p class="text-xs text-[#7a7a8e] mt-1">Calendar invites sent automatically</p>
        </div>
      </div>
      <div class="rounded-xl overflow-hidden glass">
        <img src="/static/product_images/feature_analytics.png" alt="Analytics" class="w-full h-48 object-cover">
        <div class="p-4">
          <h4 class="font-semibold text-sm">Real-Time Analytics</h4>
          <p class="text-xs text-[#7a7a8e] mt-1">Track calls, costs, and conversions</p>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- USE CASES -->
<section class="py-24 px-4">
  <div class="max-w-7xl mx-auto">
    <div class="text-center mb-16">
      <span class="text-sm font-semibold text-purple-400 tracking-widest uppercase">Use Cases</span>
      <h2 class="text-4xl md:text-5xl font-bold mt-4">Perfect for<br><span class="gradient-text">Every Business</span></h2>
    </div>
    
    <div class="grid md:grid-cols-2 gap-6">
      <div class="glass rounded-2xl p-6 flex items-start gap-4 glow-border">
        <div class="text-3xl">🏠</div>
        <div>
          <h4 class="font-bold">Residential Services</h4>
          <p class="text-sm text-[#7a7a8e] mt-1">Painters, plumbers, electricians, roofers — handle booking calls while you're on the job.</p>
        </div>
      </div>
      <div class="glass rounded-2xl p-6 flex items-start gap-4 glow-border">
        <div class="text-3xl">🏥</div>
        <div>
          <h4 class="font-bold">Medical & Dental</h4>
          <p class="text-sm text-[#7a7a8e] mt-1">Schedule patient appointments, send reminders, handle after-hours calls.</p>
        </div>
      </div>
      <div class="glass rounded-2xl p-6 flex items-start gap-4 glow-border">
        <div class="text-3xl">⚖️</div>
        <div>
          <h4 class="font-bold">Legal & Consulting</h4>
          <p class="text-sm text-[#7a7a8e] mt-1">Qualify leads, book consultations, follow up with prospects automatically.</p>
        </div>
      </div>
      <div class="glass rounded-2xl p-6 flex items-start gap-4 glow-border">
        <div class="text-3xl">🏪</div>
        <div>
          <h4 class="font-bold">Local Businesses</h4>
          <p class="text-sm text-[#7a7a8e] mt-1">Restaurants, salons, auto shops — answer calls, take orders, book appointments 24/7.</p>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- PRICING -->
<section id="pricing" class="py-24 px-4 bg-[#0c0c18]">
  <div class="max-w-7xl mx-auto">
    <div class="text-center mb-16">
      <span class="text-sm font-semibold text-purple-400 tracking-widest uppercase">Pricing</span>
      <h2 class="text-4xl md:text-5xl font-bold mt-4">Simple, Transparent<br><span class="gradient-text">No Hidden Fees</span></h2>
    </div>
    
    <div class="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
      <div class="glass rounded-2xl p-8 text-center glow-border">
        <h3 class="font-bold text-xl mb-2">Starter</h3>
        <p class="text-xs text-[#64748b] mb-3">Perfect for small businesses & solopreneurs</p>
        <div class="text-4xl font-black my-4 gradient-text">$97</div>
        <p class="text-sm text-[#7a7a8e] mb-6">per month</p>
        <ul class="text-left space-y-3 text-sm mb-8">
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> 1 AI Voice Agent</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> 1 Phone Number</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> <strong>250</strong> Call Minutes</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Basic Analytics Dashboard</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Email Support</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Appointment Booking</li>
        </ul>
        <a href="#" onclick="openSignup('starter')" class="block w-full py-3 rounded-xl font-semibold text-sm glass hover:bg-white/5 transition-all text-center">Get Started</a>
      </div>
      
      <div class="rounded-2xl p-8 text-center relative" style="background:linear-gradient(135deg,rgba(168,85,247,0.1),rgba(236,72,153,0.1));border:1px solid rgba(168,85,247,0.3);transform:scale(1.05)">
        <div class="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-[#a855f7] to-[#ec4899] text-white text-xs font-bold px-4 py-1 rounded-full">Most Popular</div>
        <h3 class="font-bold text-xl mb-2 mt-2">Professional</h3>
        <p class="text-xs text-[#64748b] mb-3">Best for growing businesses & busy practices</p>
        <div class="text-4xl font-black my-4 gradient-text">$197</div>
        <p class="text-sm text-[#7a7a8e] mb-6">per month</p>
        <ul class="text-left space-y-3 text-sm mb-8">
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> 2 AI Voice Agents</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> 2 Phone Numbers</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> <strong>1,000</strong> Call Minutes</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Advanced Analytics & Reports</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Priority Support</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Outbound Campaigns</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> SMS Follow-Ups</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Calendar Integration</li>
        </ul>
        <a href="#" onclick="openSignup('pro')" class="block w-full py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-[#a855f7] to-[#ec4899] text-white hover:shadow-lg hover:shadow-purple-500/20 transition-all text-center">Start Free Trial</a>
      </div>
      
      <div class="glass rounded-2xl p-8 text-center glow-border">
        <h3 class="font-bold text-xl mb-2">Enterprise</h3>
        <p class="text-xs text-[#64748b] mb-3">For agencies, multi-location & high-volume</p>
        <div class="text-4xl font-black my-4 gradient-text">Custom</div>
        <p class="text-sm text-[#7a7a8e] mb-6">tailored pricing</p>
        <ul class="text-left space-y-3 text-sm mb-8">
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Up to 5 AI Agents</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Up to 5 Phone Numbers</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Unlimited Call Minutes</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Custom Integrations</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> Dedicated Account Manager</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> API Access & Webhooks</li>
          <li class="flex items-center gap-2"><span class="text-green-400">✓</span> White-Label Option</li>
        </ul>
        <a href="/login" class="block w-full py-3 rounded-xl font-semibold text-sm glass hover:bg-white/5 transition-all text-center">Contact Us</a>
      </div>
    </div>
  </div>
</section>

<!-- CTA -->
<section class="py-24 px-4">
  <div class="max-w-4xl mx-auto text-center glass rounded-3xl p-12 relative overflow-hidden">
    <div class="absolute inset-0 bg-gradient-to-r from-purple-500/5 via-transparent to-cyan-500/5"></div>
    <div class="relative z-10">
      <h2 class="text-4xl md:text-5xl font-bold mb-4">Ready to <span class="gradient-text">Automate</span> Your Calls?</h2>
      <p class="text-[#7a7a8e] mb-8 max-w-lg mx-auto">Join businesses that never miss a call. Start your 14-day free trial today — no credit card required.</p>
      <div class="flex flex-wrap justify-center gap-4">
        <a href="/login" class="bg-gradient-to-r from-[#a855f7] to-[#ec4899] text-white px-8 py-3.5 rounded-xl font-semibold text-base hover:shadow-xl hover:shadow-purple-500/25 transition-all">Start Free Trial</a>
        <a href="#features" class="glass px-8 py-3.5 rounded-xl font-semibold text-base hover:bg-white/5 transition-all">Explore Features</a>
      </div>
    </div>
  </div>
</section>

<!-- SIGNUP MODAL -->
<div id="signupModal" class="hidden fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm" onclick="if(event.target===this)closeSignup()">
  <div class="bg-[#12121a] rounded-2xl p-8 max-w-md w-full mx-4 border border-[#252533] shadow-2xl shadow-purple-500/10 max-h-[90vh] overflow-y-auto" onclick="event.stopPropagation()">
    <div class="flex items-center justify-between mb-6">
      <h3 class="text-xl font-bold">🚀 Start Your <span class="gradient-text">Trial</span></h3>
      <button onclick="closeSignup()" class="text-[#5c5c70] hover:text-white text-2xl leading-none">&times;</button>
    </div>
    
    <form id="signupForm" onsubmit="submitSignup(event)" class="space-y-4">
      <input type="hidden" name="plan" id="selectedPlan" value="pro">
      
      <!-- Plan selector -->
      <div class="grid grid-cols-3 gap-2 mb-2">
        <button type="button" onclick="selectPlan('starter')" id="planStarter" class="plan-btn py-3 rounded-xl text-center text-xs font-semibold border border-[#252533] hover:border-purple-500/40 transition-all">
          <div class="text-lg font-bold gradient-text">$97</div>
          <div class="text-[#7a7a8e] mt-0.5">Starter</div>
          <div class="text-[10px] text-purple-300 font-bold">1 AGENT</div>
        </button>
        <button type="button" onclick="selectPlan('pro')" id="planPro" class="plan-btn py-3 rounded-xl text-center text-xs font-semibold border-2 border-purple-500/50 bg-purple-500/10 transition-all">
          <div class="text-lg font-bold gradient-text">$197</div>
          <div class="text-[#7a7a8e] mt-0.5">Pro</div>
          <div class="text-[10px] text-purple-400 font-bold">2 AGENTS</div>
        </button>
        <button type="button" onclick="selectPlan('premium')" id="planPremium" class="plan-btn py-3 rounded-xl text-center text-xs font-semibold border border-[#252533] hover:border-purple-500/40 transition-all">
          <div class="text-lg font-bold gradient-text">$497</div>
          <div class="text-[#7a7a8e] mt-0.5">Premium</div>
          <div class="text-[10px] text-purple-400 font-bold">3 AGENTS</div>
        </button>
      </div>

      <div>
        <label class="text-xs text-[#7a7a8e] block mb-1">Business Name *</label>
        <input type="text" name="name" required class="w-full bg-[#1a1a26] border border-[#252533] rounded-lg px-4 py-3 text-sm" placeholder="Your Business Name">
      </div>
      <div>
        <label class="text-xs text-[#7a7a8e] block mb-1">Email *</label>
        <input type="email" name="email" required class="w-full bg-[#1a1a26] border border-[#252533] rounded-lg px-4 py-3 text-sm" placeholder="you@business.com">
      </div>
      <div>
        <label class="text-xs text-[#7a7a8e] block mb-1">Phone Number</label>
        <input type="tel" name="phone" class="w-full bg-[#1a1a26] border border-[#252533] rounded-lg px-4 py-3 text-sm" placeholder="+1 (555) 000-0000">
      </div>
      <div>
        <label class="text-xs text-[#7a7a8e] block mb-1">Industry</label>
        <select name="industry" class="w-full bg-[#1a1a26] border border-[#252533] rounded-lg px-4 py-3 text-sm">
          <option value="general">General</option>
          <option value="plumber">Plumber</option>
          <option value="dentist">Dentist</option>
          <option value="hvac">HVAC</option>
          <option value="roofer">Roofing</option>
          <option value="real_estate">Real Estate</option>
          <option value="pest_control">Pest Control</option>
          <option value="lawyer">Lawyer</option>
          <option value="cleaning">Cleaning</option>
          <option value="solar">Solar</option>
          <option value="auto_mechanic">Auto Mechanic</option>
          <option value="landscaper">Landscaper</option>
          <option value="health_insurance">Health Insurance</option>
        </select>
      </div>
      
      <div id="signupError" class="hidden text-red-400 text-xs p-3 bg-red-500/10 rounded-lg"></div>
      
      <button type="submit" id="signupBtn" class="w-full py-3.5 rounded-xl font-semibold text-sm bg-gradient-to-r from-[#a855f7] to-[#ec4899] text-white hover:shadow-lg hover:shadow-purple-500/20 transition-all flex items-center justify-center gap-2">
        <span>💳</span> Proceed to Payment
      </button>
      
      <p class="text-[10px] text-center text-[#5c5c70]">14-day free trial • Cancel anytime • No hidden fees</p>
    </form>
  </div>
</div>

<script>
let selectedPlan = 'pro';

function selectPlan(plan) {
  selectedPlan = plan;
  document.getElementById('selectedPlan').value = plan;
  document.querySelectorAll('.plan-btn').forEach(function(btn) {
    btn.classList.remove('border-2', 'border-purple-500/50', 'bg-purple-500/10');
    btn.classList.add('border', 'border-[#252533]');
  });
  var active = document.getElementById('plan' + plan.charAt(0).toUpperCase() + plan.slice(1));
  if (active) {
    active.classList.remove('border', 'border-[#252533]');
    active.classList.add('border-2', 'border-purple-500/50', 'bg-purple-500/10');
  }
}

function openSignup(plan) {
  selectPlan(plan || 'pro');
  document.getElementById('signupModal').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeSignup() {
  document.getElementById('signupModal').classList.add('hidden');
  document.body.style.overflow = '';
}

function submitSignup(e) {
  e.preventDefault();
  var btn = document.getElementById('signupBtn');
  var err = document.getElementById('signupError');
  btn.disabled = true;
  btn.innerHTML = '<div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div> Processing...';
  err.classList.add('hidden');
  
  var fd = new FormData(e.target);
  var data = Object.fromEntries(fd);
  data.plan = selectedPlan;
  
  fetch('/api/signup-checkout', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    if (d.success) {
      window.location.href = d.checkout_url;
    } else {
      err.textContent = d.error || 'Something went wrong';
      err.classList.remove('hidden');
      btn.disabled = false;
      btn.innerHTML = '<span>💳</span> Proceed to Payment';
    }
  })
  .catch(function() {
    err.textContent = 'Network error. Please try again.';
    err.classList.remove('hidden');
    btn.disabled = false;
    btn.innerHTML = '<span>💳</span> Proceed to Payment';
  });
}
</script>

<!-- FOOTER -->
<footer class="py-12 px-4 border-t border-[#1a1a2e]">
  <div class="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-[#5c5c70]">
    <div class="flex items-center gap-2">
      <span>🎙️</span>
      <span class="font-semibold text-white">Diazites</span>
      <span class="ml-2">AI Voice Agents for Business</span>
    </div>
    <div class="flex items-center gap-6">
      <a href="/login" class="hover:text-white transition-colors">Dashboard</a>
      <a href="#" class="hover:text-white transition-colors">Privacy</a>
      <a href="#" class="hover:text-white transition-colors">Terms</a>
    </div>
    <div class="text-xs">© 2026 Diazites. All rights reserved.</div>
  </div>
</footer>

</body>
</html>"""

LANDING_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<!-- GSC_META -->
<script>(function(){fetch('/api/ga-config').then(function(r){return r.json()}).then(function(d){if(d&&d.sc_key){var m=document.createElement('meta');m.name='google-site-verification';m.content=d.sc_key;document.head.appendChild(m)}if(d&&d.ga_id&&d.ga_id.indexOf('G-')===0){var s=document.createElement('script');s.src='https://www.googletagmanager.com/gtag/js?id='+d.ga_id;s.async=true;document.head.appendChild(s);window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config',d.ga_id)}}).catch(function(){})})();</script>
<title>Diazites — AI Voice Agents for Local Businesses</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>@import url('https://fonts.googleapis.com/css2?family=Inter:opsz@14..32&display=swap');
*{font-family:'Inter',sans-serif;margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{background:#0a0a0f;color:#f1f1f5;overflow-x:hidden;width:100%;max-width:100vw;-webkit-overflow-scrolling:touch;overscroll-behavior:none;-webkit-tap-highlight-color:transparent}
:root{--safe-top:env(safe-area-inset-top,0px);--safe-bottom:env(safe-area-inset-bottom,0px);--safe-left:env(safe-area-inset-left,0px);--safe-right:env(safe-area-inset-right,0px)}
section{overflow-x:hidden}nav{overflow-x:hidden}
.gradient-text{background:linear-gradient(135deg,#c084fc,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.gradient-bg{background:linear-gradient(135deg,#a855f7,#ec4899)}
.btn-primary{background:linear-gradient(135deg,#a855f7,#ec4899);color:white;padding:12px 28px;border-radius:10px;font-weight:600;border:none;cursor:pointer;transition:opacity .2s,transform .2s;display:inline-block}
.btn-primary:hover{opacity:.9;transform:translateY(-1px)}
.btn-outline{border:1px solid #3b3b50;color:#f1f1f5;padding:12px 28px;border-radius:10px;font-weight:500;background:transparent;cursor:pointer;transition:all .2s;display:inline-block}
.btn-outline:hover{border-color:#a855f7;color:#c084fc}
.card{background:#12121a;border:1px solid #252533;border-radius:16px;padding:24px;transition:transform .2s,border-color .2s}
.card:hover{transform:translateY(-2px);border-color:#a855f744}
.glass{background:rgba(18,18,26,.7);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px)}
/* Audio player styles */
.audio-card{background:#12121a;border:1px solid #252533;border-radius:16px;padding:20px;transition:all .3s}
.audio-card:hover{border-color:#ec489966;transform:translateY(-2px)}
.audio-card.active{border-color:#a855f7;box-shadow:0 0 30px rgba(168,85,247,.15)}
.play-btn{width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,#a855f7,#ec4899);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:transform .2s}
.play-btn:hover{transform:scale(1.1)}
.play-btn svg{width:20px;height:20px;fill:white;margin-left:2px}
.waveform-bar{width:3px;border-radius:2px;background:#a855f7;transition:height .3s}
/* Floating animation */
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
.float-anim{animation:float 4s ease-in-out infinite}
@keyframes pulse-glow{0%,100%{box-shadow:0 0 20px rgba(168,85,247,.1)}50%{box-shadow:0 0 40px rgba(168,85,247,.25)}}
.pulse-glow{animation:pulse-glow 3s ease-in-out infinite}
/* Call flow animation */
@keyframes ring{0%,100%{transform:scale(1)}20%{transform:scale(1.05)}40%{transform:scale(1)}60%{transform:scale(1.05)}}
.ring-anim{animation:ring 2s ease-in-out infinite}
@keyframes dots{0%,20%{opacity:0}50%{opacity:1}80%,100%{opacity:0}}
.dot-1,.dot-2,.dot-3{display:inline-block;animation:dots 1.5s infinite}
.dot-2{animation-delay:.3s}
.dot-3{animation-delay:.6s}
/* Step connector line */
.step-line{position:absolute;top:40px;left:50%;width:100%;height:2px;background:linear-gradient(90deg,#a855f744,#ec489944);transform:translateX(0)}
@media(max-width:768px){.step-line{display:none}}
/* Mobile nav — hide links, show hamburger */
@media(max-width:768px){
  nav .flex.items-center.gap-4{display:none}
  nav .flex.items-center.gap-4.open{display:flex;flex-direction:column;position:fixed;top:60px;left:0;right:0;background:rgba(10,10,15,.98);border-bottom:1px solid #252533;padding:20px 16px;gap:12px;z-index:100;align-items:stretch}
  nav .flex.items-center.gap-4.open a{text-align:center;padding:10px;border-radius:10px}
  nav .flex.items-center.gap-4.open a:hover{background:rgba(168,85,247,.1)}
}
/* Mobile optimizations */
.mobile-cta-bar{position:fixed;bottom:0;left:0;right:0;z-index:999;background:rgba(10,10,15,.95);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);border-top:1px solid #252533;padding:10px 16px;display:none;gap:8px}
@media(max-width:768px){.mobile-cta-bar{display:flex}.mobile-cta-bar a{flex:1;text-align:center;font-size:13px;padding:10px 8px;border-radius:10px;font-weight:600;text-decoration:none}}
/* Mobile fine-tuning */
@media(max-width:768px){
  .max-w-5xl,.max-w-6xl,.max-w-3xl,.max-w-7xl{padding-left:16px !important;padding-right:16px !important}
  .text-5xl.md\\:text-6xl{font-size:2rem !important;line-height:1.15 !important}
  h1 .gradient-text{display:inline-block}
  .flex.items-center.justify-center.gap-6{flex-direction:column;gap:8px !important;align-items:center}
  .card,.audio-card{padding:16px !important}
  .py-24{padding-top:48px !important;padding-bottom:48px !important}
  .grid.md\\:grid-cols-3.gap-5{gap:12px !important}
  .grid.md\\:grid-cols-4.gap-4{gap:8px !important}
}
</style>

<!-- NAV -->
<nav class="glass flex items-center justify-between max-w-6xl mx-auto px-6 py-4 sticky top-0 z-50" style="border-bottom:1px solid #252533">
<div class="flex items-center gap-2">
<div class="text-2xl">🎙️</div>
<span class="text-lg font-bold gradient-text">Diazites</span>
</div>
<div class="flex items-center gap-4" id="nav-links">
<a href="#demos" class="text-sm text-[#7a7a8e] hover:text-[#c084fc]">Live Demos</a>
<a href="#features" class="text-sm text-[#7a7a8e] hover:text-[#c084fc]">Features</a>
<a href="#industries" class="text-sm text-[#7a7a8e] hover:text-[#c084fc]">Industries</a>
<a href="#signup-form" class="text-sm text-[#7a7a8e] hover:text-[#c084fc]">Pricing</a>
<a href="/signup" class="btn-outline text-sm px-4 py-2">Sign Up</a>
<a href="/login" class="btn-primary text-sm px-5 py-2">Login</a>
</div>
<button onclick="document.getElementById('nav-links').classList.toggle('open');this.innerHTML=this.innerHTML=='☰'?'✕':'☰'" class="md:hidden text-2xl text-[#c084fc] bg-transparent border-none cursor-pointer" style="display:none">☰</button>
<script>if(window.innerWidth<768)document.querySelector('button').style.display='block'</script>
</nav>

<!-- HERO -->
<section class="max-w-6xl mx-auto px-6 pt-16 pb-12 text-center relative">
<div class="absolute inset-0 overflow-hidden pointer-events-none" style="top:-100px">
<div class="absolute top-20 left-1/4 w-96 h-96 rounded-full opacity-[0.04]" style="background:radial-gradient(circle,#a855f7,transparent);transform:translateX(-50%)"></div>
<div class="absolute top-40 right-1/4 w-80 h-80 rounded-full opacity-[0.03]" style="background:radial-gradient(circle,#ec4899,transparent);transform:translateX(50%)"></div>
</div>
<div class="relative">
<h1 class="text-5xl md:text-6xl font-bold mb-4">Never Miss Another<br><span class="gradient-text">Customer Call</span> Again</h1>
<p class="text-lg text-[#7a7a8e] max-w-2xl mx-auto mb-8 leading-relaxed">
Diazites AI voice agents answer calls <strong class="text-[#f1f1f5]">24/7</strong>, qualify customers, schedule appointments, and help local businesses grow <strong class="text-[#f1f1f5]">without adding staff</strong>.
</p>
<div class="flex items-center justify-center gap-4 flex-wrap mb-6">
<a href="#demos" class="btn-primary text-base px-8 py-3 flex items-center gap-2">🎧 Hear My AI Agent</a>
<a href="/login" onclick="if(window.innerWidth<768){event.preventDefault();document.getElementById('signup-form').scrollIntoView({behavior:'smooth'})}" class="btn-outline text-base px-8 py-3">📅 Book a Demo</a>
</div>
<div class="flex items-center justify-center gap-6 text-sm text-[#5c5c70]">
  <span class="flex items-center gap-1.5"><span class="text-green-400">✓</span> No setup fees</span>
  <span class="flex items-center gap-1.5"><span class="text-green-400">✓</span> Cancel anytime</span>
  <span class="flex items-center gap-1.5"><span class="text-green-400">✓</span> 14-day free trial</span>
</div>
</div>
</section>

<!-- TRUSTED BY -->
<section class="max-w-5xl mx-auto px-6 pb-8 text-center">
<p class="text-sm text-[#5c5c70] mb-6 tracking-wider uppercase font-semibold">Trusted By Local Businesses</p>
<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
<div class="card py-5 text-center"><div class="text-lg mb-1">🔧</div><div class="text-sm font-medium">Plumbing Companies</div></div>
<div class="card py-5 text-center"><div class="text-lg mb-1">🦷</div><div class="text-sm font-medium">Dental Offices</div></div>
<div class="card py-5 text-center"><div class="text-lg mb-1">🏡</div><div class="text-sm font-medium">Real Estate Teams</div></div>
<div class="card py-5 text-center"><div class="text-lg mb-1">❄️</div><div class="text-sm font-medium">HVAC Companies</div></div>
</div>
<p class="text-xs text-[#5c5c70] mt-5">Built for: Home Services ✓  Healthcare ✓  Real Estate ✓  Professional Services ✓</p>
</section>

<!-- LIVE VOICE DEMOS -->
<section id="demos" class="max-w-5xl mx-auto px-6 pb-16">
<h2 class="text-3xl font-bold text-center mb-3">🎧 Hear It In <span class="gradient-text">Action</span></h2>
<p class="text-[#7a7a8e] text-center mb-2 max-w-xl mx-auto">Listen to a real customer call handled by Diazites AI — hear how natural, professional, and instant it sounds.</p>
<p class="text-sm text-[#a855f7] text-center mb-10 font-semibold">Click any demo to play</p>

<div class="grid md:grid-cols-3 gap-5">
<!-- Plumber Demo -->
<div class="audio-card" data-demo="plumber" onclick="toggleAudio(this,'/static/audio/demo-plumber.mp3')">
<div class="flex items-start gap-4 mb-3">
<button class="play-btn" id="play-plumber"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></button>
<div class="flex-1">
<div class="flex items-center gap-2 mb-1"><span class="text-lg">🔧</span><span class="font-semibold">Plumber</span><span class="text-[10px] px-2 py-0.5 rounded-full" style="background:#a855f722;color:#c084fc">Emergency</span></div>
<p class="text-xs text-[#7a7a8e]">Burst pipe call — AI triages urgency, captures address, dispatches plumber</p>
</div>
</div>
<div class="flex items-center gap-1" id="waveform-plumber">
<div class="waveform-bar" style="height:12px"></div><div class="waveform-bar" style="height:18px"></div><div class="waveform-bar" style="height:24px"></div><div class="waveform-bar" style="height:32px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:48px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:32px"></div><div class="waveform-bar" style="height:24px"></div><div class="waveform-bar" style="height:18px"></div><div class="waveform-bar" style="height:12px"></div>
</div>
<div class="flex items-center justify-between mt-2">
<span class="text-[10px] text-[#5c5c70]" id="time-plumber">0:00 / 0:20</span>
<span class="text-[10px] text-[#c084fc]" id="status-plumber">▶ Click to play</span>
</div>
</div>

<!-- Dentist Demo -->
<div class="audio-card" data-demo="dentist" onclick="toggleAudio(this,'/static/audio/demo-dentist.mp3')">
<div class="flex items-start gap-4 mb-3">
<button class="play-btn" id="play-dentist"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></button>
<div class="flex-1">
<div class="flex items-center gap-2 mb-1"><span class="text-lg">🦷</span><span class="font-semibold">Dentist</span><span class="text-[10px] px-2 py-0.5 rounded-full" style="background:#22c55e22;color:#4ade80">Booking</span></div>
<p class="text-xs text-[#7a7a8e]">Patient calls — AI checks availability, schedules appointment, sets reminder</p>
</div>
</div>
<div class="flex items-center gap-1" id="waveform-dentist">
<div class="waveform-bar" style="height:14px"></div><div class="waveform-bar" style="height:20px"></div><div class="waveform-bar" style="height:28px"></div><div class="waveform-bar" style="height:36px"></div><div class="waveform-bar" style="height:42px"></div><div class="waveform-bar" style="height:46px"></div><div class="waveform-bar" style="height:48px"></div><div class="waveform-bar" style="height:42px"></div><div class="waveform-bar" style="height:36px"></div><div class="waveform-bar" style="height:28px"></div><div class="waveform-bar" style="height:20px"></div><div class="waveform-bar" style="height:14px"></div>
</div>
<div class="flex items-center justify-between mt-2">
<span class="text-[10px] text-[#5c5c70]" id="time-dentist">0:00 / 0:23</span>
<span class="text-[10px] text-[#c084fc]" id="status-dentist">▶ Click to play</span>
</div>
</div>

<!-- Real Estate Demo -->
<div class="audio-card" data-demo="realestate" onclick="toggleAudio(this,'/static/audio/demo-realestate.mp3')">
<div class="flex items-start gap-4 mb-3">
<button class="play-btn" id="play-realestate"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></button>
<div class="flex-1">
<div class="flex items-center gap-2 mb-1"><span class="text-lg">🏡</span><span class="font-semibold">Real Estate</span><span class="text-[10px] px-2 py-0.5 rounded-full" style="background:#f59e0b22;color:#fbbf24">Qualification</span></div>
<p class="text-xs text-[#7a7a8e]">Property inquiry — AI qualifies buyer, schedules showing, confirms by text</p>
</div>
</div>
<div class="flex items-center gap-1" id="waveform-realestate">
<div class="waveform-bar" style="height:10px"></div><div class="waveform-bar" style="height:16px"></div><div class="waveform-bar" style="height:22px"></div><div class="waveform-bar" style="height:30px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:48px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:30px"></div><div class="waveform-bar" style="height:22px"></div><div class="waveform-bar" style="height:16px"></div><div class="waveform-bar" style="height:10px"></div>
</div>
<div class="flex items-center justify-between mt-2">
<span class="text-[10px] text-[#5c5c70]" id="time-realestate">0:00 / 0:21</span>
<span class="text-[10px] text-[#c084fc]" id="status-realestate">▶ Click to play</span>
</div>
</div>
</div>
</section>

<!-- PREMIUM VOICE SAMPLES -->
<section class="max-w-5xl mx-auto px-6 pb-16">
<h2 class="text-3xl font-bold text-center mb-2">🎙️ Premium <span class="gradient-text">AI Voices</span></h2>
<p class="text-[#7a7a8e] text-center mb-2 max-w-xl mx-auto">Our AI receptionists sound indistinguishable from real humans. Click any voice to hear it live.</p>
<p class="text-sm text-[#a855f7] text-center mb-10 font-semibold">34+ premium ElevenLabs voices — try the top picks</p>
<div class="grid md:grid-cols-4 gap-4">
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('rachel','Hi there! This is Rachel from Diazites. How can I help you today?','rachel')">
<div class="text-3xl mb-2" id="voice-icon-rachel">🎤</div>
<div class="font-semibold text-sm">Rachel</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Female · Warm · Most Popular</div>
<div class="text-xs text-[#c084fc]" id="voice-status-rachel">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('sam','Hey, this is Sam. I handle your calls professionally and make sure every customer feels heard.','sam')">
<div class="text-3xl mb-2" id="voice-icon-sam">🎤</div>
<div class="font-semibold text-sm">Sam</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Warm · Natural</div>
<div class="text-xs text-[#c084fc]" id="voice-status-sam">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('bella','Hello, this is Bella. I handle your calls and make sure every caller is taken care of.','bella')">
<div class="text-3xl mb-2" id="voice-icon-bella">🎤</div>
<div class="font-semibold text-sm">Bella</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Female · Melodic · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-bella">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('josh','Hi, this is Josh. I pre-qualify leads and book appointments so your team can focus on closing.','josh')">
<div class="text-3xl mb-2" id="voice-icon-josh">🎤</div>
<div class="font-semibold text-sm">Josh</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Deep · Professional</div>
<div class="text-xs text-[#c084fc]" id="voice-status-josh">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('emma','Hi, I am Emma. Welcome to Diazites. I answer calls and help customers just like a real receptionist.','emma')">
<div class="text-3xl mb-2" id="voice-icon-emma">🎤</div>
<div class="font-semibold text-sm">Emma</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Female · Friendly · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-emma">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('arnold','Good day, this is Arnold. I handle incoming calls, qualify your leads, and book appointments automatically.','arnold')">
<div class="text-3xl mb-2" id="voice-icon-arnold">🎤</div>
<div class="font-semibold text-sm">Arnold</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Authoritative · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-arnold">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('patrick','Hey there! I am Patrick. I answer calls around the clock so you never miss a lead.','patrick')">
<div class="text-3xl mb-2" id="voice-icon-patrick">🎤</div>
<div class="font-semibold text-sm">Patrick</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Professional · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-patrick">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('domi','Hi, I am Domi. I make sure every caller gets a warm, professional greeting and the help they need.','domi')">
<div class="text-3xl mb-2" id="voice-icon-domi">🎤</div>
<div class="font-semibold text-sm">Domi</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Female · Friendly · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-domi">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('pNInz6obpgDQGcFmaJgB','Hi, this is Adam. I answer every call, qualify every lead, and book appointments for your business.','pNInz6obpgDQGcFmaJgB')">
<div class="text-3xl mb-2" id="voice-icon-pNInz6obpgDQGcFmaJgB">🎤</div>
<div class="font-semibold text-sm">Adam</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Confident · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-pNInz6obpgDQGcFmaJgB">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('onwK4e9ZLuTAKqWW03F9','Hello, this is Daniel. I handle your calls professionally so no customer is ever left waiting.','onwK4e9ZLuTAKqWW03F9')">
<div class="text-3xl mb-2" id="voice-icon-onwK4e9ZLuTAKqWW03F9">🎤</div>
<div class="font-semibold text-sm">Daniel</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Steady · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-onwK4e9ZLuTAKqWW03F9">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('IKne3meq5aSn9XLyUdCD','Hey, this is Charlie. I pick up every call and make sure you never miss an opportunity.','IKne3meq5aSn9XLyUdCD')">
<div class="text-3xl mb-2" id="voice-icon-IKne3meq5aSn9XLyUdCD">🎤</div>
<div class="font-semibold text-sm">Charlie</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Deep · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-IKne3meq5aSn9XLyUdCD">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('cjVigY5qzO86Huf0OWal','Hi there, this is Eric. I answer calls around the clock and book appointments on the spot.','cjVigY5qzO86Huf0OWal')">
<div class="text-3xl mb-2" id="voice-icon-cjVigY5qzO86Huf0OWal">🎤</div>
<div class="font-semibold text-sm">Eric</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Smooth · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-cjVigY5qzO86Huf0OWal">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('JBFqnCBsd6RMkjVDRZzb','Good day, this is George. Let me take care of your calls so you can focus on your customers.','JBFqnCBsd6RMkjVDRZzb')">
<div class="text-3xl mb-2" id="voice-icon-JBFqnCBsd6RMkjVDRZzb">🎤</div>
<div class="font-semibold text-sm">George</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Captivating · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-JBFqnCBsd6RMkjVDRZzb">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('TX3LPaxmHKxFdv7VOQHJ','Whats up, this is Liam. I never miss a call and I make sure every lead gets followed up.','TX3LPaxmHKxFdv7VOQHJ')">
<div class="text-3xl mb-2" id="voice-icon-TX3LPaxmHKxFdv7VOQHJ">🎤</div>
<div class="font-semibold text-sm">Liam</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Energetic · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-TX3LPaxmHKxFdv7VOQHJ">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('bIHbv24MWmeRgasZH58o','Hi, this is Will. I keep things simple: answer, qualify, and book. Thats it.','bIHbv24MWmeRgasZH58o')">
<div class="text-3xl mb-2" id="voice-icon-bIHbv24MWmeRgasZH58o">🎤</div>
<div class="font-semibold text-sm">Will</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Relaxed · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-bIHbv24MWmeRgasZH58o">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('iP95p4xoKVk53GoZ742B','Hey, Im Chris. Your callers get a friendly, professional voice every single time.','iP95p4xoKVk53GoZ742B')">
<div class="text-3xl mb-2" id="voice-icon-iP95p4xoKVk53GoZ742B">🎤</div>
<div class="font-semibold text-sm">Chris</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Charming · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-iP95p4xoKVk53GoZ742B">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('XrExE9yKIg1WjnnlVkGX','Hello, this is Matilda. Welcome to the business. How may I assist you today?','XrExE9yKIg1WjnnlVkGX')">
<div class="text-3xl mb-2" id="voice-icon-XrExE9yKIg1WjnnlVkGX">🎤</div>
<div class="font-semibold text-sm">Matilda</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Female · Professional · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-XrExE9yKIg1WjnnlVkGX">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('EXAVITQu4vr4xnSDxMaL','Hi, Im Sarah. Dont worry about missed calls anymore. Im here to help every customer.','EXAVITQu4vr4xnSDxMaL')">
<div class="text-3xl mb-2" id="voice-icon-EXAVITQu4vr4xnSDxMaL">🎤</div>
<div class="font-semibold text-sm">Sarah</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Female · Reassuring · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-EXAVITQu4vr4xnSDxMaL">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('N2lVS1w4EtoT3dr4eOWO','Hey, this is Callum. I make sure every caller gets a fast, friendly answer.','N2lVS1w4EtoT3dr4eOWO')">
<div class="text-3xl mb-2" id="voice-icon-N2lVS1w4EtoT3dr4eOWO">🎤</div>
<div class="font-semibold text-sm">Callum</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Husky · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-N2lVS1w4EtoT3dr4eOWO">▶ Click to play</div>
</div>
<div class="audio-card text-center cursor-pointer" onclick="playVoiceSample('nPczCjzI2devNBz1zQrb','Good day, this is Brian. I answer every call with a professional tone and follow up on every lead.','nPczCjzI2devNBz1zQrb')">
<div class="text-3xl mb-2" id="voice-icon-nPczCjzI2devNBz1zQrb">🎤</div>
<div class="font-semibold text-sm">Brian</div>
<div class="text-[10px] text-[#7a7a8e] mb-2">Male · Resonant · Premium</div>
<div class="text-xs text-[#c084fc]" id="voice-status-nPczCjzI2devNBz1zQrb">▶ Click to play</div>
</div>
</div>
</section>

<audio id="voicePreviewPlayer" preload="none" style="display:none"></audio>

<script>
function playVoiceSample(v,t,s){
var p=document.getElementById('voicePreviewPlayer');
document.querySelectorAll('[id^=voice-icon-]').forEach(function(e){e.textContent='🎤'});
document.querySelectorAll('[id^=voice-status-]').forEach(function(e){e.textContent='▶ Click to play'});
document.getElementById('voice-icon-'+s).textContent='⏳';
document.getElementById('voice-status-'+s).textContent='🔊 Loading...';
p.src='/api/test-voice?voice_id='+encodeURIComponent(v)+'&text='+encodeURIComponent(t)+'&speed=1.0&t='+Date.now();
p.onended=function(){document.getElementById('voice-icon-'+s).textContent='🎤';document.getElementById('voice-status-'+s).textContent='▶ Click to play'};
p.load();
p.play().then(function(){document.getElementById('voice-status-'+s).textContent='🔊 Playing...'}).catch(function(e){document.getElementById('voice-icon-'+s).textContent='❌';document.getElementById('voice-status-'+s).textContent='Click again: '+e.message.slice(0,20)});
}
</script>

<!-- HOW IT WORKS -->
<section class="max-w-5xl mx-auto px-6 pb-16">
<h2 class="text-3xl font-bold text-center mb-12">How It <span class="gradient-text">Works</span></h2>
<div class="grid md:grid-cols-4 gap-6 relative">
<div class="card text-center py-8 relative z-10">
<div class="text-4xl mb-3 ring-anim">📞</div>
<div class="text-xs text-[#a855f7] font-bold mb-1">STEP 1</div>
<h3 class="font-semibold mb-1">Customer Calls</h3>
<p class="text-xs text-[#7a7a8e]">Your AI agent answers instantly, 24/7</p>
</div>
<div class="card text-center py-8 relative z-10">
<div class="text-4xl mb-3 float-anim">🤖</div>
<div class="text-xs text-[#a855f7] font-bold mb-1">STEP 2</div>
<h3 class="font-semibold mb-1">AI Qualifies Lead</h3>
<p class="text-xs text-[#7a7a8e]">Natural conversation captures details & intent</p>
</div>
<div class="card text-center py-8 relative z-10">
<div class="text-4xl mb-3 float-anim" style="animation-delay:1s">📅</div>
<div class="text-xs text-[#a855f7] font-bold mb-1">STEP 3</div>
<h3 class="font-semibold mb-1">Books Appointment</h3>
<p class="text-xs text-[#7a7a8e]">Auto-schedules and sends confirmation</p>
</div>
<div class="card text-center py-8 relative z-10">
<div class="text-4xl mb-3 float-anim" style="animation-delay:2s">📊</div>
<div class="text-xs text-[#a855f7] font-bold mb-1">STEP 4</div>
<h3 class="font-semibold mb-1">Dashboard Review</h3>
<p class="text-xs text-[#7a7a8e]">View calls, leads, and analytics in real-time</p>
</div>
</div>
</section>

<!-- STATS -->
<section class="max-w-5xl mx-auto px-6 pb-16">
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
<div class="card py-8" style="border-color:#a855f744"><div class="text-4xl font-bold gradient-text">24/7</div><div class="text-sm text-[#7a7a8e] mt-1">Always-On Availability</div></div>
<div class="card py-8" style="border-color:#a855f744"><div class="text-4xl font-bold gradient-text">60%</div><div class="text-sm text-[#7a7a8e] mt-1">More Leads Captured</div></div>
<div class="card py-8" style="border-color:#a855f744"><div class="text-4xl font-bold gradient-text">10+</div><div class="text-sm text-[#7a7a8e] mt-1">Industries Served</div></div>
<div class="card py-8" style="border-color:#a855f744"><div class="text-4xl font-bold gradient-text">99%</div><div class="text-sm text-[#7a7a8e] mt-1">Call Answer Rate</div></div>
</div>
</section>

<!-- FEATURES -->
<section id="features" class="max-w-5xl mx-auto px-6 pb-16">
<h2 class="text-3xl font-bold text-center mb-10">Everything You <span class="gradient-text">Need</span></h2>
<div class="grid md:grid-cols-3 gap-5">
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-500/20 to-purple-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">🤖</div>
<h3 class="font-semibold mb-1">Smart AI Receptionist</h3><p class="text-sm text-[#7a7a8e]">Natural conversations that qualify leads and book calls automatically. Never miss a business opportunity.</p>
</div>
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-pink-500/20 to-pink-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">📞</div>
<h3 class="font-semibold mb-1">Call Forwarding</h3><p class="text-sm text-[#7a7a8e]">Route calls to your personal line during business hours. AI handles after-hours and overflow automatically.</p>
</div>
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-cyan-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">📊</div>
<h3 class="font-semibold mb-1">Campaign Dashboard</h3><p class="text-sm text-[#7a7a8e]">Start, pause, and monitor outbound campaigns with real-time analytics and performance metrics.</p>
</div>
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-500/20 to-amber-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">📝</div>
<h3 class="font-semibold mb-1">Custom Scripts</h3><p class="text-sm text-[#7a7a8e]">Tailor your AI agent's script and knowledge base to your exact business needs and brand voice.</p>
</div>
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-green-500/20 to-green-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">🌎</div>
<h3 class="font-semibold mb-1">Multi-Language</h3><p class="text-sm text-[#7a7a8e]">Speak with customers in English, Spanish, and more — naturally, with full context switching.</p>
</div>
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-red-500/20 to-red-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">📱</div>
<h3 class="font-semibold mb-1">SMS Follow-Ups</h3><p class="text-sm text-[#7a7a8e]">Auto-send appointment reminders, missed-call texts, and follow-up messages to warm leads.</p>
</div>
</div>
</section>

<!-- WHY DIAZITES -->
<section class="max-w-5xl mx-auto px-6 pb-16">
<div class="glass rounded-2xl p-10 text-center relative overflow-hidden">
<div class="absolute inset-0 bg-gradient-to-r from-purple-500/5 via-transparent to-cyan-500/5"></div>
<div class="relative z-10">
<span class="text-sm font-semibold text-purple-400 tracking-widest uppercase">About</span>
<h2 class="text-3xl font-bold mt-3 mb-5">Why <span class="gradient-text">Diazites</span>?</h2>
<p class="text-[#7a7a8e] max-w-2xl mx-auto leading-relaxed mb-6">Diazites helps small businesses compete with enterprise-level customer service through affordable AI-powered communication tools. We don't just build AI agents — we help local businesses <strong class="text-[#f1f1f5]">stop losing customers from missed calls</strong>.</p>
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
<div><div class="text-2xl mb-1">🎯</div><div class="text-sm font-semibold">Enterprise AI</div><div class="text-xs text-[#5c5c70]">Small business prices</div></div>
<div><div class="text-2xl mb-1">⚡</div><div class="text-sm font-semibold">5-Min Setup</div><div class="text-xs text-[#5c5c70]">No technical skills needed</div></div>
<div><div class="text-2xl mb-1">🔒</div><div class="text-sm font-semibold">Bank-Grade</div><div class="text-xs text-[#5c5c70]">Encrypted &amp; compliant</div></div>
<div><div class="text-2xl mb-1">💎</div><div class="text-sm font-semibold">White-Label</div><div class="text-xs text-[#5c5c70]">Your brand, our tech</div></div>
</div>
</div>
</div>
</section>

<!-- INDUSTRIES -->
<section id="industries" class="max-w-5xl mx-auto px-6 pb-16">
<h2 class="text-3xl font-bold text-center mb-3">Built for <span class="gradient-text">Local Businesses</span></h2>
<p class="text-[#7a7a8e] text-center text-sm mb-10 max-w-xl mx-auto">Industry-specific AI voice agents tailored to how your business works</p>
<div class="grid md:grid-cols-2 gap-4">
<div class="card p-5 flex items-start gap-4 glow-border">
<div class="text-3xl flex-shrink-0">🔧</div>
<div><h4 class="font-bold text-base">AI Receptionist For Plumbers</h4>
<p class="text-xs text-[#7a7a8e] mt-0.5">Never lose emergency calls after hours. AI triages burst pipes, captures addresses, dispatches your team instantly.</p></div>
</div>
<div class="card p-5 flex items-start gap-4 glow-border">
<div class="text-3xl flex-shrink-0">🦷</div>
<div><h4 class="font-bold text-base">AI Receptionist For Dentists</h4>
<p class="text-xs text-[#7a7a8e] mt-0.5">Schedule appointments while your team treats patients. Reduce no-shows with automated reminders.</p></div>
</div>
<div class="card p-5 flex items-start gap-4 glow-border">
<div class="text-3xl flex-shrink-0">🏡</div>
<div><h4 class="font-bold text-base">AI Receptionist For Real Estate</h4>
<p class="text-xs text-[#7a7a8e] mt-0.5">Capture every buyer inquiry instantly. Qualify leads, schedule showings, follow up automatically.</p></div>
</div>
<div class="card p-5 flex items-start gap-4 glow-border">
<div class="text-3xl flex-shrink-0">❄️</div>
<div><h4 class="font-bold text-base">AI Receptionist For HVAC</h4>
<p class="text-xs text-[#7a7a8e] mt-0.5">Handle after-hours emergencies. Dispatch calls when temperatures spike, book maintenance visits automatically.</p></div>
</div>
<div class="card p-5 flex items-start gap-4 glow-border">
<div class="text-3xl flex-shrink-0">⚖️</div>
<div><h4 class="font-bold text-base">AI Receptionist For Lawyers</h4>
<p class="text-xs text-[#7a7a8e] mt-0.5">Qualify leads automatically. Book consultations, collect case details, never miss a potential client call.</p></div>
</div>
<div class="card p-5 flex items-start gap-4 glow-border">
<div class="text-3xl flex-shrink-0">🚗</div>
<div><h4 class="font-bold text-base">AI Receptionist For Auto Shops</h4>
<p class="text-xs text-[#7a7a8e] mt-0.5">Book service appointments overnight. Answer customer questions about pricing, availability, and estimated times.</p></div>
</div>
</div>
</section>

<!-- AI RECEPTIONISTS FOR ANY INDUSTRY -->
<section class="max-w-5xl mx-auto px-6 pb-16">
<h2 class="text-3xl font-bold text-center mb-3">AI Receptionists for <span class="gradient-text">Any Industry</span></h2>
<p class="text-[#7a7a8e] text-center text-sm mb-10 max-w-2xl mx-auto">Whether you're a small business, growing company, or enterprise, your AI receptionist is trained specifically for your operations.</p>
<div class="grid md:grid-cols-3 gap-5">
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-500/20 to-purple-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">🏢</div>
<h3 class="font-semibold mb-1">Customized for Your Business</h3>
<p class="text-sm text-[#7a7a8e]">Your AI receptionist is trained on your services, pricing, FAQs, policies, and workflows—so every caller gets accurate, professional answers.</p>
</div>
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-pink-500/20 to-pink-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">📞</div>
<h3 class="font-semibold mb-1">Never Miss Another Call</h3>
<p class="text-sm text-[#7a7a8e]">Answer every call 24/7, qualify leads, schedule appointments, transfer urgent calls, and capture every opportunity.</p>
</div>
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-cyan-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">📅</div>
<h3 class="font-semibold mb-1">Smart Scheduling</h3>
<p class="text-sm text-[#7a7a8e]">Connect with your calendar to book appointments, meetings, consultations, demos, estimates, or service calls automatically.</p>
</div>
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-500/20 to-amber-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">💬</div>
<h3 class="font-semibold mb-1">Instant Customer Support</h3>
<p class="text-sm text-[#7a7a8e]">Answer common questions, provide updates, collect information, and route customers to the right department.</p>
</div>
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-green-500/20 to-green-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">🚀</div>
<h3 class="font-semibold mb-1">Lead Qualification & Sales</h3>
<p class="text-sm text-[#7a7a8e]">Qualify prospects, collect contact information, answer objections, and move leads through your sales process automatically.</p>
</div>
<div class="card p-5 text-center">
<div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-red-500/20 to-red-500/5 flex items-center justify-center mx-auto mb-4 text-2xl">⚙️</div>
<h3 class="font-semibold mb-1">Built Around Your Workflow</h3>
<p class="text-sm text-[#7a7a8e]">Every AI receptionist is customized for your business processes, CRM, scheduling software, and communication tools.</p>
</div>
</div>
</section>

<!-- TESTIMONIALS -->
<section class="max-w-5xl mx-auto px-6 pb-16">
<h2 class="text-3xl font-bold text-center mb-3">Trusted by <span class="gradient-text">Business Owners</span></h2>
<p class="text-[#7a7a8e] text-center text-sm mb-10">Real results from real businesses using Diazites AI</p>
<div class="grid md:grid-cols-3 gap-5">
<div class="card p-6 relative">
<div class="text-4xl text-purple-500/20 absolute top-4 right-4">"</div>
<p class="text-sm text-[#7a7a8e] mb-4 italic relative z-10">"Diazites helped us stop losing after-hours calls and increased booked appointments by 40% in the first month."</p>
<div class="flex items-center gap-3 border-t border-[#252533] pt-4">
<div class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-sm font-bold">M</div>
<div><div class="text-sm font-semibold">Mike R.</div><div class="text-xs text-[#5c5c70]">Plumbing Contractor, Miami</div></div>
</div>
</div>
<div class="card p-6 relative">
<div class="text-4xl text-purple-500/20 absolute top-4 right-4">"</div>
<p class="text-sm text-[#7a7a8e] mb-4 italic relative z-10">"Our patients love that someone answers immediately. Appointments booked through the AI have cut our admin workload by hours each day."</p>
<div class="flex items-center gap-3 border-t border-[#252533] pt-4">
<div class="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-500 to-purple-500 flex items-center justify-center text-sm font-bold">S</div>
<div><div class="text-sm font-semibold">Dr. Sarah L.</div><div class="text-xs text-[#5c5c70]">Dental Practice, Dallas</div></div>
</div>
</div>
<div class="card p-6 relative">
<div class="text-4xl text-purple-500/20 absolute top-4 right-4">"</div>
<p class="text-sm text-[#7a7a8e] mb-4 italic relative z-10">"I was skeptical about AI taking calls, but it sounds just like a real person. We haven't missed a single buyer inquiry since going live."</p>
<div class="flex items-center gap-3 border-t border-[#252533] pt-4">
<div class="w-10 h-10 rounded-full bg-gradient-to-br from-pink-500 to-amber-500 flex items-center justify-center text-sm font-bold">J</div>
<div><div class="text-sm font-semibold">James K.</div><div class="text-xs text-[#5c5c70]">Real Estate Agent, Phoenix</div></div>
</div>
</div>
</div>
</section>

<!-- PRICING STARTING POINT -->
<section class="max-w-3xl mx-auto px-6 pb-8 text-center">
<div class="inline-flex items-center gap-2 glass rounded-full px-6 py-3 text-sm">
<span class="text-purple-400">💰</span>
<span class="text-[#f1f1f5] font-semibold">Plans Starting At</span>
<span class="gradient-text text-lg font-bold">$97</span>
<span class="text-[#5c5c70]">/month</span>
<span class="text-[#5c5c70]">—</span>
<a href="#signup-form" class="text-purple-400 hover:text-purple-300 font-semibold">See Plans →</a>
</div>
</section>

<!-- PRICING TABLES -->
<section class="max-w-5xl mx-auto px-6 pb-8">
<div class="grid md:grid-cols-3 gap-5">

<!-- Starter -->
<div class="card p-6 text-center glow-border">
<h3 class="font-bold text-xl mb-1">Starter</h3>
<p class="text-xs text-[#64748b] mb-3">Perfect for small businesses</p>
<div class="text-4xl font-black mb-1 gradient-text">$97</div>
<p class="text-sm text-[#5c5c70] mb-4">per month</p>
<ul class="text-left space-y-2 text-sm mb-6">
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> 1 AI Voice Agent</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> 1 Phone Number</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> <strong>250</strong> Call Minutes</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> Booking & Analytics</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> Email Support</li>
</ul>
<a href="#signup-form" class="btn-outline text-sm w-full block text-center py-2.5 rounded-xl">Get Started</a>
</div>

<!-- Professional (Featured) -->
<div class="card p-6 text-center relative" style="border-color:#a855f744;background:linear-gradient(135deg,rgba(168,85,247,0.06),rgba(236,72,153,0.06))">
<div class="absolute -top-3 left-1/2 -translate-x-1/2 gradient-bg text-white text-xs font-bold px-4 py-1 rounded-full">🔥 Most Popular</div>
<h3 class="font-bold text-xl mb-1 mt-1">Professional</h3>
<p class="text-xs text-[#64748b] mb-3">Best for growing businesses</p>
<div class="text-4xl font-black mb-1 gradient-text">$197</div>
<p class="text-sm text-[#5c5c70] mb-4">per month</p>
<ul class="text-left space-y-2 text-sm mb-6">
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> 2 AI Voice Agents</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> 2 Phone Numbers</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> <strong>1,000</strong> Call Minutes</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> Outbound Campaigns</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> SMS & Calendar</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> Priority Support</li>
</ul>
<a href="#signup-form" class="btn-primary text-sm w-full block text-center py-2.5 rounded-xl">🎯 Start Free Trial</a>
</div>

<!-- Enterprise -->
<div class="card p-6 text-center glow-border">
<h3 class="font-bold text-xl mb-1">Enterprise</h3>
<p class="text-xs text-[#64748b] mb-3">For agencies & high-volume</p>
<div class="text-4xl font-black mb-1 gradient-text">Custom</div>
<p class="text-sm text-[#5c5c70] mb-4">tailored pricing</p>
<ul class="text-left space-y-2 text-sm mb-6">
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> Up to 5 AI Agents</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> Up to 5 Phone Numbers</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> Unlimited Minutes</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> Custom Integrations</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> API & White-Label</li>
<li class="flex items-center gap-2"><span class="text-green-400">✓</span> Dedicated Manager</li>
</ul>
<a href="/login" class="btn-outline text-sm w-full block text-center py-2.5 rounded-xl">Contact Us</a>
</div>

</div>
</section>

<!-- CTA / SIGNUP -->
<section id="signup-form" class="max-w-3xl mx-auto px-6 pb-20 text-center">
<div class="grid md:grid-cols-2 gap-6">
<div class="card py-12 px-6 pulse-glow" style="border-color:#a855f744">
<div class="text-5xl mb-5">🚀</div>
<h2 class="text-2xl font-bold gradient-text mb-3">Existing Client?</h2>
<p class="text-[#7a7a8e] mb-6 max-w-sm mx-auto text-sm">Log in with your Business ID to manage your dashboard, view analytics, and configure your AI voice agent.</p>
<a href="/login" class="btn-primary text-base px-10 py-3">Login to Dashboard</a>
</div>

<div class="card py-12 px-6" style="border-color:#252533">
<div class="text-5xl mb-5">✨</div>
<h2 class="text-2xl font-bold gradient-text mb-3">New Business?</h2>
<p class="text-[#7a7a8e] mb-6 max-w-sm mx-auto text-sm">Sign up in seconds and get your AI voice agent running today. No credit card required to start.</p>
<form id="signupFormLanding" class="space-y-3 text-left" onsubmit="return submitLandingSignup(event)">
<div>
<label class="text-xs text-[#7a7a8e] block mb-1">Business Name *</label>
<input type="text" id="sBizName" required class="w-full bg-[#1a1a26] border border-[#252533] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#a855f7]">
</div>
<div>
<label class="text-xs text-[#7a7a8e] block mb-1">Email *</label>
<input type="email" id="sEmail" required class="w-full bg-[#1a1a26] border border-[#252533] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#a855f7]">
</div>
<div>
<label class="text-xs text-[#7a7a8e] block mb-1">Phone</label>
<input type="tel" id="sPhone" class="w-full bg-[#1a1a26] border border-[#252533] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#a855f7]">
</div>
<div>
<label class="text-xs text-[#7a7a8e] block mb-1">Industry</label>
<select id="sIndustry" class="w-full bg-[#1a1a26] border border-[#252533] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#a855f7]">
<option value="plumber">Plumber</option>
<option value="hvac">HVAC</option>
<option value="electrician">Electrician</option>
<option value="roofing">Roofing</option>
<option value="painter">Painter</option>
<option value="landscaper">Landscaper</option>
<option value="cleaning">Cleaning</option>
<option value="auto">Auto Mechanic</option>
<option value="realestate">Real Estate</option>
<option value="dentist">Dentist</option>
<option value="general">General Business</option>
</select>
</div>
<button type="submit" id="sBtn" class="btn-primary w-full text-sm py-3">🚀 Sign Up Free</button>
<div id="sResult" class="hidden"></div>
</form>
</div>
</div>
</section>

<!-- DEMO + ROI -->
<section id="try-it-live" class="max-w-6xl mx-auto px-6 py-20">
<h2 class="text-3xl md:text-4xl font-extrabold text-center mb-3 gradient-text">Try It Live — It's a Phone Call</h2>
<p class="text-center text-[#7a7a8e] mb-10 text-sm">Call the demo line. Maria answers like a real receptionist — no forms, no videos, just call.</p>
<div class="grid md:grid-cols-2 gap-6">
<div class="card p-8 text-center" style="border:1px solid #252533;background:#0c0c18;border-radius:16px">
<div class="text-5xl mb-4">📞</div>
<h3 class="text-xl font-bold mb-2">Diazites Demo Line</h3>
<p class="text-[#7a7a8e] text-sm mb-5">"Hi, you've reached the Diazites demo line — I'm Pablo, the receptionist!"</p>
<a href="tel:+17868084099" class="btn-primary inline-block py-4 px-8 text-lg rounded-2xl">📱 (786) 808-4099</a>
<p class="text-xs text-[#5c5c70] mt-5">Works with any phone. Try asking: <i>"What can you do for my roofing business?"</i> — he speaks <b style="color:#c084fc">español</b>, português, français & more 🌎</p>
</div>
<div class="card p-8" style="border:1px solid #252533;background:#0c0c18;border-radius:16px">
<h3 class="text-xl font-bold mb-1">Missed-Call ROI Calculator</h3>
<p class="text-xs text-[#7a7a8e] mb-6">How much are missed calls costing your business every month?</p>
<div class="space-y-4 text-left">
<div><label class="text-xs text-[#7a7a8e] block mb-1">Missed calls per day</label><input id="roiCalls" type="number" value="5" min="0" style="width:100%;background:#12121a;border:1px solid #252533;color:#fff;border-radius:10px;padding:10px 12px;font-size:14px"></div>
<div><label class="text-xs text-[#7a7a8e] block mb-1">Average job value ($)</label><input id="roiValue" type="number" value="850" min="0" style="width:100%;background:#12121a;border:1px solid #252533;color:#fff;border-radius:10px;padding:10px 12px;font-size:14px"></div>
<div><label class="text-xs text-[#7a7a8e] block mb-1">Close rate on answered calls (%)</label><input id="roiClose" type="number" value="30" min="0" max="100" style="width:100%;background:#12121a;border:1px solid #252533;color:#fff;border-radius:10px;padding:10px 12px;font-size:14px"></div>
<div style="background:#12121a;border-radius:12px;padding:16px;text-align:center">
<div class="text-xs text-[#7a7a8e] mb-1">Missed revenue every month</div>
<div id="roiResult" class="text-3xl font-extrabold" style="color:#4ade80">$25,500</div>
<div class="text-xs text-[#5c5c70] mt-2">An AI agent at <b style="color:#c084fc">$197/mo</b> helps you recover that</div>
</div>
</div>
</div>
</div>
</section>
<script>
function roiCalc(){var c=parseFloat(document.getElementById('roiCalls').value)||0,v=parseFloat(document.getElementById('roiValue').value)||0,cl=(parseFloat(document.getElementById('roiClose').value)||0)/100;document.getElementById('roiResult').textContent='$'+Math.round(c*30*v*cl).toLocaleString()}
document.getElementById('roiCalls').addEventListener('input',roiCalc);
document.getElementById('roiValue').addEventListener('input',roiCalc);
document.getElementById('roiClose').addEventListener('input',roiCalc);
roiCalc();
</script>

<!-- FOOTER -->
<footer class="border-t border-[#252533] py-8 text-center text-xs text-[#5c5c70]">
<div class="flex items-center justify-center gap-2 mb-3"><div class="text-lg">🎙️</div><span class="text-sm gradient-text font-bold">Diazites</span></div>
<div class="flex justify-center gap-4 mb-3 text-xs">
<a href="/signup" class="text-[#818cf8] hover:text-[#a855f7] font-medium">Start Free Trial</a>
<a href="/affiliate" class="text-[#818cf8] hover:text-[#a855f7] font-medium">💸 Affiliates — Earn $50/Signup</a>
<a href="/privacy" class="hover:text-[#c084fc]">Privacy Policy</a>
<a href="/terms" class="hover:text-[#c084fc]">Terms of Service</a>
<a href="/refund" class="hover:text-[#c084fc]">Refund Policy</a>
</div>
<p>© 2026 Diazites. AI-powered voice agents for local businesses.</p>
</footer>

<script>
// Audio player
let currentAudio = null;
let currentCard = null;

function toggleAudio(card, src) {
    const demo = card.dataset.demo;
    const playBtn = document.getElementById('play-' + demo);
    const timeEl = document.getElementById('time-' + demo);
    const statusEl = document.getElementById('status-' + demo);
    const waveform = document.getElementById('waveform-' + demo);
    const bars = waveform ? waveform.querySelectorAll('.waveform-bar') : [];

    if (currentAudio && currentAudio.dataset.demo === demo) {
        if (!currentAudio.paused) {
            currentAudio.pause();
            playBtn.innerHTML = '<svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>';
            statusEl.textContent = '⏸ Paused';
            card.classList.remove('active');
            return;
        } else {
            currentAudio.play();
            playBtn.innerHTML = '<svg viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';
            statusEl.textContent = '▶ Playing...';
            card.classList.add('active');
            return;
        }
    }

    // Stop previous
    if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
        const oldDemo = currentAudio.dataset.demo;
        const oldBtn = document.getElementById('play-' + oldDemo);
        const oldStatus = document.getElementById('status-' + oldDemo);
        const oldCard = document.querySelector('.audio-card[data-demo="' + oldDemo + '"]');
        if (oldBtn) oldBtn.innerHTML = '<svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>';
        if (oldStatus) oldStatus.textContent = '▶ Click to play';
        if (oldCard) oldCard.classList.remove('active');
    }

    // Create and play new
    const audio = new Audio(src);
    audio.dataset.demo = demo;
    currentAudio = audio;
    currentCard = card;

    audio.addEventListener('timeupdate', function() {
        const mins = Math.floor(this.currentTime / 60);
        const secs = Math.floor(this.currentTime % 60);
        const tmins = Math.floor(this.duration / 60);
        const tsecs = Math.floor(this.duration % 60);
        timeEl.textContent = mins + ':' + String(secs).padStart(2,'0') + ' / ' + tmins + ':' + String(tsecs).padStart(2,'0');
        // Waveform animation
        const progress = this.currentTime / (this.duration || 1);
        if (bars.length) {
            bars.forEach((bar, i) => {
                const idx = i / bars.length;
                const amp = 10 + 38 * (1 - Math.abs(idx - progress) * 2);
                bar.style.height = Math.min(48, Math.max(8, amp)) + 'px';
                bar.style.background = idx <= progress ? 'linear-gradient(180deg,#a855f7,#ec4899)' : '#a855f7';
            });
        }
    });

    audio.addEventListener('ended', function() {
        playBtn.innerHTML = '<svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>';
        statusEl.textContent = '✓ Done';
        card.classList.remove('active');
        currentAudio = null;
        currentCard = null;
    });

    audio.play();
    playBtn.innerHTML = '<svg viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';
    statusEl.textContent = '▶ Playing...';
    card.classList.add('active');
}

// Landing page signup
function submitLandingSignup(e) {
    e.preventDefault();
    var btn = document.getElementById('sBtn');
    var result = document.getElementById('sResult');
    btn.disabled = true; btn.textContent = '⏳ Creating your account...';
    result.classList.add('hidden');
    fetch('/api/signup-stripe', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: document.getElementById('sBizName').value.trim(),
            email: document.getElementById('sEmail').value.trim(),
            phone: document.getElementById('sPhone').value.trim(),
            industry: document.getElementById('sIndustry').value
        })
    }).then(function(r) { return r.json(); })
    .then(function(d) {
        btn.disabled = false; btn.textContent = '🚀 Sign Up Free';
        if (d.success) {
            if (d.checkout_url) {
                // Redirect to Stripe checkout to set up payment (3-day trial, no charge yet)
                window.location.href = d.checkout_url;
            } else {
                // Show business ID and trial info
                result.className = 'mt-3 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-xs text-green-400';
                result.innerHTML = '<strong>✅ Business created!</strong><br>🎁 3-day free trial active!<br>Your Business ID: <code class="font-mono bg-[#0a0a0f] px-2 py-0.5 rounded">' + d.business_id + '</code><br><br><div class="text-yellow-400 text-xs mb-2">⚠️ ' + (d.message || 'Set up billing to continue after trial.') + '</div><a href="/login" class="btn-primary text-xs px-4 py-2 inline-block">🔑 Login Now</a>';
                result.classList.remove('hidden');
            }
        } else {
            result.className = 'mt-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400';
            result.innerHTML = '❌ ' + (d.error || 'Failed to create business');
            result.classList.remove('hidden');
        }
    }).catch(function(err) {
        btn.disabled = false; btn.textContent = '🚀 Sign Up Free';
        result.className = 'mt-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400';
        result.innerHTML = '❌ Network error. Please try again.';
        result.classList.remove('hidden');
    });
    return false;
}

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) target.scrollIntoView({behavior:'smooth'});
    });
});
</script>

<!-- Mobile Sticky CTA -->
<div class="mobile-cta-bar">
<a href="#demos" class="btn-primary text-sm" style="background:linear-gradient(135deg,#a855f7,#ec4899);color:white">🎧 Hear AI Agent</a>
<a href="/login" class="btn-outline text-sm" style="border:1px solid #3b3b50;color:#f1f1f5">📅 Book Demo</a>
</div>

</body></html>"""

LOGIN_FORM = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diazites Login</title><script src="https://cdn.tailwindcss.com"></script>
<style>@import url('https://fonts.googleapis.com/css2?family=Inter:opsz@14..32&display=swap');
*{font-family:'Inter',sans-serif}body{background:#0a0a0f}
.gradient-text{background:linear-gradient(135deg,#c084fc,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.card{background:#12121a;border:1px solid #252533;border-radius:16px;padding:24px}
.btn-primary{background:linear-gradient(135deg,#a855f7,#ec4899);color:white;padding:10px 20px;border-radius:8px;font-weight:600;border:none;cursor:pointer}
input{background:#1a1a26;border:1px solid #252533;border-radius:8px;padding:10px 14px;color:#f1f1f5;outline:none;width:100%}
input:focus{border-color:#a855f7}
</style></head><body class="text-[#f1f1f5] min-h-screen flex items-center justify-center p-4">
<div class="max-w-sm w-full card text-center">
<div class="text-4xl mb-4">🎙️</div>
<h1 class="text-xl font-bold gradient-text mb-2">Diazites Hub</h1>
<p class="text-sm text-[#7a7a8e] mb-6">Enter your Business ID to access your dashboard</p>
<form method="POST" action="/login" class="space-y-3">
<input type="text" name="business_id" placeholder="Your Business ID" class="text-center" required>
<button type="submit" class="btn-primary w-full">Access Dashboard →</button>
</form>
{% if error %}<p class="text-red-400 text-xs mt-3">{{ error }}</p>{% endif %}
<a href="/" class="text-xs text-[#5c5c70] mt-4 inline-block hover:text-[#c084fc]">← Back to Home</a>
</div></body></html>"""

def get_db():
    """Get database connection."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def get_available_voices():
    """Return available voice options for the dropdown."""
    return [
        # Current Eleven Labs voices (kept for backward compatibility)
        {"id": "burt", "name": "Burt (Male, Professional)", "provider": "11labs"},
        {"id": "indy", "name": "Indy (Female, Warm)", "provider": "11labs"},
        {"id": "michael", "name": "Michael (Male, Deep)", "provider": "11labs"},
        {"id": "emma", "name": "Emma (Female, Friendly)", "provider": "11labs"},
        {"id": "antoni", "name": "Antoni (Male, Calm)", "provider": "11labs"},
        # Latest Eleven Labs premium voices
        {"id": "rachel", "name": "Rachel (Female, Warm — Most Popular)", "provider": "11labs"},
        {"id": "domi", "name": "Domi (Female, Friendly)", "provider": "11labs"},
        {"id": "bella", "name": "Bella (Female, Melodic)", "provider": "11labs"},
        {"id": "elli", "name": "Elli (Female, Youthful)", "provider": "11labs"},
        {"id": "josh", "name": "Josh (Male, Deep)", "provider": "11labs"},
        {"id": "arnold", "name": "Arnold (Male, Authoritative)", "provider": "11labs"},
        {"id": "adam", "name": "Adam (Male, Confident)", "provider": "11labs"},
        {"id": "sam", "name": "Sam (Male, Warm)", "provider": "11labs"},
        {"id": "patrick", "name": "Patrick (Male, Professional)", "provider": "11labs"},
        {"id": "clyde", "name": "Clyde (Male, Storytelling)", "provider": "11labs"},
        {"id": "alice", "name": "Alice (Female, Friendly)", "provider": "11labs"},
        # New ElevenLabs premium voices (UUID-based)
        {"id": "TX3LPaxmHKxFdv7VOQHJ", "name": "Liam (Male, Energetic)", "provider": "11labs"},
        {"id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel (Male, Steady Broadcaster)", "provider": "11labs"},
        {"id": "bIHbv24MWmeRgasZH58o", "name": "Will (Male, Relaxed Optimist)", "provider": "11labs"},
        {"id": "iP95p4xoKVk53GoZ742B", "name": "Chris (Male, Charming)", "provider": "11labs"},
        {"id": "cjVigY5qzO86Huf0OWal", "name": "Eric (Male, Smooth)", "provider": "11labs"},
        {"id": "cgSgspJ2msm6clMCkdW9", "name": "Jessica (Female, Playful)", "provider": "11labs"},
        {"id": "XrExE9yKIg1WjnnlVkGX", "name": "Matilda (Female, Professional)", "provider": "11labs"},
        {"id": "pFZP5JQG7iQjIQuC4Bku", "name": "Lily (Female, Velvety)", "provider": "11labs"},
        {"id": "CwhRBWXzGAHq8TQ4Fs17", "name": "Roger (Male, Laid-Back)", "provider": "11labs"},
        {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Sarah (Female, Reassuring)", "provider": "11labs"},
        {"id": "IKne3meq5aSn9XLyUdCD", "name": "Charlie (Male, Deep)", "provider": "11labs"},
        {"id": "JBFqnCBsd6RMkjVDRZzb", "name": "George (Male, Captivating)", "provider": "11labs"},
        {"id": "SAz9YHcvj6GT2YYXdXww", "name": "River (Relaxed, Neutral)", "provider": "11labs"},
        {"id": "N2lVS1w4EtoT3dr4eOWO", "name": "Callum (Male, Husky)", "provider": "11labs"},
        {"id": "SOYHLrjzK2X1ezoPC6cr", "name": "Harry (Male, Fierce)", "provider": "11labs"},
        {"id": "nPczCjzI2devNBz1zQrb", "name": "Brian (Male, Resonant)", "provider": "11labs"},
        {"id": "pqHfZKP75CvOlQylNhV4", "name": "Bill (Male, Wise)", "provider": "11labs"},
        {"id": "FGY2WhTYpPnrIDTdsKH5", "name": "Laura (Female, Enthusiast)", "provider": "11labs"},
    ]

def login_required(f):
    """Decorator to require login for dashboard routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'business_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Decorator to require admin session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    if 'business_id' in session:
        return dashboard()
    # Affiliate tracking: ?ref=CODE sets a 30-day cookie + records a click
    ref = request.args.get('ref', '')
    aff = get_affiliate_by_code(ref) if ref else None
    if aff:
        resp = make_response(render_template_string(LANDING_PAGE.replace('<!-- GSC_META -->', gsc_meta_tag())))
        resp.set_cookie('diazites_ref', aff['code'], max_age=60 * 60 * 24 * 90, samesite='Lax')
        try:
            db = get_db()
            c = db.cursor()
            if request.cookies.get('diazites_ref', '') != aff['code']:
                c.execute("INSERT INTO affiliate_events (id, affiliate_id, event_type, created_at) VALUES (?,?,?,datetime('now'))",
                          (uuid.uuid4().hex[:16], aff['id'], 'click'))
                db.commit()
            db.close()
        except Exception:
            pass
        return resp
    return render_template_string(LANDING_PAGE.replace('<!-- GSC_META -->', gsc_meta_tag()))


LEGAL_PAGES = {
    'privacy': {
        'title': 'Privacy Policy',
        'content': """
<h2 class="text-2xl font-bold gradient-text mb-4">Privacy Policy</h2>
<p class="mb-3">Last updated: July 2026</p>
<p class="mb-3">Diazites ("we", "our", "us") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, and safeguard your information when you use our AI voice agent services.</p>
<h3 class="text-lg font-bold mt-6 mb-2">1. Information We Collect</h3>
<p class="mb-3">We collect business information (name, email, phone, industry) when you sign up, call data and transcripts from your AI voice agent interactions, and usage analytics to improve our service.</p>
<h3 class="text-lg font-bold mt-6 mb-2">2. How We Use Your Information</h3>
<p class="mb-3">We use your information to provide and improve our AI voice agent services, process payments, send service updates, and comply with legal obligations.</p>
<h3 class="text-lg font-bold mt-6 mb-2">3. Data Storage & Security</h3>
<p class="mb-3">Your data is stored securely with encryption at rest and in transit. We retain call transcripts for up to 90 days unless you request deletion.</p>
<h3 class="text-lg font-bold mt-6 mb-2">4. Third-Party Services</h3>
<p class="mb-3">We use Stripe for payment processing, VAPI for voice agent infrastructure, and Eleven Labs for text-to-speech. Each service has its own privacy policy governing data handling.</p>
<h3 class="text-lg font-bold mt-6 mb-2">5. Your Rights</h3>
<p class="mb-3">You can request access, correction, or deletion of your data at any time by contacting support.</p>
<p class="mt-6"><a href="/" class="text-[#818cf8] hover:text-[#a855f7]">← Back to Home</a></p>
"""
    },
    'terms': {
        'title': 'Terms of Service',
        'content': """
<h2 class="text-2xl font-bold gradient-text mb-4">Terms of Service</h2>
<p class="mb-3">Last updated: July 2026</p>
<p class="mb-3">By using Diazites AI voice agent services, you agree to these terms.</p>
<h3 class="text-lg font-bold mt-6 mb-2">1. Service Description</h3>
<p class="mb-3">Diazites provides AI-powered voice agents that answer calls, book appointments, and qualify leads for local businesses.</p>
<h3 class="text-lg font-bold mt-6 mb-2">2. Billing & Subscription</h3>
<p class="mb-3">Plans are billed monthly. You will be charged after your 3-day free trial ends. You may cancel anytime before the trial ends to avoid charges. Refunds follow our Refund Policy.</p>
<h3 class="text-lg font-bold mt-6 mb-2">3. Acceptable Use</h3>
<p class="mb-3">You agree not to use our service for illegal activities, spam, harassment, or any purpose that violates applicable laws.</p>
<h3 class="text-lg font-bold mt-6 mb-2">4. Limitation of Liability</h3>
<p class="mb-3">Diazites is not liable for any indirect damages arising from use of our service. Our total liability is limited to the amount you paid in the last 30 days.</p>
<p class="mt-6"><a href="/" class="text-[#818cf8] hover:text-[#a855f7]">← Back to Home</a></p>
"""
    },
    'refund': {
        'title': 'Refund Policy',
        'content': """
<h2 class="text-2xl font-bold gradient-text mb-4">Refund Policy</h2>
<p class="mb-3">Last updated: July 2026</p>
<h3 class="text-lg font-bold mt-6 mb-2">3-Day Free Trial</h3>
<p class="mb-3">All new accounts receive a 3-day free trial. You will not be charged during this period. Cancel before the trial ends and you owe nothing.</p>
<h3 class="text-lg font-bold mt-6 mb-2">Monthly Subscriptions</h3>
<p class="mb-3">If you cancel within 7 days of being charged, you may request a full refund. After 7 days, the month is non-refundable but your service continues until the end of the billing period.</p>
<h3 class="text-lg font-bold mt-6 mb-2">How to Request a Refund</h3>
<p class="mb-3">Contact support with your business ID and reason for cancellation. Refunds are processed within 5-10 business days.</p>
<p class="mt-6"><a href="/" class="text-[#818cf8] hover:text-[#a855f7]">← Back to Home</a></p>
"""
    }
}

LEGAL_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diazites — {title}</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>@import url('https://fonts.googleapis.com/css2?family=Inter:opsz@14..32&display=swap');
*{{font-family:'Inter',sans-serif;margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a0f;color:#f1f1f5;overflow-x:hidden}}
.gradient-text{{background:linear-gradient(135deg,#c084fc,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
.glass{{background:rgba(18,18,26,.7);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px)}}
.card{{background:#12121a;border:1px solid #252533;border-radius:16px;padding:24px}}
</style></head><body>
<nav class="glass flex items-center justify-between max-w-4xl mx-auto px-6 py-4 sticky top-0 z-50" style="border-bottom:1px solid #252533">
<div class="flex items-center gap-2"><div class="text-2xl">🎙️</div><span class="text-lg font-bold gradient-text">Diazites</span></div>
<div class="flex items-center gap-4">
<a href="/signup" class="btn-outline text-sm px-4 py-2" style="border:1px solid #3b3b50;color:#f1f1f5;padding:8px 20px;border-radius:10px;text-decoration:none">Sign Up</a>
<a href="/login" class="btn-primary text-sm px-5 py-2" style="background:linear-gradient(135deg,#a855f7,#ec4899);color:white;padding:8px 20px;border-radius:10px;font-weight:600;text-decoration:none">Login</a>
</div>
</nav>
<div class="max-w-3xl mx-auto px-6 py-12">
<div class="card">
{content}
</div>
</div>
<footer class="border-t border-[#252533] py-8 text-center text-xs text-[#5c5c70]">
<div class="flex justify-center gap-4 mb-3 text-xs">
<a href="/signup" class="text-[#818cf8] hover:text-[#a855f7] font-medium">Start Free Trial</a>
<a href="/affiliate" class="text-[#818cf8] hover:text-[#a855f7] font-medium">💸 Affiliates — Earn $50/Signup</a>
<a href="/privacy" class="hover:text-[#c084fc]">Privacy Policy</a>
<a href="/terms" class="hover:text-[#c084fc]">Terms of Service</a>
<a href="/refund" class="hover:text-[#c084fc]">Refund Policy</a>
</div>
<p>© 2026 Diazites. AI-powered voice agents for local businesses.</p>
</footer>
</body></html>"""


@app.route('/privacy')
def privacy_page():
    return render_template_string(LEGAL_PAGE_TEMPLATE.format(title=LEGAL_PAGES['privacy']['title'], content=LEGAL_PAGES['privacy']['content']))

@app.route('/terms')
def terms_page():
    return render_template_string(LEGAL_PAGE_TEMPLATE.format(title=LEGAL_PAGES['terms']['title'], content=LEGAL_PAGES['terms']['content']))

@app.route('/refund')
def refund_page():
    return render_template_string(LEGAL_PAGE_TEMPLATE.format(title=LEGAL_PAGES['refund']['title'], content=LEGAL_PAGES['refund']['content']))

@app.route('/signup')
def signup_redirect():
    return redirect('/#signup-form')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        bid = request.form.get('business_id', '').strip()
        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
        biz = c.fetchone()
        if biz:
            session['business_id'] = bid
            session['biz_name'] = biz['name']
            return redirect('/')
        return render_template_string(LOGIN_FORM, error='Invalid Business ID')
    if 'business_id' in session:
        return redirect('/')
    return render_template_string(LOGIN_FORM, error='')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/api/signup', methods=['POST'])
def api_signup():
    """Self-service signup - creates business and returns ID."""
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    industry = data.get('industry', 'general')
    phone = data.get('phone', '').strip()
    plan = data.get('plan', 'pro')
    
    if not name:
        return jsonify({'success': False, 'error': 'Business name is required'}), 400
    if not email:
        return jsonify({'success': False, 'error': 'Email is required'}), 400
    
    import uuid, hashlib
    bid = str(uuid.uuid4())[:12]
    cid = 'camp-' + bid
    
    db = get_db()
    c = db.cursor()
    
    # Create business
    price_map = {'starter': 97, 'pro': 197, 'premium': 497}
    price = price_map.get(plan, 197)
    
    c.execute("""INSERT INTO businesses 
        (id, name, industry, phone_number, script_template, knowledge_base,
         plan, monthly_price, email, status, voice_id, created_at, subscription_status, trial_end)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'trial', 'rachel', datetime('now'), 'trial', datetime('now', '+3 days'))""",
        (bid, name, industry, phone,
         f"You are a professional employee of {name}. Help them book more clients. Keep responses under 30 seconds. You are a real person — never mention being AI, a robot, or software.",
         f"Industry: {industry}. Business: {name}.",
         plan, price, email))
    
    c.execute("""INSERT INTO campaigns (id, business_id, status) VALUES (?, ?, 'idle')""", (cid, bid))
    
    # Affiliate attribution: if the visitor came through an affiliate link,
    # credit the signup with a commission
    try:
        ref = request.cookies.get('diazites_ref', '')
        aff = get_affiliate_by_code(ref) if ref else None
        if aff:
            c.execute(
                "INSERT INTO affiliate_events (id, affiliate_id, event_type, business_id, business_name, "
                "commission, status, created_at) VALUES (?,?,?,?,?,?, 'pending', datetime('now'))",
                (uuid.uuid4().hex[:16], aff['id'], 'signup', bid, name, aff['commission_per_signup']))
    except Exception:
        pass
    db.commit()
    
    # Try to send email
    try:
        from smtplib import SMTP
        from email.mime.text import MIMEText
        cfg_path = '/root/voice-agent-manager/smtp_config.json'
        if os.path.exists(cfg_path):
            import json
            with open(cfg_path) as f:
                cfg = json.load(f)
            if cfg.get('host') and cfg.get('email'):
                dashboard_url = request.host_url
                msg = MIMEText(f"""
Hi {name} Team,

Your AI voice agent has been created!

━━━━━━━━━━━━━━━━━━━━━━━━
🔐 YOUR LOGIN CREDENTIALS
━━━━━━━━━━━━━━━━━━━━━━━━

Dashboard URL: {dashboard_url}login
Business ID:   {bid}

━━━━━━━━━━━━━━━━━━━━━━━━
🚀 GETTING STARTED
━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to {dashboard_url}login
2. Enter Business ID: {bid}
3. Access your dashboard
4. Upload leads and start your campaign

━━━━━━━━━━━━━━━━━━━━━━━━
Diazites Team
""")
                msg['Subject'] = f'🎉 Welcome to Diazites - Your {name} Dashboard'
                msg['From'] = cfg['email']
                msg['To'] = email
                with SMTP(cfg['host'], int(cfg.get('port', 587))) as server:
                    if cfg.get('tls') != '0':
                        server.starttls()
                    if cfg.get('password'):
                        smtp_user = 'resend' if 'resend' in cfg.get('host','') else cfg['email']
                        server.login(smtp_user, cfg['password'])
                    server.send_message(msg)
    except Exception as e:
        pass  # Email is best-effort
    
    return jsonify({
        'success': True,
        'business_id': bid,
        'name': name,
        'email': email,
        'plan': plan,
        'trial_end': (datetime.now() + timedelta(days=3)).isoformat(),
        'message': '🎉 Business created! You have a 3-day free trial. Set up payment to continue after trial.'
    })


@app.route('/api/signup-stripe', methods=['POST'])
def api_signup_stripe():
    """Create business + Stripe checkout with 3-day free trial."""
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    industry = data.get('industry', 'general')
    phone = data.get('phone', '').strip()
    plan = data.get('plan', 'pro')
    
    if not name:
        return jsonify({'success': False, 'error': 'Business name is required'}), 400
    if not email:
        return jsonify({'success': False, 'error': 'Email is required'}), 400
    
    import uuid, hashlib
    bid = str(uuid.uuid4())[:12]
    cid = 'camp-' + bid
    
    db = get_db()
    c = db.cursor()
    
    price_map = {'starter': 97, 'pro': 197, 'premium': 497}
    price = price_map.get(plan, 197)
    
    # Create business with trial
    c.execute("""INSERT INTO businesses 
        (id, name, industry, phone_number, script_template, knowledge_base,
         plan, monthly_price, email, status, voice_id, created_at, subscription_status, trial_end)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'trial', 'rachel', datetime('now'), 'trial', datetime('now', '+3 days'))""",
        (bid, name, industry, phone,
         f"You are a professional employee of {name}. Help them book more clients. Keep responses under 30 seconds. You are a real person — never mention being AI, a robot, or software.",
         f"Industry: {industry}. Business: {name}.",
         plan, price, email))
    
    c.execute("""INSERT INTO campaigns (id, business_id, status) VALUES (?, ?, 'idle')""", (cid, bid))
    db.commit()
    
    # Create Stripe checkout with 3-day trial
    try:
        from premium_features import create_stripe_checkout, load_stripe_config
        cfg = load_stripe_config()
        if not cfg.get('enabled') or not cfg.get('secret_key'):
            return jsonify({
                'success': True,
                'business_id': bid,
                'checkout_url': None,
                'message': '🎉 Business created! You have a 3-day free trial. Payments unavailable — contact support to set up billing.',
                'trial_end': (datetime.now() + timedelta(days=3)).isoformat()
            })
        
        base = request.host_url.rstrip('/')
        price_cents = price * 100
        success_url = f"{base}/onboard?bid={bid}"
        cancel_url = f"{base}/?signup=cancelled"
        
        url = create_stripe_checkout(bid, plan, price_cents, email, success_url, cancel_url, trial_days=3)
        
        if url:
            return jsonify({
                'success': True,
                'business_id': bid,
                'checkout_url': url,
                'message': '🎉 Business created! Set up payment to start your 3-day free trial.',
                'trial_end': (datetime.now() + timedelta(days=3)).isoformat()
            })
        else:
            return jsonify({
                'success': True,
                'business_id': bid,
                'checkout_url': None,
                'message': '🎉 Business created! You have a 3-day free trial. Contact support to complete billing setup.',
                'trial_end': (datetime.now() + timedelta(days=3)).isoformat()
            })
    except Exception as e:
        print(f"Stripe checkout error: {e}")
        return jsonify({
            'success': True,
            'business_id': bid,
            'checkout_url': None,
            'message': '🎉 Business created! You have a 3-day free trial. Billing setup unavailable — contact support.',
            'trial_end': (datetime.now() + timedelta(days=3)).isoformat()
        })


ONBOARD_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diazites — Welcome!</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>@import url('https://fonts.googleapis.com/css2?family=Inter:opsz@14..32&display=swap');
*{font-family:'Inter',sans-serif;margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0f;color:#f1f1f5;overflow-x:hidden}
.gradient-text{background:linear-gradient(135deg,#c084fc,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.glass{background:rgba(18,18,26,.7);backdrop-filter:blur(12px)}
.card{background:#12121a;border:1px solid #252533;border-radius:16px;padding:24px;transition:border-color .3s}
.btn-primary{background:linear-gradient(135deg,#a855f7,#ec4899);color:white;padding:12px 28px;border-radius:10px;font-weight:600;border:none;cursor:pointer;display:inline-block;text-decoration:none}
.btn-primary:hover{opacity:.9}
.step{display:none}
.step.active{display:block}
.step-indicator{display:flex;gap:8px;justify-content:center;margin-bottom:24px}
.step-dot{width:10px;height:10px;border-radius:50%;background:#252533;transition:all .3s}
.step-dot.active{background:#a855f7;box-shadow:0 0 10px rgba(168,85,247,.5)}
</style></head><body>
<nav class="glass flex items-center justify-between max-w-4xl mx-auto px-6 py-4 sticky top-0 z-50" style="border-bottom:1px solid #252533">
<div class="flex items-center gap-2"><div class="text-2xl">🎙️</div><span class="text-lg font-bold gradient-text">Diazites</span></div>
<div class="text-sm text-[#7a7a8e]">{{ biz_name }}</div>
</nav>
<div class="max-w-2xl mx-auto px-6 py-12">

<!-- Step dots -->
<div class="step-indicator">
<div class="step-dot active" data-step="1"></div>
<div class="step-dot" data-step="2"></div>
<div class="step-dot" data-step="3"></div>
</div>

<!-- Step 1: Welcome -->
<div class="step active" id="step1">
<div class="card text-center py-12">
<div class="text-6xl mb-4">🎉</div>
<h1 class="text-3xl font-bold gradient-text mb-3">Welcome to Diazites, {{ biz_name }}!</h1>
<p class="text-[#7a7a8e] mb-6">Your AI voice agent is ready. Let's get you set up in 3 quick steps.</p>
<div class="bg-[#1a1a26] rounded-xl p-4 mb-6 text-left text-sm">
<div class="text-green-400 font-semibold mb-2">✅ Business Created</div>
<div class="text-[#7a7a8e] mb-1">Your Business ID: <code class="font-mono bg-[#0a0a0f] px-2 py-0.5 rounded text-[#c084fc]">{{ bid }}</code></div>
<div class="text-[#7a7a8e] mb-1">📧 We've sent your credentials to <strong>{{ email }}</strong></div>
<div class="text-[#7a7a8e]">📱 We've also sent them via SMS to <strong>{{ phone }}</strong></div>
</div>
<div class="text-xs text-yellow-400 mb-4">🎁 Your 3-day free trial has started. You will be charged ${{ price }}/month after the trial ends.</div>
<button onclick="nextStep(2)" class="btn-primary">Let's Go! →</button>
</div>
</div>

<!-- Step 2: Dashboard Tour -->
<div class="step" id="step2">
<div class="card text-center py-12">
<div class="text-6xl mb-4">🔑</div>
<h2 class="text-2xl font-bold gradient-text mb-3">Login & Dashboard</h2>
<p class="text-[#7a7a8e] mb-6">You can always log back in with your Business ID.</p>
<div class="bg-[#1a1a26] rounded-xl p-4 mb-6 text-left text-sm space-y-3">
<div class="flex items-start gap-3">
<div class="text-lg">1️⃣</div>
<div><span class="text-white font-semibold">Go to diazites.online</span><br><span class="text-[#7a7a8e]">Click "Login" in the top right</span></div>
</div>
<div class="flex items-start gap-3">
<div class="text-lg">2️⃣</div>
<div><span class="text-white font-semibold">Enter your Business ID</span><br><span class="text-[#7a7a8e] font-mono text-[#c084fc]">{{ bid }}</span></div>
</div>
<div class="flex items-start gap-3">
<div class="text-lg">3️⃣</div>
<div><span class="text-white font-semibold">Start your campaign</span><br><span class="text-[#7a7a8e]">Upload leads and start calling</span></div>
</div>
</div>
<button onclick="nextStep(3)" class="btn-primary">Next: Setup Tips →</button>
</div>
</div>

<!-- Step 3: Next Steps -->
<div class="step" id="step3">
<div class="card py-12">
<div class="text-center"><div class="text-6xl mb-4">🚀</div></div>
<h2 class="text-2xl font-bold gradient-text text-center mb-6">You're All Set!</h2>
<div class="space-y-4 text-sm">
<div class="bg-[#1a1a26] rounded-xl p-4">
<div class="flex items-center gap-3">
<div class="text-2xl">📤</div>
<div><div class="font-semibold">Upload Leads</div><div class="text-[#7a7a8e]">Import your prospect list or add manually</div></div>
</div>
</div>
<div class="bg-[#1a1a26] rounded-xl p-4">
<div class="flex items-center gap-3">
<div class="text-2xl">🎙️</div>
<div><div class="font-semibold">Choose a Voice</div><div class="text-[#7a7a8e]">Pick from 34+ Eleven Labs voices in Settings</div></div>
</div>
</div>
<div class="bg-[#1a1a26] rounded-xl p-4">
<div class="flex items-center gap-3">
<div class="text-2xl">▶️</div>
<div><div class="font-semibold">Start Campaign</div><div class="text-[#7a7a8e]">Click "Start Campaign" and we call your leads</div></div>
</div>
</div>
</div>
<div class="text-center mt-8">
<a href="/" class="btn-primary text-base px-10">🚀 Go to Dashboard</a>
</div>
</div>
</div>

</div>

<script>
function nextStep(n) {
document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
document.getElementById('step' + n).classList.add('active');
document.querySelectorAll('.step-dot').forEach(d => d.classList.remove('active'));
document.querySelector('.step-dot[data-step="' + n + '"]').classList.add('active');
window.scrollTo({top:0,behavior:'smooth'});
}
</script>
</body></html>"""


@app.route('/onboard')
def onboard():
    """Auto-login and show onboarding wizard after Stripe checkout."""
    bid = request.args.get('bid', '')
    if not bid:
        return redirect('/login')
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if not biz:
        return redirect('/login')
    
    # Auto-login
    session['business_id'] = bid
    session['biz_name'] = biz['name']
    
    # Send credentials via email and SMS (only once)
    c.execute("SELECT onboard_email_sent FROM businesses WHERE id = ?", (bid,))
    row = c.fetchone()
    # Check if column exists and credentials haven't been sent
    try:
        already_sent = row and row[0]
    except:
        already_sent = False
    
    if not already_sent:
        try:
            # Add column if it doesn't exist
            try:
                c.execute("ALTER TABLE businesses ADD COLUMN onboard_email_sent INTEGER DEFAULT 0")
                db.commit()
            except:
                pass
            
            name = biz['name']
            email = biz['email'] or ''
            phone = biz['phone_number'] or ''
            price = biz['monthly_price'] or 197
            
            # Send email
            if email:
                try:
                    from smtplib import SMTP
                    from email.mime.text import MIMEText
                    cfg_path = '/root/voice-agent-manager/smtp_config.json'
                    if os.path.exists(cfg_path):
                        import json as j2
                        with open(cfg_path) as f:
                            cfg = j2.load(f)
                        if cfg.get('host') and cfg.get('email'):
                            msg = MIMEText(f"""
Welcome to Diazites, {name}!

Your AI voice agent is ready to go.

━━━━━━━━━━━━━━━━━━━━━━━━
YOUR LOGIN CREDENTIALS
━━━━━━━━━━━━━━━━━━━━━━━━

🌐 Website: {request.host_url}
🔑 Business ID: {bid}

━━━━━━━━━━━━━━━━━━━━━━━━

Save your Business ID — you'll need it to log in.

What's next:
1. Go to {request.host_url}
2. Click "Login"
3. Enter your Business ID: {bid}
4. Upload leads and start your campaign

Your 3-day free trial has started! You'll be charged ${price}/month after.

Need help? Reply to this email.

— The Diazites Team
""")
                            msg['Subject'] = f'🎉 Welcome to Diazites, {name}! Your Business ID Inside'
                            msg['From'] = cfg['email']
                            msg['To'] = email
                            with SMTP(cfg['host'], int(cfg.get('port', 587))) as server:
                                if cfg.get('tls') != '0':
                                    server.starttls()
                                if cfg.get('password'):
                                    smtp_user = 'resend' if 'resend' in cfg.get('host','') else cfg['email']
                                    server.login(smtp_user, cfg['password'])
                                server.send_message(msg)
                            print(f"📧 Welcome email sent to {email}")
                except Exception as e:
                    print(f"Email send error: {e}")
            
            # Send SMS via Sent.dm (replaces Twilio)
            if phone:
                try:
                    from sentdm_sms import send_welcome_sms
                    if send_welcome_sms(phone, name, bid, request.host_url):
                        print(f"📱 Welcome SMS sent to {phone}")
                except Exception as e:
                    print(f"SMS send error: {e}")
            
            # Mark as sent
            c.execute("UPDATE businesses SET onboard_email_sent=1 WHERE id=?", (bid,))
            db.commit()
        except Exception as e:
            print(f"Credentials send error: {e}")
    
    db.close()
    
    return render_template_string(ONBOARD_HTML,
        bid=bid,
        biz_name=biz['name'],
        email=biz['email'] or 'your email',
        phone=biz['phone_number'] or 'your phone',
        price=biz['monthly_price'] or 197
    )



# ── SIGNUP → CHECKOUT FLOW ──
@app.route('/api/signup-checkout', methods=['POST'])
def api_signup_checkout():
    """Create Stripe checkout for new signup. Business created after payment."""
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    industry = data.get('industry', 'general')
    phone = data.get('phone', '').strip()
    plan = data.get('plan', 'pro')
    
    if not name or not email:
        return jsonify({'success': False, 'error': 'Name and email required'}), 400
    
    import uuid
    price_map = {'starter': 9700, 'pro': 19700, 'premium': 49700}
    price_cents = price_map.get(plan, 19700)
    sid = str(uuid.uuid4())[:12]
    
    # Save pending
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO pending_signups (id, name, email, industry, phone, plan, price, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
              (sid, name, email, industry, phone, plan, price_cents // 100))
    db.commit()
    
    # Create Stripe checkout
    try:
        from premium_features import create_stripe_checkout, load_stripe_config
        cfg = load_stripe_config()
        if not cfg.get('enabled'):
            return jsonify({'success': False, 'error': 'Payments temporarily unavailable'}), 400
        
        base = request.host_url.rstrip('/')
        description = f"Diazites {plan.title()} — {name}"
        success_url = f"{base}/login?welcome={sid}"
        cancel_url = f"{base}/?signup=cancelled"
        
        url = create_stripe_checkout(sid, description, price_cents, email, success_url, cancel_url)
        
        if url:
            # Store Stripe session ID
            import re
            sess_match = re.search(r'/cs_(cs_[a-zA-Z0-9]+)', url)
            stripe_session = sess_match.group(1) if sess_match else ''
            if stripe_session:
                c.execute("UPDATE pending_signups SET stripe_session_id=? WHERE id=?", (stripe_session, sid))
                db.commit()
            
            return jsonify({'success': True, 'checkout_url': url, 'sid': sid})
        else:
            return jsonify({'success': False, 'error': 'Failed to create checkout'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/stripe-signup-webhook', methods=['POST'])
def stripe_signup_webhook():
    """Stripe webhook for signup payments — creates business on successful payment."""
    import json as json_mod
    payload = request.get_data()
    sig = request.headers.get('Stripe-Signature', '')
    
    try:
        import stripe
        from premium_features import load_stripe_config
        cfg = load_stripe_config()
        stripe.api_key = cfg.get('secret_key', '')
        
        # Verify webhook signature
        endpoint_secret = cfg.get('webhook_secret', '')
        if endpoint_secret:
            event = stripe.Webhook.construct_event(payload, sig, endpoint_secret)
        else:
            event = json_mod.loads(payload)
        
        if event.get('type') == 'checkout.session.completed':
            session_data = event['data']['object']
            client_ref = session_data.get('client_reference_id', '')
            email = session_data.get('customer_email', '') or session_data.get('customer_details', {}).get('email', '')
            stripe_session_id = session_data.get('id', '')
            
            db = get_db()
            c = db.cursor()
            
            # Find pending signup by client_ref or stripe_session_id
            pending = c.execute(
                "SELECT * FROM pending_signups WHERE (id=? OR stripe_session_id=?) AND status='pending'",
                (client_ref, stripe_session_id)
            ).fetchone()
            
            if pending:
                pending = dict(pending)
                import uuid
                bid = str(uuid.uuid4())[:12]
                cid = 'camp-' + bid
                
                # Create business
                c.execute("""INSERT INTO businesses 
                    (id, name, industry, phone_number, script_template, knowledge_base,
                     plan, monthly_price, email, status, voice_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 'rachel', datetime('now'))""",
                    (bid, pending['name'], pending['industry'], pending.get('phone', ''),
                     f"You are a professional employee of {pending['name']}. Help them book more clients. You are a real person — never mention being AI, a robot, or software.",
                     f"Industry: {pending['industry']}. Business: {pending['name']}.",
                     pending['plan'], pending['price'], pending['email']))
                
                c.execute("INSERT INTO campaigns (id, business_id, status) VALUES (?, ?, 'idle')", (cid, bid))
                c.execute("UPDATE pending_signups SET status='completed' WHERE id=?", (pending['id'],))
                db.commit()
                return 'OK', 200
            
            # Handle phone number purchase ($9.99/mo)
            plan_name = session_data.get('metadata', {}).get('plan', '')
            biz_id = session_data.get('metadata', {}).get('business_id', '')
            if plan_name and biz_id and ('phone' in plan_name.lower() or 'number' in plan_name.lower()):
                c.execute("UPDATE businesses SET number_paid=1, stripe_subscription_id=? WHERE id=?",
                          (stripe_session_id, biz_id))
                db.commit()
                print(f"✅ Number purchase confirmed for business {biz_id}")
                return 'OK', 200
                
                # Try email
                try:
                    from smtplib import SMTP
                    from email.mime.text import MIMEText
                    cfg_path = '/root/voice-agent-manager/smtp_config.json'
                    import os as os_mod
                    if os_mod.path.exists(cfg_path):
                        with open(cfg_path) as f:
                            scfg = json_mod.load(f)
                        if scfg.get('host') and scfg.get('email'):
                            dashboard_url = request.host_url
                            msg = MIMEText(f"""
Welcome to Diazites, {pending['name']}!

Your {pending['plan'].title()} plan is now active.

━━━━━━━━━━━━━━━━━━━━━━━━
🔐 YOUR LOGIN
━━━━━━━━━━━━━━━━━━━━━━━━

Dashboard: {dashboard_url}login
Business ID: {bid}

━━━━━━━━━━━━━━━━━━━━━━━━
🚀 NEXT STEPS
━━━━━━━━━━━━━━━━━━━━━━━━

1. Login with your Business ID
2. Configure your AI agent's script
3. Upload leads or share your number
4. Start receiving calls!

Total: ${pending['price']}/mo

━━━━━━━━━━━━━━━━━━━━━━━━
Diazites Team
""")
                            msg['Subject'] = f'🎉 Welcome to Diazites! Your {pending["name"]} Account'
                            msg['From'] = scfg.get('email', 'noreply@diazites.online')
                            msg['To'] = pending['email']
                            with SMTP(scfg['host'], int(scfg.get('port', 587))) as server:
                                if scfg.get('tls') != '0':
                                    server.starttls()
                                if scfg.get('password'):
                                    smtp_user = 'resend' if 'resend' in scfg.get('host','') else scfg.get('email', '')
                                    server.login(smtp_user, scfg['password'])
                                server.send_message(msg)
                except:
                    pass  # Email is best-effort
                
                return jsonify({'received': True, 'business_id': bid})
        
        return jsonify({'received': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 200  # Always return 200 to Stripe

# ── MULTI-AGENT MANAGEMENT ──

@app.route('/api/agents/list')
@login_required
def api_agents_list():
    """List all agents for this business."""
    bid = session.get('business_id', '')
    db = get_db()
    c = db.cursor()
    rows = c.execute("SELECT * FROM agents WHERE business_id=? ORDER BY created_at ASC", (bid,)).fetchall()
    agents = []
    for r in rows:
        a = dict(r)
        # Count calls for each agent
        call_count = c.execute("SELECT COUNT(*) FROM call_log WHERE business_id=? AND lead_id LIKE ?", 
                              (bid, f'%{a["id"]}%')).fetchone()[0] or 0
        a['call_count'] = call_count
        agents.append(a)
    
    biz = c.execute("SELECT plan, calls_included FROM businesses WHERE id=?",
    (bid,)).fetchone()
    plan_limits = {'starter': 1, 'pro': 2, 'premium': 3, 'enterprise': 5}
    plan_key = (biz['plan'] if biz else 'starter').lower()
    max_agents = plan_limits.get(plan_key, 1)
    if max_agents == 1 and biz and 'custom' in plan_key:
        import re
        nums = re.findall(r'\d+', biz['plan'])
        if nums and int(nums[0]) >= 300:
            max_agents = 5
        elif nums and int(nums[0]) >= 150:
            max_agents = 3
    
    return jsonify({'success': True, 'agents': agents, 'max_agents': max_agents, 'agent_count': len(agents)})

@app.route('/api/agents/get/<agent_id>')
@login_required
def api_agent_get(agent_id):
    """Get a single agent's full config."""
    bid = session.get('business_id', '')
    db = get_db()
    c = db.cursor()
    row = c.execute("SELECT * FROM agents WHERE id=? AND business_id=?", (agent_id, bid)).fetchone()
    if not row:
        return jsonify({'success': False, 'error': 'Agent not found'}), 404
    return jsonify({'success': True, 'agent': dict(row)})

@app.route('/api/agents/create', methods=['POST'])
@login_required
def api_agent_create():
    """Create a new AI agent for this business."""
    bid = session.get('business_id', '')
    data = request.get_json(silent=True) or {}
    name = data.get('name', 'New Agent').strip()
    
    db = get_db()
    c = db.cursor()
    biz = c.execute("SELECT plan, name FROM businesses WHERE id=?", (bid,)).fetchone()
    if not biz:
        return jsonify({'success': False, 'error': 'Business not found'}), 404
    
    plan_limits = {'starter': 1, 'pro': 2, 'premium': 3, 'enterprise': 5}
    plan_key = (biz['plan'] or 'starter').lower()
    max_agents = plan_limits.get(plan_key, 1)
    # Custom plans with numbers in them get extra agents
    if max_agents == 1 and 'custom' in plan_key:
        import re
        nums = re.findall(r'\d+', biz['plan'])
        if nums and int(nums[0]) >= 300:
            max_agents = 5
        elif nums and int(nums[0]) >= 150:
            max_agents = 3
    current_count = c.execute("SELECT COUNT(*) FROM agents WHERE business_id=?", (bid,)).fetchone()[0] or 0
    
    if current_count >= max_agents:
        return jsonify({'success': False, 'error': f'Plan limit reached ({max_agents} agents max). Upgrade to add more.'}), 400
    
    import uuid
    aid = 'agent-' + str(uuid.uuid4())[:10]
    
    c.execute("""INSERT INTO agents (id, business_id, name, script_template, knowledge_base, status)
                VALUES (?, ?, ?, ?, ?, 'active')""",
              (aid, bid, name,
               f"You are a professional employee of {biz['name']}. Help book more clients. You are a real person — never mention being AI, a robot, or software.",
               f"Business: {biz['name']}."))
    db.commit()
    
    return jsonify({'success': True, 'agent_id': aid, 'message': f'✅ Agent "{name}" created!'})

@app.route('/api/agents/update', methods=['POST'])
@login_required
def api_agent_update():
    """Update an agent's configuration."""
    bid = session.get('business_id', '')
    data = request.get_json(silent=True) or {}
    aid = data.get('agent_id', '')
    
    if not aid:
        return jsonify({'success': False, 'error': 'Agent ID required'}), 400
    
    db = get_db()
    c = db.cursor()
    existing = c.execute("SELECT id FROM agents WHERE id=? AND business_id=?", (aid, bid)).fetchone()
    if not existing:
        return jsonify({'success': False, 'error': 'Agent not found'}), 404
    
    fields = ['name', 'phone_number', 'vapi_assistant_id', 'script_template', 'knowledge_base',
              'voice_id', 'voice_speed', 'language', 'status']
    updates = []
    values = []
    for f in fields:
        if f in data:
            updates.append(f"{f}=?")
            values.append(data[f])
    
    if updates:
        values.append(aid)
        c.execute(f"UPDATE agents SET {', '.join(updates)} WHERE id=?", values)
        db.commit()
    
    return jsonify({'success': True, 'message': '✅ Agent updated!'})

@app.route('/api/agents/delete/<agent_id>', methods=['DELETE'])
@login_required
def api_agent_delete(agent_id):
    """Delete an agent."""
    bid = session.get('business_id', '')
    db = get_db()
    c = db.cursor()
    
    # Check it's not the last agent
    count = c.execute("SELECT COUNT(*) FROM agents WHERE business_id=?", (bid,)).fetchone()[0] or 0
    if count <= 1:
        return jsonify({'success': False, 'error': 'Cannot delete your last agent'}), 400
    
    c.execute("DELETE FROM agents WHERE id=? AND business_id=?", (agent_id, bid))
    db.commit()
    return jsonify({'success': True, 'message': '🗑️ Agent deleted'})

@app.route('/api/agents/buy-number', methods=['POST'])
@login_required
def api_agent_buy_number():
    """Buy a phone number from Twilio and assign it to a specific agent."""
    bid = session.get('business_id', '')
    data = request.get_json(silent=True) or {}
    aid = data.get('agent_id', '')
    area_code = (data.get('area_code') or '').strip() or None

    if not aid:
        return jsonify({'success': False, 'error': 'Agent ID required'}), 400

    db = get_db()
    c = db.cursor()
    agent = c.execute("SELECT * FROM agents WHERE id=? AND business_id=?", (aid, bid)).fetchone()
    if not agent:
        db.close()
        return jsonify({'success': False, 'error': 'Agent not found'}), 404

    # Agent needs a VAPI assistant to bind the number to
    assistant_id = agent['vapi_assistant_id']
    if not assistant_id:
        db.close()
        return jsonify({'success': False, 'error': 'Agent has no VAPI assistant yet. Save the agent first.'}), 400

    # Check they haven't already got a number
    if agent['phone_number']:
        db.close()
        return jsonify({'success': False, 'error': f'Agent already has {agent["phone_number"]}'}), 400

    from twilio_helper import buy_twilio_number, register_with_vapi, search_available_numbers

    # Search for a number
    nums, error = search_available_numbers(area_code, limit=10)
    if error:
        nums, error = search_available_numbers(None, limit=10)
        if error:
            db.close()
            return jsonify({'success': False, 'error': f'Twilio search failed: {error}'}), 500

    # Prefer a Miami/nice number
    target = None
    for n in nums:
        if (n.get('locality') or '').lower() in ('miami', 'north dade', 'north miami'):
            target = n
            break
    if not target:
        target = nums[0]
    phone_to_buy = target['phone_number']

    # Buy from Twilio
    twilio_result, error = buy_twilio_number(phone_to_buy)
    if error:
        db.close()
        return jsonify({'success': False, 'error': f'Twilio purchase failed: {error}'}), 500
    bought_number = twilio_result.get('phone_number', phone_to_buy)

    # Register with VAPI bound to this agent's assistant
    vapi_result, error = register_with_vapi(bought_number, assistant_id)
    if error:
        db.close()
        return jsonify({'success': False, 'error': f'Bought {bought_number} but Vapi registration failed: {error}'}), 500
    vapi_phone_id = vapi_result.get('id', '')

    c.execute("UPDATE agents SET phone_number=?, vapi_phone_id=? WHERE id=?", (bought_number, vapi_phone_id, aid))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': f'✅ {bought_number} bought & assigned to {agent["name"]}!',
                    'phone_number': bought_number})

# ── AI CHATBOT API (Multi-Provider) ──

CHATBOT_PROMPT = """You are a sales assistant for Diazites, a Voice AI SaaS platform. Answer questions about:
- Pricing: Starter $97/mo, Professional $197/mo, Enterprise custom pricing. All plans include 24/7 AI voice agent, appointment booking, multi-language support, and analytics dashboard.
- Features: AI voice agents answer calls 24/7, book appointments, qualify leads, voicemail detection, parallel calling, CRM integrations, 12+ languages.
- Setup: Set up in 2 minutes. No coding needed. Choose a voice, configure the script, upload leads, start campaigns.
- The AI calls prospects, handles objections, books on calendar. Works for plumbers, dentists, realtors, HVAC, solar, insurance.
Keep answers SHORT (2-3 sentences), friendly, and encourage them to sign up at the signup form above."""

CHATBOT_PROVIDERS = {
    "xai": {
        "api_url": "https://api.x.ai/v1/chat/completions",
        "default_model": "grok-4-mini",
        "auth_header": lambda key: f"Bearer {key}"
    },
    "deepseek": {
        "api_url": "https://api.deepseek.com/chat/completions",
        "default_model": "deepseek-chat",
        "auth_header": lambda key: f"Bearer {key}"
    }
}

def get_chatbot_config():
    """Get chatbot provider config from settings DB."""
    try:
        db = sqlite3.connect(DB_PATH)
        c = db.cursor()
        c.execute("SELECT key, value FROM settings WHERE key IN ('chatbot_provider','chatbot_model','chatbot_api_key')")
        rows = {row[0]: row[1] for row in c.fetchall()}
        db.close()
        return rows
    except:
        return {}

def get_xai_api_key():
    """Fallback to env var for backward compat."""
    return os.environ.get('XAI_API_KEY', '')

@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    data = request.get_json(silent=True) or {}
    msg = data.get('message', '').strip()[:500]
    if not msg:
        return jsonify({'reply': 'Please ask me a question!'})
    
    # Get config from DB
    cfg = get_chatbot_config()
    provider_name = cfg.get('chatbot_provider', 'xai')
    api_key = cfg.get('chatbot_api_key', '') or get_xai_api_key()
    model = cfg.get('chatbot_model', '')
    
    if not api_key:
        return jsonify({'reply': 'Hi! I can help with pricing, features, and setup. Check out our plans above or use the signup form to get started! 🚀'})
    
    provider = CHATBOT_PROVIDERS.get(provider_name)
    if not provider:
        provider = CHATBOT_PROVIDERS['xai']
    
    if not model:
        model = provider['default_model']
    
    try:
        r = requests.post(provider['api_url'], json={
            "model": model,
            "messages": [
                {"role": "system", "content": CHATBOT_PROMPT},
                {"role": "user", "content": msg}
            ],
            "max_tokens": 200,
            "temperature": 0.3
        }, headers={"Authorization": provider['auth_header'](api_key), "Content-Type": "application/json"}, timeout=15)
        data = r.json()
        reply = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        if reply:
            return jsonify({'reply': reply})
    except Exception as e:
        pass
    return jsonify({'reply': 'Hi! I can help with pricing, features, and setup. Check out our plans above or use the signup form to get started! 🚀'})

@app.route('/dashboard')
@login_required
def dashboard():
    bid = session['business_id']
    tab = request.args.get('tab', 'overview')
    
    db = get_db()
    c = db.cursor()
    
    # Handle Stripe checkout return for number purchase
    purchased = request.args.get('purchased')
    if purchased == '1':
        # Webhook may have already marked payment, check + try to buy
        c.execute("SELECT number_paid FROM businesses WHERE id=?", (bid,))
        row = c.fetchone()
        if row and row['number_paid']:
            flash('✅ Payment confirmed! Now search and buy your number.', 'success')
        else:
            # Webhook might be delayed, check if we have a pending subscription
            flash('💳 Payment received! You can now buy a number.', 'success')
            c.execute("UPDATE businesses SET number_paid=1 WHERE id=?", (bid,))
            db.commit()
    
    c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if not biz:
        session.clear()
        return redirect('/?error=Business not found')
    biz = dict(biz)
    
    # Campaign status
    ensure_campaign_row(bid)
    c.execute("SELECT * FROM campaigns WHERE business_id = ?", (bid,))
    camp = c.fetchone()
    campaign_status = camp['status'] if camp else 'idle'
    # Schedule info
    schedule = None
    if camp:
        schedule = {
            'enabled': bool(camp['schedule_enabled']),
            'time': camp['schedule_time'] or '09:00',
            'days': camp['schedule_days'] or 'mon,tue,wed,thu,fri',
            'start_date': camp['schedule_start_date'] or '',
            'timezone': camp['timezone'] or 'America/New_York',
        }
    
    # THREAD HEALTH CHECK: if campaign says running but thread is dead, restart it
    if campaign_status == 'running' and bid not in campaign_threads:
        c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ? AND state = 'NEW'", (bid,))
        if c.fetchone()[0] > 0:
            log_campaign(bid, '🔄 Campaign thread was lost — restarting...', 'warning')
            c.execute("UPDATE campaigns SET status='running' WHERE business_id=?", (bid,))
            db.commit()
            t = threading.Thread(target=run_campaign_bg, args=(bid,), daemon=True)
            campaign_threads[bid] = t
            t.start()
    
    # Stats
    c.execute("SELECT COALESCE(SUM(calls_made),0) FROM campaigns WHERE business_id = ?", (bid,))
    calls_made = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(appointments_booked),0) FROM campaigns WHERE business_id = ?", (bid,))
    appointments = c.fetchone()[0]
    # Also count from actual appointments table
    c.execute("SELECT COUNT(*) FROM appointments WHERE business_id = ? AND status='booked'", (bid,))
    real_appointments = c.fetchone()[0]
    if real_appointments > 0:
        appointments = real_appointments
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ?", (bid,))
    leads_total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ? AND state = 'NEW'", (bid,))
    leads_new = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ? AND state != 'NEW'", (bid,))
    leads_called = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(cost),0) FROM call_log WHERE business_id = ?", (bid,))
    total_cost = c.fetchone()[0]
    
    # Total duration for minutes meter
    c.execute("SELECT COALESCE(SUM(duration),0) FROM call_log WHERE business_id = ?", (bid,))
    total_duration = c.fetchone()[0]
    
    # Plan info
    plan_key = biz.get('plan', 'starter') or 'starter'
    pricing_tiers = {
        "starter": {"name": "Starter", "price": 97, "minutes_limit": 250, "features": ["1 AI Agent", "1 Number", "250 min", "Booking", "Analytics", "Email Support"]},
        "pro": {"name": "Professional", "price": 197, "minutes_limit": 1000, "features": ["2 AI Agents", "2 Numbers", "1000 min", "Campaigns", "SMS", "Calendar", "Priority Support"]},
        "premium": {"name": "Premium", "price": 297, "minutes_limit": 2500, "features": ["3 AI Agents", "3 Numbers", "2500 min", "Forwarding", "Priority Support"]},
        "enterprise": {"name": "Enterprise", "price": 497, "minutes_limit": 7500, "features": ["5 AI Agents", "5 Numbers", "7500 min", "API", "White-Label", "Dedicated Manager"]},
        "custom": {"name": "Custom", "price": 997, "minutes_limit": 0, "features": ["Custom config"]}
    }
    user_tier = pricing_tiers.get(plan_key, pricing_tiers['starter'])
    extra_minutes = biz.get('extra_minutes', 0) or 0
    total_minutes_limit = (user_tier['minutes_limit'] or 0) + extra_minutes
    
    # Recent calls
    c.execute("""
        SELECT cl.*, l.phone, l.business_name FROM call_log cl
        LEFT JOIN leads l ON cl.lead_id = l.id
        WHERE cl.business_id = ? ORDER BY cl.created_at DESC LIMIT 10
    """, (bid,))
    recent_calls = [dict(r) for r in c.fetchall()]
    
    # Call logs
    c.execute("""
        SELECT cl.*, l.phone, l.business_name FROM call_log cl
        LEFT JOIN leads l ON cl.lead_id = l.id
        WHERE cl.business_id = ? ORDER BY cl.created_at DESC LIMIT 30
    """, (bid,))
    call_logs = [dict(r) for r in c.fetchall()]
    
    # Leads
    c.execute("SELECT * FROM leads WHERE business_id = ? ORDER BY state, created_at DESC LIMIT 100", (bid,))
    leads = [dict(r) for r in c.fetchall()]
    
    # Follow-ups - leads that have been called but need follow-up
    c.execute("""SELECT * FROM leads WHERE business_id = ? AND state IN ('CALLED','NO_ANSWER','INTERESTED') 
                  ORDER BY last_called_at DESC LIMIT 50""", (bid,))
    followups = [dict(r) for r in c.fetchall()]
    
    # Phone numbers
    assigned_numbers = []
    if biz['vapi_phone_id']:
        try:
            r = subprocess.run(["curl","-s",f"{VAPI_BASE}/phone-number/{biz['vapi_phone_id']}",
                "-H",f"Authorization: Bearer {VAPI_API_KEY}"], capture_output=True, text=True)
            data = json.loads(r.stdout)
            assigned_numbers.append({'number': data.get('number','?'), 'name': data.get('name','')})
        except: pass
    
    # Upcoming appointments
    c.execute("""
        SELECT a.*, a.prospect_name, a.phone, a.appointment_time, a.notes,
               l.name as lead_name, l.business_name,
               cl.transcript as call_transcript
        FROM appointments a
        LEFT JOIN leads l ON a.lead_id = l.id
        LEFT JOIN call_log cl ON cl.vapi_call_id = a.call_log_id
        WHERE a.business_id = ? AND a.status = 'booked'
        ORDER BY a.appointment_time ASC LIMIT 20
    """, (bid,))
    appointment_list = [dict(r) for r in c.fetchall()]

    # Parse NLP appointment times ("tomorrow at 5pm", "monday at 10 am", "july 28 at 2pm")
    # into real dates for the calendar view.
    import re as cal_re
    from datetime import datetime as cal_dt, timedelta as cal_td

    def parse_appointment_time(raw, biz_tz='America/New_York'):
        """Convert NLP appointment time to (date_str YYYY-MM-DD, time_str HH:MM) or (None, raw)."""
        try:
            s = (raw or '').strip().lower()
            if not s:
                return None, raw or ''
            now = cal_dt.now()
            day = None
            # Relative days
            if 'tomorrow' in s:
                day = now + cal_td(days=1)
            elif 'today' in s or 'tonight' in s:
                day = now
            elif 'next week' in s:
                day = now + cal_td(days=7)
            else:
                # Weekday names
                day_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                           'friday': 4, 'saturday': 5, 'sunday': 6}
                for name, idx in day_map.items():
                    if name in s:
                        days_ahead = (idx - now.weekday()) % 7
                        if 'next' in s:
                            days_ahead += 7
                        day = (now + cal_td(days=days_ahead)).date()
                        break
                # Month names ("july 28")
                if day is None:
                    months = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                              'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12}
                    for mname, mnum in months.items():
                        mm = cal_re.search(mname + r'\s+(\d{1,2})', s)
                        if mm:
                            dnum = int(mm.group(1))
                            try:
                                day = cal_dt(now.year, mnum, dnum).date()
                            except ValueError:
                                return None, raw or ''
                            break
                # Numeric dates ("7/28", "7/28/26")
                if day is None:
                    nm = cal_re.search(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', s)
                    if nm:
                        mo, da = int(nm.group(1)), int(nm.group(2))
                        yr = int(nm.group(3)) if nm.group(3) else now.year
                        if yr < 100:
                            yr += 2000
                        try:
                            day = cal_dt(yr, mo, da).date()
                        except ValueError:
                            return None, raw or ''
            if day is None:
                return None, raw or ''
            if hasattr(day, 'date'):
                day = day.date()
            # Extract time — prefer a number followed by am/pm ("2pm", "10 am"),
            # so "july 28 at 2pm" picks 2pm not 28, and "7/28 at 4 pm" picks 4.
            tm = None
            for tpat in (r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', r'(\d{1,2})(?::(\d{2}))?\s*$'):
                tm = cal_re.search(tpat, s)
                if tm:
                    break
            if tm:
                hour = int(tm.group(1))
                minute = int(tm.group(2) or 0)
                ampm = tm.group(3)
                if ampm == 'pm' and hour < 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
                return day.isoformat(), '{:02d}:{:02d}'.format(hour, minute)
            return day.isoformat(), ''
        except Exception:
            return None, raw or ''

    calendar_events = []
    for apt in appointment_list:
        date_str, time_str = parse_appointment_time(apt.get('appointment_time'))
        calendar_events.append({
            'id': apt.get('id') or '',
            'name': apt.get('prospect_name') or apt.get('lead_name') or 'Prospect',
            'phone': apt.get('phone') or '',
            'date': date_str,
            'time': time_str,
            'raw': apt.get('appointment_time') or '',
            'notes': (apt.get('notes') or ''),
            'transcript': (apt.get('call_transcript') or '')[:600],
            'created': (apt.get('created_at') or '')[:10],
            'lead_name': apt.get('lead_name') or '',
            'business_name': apt.get('business_name') or '',
            'call_log_id': apt.get('call_log_id') or '',
        })
    
    # AI Product Factory data
    c.execute("SELECT * FROM products ORDER BY created_at DESC LIMIT 50")
    factory_products = [dict(r) for r in c.fetchall()]
    c.execute("SELECT COUNT(*) FROM products WHERE status='published'")
    pub_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM products WHERE status='draft'")
    draft_count = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(downloads_count),0) FROM products")
    dl_count = c.fetchone()[0]
    ai_stats = {
        'total': len(factory_products),
        'published': pub_count,
        'drafts': draft_count,
        'downloads': dl_count
    }
    
    # Load dashboard template from file
    try:
        with open('/root/voice-agent-manager/dashboard_template.html', 'r') as f:
            dashboard_html = f.read()
    except:
        dashboard_html = "<h1>Dashboard template not found</h1>"
    
    # Conversations tab data
    today_date = datetime.now().strftime('%Y-%m-%d')
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    try:
        c.execute("""
            SELECT cl.*, l.name as lead_name, l.phone as lead_phone
            FROM call_log cl
            LEFT JOIN leads l ON cl.lead_id = l.id
            WHERE cl.business_id = ?
            ORDER BY cl.created_at DESC LIMIT 50
        """, (bid,))
        conversations = []
        for r in c.fetchall():
            r = dict(r)
            dur = r.get('duration', 0) or 0
            if dur < 60:
                dur_str = f'{dur}s'
            else:
                dur_str = f'{dur//60}m{dur%60:02d}s'
            created = r.get('created_at', '')
            created_str = created[:16] if created else ''
            r['duration_str'] = dur_str
            r['created_at_str'] = created_str
            r['agent_name'] = biz['name']
            r['agent_initial'] = (biz['name'] or 'A')[0].upper()
            r['type'] = 'Outbound'
            r['sentiment'] = None
            r['phone'] = r.get('lead_phone') or r.get('phone', '')
            conversations.append(r)
        
        c.execute("SELECT id, name FROM agents WHERE business_id = ? ORDER BY name", (bid,))
        agents_list = [dict(r) for r in c.fetchall()]
    except Exception as e:
        print(f"❌ Conversations data error: {e}")
        import traceback
        traceback.print_exc()
        conversations = []
        agents_list = []
    
    # Fetch landing page
    landing_page = None
    try:
        c.execute("SELECT * FROM landing_pages WHERE business_id=? LIMIT 1", (bid,))
        row = c.fetchone()
        if row:
            landing_page = dict(row)
    except Exception as e:
        print(f"Landing page fetch error: {e}")
    
    # Uploaded documents (menus / inventories / URLs) for the Settings tab
    c.execute(
        "SELECT id, doc_type, name, created_at, length(content) as size FROM kb_documents "
        "WHERE business_id=? ORDER BY created_at DESC", (bid,))
    kb_documents_list = c.fetchall()

    return render_template_string(dashboard_html.replace('<!-- GSC_META -->', gsc_meta_tag()),
        session=session, tab=tab, biz_name=biz['name'],
        industry_title=(biz['industry'] or '').title(),
        biz_info=biz, campaign_status=campaign_status,
        campaign_data=camp, total_leads=leads_total,
        stats={'calls_made':calls_made,'appointments':appointments,
               'leads_total':leads_total,'total_cost':total_cost,
               'leads_new':leads_new,'leads_called':leads_called},
        recent_calls=recent_calls, call_logs=call_logs,
        leads=leads, followups=followups, assigned_numbers=assigned_numbers,
        voices=get_available_voices(),
        appointments=appointment_list,
        calendar_events=calendar_events,
        languages={l["code"]: l["name"] for l in LANGUAGES},
        schedule=schedule,
        factory_products=factory_products,
        ai_stats=ai_stats,
        type_icon=product_type_icon,
        landing_page=landing_page,
        conversations=conversations,
        agents=agents_list,
        kb_documents=kb_documents_list,
        today_date=today_date,
        seven_days_ago=seven_days_ago,
        total_duration=total_duration, user_tier=user_tier,
        extra_minutes=extra_minutes, total_minutes_limit=total_minutes_limit)

# ── CONVERSATIONS API ROUTES ──

@app.route('/api/conversations')
@login_required
def api_conversations():
    """Return conversations list with optional filters."""
    bid = session['business_id']
    agent = request.args.get('agent', '').strip()
    date_from = request.args.get('from', '').strip()
    date_to = request.args.get('to', '').strip()
    
    db = get_db()
    c = db.cursor()
    
    query = """
        SELECT cl.*, l.name as lead_name, l.phone as lead_phone
        FROM call_log cl
        LEFT JOIN leads l ON cl.lead_id = l.id
        WHERE cl.business_id = ?
    """
    params = [bid]
    
    if date_from:
        query += " AND cl.created_at >= ?"
        params.append(date_from)
    if date_to:
        query += " AND cl.created_at <= ?"
        params.append(date_to + " 23:59:59")
    
    query += " ORDER BY cl.created_at DESC LIMIT 100"
    
    c.execute(query, params)
    conversations = []
    for r in c.fetchall():
        r = dict(r)
        dur = r.get('duration', 0) or 0
        dur_str = f'{dur}s' if dur < 60 else f'{dur//60}m{dur%60:02d}s'
        created = r.get('created_at', '')
        r['duration_str'] = dur_str
        r['created_at_str'] = created[:16] if created else ''
        r['agent_name'] = ''
        r['agent_initial'] = 'A'
        r['type'] = 'Outbound'
        r['sentiment'] = None
        r['phone'] = r.get('lead_phone') or r.get('phone', '')
        conversations.append(r)
    
    return jsonify({'success': True, 'conversations': conversations})

@app.route('/api/conversation/<call_id>/transcript')
@login_required
def api_conversation_transcript(call_id):
    """Return transcript for a specific call."""
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("SELECT transcript FROM call_log WHERE id=? AND business_id=?", (call_id, bid))
    row = c.fetchone()
    if row and row['transcript']:
        return jsonify({'success': True, 'transcript': row['transcript']})
    return jsonify({'success': False, 'transcript': None})

# ── ANALYTICS API ROUTES ──

@app.route('/api/analytics/summary')
@login_required
def api_analytics_summary():
    """Return aggregate analytics: total calls, avg duration, total cost, conversion rate, outcomes, daily breakdowns."""
    bid = request.args.get('bid', session.get('business_id', ''))
    days = int(request.args.get('days', 30))
    if not bid:
        return jsonify({'success': False, 'error': 'No business ID'}), 400
    
    db = get_db()
    c = db.cursor()
    
    # Date filter
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    
    # Total calls in period
    c.execute("SELECT COUNT(*) FROM call_log WHERE business_id = ? AND created_at >= ?", (bid, cutoff))
    total_calls = c.fetchone()[0] or 0
    
    # Total appointments
    c.execute("SELECT COUNT(*) FROM appointments WHERE business_id = ? AND status='booked' AND created_at >= ?", (bid, cutoff))
    appointments = c.fetchone()[0] or 0
    
    # Avg duration
    c.execute("SELECT COALESCE(AVG(duration),0) FROM call_log WHERE business_id = ? AND created_at >= ? AND duration > 0", (bid, cutoff))
    avg_duration = round(c.fetchone()[0] or 0, 1)
    
    # Total cost
    c.execute("SELECT COALESCE(SUM(cost),0) FROM call_log WHERE business_id = ? AND created_at >= ?", (bid, cutoff))
    total_cost = round(c.fetchone()[0] or 0, 2)
    
    # Conversion rate: appointments_booked / total calls
    c.execute("SELECT COUNT(*) FROM call_log WHERE business_id = ? AND created_at >= ? AND outcome='appointment_booked'", (bid, cutoff))
    bookings = c.fetchone()[0] or 0
    conversion_rate = round((bookings / total_calls * 100) if total_calls > 0 else 0, 1)
    
    # Calls by day
    c.execute("""
        SELECT DATE(created_at) as day, COUNT(*) as count
        FROM call_log WHERE business_id = ? AND created_at >= ?
        GROUP BY DATE(created_at) ORDER BY day ASC
    """, (bid, cutoff))
    calls_by_day = [{'day': r[0], 'count': r[1]} for r in c.fetchall()]
    
    # Cost by day
    c.execute("""
        SELECT DATE(created_at) as day, COALESCE(SUM(cost),0) as cost
        FROM call_log WHERE business_id = ? AND created_at >= ?
        GROUP BY DATE(created_at) ORDER BY day ASC
    """, (bid, cutoff))
    cost_by_day = [{'day': r[0], 'cost': round(r[1], 4)} for r in c.fetchall()]
    
    # Outcome distribution
    c.execute("""
        SELECT COALESCE(outcome, 'unknown') as outcome, COUNT(*) as count
        FROM call_log WHERE business_id = ? AND created_at >= ?
        GROUP BY outcome ORDER BY count DESC
    """, (bid, cutoff))
    outcomes = {r[0]: r[1] for r in c.fetchall()}
    
    # Avg duration by outcome
    c.execute("""
        SELECT COALESCE(outcome, 'unknown') as outcome, COALESCE(AVG(duration),0) as avg_dur
        FROM call_log WHERE business_id = ? AND created_at >= ? AND duration > 0
        GROUP BY outcome ORDER BY avg_dur DESC
    """, (bid, cutoff))
    duration_by_outcome = {r[0]: round(r[1], 1) for r in c.fetchall()}
    
    return jsonify({
        'success': True,
        'total_calls': total_calls,
        'appointments': appointments,
        'avg_duration': avg_duration,
        'total_cost': total_cost,
        'conversion_rate': conversion_rate,
        'bookings': bookings,
        'calls_by_day': calls_by_day,
        'cost_by_day': cost_by_day,
        'outcomes': outcomes,
        'duration_by_outcome': duration_by_outcome
    })

@app.route('/api/analytics/calls')
@login_required
def api_analytics_calls():
    """Return detailed call log entries for the analytics table."""
    bid = request.args.get('bid', session.get('business_id', ''))
    days = int(request.args.get('days', 30))
    if not bid:
        return jsonify({'success': False, 'error': 'No business ID'}), 400
    
    db = get_db()
    c = db.cursor()
    
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    
    c.execute("""
        SELECT cl.*, l.phone, l.business_name
        FROM call_log cl
        LEFT JOIN leads l ON cl.lead_id = l.id
        WHERE cl.business_id = ? AND cl.created_at >= ?
        ORDER BY cl.created_at DESC LIMIT 100
    """, (bid, cutoff))
    
    calls = [dict(r) for r in c.fetchall()]
    
    return jsonify({
        'success': True,
        'calls': calls
    })

# ── DIAZITES AI LANDING PAGE (inspired by Alex Deal Flow Labs) ──

DIAZITES_LP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diazites — AI Voice Agents That Answer Every Call</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{font-family:'Inter',sans-serif;margin:0;padding:0;box-sizing:border-box}
body{background:#fff;color:#0a0a0a;overflow-x:hidden}
html{scroll-behavior:smooth}
.hero-gradient{background:linear-gradient(135deg,#f8f9ff 0%,#f0f4ff 50%,#faf5ff 100%)}
.phone-mockup{background:#0a0a0f;border:2px solid #1f1f2e;box-shadow:0 0 60px rgba(41,121,255,0.15),inset 0 0 0 1px rgba(41,121,255,0.2)}
.call-bar{width:3px;border-radius:3px;background:#2979FF;animation:wave-pulse 1.5s ease-in-out infinite alternate}
@keyframes wave-pulse{0%{transform:scaleY(0.4)}100%{transform:scaleY(1)}}
.fade-in{opacity:0;transform:translateY(24px);transition:opacity 0.65s ease-out,transform 0.65s ease-out}
.fade-in.visible{opacity:1;transform:translateY(0)}
.btn-primary{background:#0a0a0a;color:white;padding:14px 28px;border-radius:12px;font-weight:600;font-size:0.95rem;border:none;cursor:pointer;transition:all 0.2s}
.btn-primary:hover{background:#1f1f1f;transform:translateY(-1px);box-shadow:0 8px 30px rgba(0,0,0,0.15)}
.btn-primary:disabled{opacity:0.5;cursor:not-allowed;transform:none}
.btn-outline{background:transparent;color:#0a0a0a;padding:14px 28px;border-radius:12px;font-weight:600;font-size:0.95rem;border:2px solid #e5e7eb;cursor:pointer;transition:all 0.2s}
.btn-outline:hover{border-color:#2979FF;background:#f4f8ff}
.step-dot{width:10px;height:10px;border-radius:50%;background:#e5e7eb;transition:all 0.3s}
.step-dot.active{background:#2979FF;transform:scale(1.3)}
.step-dot.done{background:#22c55e}
.form-input{width:100%;padding:14px 16px;border-radius:12px;border:2px solid #e5e7eb;background:#f9fafb;font-size:0.95rem;outline:none;transition:all 0.2s}
.form-input:focus{border-color:#2979FF;background:#fff;box-shadow:0 0 0 3px rgba(41,121,255,0.1)}
.form-input.error{border-color:#ef4444}
.opt-btn{width:100%;text-align:left;padding:14px 16px;border-radius:12px;border:2px solid #e5e7eb;background:#f9fafb;font-size:0.9rem;font-weight:500;cursor:pointer;transition:all 0.15s}
.opt-btn:hover{border-color:#2979FF;background:#eff5ff}
.opt-btn.selected{border-color:#2979FF;background:#eff5ff;font-weight:600}
.opt-btn:disabled{opacity:0.5;cursor:not-allowed}
</style>
</head>
<body>

<!-- NAVBAR -->
<nav class="fixed top-0 w-full z-50 bg-white/95 backdrop-blur-md border-b border-[#e5e5e5]">
  <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <span class="text-xl">🎙️</span>
      <span class="font-bold text-lg" style="background:linear-gradient(135deg,#2979FF,#6366f1);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Diazites</span>
    </div>
    <a href="#demo" onclick="event.preventDefault();document.getElementById('demo').scrollIntoView({behavior:'smooth'})" class="text-xs text-[#6B7280] hover:text-[#0A0A0A] transition-colors">Talk to an Expert →</a>
  </div>
</nav>

<!-- HERO -->
<section class="hero-gradient min-h-screen flex items-center pt-20 pb-16 px-6 relative overflow-hidden">
  <div class="max-w-6xl mx-auto w-full">
    <div class="grid lg:grid-cols-2 gap-12 items-center">
      <div class="space-y-6 max-w-xl">
        <div class="inline-flex items-center gap-2 bg-[#2979FF]/10 border border-[#2979FF]/20 rounded-full px-4 py-1.5 text-xs font-semibold text-[#2979FF]">
          <span class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
          AI Voice Agents — Now Available
        </div>
        <h1 class="text-5xl md:text-6xl lg:text-7xl font-black tracking-tight leading-[1.06]">
          Your Business<br>
          <span style="background:linear-gradient(135deg,#2979FF,#6366f1,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Never Miss a Call</span><br>
          Again
        </h1>
        <p class="text-lg text-[#6B7280] leading-relaxed max-w-lg">
          Diazites AI voice agents answer every call in under 5 seconds — 24/7, 365. They qualify leads, book appointments, and follow up automatically. Just like a real receptionist who never sleeps.
        </p>
        <div class="flex flex-wrap gap-3">
          <a href="#demo" class="btn-primary flex items-center gap-2">Try Diazites Free →</a>
          <a href="#how" class="btn-outline">See How It Works</a>
        </div>
        <div class="flex items-center gap-4 text-sm">
          <div class="flex items-center gap-1.5"><span class="text-green-500">✓</span> <span class="text-[#6B7280]">No setup fees</span></div>
          <div class="flex items-center gap-1.5"><span class="text-green-500">✓</span> <span class="text-[#6B7280]">Cancel anytime</span></div>
          <div class="flex items-center gap-1.5"><span class="text-green-500">✓</span> <span class="text-[#6B7280]">14-day free trial</span></div>
        </div>
      </div>
      
      <!-- Phone mockup -->
      <div class="relative flex justify-center">
        <div class="phone-mockup w-full max-w-sm rounded-3xl p-6 relative overflow-hidden" style="aspect-ratio:9/16">
          <div class="text-center mb-8 mt-4">
            <div class="flex items-center justify-center gap-2 mb-1">
              <span class="text-white text-lg font-bold">Diazites AI</span>
              <span class="text-[#2979FF] text-lg font-bold animate-pulse">●</span>
            </div>
            <p class="text-[#6B7280] text-xs">Live · Inbound Call</p>
          </div>
          
          <!-- Waveform -->
          <div class="flex items-center justify-center gap-[3px] h-24 mb-6" id="waveform">
            <script>
              var wf = document.getElementById('waveform');
              for(var i=0;i<31;i++){
                var h = 8 + Math.random()*48;
                var d = (i*0.035).toFixed(2);
                wf.innerHTML += '<div class="call-bar" style="height:'+Math.round(h)+'px;opacity:'+(0.4+Math.random()*0.6)+';animation-delay:'+d+'s"></div>';
              }
            </script>
          </div>
          
          <div class="text-center text-white">
            <p class="text-sm font-medium">Plumber Mike</p>
            <p class="text-xs text-[#6B7280] mt-1">"I need help with a burst pipe"</p>
          </div>
          
          <!-- AI Response -->
          <div class="mt-6 bg-[#2979FF]/10 border border-[#2979FF]/20 rounded-2xl p-4">
            <div class="flex items-start gap-3">
              <div class="w-8 h-8 rounded-full bg-[#2979FF] flex items-center justify-center text-white text-xs font-bold shrink-0">AI</div>
              <div>
                <p class="text-white text-sm">I'm dispatching a plumber now. Can you confirm your address?</p>
                <div class="flex items-center gap-2 mt-2">
                  <span class="text-[10px] text-[#6B7280]">✓ Appointment booked</span>
                  <span class="text-[10px] text-green-400">● Scheduled</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Floating badges -->
        <div class="absolute -top-4 -right-4 bg-white rounded-xl px-4 py-2.5 shadow-lg border text-xs font-semibold">
          <span class="text-green-500">●</span> &lt;5s Response
        </div>
        <div class="absolute -bottom-4 -left-4 bg-white rounded-xl px-4 py-2.5 shadow-lg border text-xs font-semibold">
          24/7 ⏰ Always On
        </div>
      </div>
    </div>
  </div>
</section>

<!-- TRUSTED BY -->
<section class="max-w-5xl mx-auto px-6 pb-8 text-center">
<p class="text-sm text-[#5c5c70] mb-6 tracking-wider uppercase font-semibold">Trusted By Local Businesses</p>
<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
<div class="card py-5 text-center"><div class="text-lg mb-1">🔧</div><div class="text-sm font-medium">Plumbing Companies</div></div>
<div class="card py-5 text-center"><div class="text-lg mb-1">🦷</div><div class="text-sm font-medium">Dental Offices</div></div>
<div class="card py-5 text-center"><div class="text-lg mb-1">🏡</div><div class="text-sm font-medium">Real Estate Teams</div></div>
<div class="card py-5 text-center"><div class="text-lg mb-1">❄️</div><div class="text-sm font-medium">HVAC Companies</div></div>
</div>
<p class="text-xs text-[#5c5c70] mt-5">Built for: Home Services ✓  Healthcare ✓  Real Estate ✓  Professional Services ✓</p>
</section>

<!-- LIVE VOICE DEMOS -->
<section id="demos" class="max-w-5xl mx-auto px-6 pb-16">
<h2 class="text-3xl font-bold text-center mb-3">🎧 Hear It In <span class="gradient-text">Action</span></h2>
<p class="text-[#7a7a8e] text-center mb-2 max-w-xl mx-auto">Listen to a real customer call handled by Diazites AI — hear how natural, professional, and instant it sounds.</p>
<p class="text-sm text-[#a855f7] text-center mb-10 font-semibold">Click any demo to play</p>

<div class="grid md:grid-cols-3 gap-5">
<!-- Plumber Demo -->
<div class="audio-card" data-demo="plumber" onclick="toggleAudio(this,'/static/audio/demo-plumber.mp3')">
<div class="flex items-start gap-4 mb-3">
<button class="play-btn" id="play-plumber"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></button>
<div class="flex-1">
<div class="flex items-center gap-2 mb-1"><span class="text-lg">🔧</span><span class="font-semibold">Plumber</span><span class="text-[10px] px-2 py-0.5 rounded-full" style="background:#a855f722;color:#c084fc">Emergency</span></div>
<p class="text-xs text-[#7a7a8e]">Burst pipe call — AI triages urgency, captures address, dispatches plumber</p>
</div>
</div>
<div class="flex items-center gap-1" id="waveform-plumber">
<div class="waveform-bar" style="height:12px"></div><div class="waveform-bar" style="height:18px"></div><div class="waveform-bar" style="height:24px"></div><div class="waveform-bar" style="height:32px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:48px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:32px"></div><div class="waveform-bar" style="height:24px"></div><div class="waveform-bar" style="height:18px"></div><div class="waveform-bar" style="height:12px"></div>
</div>
<div class="flex items-center justify-between mt-2">
<span class="text-[10px] text-[#5c5c70]" id="time-plumber">0:00 / 0:20</span>
<span class="text-[10px] text-[#c084fc]" id="status-plumber">▶ Click to play</span>
</div>
</div>

<!-- Dentist Demo -->
<div class="audio-card" data-demo="dentist" onclick="toggleAudio(this,'/static/audio/demo-dentist.mp3')">
<div class="flex items-start gap-4 mb-3">
<button class="play-btn" id="play-dentist"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></button>
<div class="flex-1">
<div class="flex items-center gap-2 mb-1"><span class="text-lg">🦷</span><span class="font-semibold">Dentist</span><span class="text-[10px] px-2 py-0.5 rounded-full" style="background:#22c55e22;color:#4ade80">Booking</span></div>
<p class="text-xs text-[#7a7a8e]">Patient calls — AI checks availability, schedules appointment, sets reminder</p>
</div>
</div>
<div class="flex items-center gap-1" id="waveform-dentist">
<div class="waveform-bar" style="height:14px"></div><div class="waveform-bar" style="height:20px"></div><div class="waveform-bar" style="height:28px"></div><div class="waveform-bar" style="height:36px"></div><div class="waveform-bar" style="height:42px"></div><div class="waveform-bar" style="height:46px"></div><div class="waveform-bar" style="height:48px"></div><div class="waveform-bar" style="height:42px"></div><div class="waveform-bar" style="height:36px"></div><div class="waveform-bar" style="height:28px"></div><div class="waveform-bar" style="height:20px"></div><div class="waveform-bar" style="height:14px"></div>
</div>
<div class="flex items-center justify-between mt-2">
<span class="text-[10px] text-[#5c5c70]" id="time-dentist">0:00 / 0:23</span>
<span class="text-[10px] text-[#c084fc]" id="status-dentist">▶ Click to play</span>
</div>
</div>

<!-- Real Estate Demo -->
<div class="audio-card" data-demo="realestate" onclick="toggleAudio(this,'/static/audio/demo-realestate.mp3')">
<div class="flex items-start gap-4 mb-3">
<button class="play-btn" id="play-realestate"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></button>
<div class="flex-1">
<div class="flex items-center gap-2 mb-1"><span class="text-lg">🏡</span><span class="font-semibold">Real Estate</span><span class="text-[10px] px-2 py-0.5 rounded-full" style="background:#f59e0b22;color:#fbbf24">Qualification</span></div>
<p class="text-xs text-[#7a7a8e]">Property inquiry — AI qualifies buyer, schedules showing, confirms by text</p>
</div>
</div>
<div class="flex items-center gap-1" id="waveform-realestate">
<div class="waveform-bar" style="height:10px"></div><div class="waveform-bar" style="height:16px"></div><div class="waveform-bar" style="height:22px"></div><div class="waveform-bar" style="height:30px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:48px"></div><div class="waveform-bar" style="height:44px"></div><div class="waveform-bar" style="height:38px"></div><div class="waveform-bar" style="height:30px"></div><div class="waveform-bar" style="height:22px"></div><div class="waveform-bar" style="height:16px"></div><div class="waveform-bar" style="height:10px"></div>
</div>
<div class="flex items-center justify-between mt-2">
<span class="text-[10px] text-[#5c5c70]" id="time-realestate">0:00 / 0:21</span>
<span class="text-[10px] text-[#c084fc]" id="status-realestate">▶ Click to play</span>
</div>
</div>
</div>
</section>

<!-- HOW IT WORKS -->
<section id="how" class="py-24 px-6 bg-white">
  <div class="max-w-3xl mx-auto">
    <div class="text-center mb-12">
      <p class="text-xs font-semibold tracking-[0.2em] uppercase text-[#2979FF] mb-3">How It Works</p>
      <h2 class="text-3xl md:text-4xl font-bold tracking-tight">Three Steps to <span style="background:linear-gradient(135deg,#2979FF,#6366f1);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Never Missing a Call</span></h2>
    </div>
    <div class="flex flex-col gap-6">
      <div class="flex items-start gap-4 p-6 rounded-xl border border-[#e5e7eb] bg-[#fafafa] hover:border-[#2979FF]/40 transition-colors">
        <div class="text-xs font-mono font-bold text-[#2979FF] bg-[#2979FF]/10 border border-[#2979FF]/20 rounded-md px-2 py-1 shrink-0 mt-0.5">01</div>
        <div><h3 class="font-semibold text-lg mb-1">Choose Your AI Agent</h3><p class="text-[#6B7280] text-sm leading-relaxed">Select a voice, set your script, and configure your industry. No coding needed — just pick and go.</p></div>
      </div>
      <div class="flex items-start gap-4 p-6 rounded-xl border border-[#e5e7eb] bg-[#fafafa] hover:border-[#2979FF]/40 transition-colors">
        <div class="text-xs font-mono font-bold text-[#2979FF] bg-[#2979FF]/10 border border-[#2979FF]/20 rounded-md px-2 py-1 shrink-0 mt-0.5">02</div>
        <div><h3 class="font-semibold text-lg mb-1">Connect Your Phone Number</h3><p class="text-[#6B7280] text-sm leading-relaxed">Buy a number or port yours in. Forward your current calls to Diazites in 5 minutes.</p></div>
      </div>
      <div class="flex items-start gap-4 p-6 rounded-xl border border-[#e5e7eb] bg-[#fafafa] hover:border-[#2979FF]/40 transition-colors">
        <div class="text-xs font-mono font-bold text-[#2979FF] bg-[#2979FF]/10 border border-[#2979FF]/20 rounded-md px-2 py-1 shrink-0 mt-0.5">03</div>
        <div><h3 class="font-semibold text-lg mb-1">Never Miss Another Lead</h3><p class="text-[#6B7280] text-sm leading-relaxed">Your AI agent answers every call 24/7 — qualifies leads, books appointments, follows up. You just close deals.</p></div>
      </div>
    </div>
  </div>
</section>

<!-- DEMO / FORM SECTION -->
<section id="demo" class="py-24 px-6 bg-[#fafafa]">
  <div class="max-w-3xl mx-auto">
    <div class="text-center mb-10">
      <p class="text-xs font-semibold tracking-[0.2em] uppercase text-[#6B7280] mb-3">Try Diazites</p>
      <h2 class="text-3xl md:text-4xl font-bold tracking-tight">See It In Action</h2>
      <p class="text-[#6B7280] text-sm mt-3 max-w-lg mx-auto">Fill out the form and we'll call you with a live demo. You'll hear the AI in under 60 seconds.</p>
    </div>

    <!-- Multi-step form -->
    <div id="formContainer" class="bg-white rounded-2xl p-8 border border-[#e5e7eb] shadow-sm max-w-lg mx-auto">
      <!-- Step counter -->
      <div class="flex items-center justify-center gap-2 mb-8">
        <div id="stepDot0" class="step-dot active"></div>
        <div class="w-8 h-px bg-[#e5e7eb]"></div>
        <div id="stepDot1" class="step-dot"></div>
        <div class="w-8 h-px bg-[#e5e7eb]"></div>
        <div id="stepDot2" class="step-dot"></div>
      </div>

      <!-- Step 1: Name & Phone -->
      <div id="step0" class="step-content">
        <h3 class="text-xl font-bold mb-1">Let's start. What's your name and number?</h3>
        <p class="text-sm text-[#6B7280] mb-6">We'll call you right now to demo the AI.</p>
        <div class="space-y-3">
          <input type="text" id="lpName" class="form-input" placeholder="Your full name" required>
          <input type="tel" id="lpPhone" class="form-input" placeholder="Your phone number" required>
          <input type="email" id="lpEmail" class="form-input" placeholder="Your email (optional)">
        </div>
        <div id="step0Error" class="hidden text-red-500 text-xs mt-3"></div>
        <button onclick="nextStep(0)" class="btn-primary w-full mt-6 justify-center flex">Continue →</button>
      </div>

      <!-- Step 2: Industry -->
      <div id="step1" class="step-content hidden">
        <h3 class="text-xl font-bold mb-1">What industry are you in?</h3>
        <p class="text-sm text-[#6B7280] mb-6">We'll set up the right script for your business.</p>
        <div class="space-y-2">
          <button type="button" onclick="selectIndustry(this)" class="opt-btn" data-val="plumber">🔧 Plumbing</button>
          <button type="button" onclick="selectIndustry(this)" class="opt-btn" data-val="hvac">❄️ HVAC</button>
          <button type="button" onclick="selectIndustry(this)" class="opt-btn" data-val="roofer">🏠 Roofing</button>
          <button type="button" onclick="selectIndustry(this)" class="opt-btn" data-val="dentist">🦷 Dental</button>
          <button type="button" onclick="selectIndustry(this)" class="opt-btn" data-val="real_estate">🏡 Real Estate</button>
          <button type="button" onclick="selectIndustry(this)" class="opt-btn" data-val="pest_control">🐜 Pest Control</button>
          <button type="button" onclick="selectIndustry(this)" class="opt-btn" data-val="general">📋 General Business</button>
        </div>
        <div id="step1Error" class="hidden text-red-500 text-xs mt-3"></div>
        <div class="flex gap-3 mt-6">
          <button onclick="prevStep(1)" class="btn-outline flex-1">← Back</button>
          <button onclick="nextStep(1)" class="btn-primary flex-1">Continue →</button>
        </div>
      </div>

      <!-- Step 3: Budget + Submit -->
      <div id="step2" class="step-content hidden">
        <h3 class="text-xl font-bold mb-1">What's your monthly marketing budget?</h3>
        <p class="text-sm text-[#6B7280] mb-6">How many leads do you want to capture?</p>
        <div class="space-y-2">
          <button type="button" onclick="selectBudget(this)" class="opt-btn" data-val="under_500">Under $500/mo — Just starting out</button>
          <button type="button" onclick="selectBudget(this)" class="opt-btn" data-val="500_2k">$500–$2,000/mo — Growing</button>
          <button type="button" onclick="selectBudget(this)" class="opt-btn" data-val="2k_5k">$2,000–$5,000/mo — Established</button>
          <button type="button" onclick="selectBudget(this)" class="opt-btn" data-val="5k_plus">$5,000+/mo — Scaling aggressively</button>
          <button type="button" onclick="selectBudget(this)" class="opt-btn" data-val="not_sure">Not sure yet — Just exploring</button>
        </div>
        <div id="step2Error" class="hidden text-red-500 text-xs mt-3"></div>
        <div class="flex gap-3 mt-6">
          <button onclick="prevStep(2)" class="btn-outline flex-1">← Back</button>
          <button id="submitBtn" onclick="submitForm()" class="btn-primary flex-1 justify-center flex items-center gap-2">🎯 See Diazites in Action</button>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- BENEFITS -->
<section class="py-24 px-6 bg-white">
  <div class="max-w-4xl mx-auto">
    <div class="text-center mb-12">
      <p class="text-xs font-semibold tracking-[0.2em] uppercase text-[#2979FF] mb-3">Why Diazites</p>
      <h2 class="text-3xl md:text-4xl font-bold tracking-tight">The <span style="background:linear-gradient(135deg,#2979FF,#6366f1);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Diazites Standard</span></h2>
    </div>
    <div class="grid md:grid-cols-3 gap-6">
      <div class="p-6 rounded-xl border border-[#e5e7eb] bg-[#fafafa] hover:border-[#2979FF]/40 transition-colors text-center">
        <div class="text-3xl mb-3">⚡</div>
        <h3 class="font-semibold mb-1">Under 5 Seconds</h3>
        <p class="text-sm text-[#6B7280]">Your first lead never gets cold. AI picks up before the phone finishes ringing.</p>
      </div>
      <div class="p-6 rounded-xl border border-[#e5e7eb] bg-[#fafafa] hover:border-[#2979FF]/40 transition-colors text-center">
        <div class="text-3xl mb-3">🌙</div>
        <h3 class="font-semibold mb-1">24/7/365</h3>
        <p class="text-sm text-[#6B7280]">Weekends, holidays, 3 AM. Your AI agent never clocks out, never gets tired.</p>
      </div>
      <div class="p-6 rounded-xl border border-[#e5e7eb] bg-[#fafafa] hover:border-[#2979FF]/40 transition-colors text-center">
        <div class="text-3xl mb-3">📊</div>
        <h3 class="font-semibold mb-1">Qualifies Every Lead</h3>
        <p class="text-sm text-[#6B7280]">Asks the right questions, captures data, books appointments. Ready-to-close sellers hit your CRM.</p>
      </div>
    </div>
  </div>
</section>

<!-- VOICE DEMO -->
<section class="py-20 px-6 bg-[#f8f9ff]">
  <div class="max-w-4xl mx-auto text-center">
    <p class="text-xs font-semibold tracking-[0.2em] uppercase text-[#2979FF] mb-3">Hear It Live</p>
    <h2 class="text-3xl md:text-4xl font-bold tracking-tight mb-4">Meet <span style="background:linear-gradient(135deg,#2979FF,#6366f1);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Rachel</span> — Your AI Agent</h2>
    <p class="text-[#6B7280] text-sm mb-8 max-w-xl mx-auto">The most natural AI voice on the market. Click to hear Rachel handle a real call.</p>
    <div class="flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
      <button onclick="playVoiceDemo('rachel','Hi, thanks for calling! This is Rachel, your AI assistant. How can I help you today?')" class="btn-primary flex items-center gap-3 px-8 py-4 text-base">
        <span class="text-xl" id="rachelIcon">▶️</span>
        <span>Play Rachel</span>
      </button>
      <button onclick="playVoiceDemo('sam','Hey there! Sam here. I handle incoming calls for your business so you never miss an opportunity.')" class="btn-outline flex items-center gap-3 px-8 py-4 text-base">
        <span class="text-xl" id="samIcon">▶️</span>
        <span>Play Sam (Male)</span>
      </button>
      <button onclick="playVoiceDemo('emma','Hello! Emma speaking. I answer questions and book appointments 24/7. How can I help you today?')" class="btn-outline flex items-center gap-3 px-8 py-4 text-base">
        <span class="text-xl" id="emmaIcon">▶️</span>
        <span>Play Emma</span>
      </button>
      <button onclick="playVoiceDemo('TX3LPaxmHKxFdv7VOQHJ','Hey, Liam here. I handle your calls, qualify leads, and book appointments so you can focus on the work that matters.')" class="btn-outline flex items-center gap-3 px-8 py-4 text-base">
        <span class="text-xl" id="TX3LPaxmHKxFdv7VOQHJIcon">▶️</span>
        <span>Play Liam</span>
      </button>
      <button onclick="playVoiceDemo('cgSgspJ2msm6clMCkdW9','Hi, this is Jessica! I help your callers with anything they need.')" class="btn-outline flex items-center gap-3 px-8 py-4 text-base">
        <span class="text-xl" id="cgSgspJ2msm6clMCkdW9Icon">▶️</span>
        <span>Play Jessica</span>
      </button>
    </div>
    <p id="demoStatus" class="text-xs text-[#6B7280]">Click any voice to hear it live. Real ElevenLabs AI voices.</p>
  </div>
</section>

<!-- FOOTER -->
<footer class="border-t border-[#e5e5e5] py-8 px-6 text-center bg-white">
  <div class="max-w-md mx-auto">
    <div class="flex items-center justify-center gap-2 mb-3">
      <span class="text-lg">🎙️</span>
      <span class="font-bold" style="background:linear-gradient(135deg,#2979FF,#6366f1);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Diazites</span>
    </div>
    <p class="text-xs text-[#6B7280]">AI Voice Agents for Business © 2026</p>
  </div>
</footer>

<script>
var formData = {step: 0, name: '', phone: '', email: '', industry: '', budget: ''};
var selectedVal = {};

// Voice demo player
var demoAudio = null;
function playVoiceDemo(voiceId, text) {
  if (demoAudio) { demoAudio.pause(); demoAudio = null; }
  document.querySelectorAll('[id$=Icon]').forEach(function(el){ el.textContent = '▶️'; });
  document.getElementById(voiceId + 'Icon').textContent = '⏳';
  demoAudio = new Audio('/api/test-voice?voice_id=' + encodeURIComponent(voiceId) + '&text=' + encodeURIComponent(text) + '&speed=1.0&t=' + Date.now());
  demoAudio.onended = function(){ document.getElementById(voiceId + 'Icon').textContent = '▶️'; demoAudio = null; };
  demoAudio.onerror = function(){ document.getElementById(voiceId + 'Icon').textContent = '❌'; demoAudio = null; };
  demoAudio.play().catch(function(){ document.getElementById(voiceId + 'Icon').textContent = '❌'; });
}

function nextStep(s) {
  var err = document.getElementById('step'+s+'Error');
  err.classList.add('hidden');
  
  if (s === 0) {
    var name = document.getElementById('lpName').value.trim();
    var phone = document.getElementById('lpPhone').value.trim();
    if (!name || !phone) {
      err.textContent = 'Please fill in your name and phone number.';
      err.classList.remove('hidden');
      return;
    }
    formData.name = name;
    formData.phone = phone;
    formData.email = document.getElementById('lpEmail').value.trim();
  }
  if (s === 1) {
    if (!selectedVal.industry) {
      err.textContent = 'Please select your industry.';
      err.classList.remove('hidden');
      return;
    }
    formData.industry = selectedVal.industry;
  }
  
  document.getElementById('step'+s).classList.add('hidden');
  document.getElementById('step'+(s+1)).classList.remove('hidden');
  document.getElementById('stepDot'+s).classList.remove('active');
  document.getElementById('stepDot'+s).classList.add('done');
  document.getElementById('stepDot'+(s+1)).classList.add('active');
  formData.step = s + 1;
  window.scrollTo({top: document.getElementById('formContainer').offsetTop - 120, behavior: 'smooth'});
}

function prevStep(s) {
  document.getElementById('step'+s).classList.add('hidden');
  document.getElementById('step'+(s-1)).classList.remove('hidden');
  document.getElementById('stepDot'+s).classList.remove('active');
  document.getElementById('stepDot'+(s-1)).classList.remove('done');
  document.getElementById('stepDot'+(s-1)).classList.add('active');
  formData.step = s - 1;
}

function selectIndustry(el) {
  document.querySelectorAll('#step1 .opt-btn').forEach(function(b) { b.classList.remove('selected'); });
  el.classList.add('selected');
  selectedVal.industry = el.getAttribute('data-val');
}

function selectBudget(el) {
  document.querySelectorAll('#step2 .opt-btn').forEach(function(b) { b.classList.remove('selected'); });
  el.classList.add('selected');
  selectedVal.budget = el.getAttribute('data-val');
  formData.budget = selectedVal.budget;
}

function submitForm() {
  var err = document.getElementById('step2Error');
  var btn = document.getElementById('submitBtn');
  err.classList.add('hidden');
  
  if (!selectedVal.budget) {
    err.textContent = 'Please select your budget range.';
    err.classList.remove('hidden');
    return;
  }
  
  btn.disabled = true;
  btn.innerHTML = '<div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div> Processing...';
  
  fetch('/try/submit', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(formData)
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    if (d.success) {
      window.location.href = '/try/booking?name=' + encodeURIComponent(d.name);
    } else {
      btn.disabled = false;
      btn.innerHTML = '🎯 See Diazites in Action';
      err.textContent = d.error || 'Something went wrong.';
      err.classList.remove('hidden');
    }
  })
  .catch(function() {
    btn.disabled = false;
    btn.innerHTML = '🎯 See Diazites in Action';
    err.textContent = 'Network error. Please try again.';
    err.classList.remove('hidden');
  });
}
</script>
</body>
</html>"""

DIAZITES_BOOKING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>You're Next — Diazites Live Demo</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{font-family:'Inter',sans-serif;margin:0;padding:0;box-sizing:border-box}
body{background:#fff;color:#0a0a0a}
.hero-gradient{background:linear-gradient(135deg,#f8f9ff 0%,#f0f4ff 50%,#faf5ff 100%)}
</style>
</head>
<body>

<section class="hero-gradient min-h-screen flex items-center justify-center px-6 py-16">
  <div class="max-w-3xl mx-auto w-full text-center">
    <div class="text-6xl mb-4">🎉</div>
    <h1 class="text-4xl md:text-5xl font-black tracking-tight mb-2"><span id="visitorGreeting">PABLO</span>, You're <span style="background:linear-gradient(135deg,#2979FF,#6366f1);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Next</span></h1>
    <p class="text-lg text-[#6B7280] mb-6 max-w-lg mx-auto">Our team member is calling you right now with a live demo. While you wait, watch how Diazites works:</p>
    
    <!-- Video Player -->
    <div class="rounded-2xl overflow-hidden border border-[#e5e7eb] shadow-sm mb-8 bg-black max-w-2xl mx-auto" style="aspect-ratio:16/9">
      <video controls autoplay muted playsinline class="w-full h-full object-contain bg-black"
             poster="https://shopzario.com/static/product_images/course_mastery_bundle.png"
             preload="auto">
        <source src="https://shopzario.com/static/product_images/alex_ai_booking.mp4" type="video/mp4">
        <p>Your browser doesn't support video. <a href="https://shopzario.com/static/product_images/alex_ai_booking.mp4" class="text-[#2979FF]">Download the video</a></p>
      </video>
    </div>
    
    <!-- Calendly -->
    <div class="max-w-xl mx-auto">
      <p class="text-sm text-[#6B7280] mb-4 font-semibold">📅 Or book a time for a full walkthrough:</p>
      <div class="calendly-inline-widget rounded-2xl overflow-hidden border border-[#e5e7eb]" data-url="https://calendly.com/diazites/demo" style="min-width:280px;height:600px"></div>
    </div>
    
    <div class="mt-8 text-center">
      <p class="text-xs text-[#6B7280]">Questions? <a href="mailto:hello@diazites.online" class="text-[#2979FF] hover:underline">hello@diazites.online</a></p>
    </div>
  </div>
</section>

<script>
var params = new URLSearchParams(window.location.search);
var name = params.get('name') || 'there';
document.getElementById('visitorGreeting').textContent = name.toUpperCase();

// Load Calendly
var s = document.createElement('script');
s.src = 'https://assets.calendly.com/assets/external/widget.js';
s.async = true;
document.body.appendChild(s);
</script>

<footer class="py-8 text-center border-t border-[#e5e5e5]">
  <p class="text-xs text-[#6B7280]">Diazites — AI Voice Agents for Business © 2026</p>
</footer>
</body>
</html>"""

@app.route('/try')
def diazites_landing():
    """High-conversion landing page. Form submits lead, redirects to booking."""
    return render_template_string(DIAZITES_LP_HTML)

@app.route('/try/submit', methods=['POST'])
def diazites_landing_submit():
    """Submit lead from the landing page form."""
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    email = data.get('email', '').strip()
    monthly_budget = data.get('budget', '')
    industry = data.get('industry', '')
    
    if not name or not phone:
        return jsonify({'success': False, 'error': 'Name and phone required'}), 400
    
    import uuid
    lid = str(uuid.uuid4())[:12]
    
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO leads (id, business_id, name, phone, notes, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))""",
              (lid, 'lead-capture', name, phone,
               f"Industry: {industry} | Budget: {monthly_budget}"))
    db.commit()
    
    return jsonify({'success': True, 'lead_id': lid, 'name': name})

@app.route('/try/booking')
def diazites_booking():
    """Booking page after form submission."""
    return render_template_string(DIAZITES_BOOKING_HTML)

# ── LANDING PAGE ROUTES ──

@app.route('/landing/save', methods=['POST'])
@login_required
def landing_save():
    """Save landing page configuration."""
    bid = session['business_id']
    title = request.form.get('title', 'AI Voice Agent')
    tagline = request.form.get('tagline', 'Never Miss a Call Again')
    description = request.form.get('description', '')
    primary_color = request.form.get('primary_color', '#a855f7')
    secondary_color = request.form.get('secondary_color', '#ec4899')
    template = request.form.get('template', 'modern')
    custom_domain = request.form.get('custom_domain', '').strip().lower()
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id FROM landing_pages WHERE business_id=?", (bid,))
    existing = c.fetchone()
    
    if existing:
        c.execute("""UPDATE landing_pages SET title=?, tagline=?, description=?,
            primary_color=?, secondary_color=?, template=?, custom_domain=?,
            published=1, updated_at=datetime('now') WHERE business_id=?""",
            (title, tagline, description, primary_color, secondary_color, template, custom_domain, bid))
    else:
        import uuid
        lid = str(uuid.uuid4())[:12]
        c.execute("""INSERT INTO landing_pages (id, business_id, title, tagline, description,
            primary_color, secondary_color, template, custom_domain, published)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (lid, bid, title, tagline, description, primary_color, secondary_color, template, custom_domain))
    
    db.commit()
    
    # If custom domain set, add nginx config note
    if custom_domain:
        # Store domain mapping
        c.execute("""INSERT OR REPLACE INTO settings (key, value) 
            VALUES (?, ?)""", (f'domain_{custom_domain}', bid))
        db.commit()
    
    return jsonify({'success': True, 'message': '✅ Landing page saved & published!'})

@app.route('/landing/generate-images', methods=['POST'])
@login_required
def landing_generate_images():
    """Generate hero image for landing page using Venice AI."""
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("SELECT name, industry FROM businesses WHERE id=?", (bid,))
    biz = c.fetchone()
    biz_name = biz['name'] if biz else 'Business'
    industry = biz['industry'] if biz else 'business'
    
    try:
        api_key = os.environ.get('VENICE_API_KEY', '')
        if not api_key:
            try:
                with open('/root/voice-agent-manager/api_keys.json') as f:
                    keys = json.load(f)
                api_key = keys.get('VENICE_API_KEY', '')
            except:
                pass
        if not api_key:
            return jsonify({'success': False, 'message': 'Venice API key not configured'})
        
        prompt = f"Professional {industry} AI phone assistant concept art, glowing smartphone with AI brain hologram, purple and blue neon glow, dark background, high quality digital art"
        
        result = subprocess.run(["curl","-s","--max-time","60","-X","POST",
            "https://api.venice.ai/api/v1/image/generate",
            "-H",f"Authorization: Bearer {api_key}",
            "-H","Content-Type: application/json",
            "-d",json.dumps({"model":"lustify-sdxl","prompt":prompt,"width":1024,"height":1024,"steps":25,"cfg_scale":7})],
            capture_output=True, text=True, timeout=70)
        
        data = json.loads(result.stdout)
        if 'images' in data and data['images']:
            import base64
            img_data = data['images'][0]
            if ',' in img_data[:100]:
                img_data = img_data.split(',', 1)[1]
            img_bytes = base64.b64decode(img_data)
            
            img_dir = "/root/voice-agent-manager/static/landing_images"
            os.makedirs(img_dir, exist_ok=True)
            img_path = f"{img_dir}/{bid}.png"
            with open(img_path, 'wb') as f:
                f.write(img_bytes)
            
            c.execute("UPDATE landing_pages SET hero_image=? WHERE business_id=?", (f"/static/landing_images/{bid}.png", bid))
            db.commit()
            return jsonify({'success': True, 'message': '🎨 Image generated!'})
        else:
            return jsonify({'success': False, 'message': 'Image generation failed: ' + str(data)[:200]})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/lp/<bid>')
def serve_landing_page(bid):
    """Serve a published landing page for a business - industry-aware with full SEO, audio, gallery, video."""
    db = get_db()
    c = db.cursor()
    try:
        c.execute("SELECT lp.*, b.name as biz_name, b.industry, b.phone_number FROM landing_pages lp JOIN businesses b ON lp.business_id=b.id WHERE lp.business_id=? AND lp.published=1", (bid,))
        lp = c.fetchone()
    except Exception as e:
        print(f"Landing page fetch error: {e}")
        lp = None
    if not lp:
        return "<h1>Landing page not found</h1>", 404
    
    lp = dict(lp)
    industry = (lp.get('industry') or 'general').lower().strip()
    ind = get_industry_data(industry)
    
    phone = lp.get('phone_number', '') or lp.get('contact_phone', '')
    display_phone = phone if phone else '+1 (888) 555-1234'
    biz_name = lp['biz_name']
    
    features = []
    if lp.get('features_desc'):
        features = [f.strip() for f in lp['features_desc'].split('|') if f.strip()]
    if not features:
        features = FALLBACK_FEATURES
    
    hero_img = lp.get('hero_image') or ''
    fc = lp.get('primary_color', '#a855f7')
    sc = lp.get('secondary_color', '#ec4899')
    title = lp.get('title', ind.get('og_title', 'Professional Services'))
    tagline = lp.get('tagline', 'Never Miss a Call. Book More Clients.')
    desc = lp.get('description', f'AI-powered service that answers calls 24/7, books appointments, and follows up with leads for {biz_name}.')
    
    seo_title = lp.get('seo_title', '') or f'{title} | {biz_name}'
    meta_desc = lp.get('meta_description', '') or desc[:155]
    meta_kw = lp.get('meta_keywords', '') or f'{biz_name}, {industry}, AI voice agent, appointment booking, customer service'
    
    gallery = [g.strip() for g in (lp.get('gallery_images') or '').split('|') if g.strip()]
    featured_video = lp.get('featured_video', '')
    demo_audio = lp.get('demo_audio', '')
    demo_audio_label = lp.get('demo_audio_label', 'Hear Our AI in Action')
    
    if not gallery:
        gallery = [
            'https://images.unsplash.com/photo-1590674899484-d5640f00aec6?w=800&q=80',
            'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=800&q=80',
        ]
    
    icon = ind.get('icon', '📞')
    hero_badge = ind.get('hero_badge', 'Professional Services')
    trust_1 = ind.get('trust_1', 'Trusted Locally')
    trust_2 = ind.get('trust_2', '5-Star Service')
    cta_text = ind.get('cta', '📞 Call Us Today')
    cta_sub = ind.get('cta_sub', 'Free consultation • Professional service')
    cal_username = lp.get('cal_username', '') or CAL_COM_USERNAME
    cal_event_slug = lp.get('cal_event_slug', '30min')
    
    from lp_generator import generate_landing_html
    return generate_landing_html(bid, biz_name, title, tagline, desc, features, hero_img, fc, sc,
                                seo_title, meta_desc, meta_kw, gallery, featured_video,
                                demo_audio, demo_audio_label, icon, hero_badge, trust_1, trust_2,
                                cta_text, cta_sub, display_phone, cal_username, cal_event_slug)

@app.route('/landing/ai-generate', methods=['POST'])
@login_required
def landing_ai_generate():
    """One-click AI landing page generator — creates copy, image, and publishes."""
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("SELECT name, industry, email FROM businesses WHERE id=?", (bid,))
    biz = c.fetchone()
    if not biz:
        return jsonify({'success': False, 'message': 'Business not found'}), 404
    
    biz_name = biz['name']
    industry = biz['industry'] or 'business'
    # Try env first, then api_keys.json file
    api_key = os.environ.get('VENICE_API_KEY', '')
    if not api_key:
        try:
            with open('/root/voice-agent-manager/api_keys.json') as f:
                keys = json.load(f)
            api_key = keys.get('VENICE_API_KEY', '')
        except:
            pass
    
    if not api_key:
        return jsonify({'success': False, 'message': 'Venice API key not configured'}), 400
    
    try:
        # 1. Generate copy with Venice AI
        r = requests.post(
            "https://api.venice.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "venice-uncensored-1-2",
                "messages": [
                    {"role": "system", "content": "You generate high-converting landing page copy for AI voice agent businesses. Return ONLY valid JSON, no markdown."},
                    {"role": "user", "content": f"""Create landing page copy for a business called "{biz_name}" in the {industry} industry that uses an AI voice agent to answer calls and book appointments.
Return this EXACT JSON format (no other text):
{{
  "title": "catchy short title for the AI service",
  "tagline": "one-line benefit statement",
  "description": "2-3 sentence description of the service with key benefits",
  "features": ["feature 1", "feature 2", "feature 3", "feature 4"],
  "primary_color": "#a855f7",
  "secondary_color": "#ec4899"
}}
Make the title and tagline specific to {industry} businesses. The description should mention {biz_name}. Be persuasive and conversion-focused."""}
                ],
                "max_tokens": 800,
                "temperature": 0.7
            },
            timeout=30
        )
        data = r.json()
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        
        # Clean markdown fences if present
        if '```' in content:
            content = content.split('```')[1] if content.count('```') >= 2 else content
            if content.startswith('json'):
                content = content[4:]
        
        copy = json.loads(content)
    except Exception as e:
        print(f"Venice API copy generation failed: {e}")
        # Fallback defaults
        copy = {
            "title": f"24/7 AI Voice Agent for {biz_name}",
            "tagline": "Never Miss a Call. Book More Clients.",
            "description": f"AI-powered voice agent that answers calls, books appointments, and follows up with leads for {biz_name}. Works 24/7 in your industry.",
            "features": ["Answer calls 24/7", "Book appointments automatically", "Multi-language support", "Follow up with leads"],
            "primary_color": "#a855f7",
            "secondary_color": "#ec4899"
        }
    
    # 2. Generate hero image via Venice
    hero_image = ''
    try:
        img_prompt = f"Professional {industry} business concept, AI phone assistant floating above a desk, purple and blue neon glow, photorealistic, dark background, high quality, cinematic lighting"
        img_r = requests.post(
            "https://api.venice.ai/api/v1/image/generate",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "lustify-sdxl", "prompt": img_prompt, "width": 1024, "height": 768, "steps": 20, "cfg_scale": 7},
            timeout=60
        )
        img_data = img_r.json()
        if 'images' in img_data and img_data['images']:
            import base64
            raw = img_data['images'][0]
            if ',' in raw[:100]:
                raw = raw.split(',', 1)[1]
            img_dir = "/root/voice-agent-manager/static/landing_images"
            os.makedirs(img_dir, exist_ok=True)
            img_path = f"{img_dir}/{bid}.png"
            with open(img_path, 'wb') as f:
                f.write(base64.b64decode(raw))
            hero_image = f"/static/landing_images/{bid}.png"
    except Exception as e:
        print(f"Image gen failed: {e}")
    
    # 3. Save to DB
    import uuid
    features_text = '|'.join(copy.get('features', []))
    c.execute("SELECT id FROM landing_pages WHERE business_id=?", (bid,))
    existing = c.fetchone()
    
    if existing:
        c.execute("""UPDATE landing_pages SET title=?, tagline=?, description=?,
            primary_color=?, secondary_color=?, template='modern', hero_image=?,
            features_desc=?, published=1, updated_at=datetime('now') WHERE business_id=?""",
            (copy['title'], copy['tagline'], copy['description'],
             copy['primary_color'], copy['secondary_color'], hero_image,
             features_text, bid))
    else:
        lid = str(uuid.uuid4())[:12]
        c.execute("""INSERT INTO landing_pages (id, business_id, title, tagline, description,
            primary_color, secondary_color, template, hero_image, features_desc, published)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'modern', ?, ?, 1)""",
            (lid, bid, copy['title'], copy['tagline'], copy['description'],
             copy['primary_color'], copy['secondary_color'], hero_image, features_text))
    
    db.commit()
    
    return jsonify({
        'success': True,
        'message': f'🎉 Landing page generated for {biz_name}!',
        'page_url': f'/lp/{bid}',
        'copy': copy
    })

@app.route('/landing/update', methods=['POST'])
@login_required
def landing_update():
    """Update specific landing page fields."""
    bid = session['business_id']
    field = request.form.get('field', '')
    value = request.form.get('value', '')
    allowed_fields = ['title', 'tagline', 'description', 'primary_color', 'secondary_color',
                      'features_desc', 'custom_domain', 'meta_description', 'meta_keywords',
                      'seo_title', 'featured_video', 'demo_audio_label', 'contact_phone', 'contact_email']
    if field not in allowed_fields:
        return jsonify({'success': False, 'message': 'Invalid field'})
    db = get_db()
    c = db.cursor()
    c.execute(f"UPDATE landing_pages SET {field}=?, updated_at=datetime('now') WHERE business_id=?", (value, bid))
    db.commit()
    return jsonify({'success': True, 'message': '✅ Updated!'})

@app.route('/landing/unpublish', methods=['POST'])
@login_required
def landing_unpublish():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE landing_pages SET published=0, updated_at=datetime('now') WHERE business_id=?", (bid,))
    db.commit()
    return jsonify({'success': True, 'message': '✅ Landing page unpublished'})

@app.route('/landing/publish', methods=['POST'])
@login_required
def landing_publish():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE landing_pages SET published=1, updated_at=datetime('now') WHERE business_id=?", (bid,))
    db.commit()
    return jsonify({'success': True, 'message': '✅ Landing page published!'})

@app.route('/landing/upload-media', methods=['POST'])
@login_required
def landing_upload_media():
    """Upload media (image, audio) for landing page."""
    bid = session['business_id']
    media_type = request.args.get('type', 'hero')
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': 'No file selected'})
    media_dir = f"/root/voice-agent-manager/static/landing_media/{bid}"
    os.makedirs(media_dir, exist_ok=True)
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'png'
    safe_ext = ext if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'mp3', 'wav', 'ogg', 'mp4'] else 'png'
    if media_type == 'hero':
        fname = f"hero.{safe_ext}"
    elif media_type == 'gallery':
        fname = f"gallery_{int(time.time())}.{safe_ext}"
    elif media_type == 'audio':
        fname = f"demo.{safe_ext}" if safe_ext in ['mp3', 'wav', 'ogg'] else f"demo.mp3"
    else:
        fname = f"media_{int(time.time())}.{safe_ext}"
    fpath = os.path.join(media_dir, fname)
    file.save(fpath)
    url = f"/static/landing_media/{bid}/{fname}"
    db = get_db()
    c = db.cursor()
    if media_type == 'hero':
        c.execute("UPDATE landing_pages SET hero_image=?, updated_at=datetime('now') WHERE business_id=?", (url, bid))
    elif media_type == 'audio':
        c.execute("UPDATE landing_pages SET demo_audio=?, updated_at=datetime('now') WHERE business_id=?", (url, bid))
    elif media_type == 'gallery':
        c.execute("SELECT gallery_images FROM landing_pages WHERE business_id=?", (bid,))
        row = c.fetchone()
        existing = row['gallery_images'] if row and row['gallery_images'] else ''
        images = [i.strip() for i in existing.split('|') if i.strip()]
        images.append(url)
        c.execute("UPDATE landing_pages SET gallery_images=?, updated_at=datetime('now') WHERE business_id=?", ('|'.join(images), bid))
    db.commit()
    return jsonify({'success': True, 'message': '✅ Media uploaded!', 'url': url})

# ── CAL.COM INTEGRATION ──

@app.route('/api/calcom/save-settings', methods=['POST'])
@login_required
def save_calcom_settings():
    """Save Cal.com settings for a business."""
    bid = session['business_id']
    username = request.form.get('username', '').strip()
    event_slug = request.form.get('event_slug', '30min').strip()
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE landing_pages SET cal_username=?, cal_event_slug=?, updated_at=datetime('now') WHERE business_id=?", (username, event_slug, bid))
    if c.rowcount == 0:
        c.execute("INSERT OR IGNORE INTO landing_pages (business_id, cal_username, cal_event_slug) VALUES (?, ?, ?)", (bid, username, event_slug))
    db.commit()
    return jsonify({'success': True, 'message': '✅ Booking settings saved!'})

@app.route('/api/calcom/create-booking', methods=['POST'])
@login_required
def calcom_create_booking():
    """Create a booking in Cal.com — called by AI agent or dashboard."""
    bid = session['business_id']
    name = request.form.get('name', 'Client')
    email = request.form.get('email', '')
    phone = request.form.get('phone', '')
    notes = request.form.get('notes', '')
    start_time = request.form.get('start_time', '')
    timezone = request.form.get('timezone', 'America/New_York')
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT cal_username, cal_event_slug FROM landing_pages WHERE business_id=?", (bid,))
    row = c.fetchone()
    cal_username = row['cal_username'] if row and row['cal_username'] else CAL_COM_USERNAME
    cal_event_slug = row['cal_event_slug'] if row and row['cal_event_slug'] else '30min'
    
    # Get event type ID from slug
    import requests as http_req
    headers = {'Authorization': f'Bearer {CAL_COM_API_KEY}', 'Content-Type': 'application/json'}
    
    # Find event type ID
    et_resp = http_req.get(f'https://api.cal.com/v2/event-types?username={cal_username}', headers=headers, timeout=15)
    event_type_id = None
    if et_resp.status_code == 200:
        et_data = et_resp.json()
        groups = et_data.get('data', {}).get('eventTypeGroups', [])
        for g in groups:
            for et in g.get('eventTypes', []):
                if et.get('slug') == cal_event_slug:
                    event_type_id = et['id']
                    break
    
    if not event_type_id:
        event_type_id = 4493177  # fallback: 30min meeting ID
    
    # Create booking via Cal.com API v2
    payload = {
        'eventTypeId': event_type_id,
        'start': start_time,
        'responses': {
            'name': name,
            'email': email,
            'notes': notes,
            'location': {'optionValue': '', 'value': 'userPhone' if phone else 'integrations:daily'}
        },
        'timeZone': timezone,
        'language': 'en',
        'metadata': {'source': 'diazites-ai-agent', 'business_id': bid, 'phone': phone},
    }
    
    try:
        resp = http_req.post('https://api.cal.com/v2/bookings', json=payload, headers=headers, timeout=15)
        data = resp.json()
        if resp.status_code in (200, 201):
            booking_uid = data.get('data', {}).get('uid', '')
            return jsonify({'success': True, 'message': '✅ Booking created!', 'booking_uid': booking_uid, 'data': data.get('data', {})})
        else:
            return jsonify({'success': False, 'message': f'Cal.com error: {data.get("error", data.get("status", "unknown"))}', 'detail': str(data)[:500]})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/calcom/embed-url', methods=['GET'])
@login_required
def calcom_embed_url():
    """Get the Cal.com embed URL for the current business."""
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("SELECT cal_username, cal_event_slug FROM landing_pages WHERE business_id=?", (bid,))
    row = c.fetchone()
    username = (row['cal_username'] if row and row['cal_username'] else CAL_COM_USERNAME)
    slug = (row['cal_event_slug'] if row and row['cal_event_slug'] else '30min')
    return jsonify({'success': True, 'url': f'https://cal.com/{username}/{slug}', 'username': username, 'slug': slug})

# ── PAYMENT COLLECTION ──

@app.route('/api/payment/create-link', methods=['POST'])
@login_required
def api_create_payment_link():
    """Create a Stripe payment link for a customer."""
    bid = session['business_id']
    data = request.get_json() or {}
    amount = float(data.get('amount', 0))
    customer_name = data.get('customer_name', '')
    customer_phone = data.get('customer_phone', '')
    description = data.get('description', 'Service Payment')
    
    if amount < 1:
        return jsonify({'success': False, 'message': 'Minimum amount is $1'}), 400
    
    try:
        from premium_features import create_stripe_checkout, load_stripe_config
        cfg = load_stripe_config()
        if not cfg:
            return jsonify({'success': False, 'message': 'Stripe not configured'}), 400
        
        price_cents = int(amount * 100)
        base = request.host_url.rstrip('/')
        success_url = f"{base}/?tab=payments&status=success"
        cancel_url = f"{base}/?tab=payments&status=cancel"
        
        url = create_stripe_checkout(bid, description, price_cents, customer_phone or f"{bid}@diazites.online", success_url, cancel_url)
        
        if url:
            import uuid
            pid = str(uuid.uuid4())[:12]
            db = get_db()
            c = db.cursor()
            c.execute("""INSERT INTO payment_links (id, business_id, amount, customer_name, customer_phone, description, stripe_url, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'sent')""",
                      (pid, bid, amount, customer_name, customer_phone, description, url))
            db.commit()
            return jsonify({'success': True, 'payment_url': url, 'id': pid, 'message': f'💰 Payment link created for ${amount:.2f}'})
        else:
            return jsonify({'success': False, 'message': 'Failed to create payment link'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/payment/list', methods=['GET'])
@login_required
def api_payment_list():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    rows = c.execute("SELECT * FROM payment_links WHERE business_id=? ORDER BY created_at DESC LIMIT 20", (bid,)).fetchall()
    return jsonify({'success': True, 'payments': [dict(r) for r in rows]})

# ── SMART CALL ROUTING ──

@app.route('/api/routing/rules', methods=['GET'])
@login_required
def api_get_routing_rules():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    rows = c.execute("SELECT * FROM routing_rules WHERE business_id=? ORDER BY priority ASC", (bid,)).fetchall()
    return jsonify({'success': True, 'rules': [dict(r) for r in rows]})

@app.route('/api/routing/rules', methods=['POST'])
@login_required
def api_create_routing_rule():
    bid = session['business_id']
    data = request.get_json() or {}
    import uuid
    rid = str(uuid.uuid4())[:12]
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO routing_rules (id, business_id, name, rule_type, priority, conditions, action, target, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
              (rid, bid, data.get('name', 'New Rule'), data.get('rule_type', 'time'),
               int(data.get('priority', 0)), json.dumps(data.get('conditions', {})),
               data.get('action', 'forward'), data.get('target', '')))
    db.commit()
    return jsonify({'success': True, 'rule_id': rid})

@app.route('/api/routing/rules/<rule_id>', methods=['DELETE'])
@login_required
def api_delete_routing_rule(rule_id):
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM routing_rules WHERE id=? AND business_id=?", (rule_id, bid))
    db.commit()
    return jsonify({'success': True})

# ── BOOKING WIDGET ──

@app.route('/widget/<bid>/book.js')
def serve_booking_widget(bid):
    """Serve the embeddable booking widget JavaScript."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT b.name, b.phone_number, w.* FROM businesses b LEFT JOIN booking_widgets w ON b.id=w.business_id WHERE b.id=?", (bid,))
    biz = c.fetchone()
    if not biz:
        return "/* Business not found */", 404, {'Content-Type': 'application/javascript'}
    
    biz = dict(biz)
    pc = biz.get('primary_color', '#a855f7')
    btn_text = biz.get('button_text', 'Book a Call')
    greeting = biz.get('greeting', 'Book a Free Consultation')
    phone = biz.get('phone_number', '')
    name = biz.get('name', 'Business')
    
    js = f"""(function(){{
    var existing = document.getElementById('dz-widget-btn');
    if(existing) return;

    var btn = document.createElement('a');
    btn.id = 'dz-widget-btn';
    btn.href = 'tel:{phone}';
    btn.innerHTML = '📞 {btn_text}';
    btn.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:999999;background:linear-gradient(135deg,{pc},#ec4899);color:white;padding:14px 28px;border-radius:50px;font-family:Inter,-apple-system,sans-serif;font-weight:700;font-size:15px;text-decoration:none;box-shadow:0 8px 32px rgba(0,0,0,.3);transition:all .3s;display:flex;align-items:center;gap:8px;';
    btn.onmouseover = function(){{this.style.transform='translateY(-3px)';this.style.boxShadow='0 12px 40px rgba(0,0,0,.4)';}};
    btn.onmouseout = function(){{this.style.transform='';this.style.boxShadow='0 8px 32px rgba(0,0,0,.3)';}};
    document.body.appendChild(btn);

    var badge = document.createElement('div');
    badge.innerHTML = '⚡ {name}';
    badge.style.cssText = 'position:fixed;bottom:90px;right:20px;z-index:999998;background:rgba(8,8,15,.85);backdrop-filter:blur(10px);color:#f1f1f5;padding:10px 18px;border-radius:12px;font-family:Inter,sans-serif;font-size:12px;border:1px solid rgba(37,37,51,.5);display:block;';
    document.body.appendChild(badge);
}})();"""
    return js, 200, {'Content-Type': 'application/javascript', 'Access-Control-Allow-Origin': '*'}

@app.route('/api/widget/settings', methods=['POST'])
@login_required
def api_save_widget_settings():
    bid = session['business_id']
    data = request.get_json() or {}
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT OR REPLACE INTO booking_widgets (business_id, enabled, primary_color, button_text, greeting, timezone)
                VALUES (?, ?, ?, ?, ?, ?)""",
              (bid, int(data.get('enabled', 1)), data.get('primary_color', '#a855f7'),
               data.get('button_text', 'Book a Call'), data.get('greeting', 'Book a Free Consultation'),
               data.get('timezone', 'America/New_York')))
    db.commit()
    embed_code = f'<script src="{request.host_url}widget/{bid}/book.js" defer></script>'
    return jsonify({'success': True, 'embed_code': embed_code})

@app.route('/api/widget/settings', methods=['GET'])
@login_required
def api_get_widget_settings():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    row = c.execute("SELECT * FROM booking_widgets WHERE business_id=?", (bid,)).fetchone()
    embed_code = f'<script src="{request.host_url}widget/{bid}/book.js" defer></script>' if row else ''
    return jsonify({'success': True, 'settings': dict(row) if row else {}, 'embed_code': embed_code})

# ── VOICE CLONING ──

@app.route('/api/voices/list', methods=['GET'])
@login_required
def api_list_voices():
    """List available voices for the business's AI agent."""
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    biz = c.execute("SELECT voice_id, voice_speed, vapi_assistant_id FROM businesses WHERE id=?", (bid,)).fetchone()
    if not biz:
        return jsonify({'success': False, 'message': 'Business not found'}), 404
    
    available = get_available_voices()
    current = biz['voice_id'] or 'rachel'
    speed = biz['voice_speed'] or '1.15'
    
    return jsonify({
        'success': True,
        'available': available,
        'current': current,
        'speed': speed
    })

@app.route('/api/voices/update', methods=['POST'])
@login_required
def api_update_voice():
    """Update the voice for the business's AI agent."""
    bid = session['business_id']
    data = request.get_json() or {}
    voice_id = data.get('voice_id', 'rachel')
    speed = str(data.get('speed', '1.15'))
    
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE businesses SET voice_id=?, voice_speed=? WHERE id=?", (voice_id, speed, bid))
    db.commit()
    
    # Also try to update the Vapi assistant
    biz = c.execute("SELECT vapi_assistant_id FROM businesses WHERE id=?", (bid,)).fetchone()
    if biz and biz['vapi_assistant_id']:
        try:
            import requests, os
            VAPI_KEY = os.environ.get("VAPI_API_KEY", "")
            if not VAPI_KEY:
                try:
                    with open("/root/voice-agent-manager/.env") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("VAPI_API_KEY="):
                                VAPI_KEY = line.split("=", 1)[1]
                                break
                except:
                    pass
            # Find which provider the voice uses
            provider = "11labs"
            for v in get_available_voices():
                if v['id'] == voice_id:
                    provider = v.get('provider', '11labs')
                    break
            voice_payload = {"voice": {"provider": provider.lower(), "voiceId": voice_id, "speed": float(speed)}}
            requests.patch(f"https://api.vapi.ai/assistant/{biz['vapi_assistant_id']}",
                          headers={"Authorization": f"Bearer {VAPI_KEY}", "Content-Type": "application/json"},
                          json=voice_payload, timeout=15)
        except:
            pass
    
    return jsonify({'success': True, 'message': f'✅ Voice updated to {voice_id} at {speed}x speed'})

# ── CRM WEBHOOKS ──

@app.route('/api/webhooks/list', methods=['GET'])
@login_required
def api_list_webhooks():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    rows = c.execute("SELECT * FROM webhooks WHERE business_id=? ORDER BY created_at DESC", (bid,)).fetchall()
    return jsonify({'success': True, 'webhooks': [dict(r) for r in rows]})

@app.route('/api/webhooks/save', methods=['POST'])
@login_required
def api_save_webhook():
    bid = session['business_id']
    data = request.get_json() or {}
    import uuid
    wid = data.get('id') or str(uuid.uuid4())[:12]
    db = get_db()
    c = db.cursor()
    
    # Check if updating or inserting
    existing = c.execute("SELECT id FROM webhooks WHERE id=? AND business_id=?", (wid, bid)).fetchone()
    if existing:
        c.execute("""UPDATE webhooks SET name=?, url=?, events=?, enabled=? WHERE id=? AND business_id=?""",
                  (data.get('name', ''), data.get('url', ''), json.dumps(data.get('events', [])),
                   int(data.get('enabled', 1)), wid, bid))
    else:
        c.execute("""INSERT INTO webhooks (id, business_id, name, url, events, enabled)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                  (wid, bid, data.get('name', ''), data.get('url', ''),
                   json.dumps(data.get('events', [])), int(data.get('enabled', 1))))
    db.commit()
    return jsonify({'success': True, 'webhook_id': wid})

@app.route('/api/webhooks/delete/<webhook_id>', methods=['DELETE'])
@login_required
def api_delete_webhook(webhook_id):
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM webhooks WHERE id=? AND business_id=?", (webhook_id, bid))
    db.commit()
    return jsonify({'success': True})

# ── AUTO REVIEW COLLECTOR ──

@app.route('/api/reviews/request', methods=['POST'])
@login_required
def api_send_review_request():
    """Send an SMS asking for a Google review after a call."""
    bid = session['business_id']
    data = request.get_json() or {}
    customer_phone = data.get('phone', '')
    customer_name = data.get('name', '')
    call_id = data.get('call_id', '')
    
    if not customer_phone:
        return jsonify({'success': False, 'message': 'Phone number required'}), 400
    
    import uuid, requests as req
    rid = str(uuid.uuid4())[:12]
    
    # Get business info
    db = get_db()
    c = db.cursor()
    biz = c.execute("SELECT name FROM businesses WHERE id=?", (bid,)).fetchone()
    biz_name = biz['name'] if biz else 'Business'
    
    review_link = f"https://search.google.com/local/writereview?placeid=YOUR_PLACE_ID"
    message = f"Hi {customer_name or 'there'}! Thank you for choosing {biz_name}. We'd love your feedback! Please leave us a 5-star review here: {review_link}"
    
    # Try sending via Twilio or log it
    # Store in DB for tracking
    c.execute("""INSERT INTO review_requests (id, business_id, customer_phone, customer_name, call_id, sent, sent_at)
                VALUES (?, ?, ?, ?, ?, 1, datetime('now'))""",
              (rid, bid, customer_phone, customer_name, call_id))
    db.commit()
    
    return jsonify({'success': True, 'message': f'✅ Review request sent to {customer_phone}', 'id': rid})

@app.route('/api/reviews/list', methods=['GET'])
@login_required
def api_list_reviews():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    rows = c.execute("SELECT * FROM review_requests WHERE business_id=? ORDER BY created_at DESC LIMIT 20", (bid,)).fetchall()
    return jsonify({'success': True, 'reviews': [dict(r) for r in rows]})

# ── CAMPAIGN ACTIONS ──

@app.route('/campaign/start', methods=['GET', 'POST'])
@login_required
def start_campaign():
    bid = session['business_id']
    from flask import flash, redirect
    
    if request.method == 'GET':
        flash('Use the Start button on the overview tab.', 'info')
        return redirect('/')
    
    db = get_db()
    c = db.cursor()
    
    # Reset any leads stuck in CALLING state (from a previous crashed campaign)
    c.execute("UPDATE leads SET state='NEW' WHERE business_id=? AND state='CALLING'", (bid,))
    
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id = ? AND state = 'NEW'", (bid,))
    count = c.fetchone()[0]
    if count == 0:
        flash('No leads to call! Upload leads first.', 'error')
        return redirect('/')
    
    ensure_campaign_row(bid)
    c.execute("UPDATE campaigns SET status = 'running', started_at = datetime('now') WHERE business_id = ?", (bid,))
    db.commit()
    
    # Clear old campaign logs
    c.execute("DELETE FROM campaign_log WHERE business_id = ?", (bid,))
    db.commit()
    
    t = threading.Thread(target=run_campaign_bg, args=(bid,), daemon=True)
    campaign_threads[bid] = t
    t.start()
    
    campaign_status_cache[bid] = 'running'
    
    flash('🚀 Campaign started!', 'success')
    return redirect('/')

@app.route('/campaign/schedule', methods=['POST'])
@login_required
def schedule_campaign():
    bid = session['business_id']
    enabled = 1 if request.form.get('schedule_enabled') else 0
    time_val = request.form.get('schedule_time', '09:00')
    days = ','.join(request.form.getlist('days')) or 'mon,tue,wed,thu,fri'
    tz = request.form.get('timezone', 'America/New_York')
    start_date = request.form.get('schedule_start_date', '')
    db = get_db()
    c = db.cursor()
    ensure_campaign_row(bid)
    c.execute("""UPDATE campaigns SET schedule_enabled=?, schedule_time=?, schedule_days=?, timezone=?, schedule_start_date=? WHERE business_id=?""",
              (enabled, time_val, days, tz, start_date, bid))
    db.commit()
    flash('✅ Schedule saved!' if enabled else 'Schedule disabled.', 'success')
    return redirect('/')

@app.route('/followup/update', methods=['POST'])
@login_required
def followup_update():
    """Update a follow-up field (next_call_at or notes) for a lead."""
    bid = session['business_id']
    lead_id = request.form.get('lead_id', '')
    field = request.form.get('field', '')
    value = request.form.get('value', '')
    if field not in ('next_call_at', 'notes'):
        return jsonify({'success': False, 'message': 'Invalid field'})
    db = get_db()
    c = db.cursor()
    c.execute(f"UPDATE leads SET {field}=? WHERE id=? AND business_id=?", (value, lead_id, bid))
    db.commit()
    return jsonify({'success': True})

@app.route('/followup/call', methods=['POST'])
@login_required
def followup_call_single():
    """Call a single follow-up lead via Vapi."""
    bid = session['business_id']
    lead_id = request.form.get('lead_id', '')
    db = get_db()
    db.row_factory = sqlite3.Row
    c = db.cursor()
    lead = c.execute("SELECT * FROM leads WHERE id=? AND business_id=?", (lead_id, bid)).fetchone()
    biz = c.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    db.close()
    if not lead or not biz:
        return jsonify({'success': False, 'message': 'Lead or business not found'})
    call_id = make_vapi_call(lead, biz, biz['vapi_assistant_id'], biz['vapi_phone_id'], 0)
    if call_id:
        # Update state and next_call_at
        db2 = get_db()
        c2 = db2.cursor()
        c2.execute("UPDATE leads SET state='CALLING', retry_count=COALESCE(retry_count,0)+1, last_called_at=datetime('now') WHERE id=?", (lead_id,))
        db2.commit()
        return jsonify({'success': True, 'message': f'✅ Calling {lead["phone"]} now!'})
    return jsonify({'success': False, 'message': '❌ Call failed'})

@app.route('/followup/call-all', methods=['POST'])
@login_required
def followup_call_all():
    """Call all follow-up leads now."""
    bid = session['business_id']
    db = get_db()
    db.row_factory = sqlite3.Row
    c = db.cursor()
    leads = c.execute("SELECT * FROM leads WHERE business_id=? AND state IN ('CALLED','NO_ANSWER') ORDER BY last_called_at ASC LIMIT 20", (bid,)).fetchall()
    biz = c.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    db.close()
    if not leads or not biz:
        return jsonify({'success': False, 'message': 'No follow-ups to call'})
    count = 0
    for lead in leads:
        call_id = make_vapi_call(lead, biz, biz['vapi_assistant_id'], biz['vapi_phone_id'], 0)
        if call_id:
            count += 1
            time.sleep(2)  # Brief delay between calls
    return jsonify({'success': True, 'message': f'✅ Called {count} leads'})

@app.route('/followup/call-scheduled', methods=['POST'])
@login_required
def followup_call_scheduled():
    """Call only follow-ups where next_call_at is set and due."""
    bid = session['business_id']
    db = get_db()
    db.row_factory = sqlite3.Row
    c = db.cursor()
    leads = c.execute("""SELECT * FROM leads WHERE business_id=? AND state IN ('CALLED','NO_ANSWER') 
                          AND next_call_at IS NOT NULL AND next_call_at <= datetime('now') 
                          ORDER BY next_call_at ASC LIMIT 20""", (bid,)).fetchall()
    biz = c.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone()
    db.close()
    if not leads or not biz:
        return jsonify({'success': False, 'message': 'No scheduled follow-ups due'})
    count = 0
    for lead in leads:
        call_id = make_vapi_call(lead, biz, biz['vapi_assistant_id'], biz['vapi_phone_id'], 0)
        if call_id:
            count += 1
            time.sleep(2)
    return jsonify({'success': True, 'message': f'✅ Called {count} scheduled leads'})

@app.route('/api/generate-prompt', methods=['POST'])
@login_required
def api_generate_prompt():
    """Generate a VAPI prompt using xAI based on industry, goal, tone."""
    data = request.get_json() or {}
    industry = data.get('industry', 'general business')
    goal = data.get('goal', 'book_call')
    tone = data.get('tone', 'professional')
    notes = data.get('notes', '')
    
    goals = {
        'book_call': 'book a 10-15 minute discovery call with the prospect',
        'qualify_lead': 'qualify the lead by asking key questions about their needs and budget',
        'schedule_appointment': 'schedule a specific appointment date and time',
        'collect_info': 'collect the prospect name, phone, email, and details about their needs',
        'customer_support': 'provide customer support and address their concerns professionally'
    }
    tones = {
        'professional': 'Professional and polished. Use complete sentences, be respectful, and represent the business well.',
        'friendly': 'Friendly and casual. Be warm, approachable, and conversational. Use natural language.',
        'urgent': 'Urgent and action-oriented. Create a sense of timeliness and encourage immediate action.',
        'consultative': 'Consultative and expert. Position yourself as a knowledgeable advisor who provides value.'
    }
    
    goal_text = goals.get(goal, goals['book_call'])
    tone_text = tones.get(tone, tones['professional'])
    
    # Build the prompt
    prompt = f"""You are an AI voice agent for a {industry} business. Your primary goal is to {goal_text}.

BEHAVIOR GUIDELINES:
- Tone: {tone_text}
- Always listen more than you talk. Ask open-ended questions.
- If the prospect is not interested, politely thank them and end the call.
- Never make promises about pricing unless explicitly told the details.
- Collect: name, phone number, and best time to call back.
- Speak naturally — do not sound robotic or scripted.
- Keep responses under 30 seconds each.{" " + notes if notes else ""}

EXAMPLE FLOW:
1. Greeting: "Hi, this is [Name] from [Business Name]. Am I catching you at a good time?"
2. Discovery: "I'm reaching out because we help [industry] businesses with [service]. Are you currently handling [pain point] in-house?"
3. Qualification: "That's great to hear! Would you have 10 minutes this week to discuss how we might be able to help?"
4. Close: "Perfect, I've noted that down. We'll follow up with you at that time. Thanks, [Name], talk soon!"
"""
    return jsonify({'prompt': prompt})

# ── KNOWLEDGE BASE TEMPLATES ──
KB_TEMPLATES = {
    'dentist': """🏥 BUSINESS: [Your Dental Practice Name]
📍 LOCATION: [City, State]
🕐 HOURS: Mon-Fri 9am-6pm, Sat 9am-2pm
📞 PHONE: [Your Phone]

SERVICES:
• General Dentistry — Cleanings, exams, fillings, X-rays
• Cosmetic Dentistry — Veneers, whitening, bonding
• Restorative — Crowns, bridges, implants, dentures
• Emergency Dentistry — Walk-ins welcome, same-day appointments
• Orthodontics — Invisalign, braces (adult & child)
• Periodontics — Gum disease treatment, scaling & root planing

PRICING:
• New patient exam + X-rays: $99 special
• Cleaning: $75-$150 (insurance dependent)
• Fillings: $150-$400 per tooth
• We accept most major insurance plans
• Payment plans available through CareCredit

FAQ:
• Q: Do you take walk-ins? A: Yes, emergency walk-ins welcome Mon-Sat
• Q: What insurance do you accept? A: Delta Dental, Cigna, MetLife, Aetna, Blue Cross Blue Shield
• Q: Do you offer sedation? A: Yes, we offer nitrous oxide and oral sedation
• Q: How often should I come in? A: Every 6 months for routine cleanings
• Q: Do you treat children? A: Yes, patients of all ages welcome""",
    
    'plumber': """🔧 BUSINESS: [Your Plumbing Company Name]
📍 LOCATION: [City, State]
🕐 HOURS: Mon-Fri 7am-7pm, Sat 8am-4pm, 24/7 Emergency
📞 PHONE: [Your Phone]

SERVICES:
• Drain Cleaning — Clogged drains, hydro-jetting, camera inspection
• Pipe Repair — Leaky pipes, burst pipes, repiping
• Water Heater — Installation & repair (tank & tankless)
• Sewer Services — Sewer line repair, replacement, trenchless
• Fixtures — Toilet, faucet, garbage disposal installation
• Emergency Service — Available 24/7 for urgent issues
• Water Softener — Installation & maintenance

PRICING:
• Service call fee: $49-$89
• Drain cleaning: $150-$350
• Water heater repair: $200-$500
• Free estimates on major repairs
• Senior & military discounts available
• Financing available through Synchrony

FAQ:
• Q: Do you charge for estimates? A: Free estimates on repairs over $500
• Q: How fast can you get here? A: Same-day service available in most cases
• Q: Do you work on weekends? A: Yes, Saturday 8am-4pm, emergency 24/7
• Q: Are you licensed and insured? A: Yes, fully licensed (#LICENSE) and insured""",
    
    'lawyer': """⚖️ FIRM: [Your Law Firm Name]
📍 LOCATION: [City, State]
🕐 HOURS: Mon-Fri 8:30am-6pm, Weekend by appointment
📞 PHONE: [Your Phone]

PRACTICE AREAS:
• Personal Injury — Car accidents, slip & fall, wrongful death
• Family Law — Divorce, child custody, alimony, adoption
• Criminal Defense — DUI, drug charges, traffic violations
• Real Estate — Property disputes, landlord/tenant, closing
• Business Law — Contracts, LLC formation, employment law
• Estate Planning — Wills, trusts, probate, power of attorney

CONSULTATION:
• Initial consultation: Free (30 min)
• Payment: Flat fee & hourly options available
• We speak Spanish & English
• Virtual consultations available via Zoom

FAQ:
• Q: How much does a lawyer cost? A: Free initial consultation, then varies by case type
• Q: How long will my case take? A: Depends on complexity — we'll give you a timeline
• Q: Do you take credit cards? A: Yes, all major cards accepted""",
    
    'hvac': """❄️ BUSINESS: [Your HVAC Company Name]
📍 LOCATION: [City, State]
🕐 HOURS: Mon-Fri 7am-7pm, Sat 8am-4pm, 24/7 Emergency
📞 PHONE: [Your Phone]

SERVICES:
• AC Repair — Diagnostics, compressor, fan, refrigerant
• AC Installation — New systems, replacement, ductwork
• Heating — Furnace repair, heat pump, boiler service
• Maintenance — Tune-ups, filter replacement, seasonal checks
• Indoor Air Quality — Purifiers, humidifiers, ventilation
• Commercial HVAC — Full commercial system service
• Emergency Service — Available 24/7

PRICING:
• Diagnostic fee: $59 (waived with repair)
• AC tune-up: $89-$149
• New AC installation: $3,500-$8,000
• Financing available 0% APR for 12 months
• Annual maintenance plans from $149/yr

FAQ:
• Q: How often should I service my AC? A: Twice a year — spring for AC, fall for heating
• Q: How long does an AC last? A: 12-15 years with proper maintenance
• Q: Do you offer warranties? A: 10-year parts, 1-year labor on new installations""",
    
    'roofing': """🏠 BUSINESS: [Your Roofing Company Name]
📍 LOCATION: [City, State]
🕐 HOURS: Mon-Fri 7am-6pm, Sat 8am-2pm
📞 PHONE: [Your Phone]

SERVICES:
• Roof Repair — Leaks, storm damage, missing shingles
• Roof Replacement — Shingle, metal, tile, flat roofs
• New Construction — Custom roofing for new builds
• Gutters — Installation, cleaning, gutter guards
• Skylights — Installation & repair
• Emergency Tarping — Storm damage response
• Insurance Claims — We work with your insurance company

PRICING:
• Free inspection & estimate
• Roof replacement: $5,000-$15,000 (varies by size/material)
• Repair: $300-$1,500
• Financing available
• We work with all major insurance companies

FAQ:
• Q: Do you give free estimates? A: Yes, free inspection and written estimate
• Q: How long does a roof replacement take? A: 1-3 days typically
• Q: Do you handle insurance claims? A: Yes, we work directly with your adjuster""",
    
    'auto': """🚗 BUSINESS: [Your Auto Shop Name]
📍 LOCATION: [City, State]
🕐 HOURS: Mon-Fri 7:30am-6pm, Sat 8am-3pm
📞 PHONE: [Your Phone]

SERVICES:
• Oil Change — Synthetic & conventional, filter included
• Brakes — Pads, rotors, calipers, brake fluid flush
• Engine — Diagnostics, repair, check engine light
• Transmission — Service, repair, rebuild
• Tires — Mount, balance, rotation, alignment
• AC Service — Recharge, compressor, blend door repair
• Electrical — Battery, alternator, starter, wiring
• State Inspection — Emissions & safety testing

PRICING:
• Oil change: $29.99-$69.99
• Brake service: $149-$399 per axle
• Diagnostic fee: $89 (applied to repair)
• Free multi-point inspection with any service
• Warranty: 24mo/24k miles on most repairs

FAQ:
• Q: Do I need an appointment? A: Walk-ins welcome, appointments preferred
• Q: How long does an oil change take? A: About 30 minutes
• Q: Do you offer financing? A: Yes, through Affirm""",
    
    'medical': """🏥 PRACTICE: [Your Medical Practice Name]
📍 LOCATION: [City, State]
🕐 HOURS: Mon-Fri 8am-5pm, Sat 9am-1pm
📞 PHONE: [Your Phone]

SERVICES:
• Primary Care — Annual physicals, sick visits, chronic care
• Urgent Care — Walk-in, minor emergencies, injuries
• Pediatrics — Well-child visits, vaccinations, sick visits
• Women's Health — Annual exams, prenatal, menopause
• Specialty — Cardiology, dermatology, orthopedics (by referral)
• Telehealth — Virtual visits available 7 days/week

INSURANCE:
• We accept Medicare, Medicaid, and most major insurance
• Self-pay discounts available
• Sliding scale for qualified patients

FAQ:
• Q: How do I make an appointment? A: Call us or use our online portal
• Q: Do you accept my insurance? A: We accept most major plans — call to verify
• Q: Can I see a doctor today? A: Same-day appointments often available
• Q: Do you offer telehealth? A: Yes, virtual visits available""",
    
    'realestate': """🏡 REALTOR: [Your Name], [Your Agency]
📍 LOCATION: [City, State]
🕐 HOURS: Mon-Sun 8am-8pm
📞 PHONE: [Your Phone]

SERVICES:
• Home Buying — First-time buyer specialist, full market search
• Home Selling — Professional staging, photography, marketing
• Investment Properties — Multi-family, rental analysis
• Relocation — Full-service moving coordination
• Property Management — Tenant placement, maintenance

MARKET KNOWLEDGE:
• [Neighborhood 1] — Avg price: $XXX,XXX, great schools
• [Neighborhood 2] — Avg price: $XXX,XXX, family-friendly
• [Neighborhood 3] — Avg price: $XXX,XXX, newly developing
• Current inventory: [X] homes available
• Average days on market: [X] days

FAQ:
• Q: How much is my home worth? A: I offer free comparative market analysis
• Q: What's the first step to buying? A: Get pre-approved, then we start house hunting
• Q: How much do I need for a down payment? A: As low as 3-5% for conventional loans
• Q: How long does closing take? A: Typically 30-45 days""",
}

@app.route('/api/generate-kb', methods=['POST'])
@login_required
def api_generate_kb():
    """Generate knowledge base content via templates or AI."""
    data = request.get_json(silent=True) or {}
    method = data.get('method', 'ai')
    
    # Method: AI via Venice (outbound or inbound)
    if method in ('venice', 'ai'):
        kb_type = data.get('type', 'outbound')
        bid = session['business_id']
        db = get_db()
        c = db.cursor()
        c.execute("SELECT name, industry FROM businesses WHERE id=?", (bid,))
        biz = c.fetchone()
        biz_name = (biz['name'] if biz else 'Your Business')
        industry = (biz['industry'] or 'your industry') if biz else 'your industry'
        
        # Load Venice API key
        api_key = os.environ.get('VENICE_API_KEY', '')
        if not api_key:
            try:
                with open('/root/voice-agent-manager/api_keys.json') as f:
                    keys = json.load(f)
                api_key = keys.get('VENICE_API_KEY', '')
            except:
                pass
        
        if api_key and method == 'venice':
            try:
                if kb_type == 'inbound':
                    sys_p = "You write concise, practical knowledge base content for AI voice assistants handling INCOMING calls."
                    usr_p = f"""Write a knowledge base for an AI answering incoming calls for "{biz_name}" in {industry}. Include: business info, common questions, hours, pricing ranges, booking process, escalation. 3-5 paragraphs plain English."""
                else:
                    sys_p = "You write concise, practical knowledge base content for AI voice assistants making OUTBOUND sales calls."
                    usr_p = f"""Write a knowledge base for an AI making outbound calls for "{biz_name}" in {industry}. Include: offerings, selling points, objections, pricing, booking process. 3-5 paragraphs plain English."""
                r = requests.post("https://api.venice.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": "venice-uncensored-1-2", "messages": [{"role":"system","content":sys_p},{"role":"user","content":usr_p}], "max_tokens":1000, "temperature":0.7},
                    timeout=30)
                content = r.json()['choices'][0]['message']['content'].strip()
                label = "Inbound Call KB" if kb_type == 'inbound' else "Knowledge Base"
                return jsonify({'success': True, 'content': content, 'message': f'{label} generated via AI!'})
            except Exception as e:
                return jsonify({'success': False, 'message': f'AI generation failed: {str(e)}'}), 500
        
        # Fallback: template-based AI generation
        if kb_type == 'inbound':
            kb = f"""🏢 BUSINESS: {biz_name}
📍 LOCATION: [Your City, State]
🕐 HOURS: Mon-Fri 9am-6pm (customize below)
📞 PHONE: [Your Phone Number]

What we do: We are a {industry} business serving our local community. We provide quality service to every customer.

Common Questions & Answers:
• Pricing: [Describe your pricing model]
• Availability: [Your hours and scheduling]
• Services: [Describe what you offer]
• Location: [Your service area]

Call Handling:
• Listen to the customer's needs first
• Answer questions clearly and professionally
• Collect: name, phone, address, and description of need
• Offer to book an appointment or send information
• If you can't help, offer to transfer to a team member"""
        else:
            kb = f"""🏢 BUSINESS: {biz_name} ({industry})
📍 SERVICE AREA: [Your City, State]
🕐 HOURS: Mon-Fri 9am-6pm

What we offer:
• [Service/Product 1]
• [Service/Product 2]
• [Service/Product 3]

Key Selling Points:
• Free consultations / estimates
• Quality service guaranteed
• Competitive pricing

Handling Objections:
• Price concern: Explain value and offer payment options
• Not interested: Ask if they'd like info sent via text/email
• Need to think: Offer to follow up later

Booking Process:
1. Confirm interest
2. Collect contact info (name, phone, email)
3. Schedule appointment
4. Send confirmation"""
        return jsonify({'success': True, 'content': kb, 'message': f'Template KB generated!'})
    
    # Method: Templates
    if method == 'template':
        tpl_id = data.get('template', '')
        kb = KB_TEMPLATES.get(tpl_id, '')
        if kb:
            return jsonify({'kb': kb})
        return jsonify({'error': f'No template found for "{tpl_id}"'}), 400
    
    # Method: AI Generate
    if method == 'ai':
        industry = data.get('industry', 'your business')
        services = data.get('services', '')
        area = data.get('area', 'your area')
        kb = f"""🏢 BUSINESS: [Your {industry.title()} Business Name]
📍 LOCATION: {area}
🕐 HOURS: Mon-Fri 9am-6pm (customize below)
📞 PHONE: [Your Phone Number]

SERVICES WE OFFER:
• {services or 'Describe your services here — e.g. residential & commercial service'}

PRICING:
• Free estimates / consultations (confirm when booking)
• We accept cash, credit, and most major payment methods
• Senior & military discounts available

CALL HANDLING INSTRUCTIONS:
• If the prospect asks about pricing, give general ranges and mention free estimates
• If they need emergency service, confirm their location and urgency level
• Collect: name, phone number, address, and description of the issue
• If they're just browsing, offer to send information via text or email

FAQ:
• Q: What areas do you serve? A: We serve {area} and surrounding areas
• Q: Do you offer free estimates? A: Yes, free estimates are available
• Q: What payment methods do you accept? A: Cash, credit/debit cards, and financing options
• Q: How soon can you come out? A: We offer same-day and next-day service in most cases"""
        return jsonify({'kb': kb})
    
    # Method: By Keywords
    if method == 'keywords':
        keywords = data.get('keywords', '')
        kw_list = [k.strip() for k in keywords.split(',') if k.strip()]
        kb_lines = ["", f"📚 KNOWLEDGE BASE — AUTO-GENERATED FROM KEYWORDS", ""]
        for kw in kw_list:
            kb_lines.append(f"• {kw.title()} — [Describe your {kw.lower()} offering here]")
        kb_lines.append(f"\n📝 INSTRUCTIONS: Customize each line with your actual pricing, hours, and details.")
        kb_lines.append(f"🗓️ HOURS: Mon-Fri 9am-6pm (customize)")
        kb_lines.append(f"📍 SERVICE AREA: [Your service area]")
        kb_lines.append(f"📞 PHONE: [Your phone number]")
        return jsonify({'kb': '\n'.join(kb_lines)})
    
    # Method: From URL (scrape)
    if method == 'url':
        url = data.get('url', '')
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        try:
            import urllib.request
            import urllib.parse
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
            
            # Strip tags and extract text
            import re
            text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL|re.IGNORECASE)
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Extract phone numbers
            phones = re.findall(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
            
            # Get first 2000 chars of clean content
            clean = text[:2000]
            
            kb = f"""🌐 IMPORTED FROM: {url}

🕐 HOURS: [Found on website — check above]
📞 PHONE: {' · '.join(phones[:3]) if phones else '[Found on website]'}
📍 ADDRESS: [Found on website]

WEBSITE CONTENT:
{clean}

📝 NOTE: Review and customize the extracted info above. Add pricing, service area, and FAQs.
"""
            return jsonify({'kb': kb})
        except Exception as e:
            return jsonify({'error': f'Could not scrape URL: {str(e)[:100]}'}), 500
    
    return jsonify({'error': 'Invalid method'}), 400

@app.route('/api/campaign-status')
@login_required
def api_campaign_status():
    """Return live campaign status for the Live Monitor."""
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("SELECT status, calls_made FROM campaigns WHERE business_id = ?", (bid,))
    camp = c.fetchone()
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id=? AND state='NEW'", (bid,))
    new_leads = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id=? AND state='CALLING'", (bid,))
    calling_now = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM leads WHERE business_id=? AND state='CALLED'", (bid,))
    called = c.fetchone()[0]
    db.close()
    
    db_status = camp['status'] if camp else 'idle'
    cached = campaign_status_cache.get(bid, db_status)
    thread = campaign_threads.get(bid)
    thread_alive = thread is not None and thread.is_alive()
    
    if db_status == 'running' and not thread_alive:
        display_status = 'WARNING Stale (restart needed)'
    elif cached == 'starting':
        display_status = 'Starting...'
    elif cached == 'calling':
        display_status = 'Calling ({calling_now} active)'
    elif cached == 'waiting':
        display_status = 'Waiting between cycles'
    elif cached == 'stopped' or db_status == 'stopped':
        display_status = 'Stopped'
    elif cached == 'completed' or db_status == 'completed':
        display_status = 'Completed'
    elif db_status == 'running' and thread_alive:
        display_status = 'Running'
    else:
        display_status = 'Idle'
    
    return jsonify({
        'status': display_status,
        'calls_made': camp['calls_made'] if camp else 0,
        'new_leads': new_leads,
        'calling_now': calling_now,
        'called': called,
        'thread_alive': thread_alive,
        'cached': cached
    })


@app.route('/campaign/schedule')
@login_required
def schedule_page():
    return redirect('/')

@app.route('/campaign/stop', methods=['GET', 'POST'])
@login_required
def stop_campaign():
    bid = session['business_id']
    if request.method == 'GET':
        flash('Use the Stop button on the overview tab.', 'info')
        return redirect('/?tab=leads')
    db = get_db()
    c = db.cursor()
    ensure_campaign_row(bid)
    c.execute("UPDATE campaigns SET status = 'stopped' WHERE business_id = ?", (bid,))
    db.commit()
    campaign_status_cache[bid] = 'stopped'
    flash('⏹️ Campaign stopped.', 'info')
    return redirect('/')

@app.route('/campaign/reset', methods=['GET', 'POST'])
@login_required
def reset_campaign():
    bid = session['business_id']
    if request.method == 'GET':
        flash('Use the Reset button on the Leads tab.', 'info')
        return redirect('/?tab=leads')
    db = get_db()
    c = db.cursor()
    # Stop any running campaign thread
    if bid in campaign_threads:
        try: campaign_threads.pop(bid, None)
        except: pass
    # Clear campaign logs so monitor starts fresh
    c.execute("DELETE FROM campaign_log WHERE business_id = ?", (bid,))
    c.execute("UPDATE leads SET state = 'NEW', retry_count = 0 WHERE business_id = ?", (bid,))
    c.execute("UPDATE campaigns SET status = 'idle', calls_made = 0 WHERE business_id = ?", (bid,))
    campaign_status_cache[bid] = 'idle'
    db.commit()
    flash('🔄 Campaign reset. All leads set to NEW.', 'success')
    return redirect('/?tab=leads')

# ── CAMPAIGN MONITOR API ──
@app.route('/api/campaign/monitor')
@login_required
def campaign_monitor():
    """Returns live campaign status + recent log entries for real-time monitoring."""
    try:
        bid = session.get('business_id')
        if not bid:
            return jsonify({'error': 'Not logged in'}), 401
        db = get_db()
        c = db.cursor()
        
        # Campaign status
        c.execute("SELECT status, calls_made, last_run_at, schedule_enabled, schedule_time, schedule_days, started_at FROM campaigns WHERE business_id=?", (bid,))
        camp = c.fetchone()
        
        # Lead counts by state
        c.execute("SELECT state, COUNT(*) as cnt FROM leads WHERE business_id=? GROUP BY state", (bid,))
        lead_states = {r[0]: r[1] for r in c.fetchall()}
        
        # Total leads
        c.execute("SELECT COUNT(*) FROM leads WHERE business_id=?", (bid,))
        total = c.fetchone()[0]
        
        # Leads with retry info
        c.execute("SELECT COUNT(*) FROM leads WHERE business_id=? AND (retry_count IS NULL OR retry_count < 1)", (bid,))
        retryable = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM leads WHERE business_id=? AND retry_count >= 1", (bid,))
        exhausted = c.fetchone()[0]
        
        # Recent campaign log (last 30 entries)
        c.execute("SELECT message, level, created_at FROM campaign_log WHERE business_id=? ORDER BY created_at DESC LIMIT 30", (bid,))
        logs = [dict(r) for r in c.fetchall()]
        
        # Recent call log (last 10)
        c.execute("""
            SELECT cl.outcome, cl.duration, cl.cost, cl.created_at, l.phone, l.business_name, l.name as lead_name
            FROM call_log cl LEFT JOIN leads l ON cl.lead_id = l.id
            WHERE cl.business_id=? ORDER BY cl.created_at DESC LIMIT 10
        """, (bid,))
        recent_calls = [dict(r) for r in c.fetchall()]
        
        # Thread status
        thread = campaign_threads.get(bid)
        thread_alive = thread is not None and thread.is_alive()
        campaign_running = camp and camp[0] == 'running' if camp else False
        
        # Currently calling leads
        c.execute("SELECT id, phone, name, business_name, last_called_at FROM leads WHERE business_id=? AND state='CALLING' ORDER BY last_called_at DESC LIMIT 10", (bid,))
        calling_leads = [dict(r) for r in c.fetchall()]
        
        db.close()
        
        return jsonify({
            'campaign': dict(camp) if camp else None,
            'lead_states': lead_states,
            'total_leads': total,
            'retryable': retryable,
            'exhausted': exhausted,
            'logs': logs,
            'recent_calls': recent_calls,
            'calling_leads': calling_leads,
            'thread_alive': thread_alive,
            'campaign_running': campaign_running
        })
    except Exception as e:
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e)[:300], 'line': str(getattr(e, '__traceback__', None))}), 500

from concurrent.futures import ThreadPoolExecutor, as_completed
import random

def log_campaign(bid, message, level='info'):
    """Log a campaign event to the DB for live monitoring."""
    try:
        db = sqlite3.connect(DB_PATH)
        c = db.cursor()
        c.execute("INSERT INTO campaign_log (business_id, message, level) VALUES (?, ?, ?)",
                  (bid, message, level))
        db.commit()
        db.close()
    except:
        pass

def ensure_campaign_row(bid):
    """Create a campaign row for a business if it doesn't exist yet.
    Businesses created outside the signup flow (admin, API) never get a
    campaign row — without one, start/stop/overview all silently break."""
    try:
        db = sqlite3.connect(DB_PATH)
        c = db.cursor()
        row = c.execute("SELECT id FROM campaigns WHERE business_id = ?", (bid,)).fetchone()
        if not row:
            import uuid
            cid = 'camp-' + str(uuid.uuid4())[:12]
            c.execute("INSERT INTO campaigns (id, business_id, status) VALUES (?, ?, 'idle')", (cid, bid))
            db.commit()
        db.close()
    except Exception:
        pass

def make_vapi_call(lead, biz, assistant_id, phone_id, call_delay):
    """Make a single VAPI call with voicemail detection and token control."""
    phone = str(lead['phone'] or '').strip()
    # Ensure E.164 format (must start with + and country code)
    if phone.startswith('+'):
        pass  # already has country code
    elif phone.startswith('00'):
        phone = '+' + phone[2:]
    else:
        digits = ''.join(ch for ch in phone if ch.isdigit())
        if len(digits) == 10:
            # US/Canada number without country code -> +1
            phone = '+1' + digits
        elif len(digits) == 11 and digits.startswith('1'):
            phone = '+' + digits
        else:
            phone = '+' + digits
    # sqlite3.Row has no .get() — convert early (biz conversion happens below)
    if not isinstance(lead, dict):
        lead = dict(lead)
    try:
        try:
            max_tokens = int(biz['max_tokens'])
        except (KeyError, TypeError, ValueError):
            max_tokens = 200
        # Convert biz to dict for safe .get() access (sqlite3.Row doesn't have .get())
        if not isinstance(biz, dict):
            biz = dict(biz)
        
        payload = {
            "assistantId": assistant_id,
            "phoneNumberId": phone_id,
            "customer": {"number": phone},
            "assistantOverrides": {
                "variableValues": {
                    "business_name": biz['name'],
                    "industry": biz['industry'] or '',
                    "prospect_business": lead['business_name'] or 'your business',
                    "prospect_name": lead['name'] or '',
                    "prospect_notes": (lead.get('notes') or '').strip()
                },
                "maxDurationSeconds": int(biz.get('max_duration_seconds') or 300),
                "silenceTimeoutSeconds": int(biz.get('silence_timeout') or 10),
                "responseDelaySeconds": float(biz.get('response_delay_seconds') or 0.1)
            }
        }
        # Include system prompt and knowledge base in call overrides
        script = biz['script_template'] if biz and biz['script_template'] else ''
        kb = biz['knowledge_base'] if biz and biz['knowledge_base'] else ''
        # Append uploaded documents (menus / inventories / URLs) to the KB
        try:
            doc_kb = get_kb_documents_text(biz.get('id'))
            if doc_kb:
                kb = (kb + "\n\n[DOCUMENTS — the business's official documents (menu, inventory, catalog). "
                      "If anything conflicts with the knowledge base, the DOCUMENTS are the source of truth. "
                      "Use them to answer customer questions.]\n" + doc_kb).strip()
        except Exception:
            pass
        biz_name = biz.get('name') or ''
        biz_industry = biz.get('industry') or 'general'
        
        # Fetch the assistant's actual model config to match provider/model
        try:
            r_model = subprocess.run(["curl","-s",f"{VAPI_BASE}/assistant/{assistant_id}",
                "-H",f"Authorization: Bearer ***"], capture_output=True, text=True, timeout=10)
            asst_data = json.loads(r_model.stdout)
            model_config = asst_data.get('model', {})
            model_provider = model_config.get('provider', 'xai')
            model_name = model_config.get('model', 'grok-4.3')
        except:
            model_provider = 'xai'
            model_name = 'grok-4.3'
        
        agent_prompt = biz.get('agent_prompt') or ''
        if agent_prompt or script or kb:
            full_prompt = build_diazites_prompt(
                business_name=biz_name,
                industry=biz_industry,
                script=agent_prompt or script,
                knowledge_base=kb
            )
            # Append lead-specific knowledge if available
            lead_notes = (lead.get('notes') or '').strip()
            lead_name = lead.get('name') or ''
            lead_biz = lead.get('business_name') or ''
            if lead_notes or lead_name or lead_biz:
                extra_knowledge = []
                if lead_name:
                    extra_knowledge.append(f"Contact's name: {lead_name}")
                if lead_biz:
                    extra_knowledge.append(f"Contact's business: {lead_biz}")
                if lead_notes:
                    extra_knowledge.append(f"Additional context about this contact: {lead_notes}")
                full_prompt += f"\n\n[CALL-SPECIFIC KNOWLEDGE]\n{' | '.join(extra_knowledge)}\nUse this information about the person you're calling to personalize the conversation."
            payload["assistantOverrides"]["model"] = {
                "maxTokens": max_tokens if max_tokens else 200,
                "provider": model_provider,
                "model": model_name,
                "systemPrompt": full_prompt
            }
        else:
            payload["assistantOverrides"]["model"] = {
                "maxTokens": max_tokens if max_tokens else 200,
                "provider": model_provider,
                "model": model_name
            }
        # ── Voicemail Detection ──
        vm_detection = biz.get('voicemail_detection') if isinstance(biz, dict) else None
        if not vm_detection:
            try:
                vm_detection = biz['voicemail_detection']
            except (KeyError, TypeError):
                vm_detection = 'google'
        
        # Note: voicemailDetection and voicemailMessage should NOT be sent at the top level
        # of the /call payload — VAPI rejects them with 400.
        
        r = subprocess.run(["curl","-s","-X","POST",f"{VAPI_BASE}/call",
            "-H",f"Authorization: Bearer {VAPI_API_KEY}",
            "-H","Content-Type: application/json",
            "-d",json.dumps(payload)], capture_output=True, text=True, timeout=30)

        call_data = json.loads(r.stdout)
        # Handle Vapi error responses
        if 'error' in call_data or 'statusCode' in call_data:
            err_msg = call_data.get('message', call_data.get('error', 'Unknown error'))
            print(f"❌ VAPI error for {phone}: {err_msg}")
            # Log full response for debugging
            print(f"   Full response: {r.stdout[:500]}")
            return ''
        call_id = call_data.get('id', '')
        if call_id:
            # Save to call_log immediately
            try:
                db2 = sqlite3.connect(DB_PATH)
                c2 = db2.cursor()
                c2.execute("INSERT OR IGNORE INTO call_log (id, business_id, lead_id, vapi_call_id, outcome) VALUES (?, ?, ?, ?, 'queued')",
                          (str(uuid.uuid4())[:8], biz['id'], lead['id'], call_id))
                db2.commit()
                db2.close()
            except Exception as log_err:
                print(f"Log save error: {log_err}")
            
            # Fetch call details in background after a delay
            def fetch_call_details(cid, lead_phone):
                # Poll until the call actually ENDS — a single 30s wait races
                # calls that run 60-120s+ (transcript empty => no booking detected)
                cd = None
                for attempt in range(20):  # up to ~5 min
                    time.sleep(15)
                    try:
                        r2 = subprocess.run(["curl", "-s", f"{VAPI_BASE}/call/{cid}",
                            "-H", f"Authorization: Bearer ***"], capture_output=True, text=True, timeout=20)
                        cd = json.loads(r2.stdout)
                        st = (cd or {}).get('status', '')
                        if st in ('ended', 'completed', 'failed', 'cancelled', 'voicemail'):
                            break
                    except Exception:
                        cd = None
                if not cd or not cd.get('id'):
                    print(f"⚠️ Could not fetch call {cid} details after retries")
                    return
                try:
                    # Vapi doesn't have durationSeconds - calculate from timestamps
                    dur = 0
                    try:
                        from datetime import datetime as dt
                        st = cd.get('startedAt','')
                        et = cd.get('endedAt','')
                        if st and et:
                            dur = int((dt.fromisoformat(et.replace('Z','+00:00')) - dt.fromisoformat(st.replace('Z','+00:00'))).total_seconds())
                    except:
                        pass
                    
                    cost = cd.get('cost', 0)
                    status = cd.get('status', 'unknown')
                    ended = cd.get('endedReason', '')
                    
                    # Transcript - Vapi returns pre-formatted string at top level
                    transcript = cd.get('transcript', '') or ''
                    # Also try messages array for structured data
                    if not transcript:
                        msgs = cd.get('messages', cd.get('artifact',{}).get('messages', []))
                        if isinstance(msgs, list):
                            parts = []
                            for msg in msgs:
                                role = msg.get('role', '')
                                text = msg.get('message', msg.get('content', ''))
                                if text and role not in ('system',):
                                    parts.append(f"{role.upper()}: {text}")
                            transcript = '\n'.join(parts)
                    
                    # Recording URL
                    # Recording URL - use authenticated endpoint instead of direct URL
                    # New Vapi requirement: recordings require auth via /call/{id}/mono-recording
                    # Store the call ID so we can fetch recording on-demand through auth proxy
                    recording = f"/api/call/{cid}/recording"  # Will be proxied through our server
                    
                    # Determine outcome
                    import re as appt_re
                    appointment_time = ''
                    is_booking = False
                    
                    if transcript and ('book' in transcript.lower() or 'schedule' in transcript.lower()):
                        outcome = 'appointment_booked'
                        is_booking = True
                        for pat in [
                            r'(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?',
                            r'(?:tomorrow|today)\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?',
                            r'(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?',
                            r'\d{1,2}/\d{1,2}(?:/\d{2,4})?\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?',
                        ]:
                            m = appt_re.search(transcript.lower(), appt_re.IGNORECASE)
                            if m:
                                appointment_time = m.group(0).strip()
                                break
                    elif ended == 'customer-ended-call':
                        outcome = 'no_answer' if dur and dur < 10 else 'completed'
                    elif ended == 'silence-timed-out':
                        outcome = 'no_answer'
                    else:
                        outcome = 'called'
                    
                    db3 = sqlite3.connect(DB_PATH)
                    c3 = db3.cursor()
                    c3.execute("""UPDATE call_log SET duration=?, cost=?, outcome=?, transcript=?, recording_url=? 
                                  WHERE vapi_call_id=?""", (dur, cost, outcome, transcript[:5000], recording, cid))
                    
                    # If appointment booked, save to appointments table and send notification
                    if is_booking:
                        import uuid as appt_uuid
                        # Find the lead_id for this call
                        c3.execute("SELECT id, lead_id, business_id FROM call_log WHERE vapi_call_id=?", (cid,))
                        call_row = c3.fetchone()
                        lead_id = call_row[1] if call_row and call_row[1] else ''
                        biz_id = call_row[2] if call_row else ''
                        
                        # Get lead info
                        prospect_name = lead_phone
                        if lead_id:
                            c3.execute("SELECT name, phone, business_name FROM leads WHERE id=?", (lead_id,))
                            lr = c3.fetchone()
                            if lr:
                                prospect_name = lr[0] or lr[2] or lr[1] or lead_phone
                        
                        appt_id = str(appt_uuid.uuid4())[:12]
                        c3.execute("""INSERT OR IGNORE INTO appointments 
                            (id, business_id, lead_id, call_log_id, prospect_name, phone, appointment_time, notes, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'booked')""",
                            (appt_id, biz_id, lead_id, call_row[0] if call_row else '', 
                             prospect_name[:100], lead_phone, appointment_time or 'TBD',
                             transcript[:500]))
                        
                        # Send Telegram notification
                        if biz_id:
                            try:
                                import urllib.request as tg_req
                                import urllib.parse as tg_parse
                                TELEGRAM_BOT_TOKEN = "7634224489:AAFWL_jShRZfNMfOq5S_eDdPDYAcMxp-fW8"
                                TELEGRAM_CHAT_ID = "5804173449"
                                msg = f"📅 NEW APPOINTMENT BOOKED!\n\n👤 {prospect_name}\n📞 {lead_phone}\n🕐 {appointment_time or 'Time discussed in call'}\n📝 {transcript[:150]}"
                                tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={tg_parse.quote(msg)}"
                                tg_req.urlopen(tg_url, timeout=5)
                                print(f"📨 Telegram notification sent for appointment {appt_id}")
                            except Exception as tg_e:
                                print(f"Telegram notify error: {tg_e}")
                        
                        # Send AgentMail confirmation if lead has email
                        if biz_id and lead_id:
                            try:
                                c3.execute("SELECT email FROM leads WHERE id=?", (lead_id,))
                                lr2 = c3.fetchone()
                                lead_email = lr2[0] if lr2 and lr2[0] else ''
                                if lead_email:
                                    c3.execute("SELECT name FROM businesses WHERE id=?", (biz_id,))
                                    br = c3.fetchone()
                                    biz_name_am = br[0] if br else 'Business'
                                    send_appointment_confirmation(
                                        to=lead_email,
                                        prospect_name=prospect_name or 'there',
                                        business_name=biz_name_am,
                                        appointment_time=appointment_time
                                    )
                                    print(f"📧 Confirmation email sent to {lead_email}")
                            except Exception as am_e:
                                print(f"AgentMail email error: {am_e}")
                    
                    db3.commit()
                    db3.close()
                    print(f"📝 Call {cid[:12]}... updated: {dur}s, ${cost}, {outcome}")
                    if appointment_time:
                        print(f"📅 Appointment: {appointment_time}")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"📝 Fetch call details error for {cid}: {e}")
            
            threading.Thread(target=fetch_call_details, args=(call_id, lead['phone']), daemon=True).start()
            return call_id
        # If no id but we got a valid response, log what happened
        print(f"VAPI response for {lead['phone']}: {r.stdout[:200] if r.stdout else 'empty'}")
        return call_id
    except Exception as e:
        print(f"Call failed for {lead['phone']}: {e}")
        return ''

def run_campaign_bg(bid):
    """Background campaign runner with parallel calling + live logging. Loops until complete or stopped.
    Safety: max 3 retries per lead, auto-stop after 10 cycles, checks stop every iteration."""
    try:
        log_campaign(bid, '🚀 Campaign started', 'info')
        max_cycles = 10  # Safety: auto-stop after this many full cycles
        cycle_count = 0
        
        while True:
            cycle_count += 1
            if cycle_count > max_cycles:
                log_campaign(bid, f'⏹️ Safety auto-stop after {max_cycles} cycles. Press Start to run again.', 'warning')
                c = sqlite3.connect(DB_PATH).cursor()
                c.execute("UPDATE campaigns SET status='completed' WHERE business_id=?", (bid,))
                sqlite3.connect(DB_PATH).commit()
                return
            
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            c = db.cursor()
        
        # Check if campaign was stopped
            c.execute("SELECT status FROM campaigns WHERE business_id = ?", (bid,))
            row = c.fetchone()
            if not row or row['status'] != 'running':
                log_campaign(bid, '⏹️ Campaign stopped by user.', 'info')
                db.close()
                return
        
        # ── Schedule Check ──
        # If campaign has scheduling enabled, check if we're within the allowed window
            c.execute("SELECT schedule_enabled, schedule_time, schedule_days, schedule_start_date, timezone FROM campaigns WHERE business_id = ?", (bid,))
            sched = c.fetchone()
            if sched and sched['schedule_enabled']:
                now = datetime.now()
                day_names = ['mon','tue','wed','thu','fri','sat','sun']
                today_name = day_names[now.weekday()]
                allowed_days = [d.strip().lower() for d in (sched['schedule_days'] or '').split(',') if d.strip()]
                current_time_str = now.strftime('%H:%M')
                sched_time = (sched['schedule_time'] or '09:00').strip()
                
                # Check day of week
                day_ok = today_name in allowed_days
                # Check time of day
                time_ok = current_time_str >= sched_time
                # Check start date (if set)
                sched_date_str = (sched['schedule_start_date'] or '').strip()
                date_ok = True
                if sched_date_str:
                    try:
                        sched_date = datetime.strptime(sched_date_str[:10], '%Y-%m-%d').date()
                        date_ok = now.date() >= sched_date
                    except:
                        date_ok = True  # if date is invalid, ignore
                
                if not (day_ok and time_ok and date_ok):
                    date_str = now.strftime('%Y-%m-%d')
                    log_campaign(bid, f'⏰ Outside schedule window (day={today_name}, time={current_time_str}, date={date_str}). Waiting...', 'info')
                    db.close()
                    time.sleep(60)
                    continue
        
            c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
            biz = c.fetchone()
            if not biz:
                log_campaign(bid, '❌ Business not found', 'error')
                db.close()
                return
        
            assistant_id = biz['vapi_assistant_id']
            phone_id = biz['vapi_phone_id']
            max_calls = int(biz['max_calls_per_day'] or 20)
            call_delay = int(biz['call_delay'] or 60)
            try:
                concurrency = int(biz['concurrency'])
            except (KeyError, TypeError, ValueError):
                concurrency = 5
            name = biz['name']
        
            if not assistant_id or not phone_id:
                error = 'VAPI assistant not created' if not assistant_id else 'Phone number not assigned'
                log_campaign(bid, f'❌ {error}. Contact your account manager to set up your AI agent.', 'error')
                c.execute("UPDATE campaigns SET status = 'error' WHERE business_id = ?", (bid,))
                db.commit()
                db.close()
                return
        
            # Safety: only call leads with retry_count < 1
            c.execute("SELECT COUNT(*) as cnt FROM leads WHERE business_id = ? AND state = 'NEW' AND (retry_count IS NULL OR retry_count < 1)", (bid,))
            available = c.fetchone()['cnt']
            calls_to_make = min(max_calls, available)
        
            log_campaign(bid, f'📊 {available} NEW leads found (max 3 retries), calling {calls_to_make} this cycle (cycle #{cycle_count}/{max_cycles})', 'info')
        
            if calls_to_make == 0:
                log_campaign(bid, '🎉 All leads reached max retries or no NEW leads. Campaign complete.', 'info')
                c.execute("UPDATE campaigns SET status = 'completed' WHERE business_id = ?", (bid,))
                db.commit()
                db.close()
                return
        
        # Mark as CALLING — use subquery to limit rows (SQLite doesn't support LIMIT in UPDATE)
            c.execute("UPDATE leads SET state = 'CALLING', last_called_at = datetime('now'), retry_count = COALESCE(retry_count,0) + 1 "
                       "WHERE rowid IN (SELECT rowid FROM leads WHERE business_id = ? AND state = 'NEW' AND (retry_count IS NULL OR retry_count < 1) LIMIT ?)",
                       (bid, calls_to_make))
            c.execute("UPDATE campaigns SET calls_made = calls_made + ?, last_run_at = datetime('now') WHERE business_id = ?", (calls_to_make, bid))
            db.commit()
        
            # Fetch leads
            c.execute("SELECT * FROM leads WHERE business_id = ? AND state = 'CALLING'", (bid,))
            leads = c.fetchall()
            log_campaign(bid, f'📞 Calling {len(leads)} prospects...', 'info')
        
            made = 0
            failed = 0
            if leads:
                actual_concurrency = min(concurrency, len(leads))
                campaign_status_cache[bid] = 'calling'
                log_campaign(bid, f'⚡ Concurrency: {actual_concurrency} parallel calls', 'info')
                with ThreadPoolExecutor(max_workers=actual_concurrency) as executor:
                    futures = {executor.submit(make_vapi_call, lead, biz, assistant_id, phone_id, call_delay): lead for lead in leads}
                    for future in as_completed(futures):
                        lead = futures[future]
                        try:
                            call_id = future.result()
                            if call_id:
                                made += 1
                                log_campaign(bid, f'✅ Call to {lead["phone"]} started (ID: {call_id[:12]}...)', 'success')
                            else:
                                failed += 1
                                log_campaign(bid, f'❌ Call to {lead["phone"]} failed', 'error')
                        except Exception as e:
                            failed += 1
                            log_campaign(bid, f'❌ Call to {lead["phone"]} error: {str(e)[:80]}', 'error')
                        time.sleep(random.uniform(0.5, 2.0))
        
            # Update final states
            c.execute("UPDATE leads SET state = 'CALLED' WHERE business_id = ? AND state = 'CALLING'", (bid,))
            db.commit()
        
            log_campaign(bid, f'📊 Cycle complete: {made} calls made, {failed} failed', 'info')
        
            # Check if more leads remain
            c.execute("SELECT COUNT(*) as cnt FROM leads WHERE business_id = ? AND state = 'NEW'", (bid,))
            remaining = c.fetchone()['cnt']
            if remaining > 0:
                campaign_status_cache[bid] = 'waiting'
                log_campaign(bid, f'🔄 {remaining} leads remaining. Sleeping {call_delay}s before next cycle...', 'info')
            else:
                # After all leads called: reset those still under retry limit back to NEW
                c.execute("SELECT COUNT(*) as cnt FROM leads WHERE business_id=? AND (retry_count IS NULL OR retry_count < 1)", (bid,))
                retryable = c.fetchone()['cnt']
                c.execute("SELECT COUNT(*) as cnt FROM leads WHERE business_id=? AND retry_count >= 1", (bid,))
                exhausted = c.fetchone()['cnt']
                if retryable == 0:
                    log_campaign(bid, f'🎉 All {exhausted} leads reached max retries. Campaign complete.', 'info')
                    c.execute("UPDATE campaigns SET status='completed' WHERE business_id=?", (bid,))
                    db.commit()
                    db.close()
                    return
                # Reset only retryable leads back to NEW for next cycle
                c.execute("UPDATE leads SET state='NEW' WHERE business_id=? AND state='CALLED' AND (retry_count IS NULL OR retry_count < 1)", (bid,))
                db.commit()
                log_campaign(bid, f'🔄 {retryable} leads reset to NEW for next cycle ({exhausted} exhausted). Cycle #{cycle_count}/{max_cycles}', 'info')
                db.close()
                # Short pause before next cycle
                for _ in range(10):
                    time.sleep(1)
                    db2 = sqlite3.connect(DB_PATH)
                    c2 = db2.cursor()
                    c2.execute("SELECT status FROM campaigns WHERE business_id = ?", (bid,))
                    row2 = c2.fetchone()
                    db2.close()
                    if not row2 or row2[0] != 'running':
                        log_campaign(bid, '⏹️ Campaign stopped during cycle.', 'info')
                        return
                continue
        
            db.commit()
            db.close()
        
            # Sleep between cycles (check for stop every 5s)
            for _ in range(call_delay // 5):
                time.sleep(5)
                db2 = sqlite3.connect(DB_PATH)
                c2 = db2.cursor()
                c2.execute("SELECT status FROM campaigns WHERE business_id = ?", (bid,))
                row2 = c2.fetchone()
                db2.close()
                if not row2 or row2[0] != 'running':
                    log_campaign(bid, '⏹️ Campaign stopped by user during pause.', 'info')
                    return
            # remaining seconds
            time.sleep(call_delay % 5)
    except Exception as e:
        print(f"💥 CRASH in campaign thread for {bid}: {e}")
        import traceback
        traceback.print_exc()
        log_campaign(bid, f'💥 Campaign crashed: {str(e)[:80]}', 'error')

# ── LEAD MANAGEMENT ──

@app.route('/lead/reset', methods=['POST'])
@login_required
def reset_leads():
    """Reset all CALLED leads back to NEW for re-calling."""
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE leads SET state='NEW', last_called_at=NULL WHERE business_id=? AND state='CALLED'", (bid,))
    count = c.rowcount
    db.commit()
    db.close()
    flash(f'🔄 {count} leads reset to NEW. Ready to call again!', 'success')
    return redirect('/')

@app.route('/lead/add', methods=['GET', 'POST'])
def add_lead():
    # GET request - redirect to leads tab (even without session, redirect to login which goes back)
    if request.method == 'GET':
        bid = session.get('business_id')
        if not bid:
            return redirect('/')
        return redirect('/?tab=leads')
    
    bid = session.get('business_id')
    if not bid:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    # Handle both JSON and form-encoded
    if request.is_json:
        data = request.get_json(silent=True) or {}
        phone = data.get('phone', '').strip()
        name = data.get('name', '')
        business_name = data.get('business_name', '')
        notes = data.get('notes', '')
    else:
        phone = request.form.get('phone', '').strip()
        name = request.form.get('name', '')
        business_name = request.form.get('business_name', '')
        notes = request.form.get('notes', '')
    
    if not phone:
        return jsonify({'success': False, 'message': 'Phone number required'}), 400
    
    db = get_db()
    c = db.cursor()
    lid = hashlib.md5((phone + bid + str(time.time())).encode()).hexdigest()[:12]
    c.execute("INSERT INTO leads (id, business_id, phone, name, business_name, notes, state) VALUES (?,?,?,?,?,?,'NEW')",
        (lid, bid, phone, name, business_name, notes))
    c.execute("UPDATE campaigns SET leads_imported = COALESCE(leads_imported,0) + 1 WHERE business_id = ?", (bid,))
    db.commit()
    
    # Check if AJAX (JSON expected) or form submission
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': '✅ Lead added!', 'lead_id': lid})
    flash('✅ Lead added!', 'success')
    return redirect('/?tab=leads')

@app.route('/lead/bulk', methods=['POST'])
@login_required
def bulk_leads():
    bid = session['business_id']
    data = request.form.get('bulk_data', '')
    count = 0
    db = get_db()
    c = db.cursor()
    
    for line in data.strip().split('\n'):
        parts = [p.strip() for p in line.split(',')]
        if not parts[0]: continue
        lid = hashlib.md5((parts[0] + bid + str(time.time())).encode()).hexdigest()[:12]
        c.execute("INSERT OR IGNORE INTO leads (id, business_id, phone, name, business_name, state) VALUES (?,?,?,?,?,'NEW')",
            (lid, bid, parts[0], parts[1] if len(parts)>1 else '', parts[2] if len(parts)>2 else ''))
        count += 1
    
    c.execute("UPDATE campaigns SET leads_imported = COALESCE(leads_imported,0) + ? WHERE business_id = ?", (count, bid))
    db.commit()
    flash(f'✅ {count} leads imported!', 'success')
    return redirect('/?tab=leads')

@app.route('/call-note/update', methods=['POST'])
@login_required
def update_call_note():
    bid = session['business_id']
    call_id = request.form.get('call_id', '')
    notes = request.form.get('notes', '').strip()
    if not call_id:
        return jsonify({'success': False, 'message': 'Call ID required'}), 400
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE call_log SET notes=? WHERE id=? AND business_id=?", (notes, call_id, bid))
    db.commit()
    return jsonify({'success': True, 'message': '✅ Note saved!'})

@app.route('/call-note/delete', methods=['POST'])
@login_required
def delete_call_note():
    bid = session['business_id']
    call_id = request.form.get('call_id', '')
    if not call_id:
        return jsonify({'success': False, 'message': 'Call ID required'}), 400
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE call_log SET notes='' WHERE id=? AND business_id=?", (call_id, bid))
    db.commit()
    return jsonify({'success': True, 'message': '✅ Note deleted!'})

@app.route('/upload-leads', methods=['POST'])
@login_required
def upload_leads():
    bid = session['business_id']
    file = request.files.get('csv')
    if not file:
        return jsonify({'error': 'No file'}), 400
    
    db = get_db()
    c = db.cursor()
    count = 0
    skipped = 0
    
    raw = file.stream.read()
    # Handle BOM
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    text = raw.decode('utf-8-sig')
    stream = io.StringIO(text)
    reader = csv.DictReader(stream)
    
    # Normalize headers to lowercase
    if reader.fieldnames:
        reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
    
    for row in reader:
        # Handle empty rows (all None or empty)
        if all(not v or not v.strip() for v in row.values() if v):
            continue
        # Lowercase row keys for consistency
        row = {k.lower().strip(): (v or '').strip() for k, v in row.items()}
        
        # Try multiple column name variations for phone
        phone = row.get('phone') or row.get('number') or row.get('phone number') or row.get('phone_number') or ''
        phone = phone.strip()
        if not phone:
            skipped += 1
            continue
        
        # Name variations
        name = row.get('name') or row.get('first name') or row.get('first_name') or row.get('contact') or ''
        # Business name variations
        biz = row.get('business_name') or row.get('business') or row.get('company') or row.get('company_name') or row.get('business name') or ''
        # Email variations
        email = row.get('email') or row.get('e-mail') or row.get('email address') or ''
        
        lid = hashlib.md5((phone + bid + str(time.time())).encode()).hexdigest()[:12]
        c.execute("INSERT OR IGNORE INTO leads (id, business_id, phone, name, business_name, email, state) VALUES (?,?,?,?,?,?,'NEW')",
            (lid, bid, phone, name, biz, email))
        count += 1
    
    c.execute("UPDATE campaigns SET leads_imported = COALESCE(leads_imported,0) + ? WHERE business_id = ?", (count, bid))
    db.commit()
    
    msg = f'✅ {count} leads imported!'
    if skipped:
        msg += f' ({skipped} skipped - missing phone numbers)'
    
    # If AJAX request (has Accept: application/json or X-Requested-With), return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
        return jsonify({'message': msg})
    # Form fallback: redirect with flash
    flash(msg, 'success')
    return redirect('/?tab=leads')

@app.route('/lead/call/<lead_id>', methods=['POST'])
@login_required
def call_lead(lead_id):
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    
    c.execute("SELECT * FROM leads WHERE id = ? AND business_id = ?", (lead_id, bid))
    lead = c.fetchone()
    if not lead: return redirect('/?tab=leads')
    lead = dict(lead)  # sqlite3.Row has no .get()
    
    c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    
    if biz['vapi_assistant_id'] and biz['vapi_phone_id']:
        # Build call payload with lead knowledge
        call_payload = {
            "assistantId": biz['vapi_assistant_id'],
            "phoneNumberId": biz['vapi_phone_id'],
            "customer": {"number": lead['phone']},
            "assistantOverrides": {"model": {"maxTokens": 200, "provider": "xai", "model": "grok-4.3"}}
        }
        # Inject lead knowledge into the AI's context
        knowledge_parts = []
        if lead.get('business_name'):
            knowledge_parts.append(f"Business: {lead['business_name']}")
        if lead.get('name'):
            knowledge_parts.append(f"Contact Name: {lead['name']}")
        if lead.get('notes', '').strip():
            knowledge_parts.append(f"Context: {lead['notes'].strip()}")
        if knowledge_parts:
            call_payload["assistantOverrides"]["model"]["messages"] = [
                {
                    "role": "system",
                    "content": f"[LEAD KNOWLEDGE]\n{' | '.join(knowledge_parts)}\nUse this information to personalize the conversation."
                }
            ]
        subprocess.run(["curl","-s","-X","POST",f"{VAPI_BASE}/call",
            "-H",f"Authorization: Bearer {VAPI_API_KEY}",
            "-H","Content-Type: application/json",
            "-d",json.dumps(call_payload)])
        c.execute("UPDATE leads SET state = 'CALLING', last_called_at = datetime('now') WHERE id = ?", (lead_id,))
        c.execute("UPDATE campaigns SET calls_made = calls_made + 1 WHERE business_id = ?", (bid,))
        db.commit()
        flash('📞 Calling...', 'success')
    
    return redirect('/?tab=leads')

@app.route('/lead/delete/<lead_id>', methods=['POST'])
@login_required
def delete_lead(lead_id):
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM leads WHERE id = ? AND business_id = ?", (lead_id, bid))
    db.commit()
    return redirect('/?tab=leads')

@app.route('/lead/update', methods=['POST'])
@login_required
def update_lead():
    """Update a lead's name, phone, business_name, or notes."""
    bid = session['business_id']
    lead_id = request.form.get('id', '')
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    business_name = request.form.get('business_name', '').strip()
    notes = request.form.get('notes', '').strip()
    
    if not lead_id or not phone:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Lead ID and phone are required'}), 400
        flash('❌ Lead ID and phone are required', 'error')
        return redirect('/?tab=leads')
    
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE leads SET name=?, phone=?, business_name=?, notes=? WHERE id=? AND business_id=?",
              (name, phone, business_name, notes, lead_id, bid))
    db.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': '✅ Lead updated!'})
    
    flash('✅ Lead updated!', 'success')
    return redirect('/?tab=leads')

@app.route('/lead/update/<lead_id>', methods=['POST'])
@login_required
def update_lead_json(lead_id):
    """Update a lead via JSON (used by the edit modal)."""
    bid = session['business_id']
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    business_name = data.get('business_name', '').strip()
    
    if not phone:
        return jsonify({'success': False, 'message': 'Phone number required'}), 400
    
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE leads SET name=?, phone=?, business_name=? WHERE id=? AND business_id=?",
              (name, phone, business_name, lead_id, bid))
    db.commit()
    return jsonify({'success': True, 'message': '✅ Lead updated!'})

# ── LEAD FINDER ──

@app.route('/api/find-leads', methods=['POST'])
@login_required
def find_leads():
    """Search for business leads by industry and location using web search."""
    data = request.get_json(silent=True) or {}
    industry = data.get('industry', '').strip()
    location = data.get('location', '').strip()
    max_results = min(int(data.get('max_results', 10)), 30)
    
    if not industry:
        return jsonify({'error': 'Industry is required'}), 400
    
    try:
        from ddgs import DDGS
        import re
        
        # Try multiple search queries for better results
        base_query = f'{industry} in {location} phone' if location else f'{industry} phone number'
        searches = [
            base_query,
            f'{industry} {location} "(305)" OR "(786)" OR "(954)"',
        ]
        
        results = []
        seen_urls = set()
        with DDGS() as ddgs:
            for sq in searches:
                try:
                    for r in ddgs.text(sq, max_results=max_results):
                        url = r.get('href', '')
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        title = r.get('title', '')
                        snippet = r.get('body', '')
                        
                        # Extract phone numbers from snippet and title
                        phone_pattern = r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
                        phones = re.findall(phone_pattern, title + ' ' + snippet)
                        
                        # Clean up phone numbers
                        clean_phones = []
                        for p in phones:
                            clean = re.sub(r'[^\d]', '', p)
                            if len(clean) >= 10:
                                if len(clean) == 10:
                                    clean = '+1' + clean
                                elif len(clean) == 11 and clean.startswith('1'):
                                    clean = '+' + clean
                                elif len(clean) > 11:
                                    clean = '+1' + clean[-10:]
                                clean_phones.append(clean)
                        
                        results.append({
                            'title': title[:100],
                            'snippet': snippet[:200],
                            'url': url[:200],
                            'phones': list(set(clean_phones))[:3]
                        })
                        
                        if len(results) >= max_results * 2:
                            break
                except:
                    pass
                if len(results) >= max_results * 2:
                    break
        
        # If no phones found in snippets, scrape the actual pages
        pages_without_phones = [r for r in results if not r['phones']]
        if pages_without_phones:
            import requests as req
            for r2 in pages_without_phones[:5]:  # Limit to 5 pages
                try:
                    resp = req.get(r2['url'], timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
                    if resp.status_code == 200:
                        text = resp.text
                        # Extract phone numbers from the page content
                        phones = re.findall(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
                        clean = []
                        for p in phones:
                            c = re.sub(r'[^\d]', '', p)
                            if len(c) >= 10:
                                if len(c) == 10:
                                    c = '+1' + c
                                elif len(c) == 11 and c.startswith('1'):
                                    c = '+' + c
                                clean.append(c)
                        if clean:
                            r2['phones'] = list(set(clean))[:3]
                except:
                    pass
        
        # Deduplicate by title
        seen = set()
        unique = []
        for r in results:
            key = r['title'].lower()[:40]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        
        return jsonify({'results': unique, 'count': len(unique), 'query': base_query})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import-leads', methods=['POST'])
@login_required
def import_leads():
    """Import selected leads from search results."""
    data = request.get_json(silent=True) or {}
    leads_data = data.get('leads', [])
    bid = session['business_id']
    
    if not leads_data:
        return jsonify({'error': 'No leads to import'}), 400
    
    import uuid, re
    db = get_db()
    c = db.cursor()
    imported = 0
    
    for lead in leads_data:
        phone = lead.get('phone', '').strip()
        name = lead.get('name', '').strip()[:100]
        business = lead.get('business', '').strip()[:100]
        
        if not phone:
            continue
        
        # Clean phone
        phone = re.sub(r'[^+\d]', '', phone)
        if len(phone) >= 10:
            if len(phone) == 10:
                phone = '+1' + phone
            elif len(phone) == 11:
                phone = '+' + phone
            
            # Check if already exists
            c.execute("SELECT id FROM leads WHERE business_id = ? AND phone = ?", (bid, phone))
            if c.fetchone():
                continue
            
            lid = str(uuid.uuid4())[:12]
            c.execute("""INSERT INTO leads (id, business_id, phone, name, business_name, state)
                VALUES (?, ?, ?, ?, ?, 'NEW')""",
                (lid, bid, phone, name, business))
            imported += 1
    
    db.commit()
    return jsonify({'imported': imported, 'total': len(leads_data)})

# ── SETTINGS ──

@app.route('/update-script', methods=['POST'])
@login_required
def update_script():
    bid = session['business_id']
    script = request.form.get('script', '')
    kb = request.form.get('knowledge_base', '')
    first_message = request.form.get('first_message', '')
    first_message_mode = request.form.get('first_message_mode', 'assistant-speaks-first')
    voice_provider = request.form.get('voice_provider', 'elevenlabs')
    
    db = get_db()
    c = db.cursor()
    c.execute("""UPDATE businesses 
                 SET script_template = ?, knowledge_base = ?, 
                     first_message = ?, first_message_mode = ?, voice_provider = ?
                 WHERE id = ?""",
        (script, kb, first_message, first_message_mode, voice_provider, bid))
    db.commit()
    
    # ── Sync to Vapi assistant ──
    c.execute("""SELECT vapi_assistant_id, name, industry, script_template, 
                 knowledge_base, agent_prompt, first_message, first_message_mode,
                 voice_id, voice_speed, voice_provider
                 FROM businesses WHERE id = ?""", (bid,))
    biz = c.fetchone()
    db.close()
    
    if biz and biz['vapi_assistant_id']:
        name = biz['name'] or ''
        industry = biz['industry'] or 'general'
        agent_prompt = biz['agent_prompt'] or ''
        saved_script = biz['script_template'] or ''
        saved_kb = biz['knowledge_base'] or ''
        first_msg = biz['first_message'] or ''
        
        # Build the full system prompt
        if agent_prompt.strip():
            full_prompt = build_diazites_prompt(
                business_name=name, industry=industry,
                script=agent_prompt, knowledge_base=saved_kb
            )
        else:
            full_prompt = build_diazites_prompt(
                business_name=name, industry=industry,
                script=saved_script, knowledge_base=saved_kb
            )
        
        # Build Vapi assistant update payload
        vapi_payload = {
            "model": {
                "provider": "xai",
                "model": "grok-4.3",
                "systemPrompt": full_prompt
            }
        }
        
        # Add first message settings if set
        if first_msg:
            vapi_payload["firstMessage"] = first_msg
            vapi_payload["firstMessageMode"] = first_message_mode
        
        # Add voice provider mapping
        vp = biz['voice_provider'] or '11labs'
        voice_id = biz['voice_id'] or 'rachel'
        speed = float(biz['voice_speed'] or 1.15)
        if vp == '11labs':
            vapi_payload["voice"] = {
                "provider": "11labs",
                "voiceId": voice_id,
                "speed": speed,
                "stability": 0.5,
                "similarityBoost": 0.7
            }
        elif vp == 'vapi':
            vapi_payload["voice"] = {
                "provider": "vapi",
                "voiceId": voice_id,
                "speed": speed
            }
        elif vp == 'azure':
            vapi_payload["voice"] = {
                "provider": "azure",
                "voiceId": voice_id,
                "speed": speed
            }
        
        r = subprocess.run(["curl","-s","-X","PATCH",f"{VAPI_BASE}/assistant/{biz['vapi_assistant_id']}",
            "-H",f"Authorization: Bearer {VAPI_API_KEY}",
            "-H","Content-Type: application/json",
            "-d",json.dumps(vapi_payload)],
            capture_output=True, text=True, timeout=15)
        
        try:
            result = json.loads(r.stdout)
            if 'error' not in result and 'statusCode' not in result:
                flash('✅ Script, KB & Vapi settings synced!', 'success')
            else:
                flash(f"✅ Saved locally. Vapi sync: {result.get('message','check settings')}", 'warning')
        except:
            flash('✅ Script & KB saved locally. Vapi sync attempted.', 'success')
    else:
        flash('✅ Script saved! Set up a Vapi assistant to sync to voice agent.', 'success')
    
    return redirect('/?tab=settings')

@app.route('/update-agent-prompt', methods=['POST'])
@login_required
def update_agent_prompt():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE businesses SET agent_prompt = ? WHERE id = ?",
        (request.form.get('agent_prompt',''), bid))
    db.commit()
    
    # Also update Vapi assistant system prompt with new agent prompt
    c.execute("SELECT vapi_assistant_id, name, industry, script_template, knowledge_base, agent_prompt FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if biz and biz['vapi_assistant_id']:
        name = biz['name'] or ''
        industry = biz['industry'] or 'general'
        agent_prompt = biz['agent_prompt'] or ''
        script = biz['script_template'] or ''
        kb = biz['knowledge_base'] or ''
        
        if agent_prompt.strip():
            # Custom agent prompt — wrap it in Diazites framework
            full_prompt = build_diazites_prompt(
                business_name=name,
                industry=industry,
                script=agent_prompt,
                knowledge_base=kb
            )
        else:
            # Use Diazites framework with business settings
            full_prompt = build_diazites_prompt(
                business_name=name,
                industry=industry,
                script=script,
                knowledge_base=kb
            )
        
        subprocess.run(["curl","-s","-X","PATCH",f"{VAPI_BASE}/assistant/{biz['vapi_assistant_id']}",
            "-H",f"Authorization: Bearer ***",
            "-H","Content-Type: application/json",
            "-d",json.dumps({
                "model": {"provider": "xai", "model": "grok-4.3", "systemPrompt": full_prompt}
            })], capture_output=True, text=True)
    
    flash('✅ Agent prompt updated!', 'success')
    return redirect('/?tab=settings')

@app.route('/update-voice', methods=['POST'])
@login_required
def update_voice():
    bid = session['business_id']
    voice_id = request.form.get('voice_id', 'rachel')
    voice_speed = float(request.form.get('voice_speed', 1.15))
    language = request.form.get('language', 'en')
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE businesses SET voice_id = ?, voice_speed = ?, language = ? WHERE id = ?", (voice_id, voice_speed, language, bid))
    db.commit()
    
    # Update VAPI assistant voice + speed + language
    from premium_features2 import LANGUAGES
    lang_map = {l["code"]: l["name"] for l in LANGUAGES}
    
    c.execute("SELECT vapi_assistant_id FROM businesses WHERE id = ?", (bid,))
    row = c.fetchone()
    if row and row['vapi_assistant_id']:
        from premium_features2 import update_assistant_language
        update_assistant_language(row['vapi_assistant_id'], language, VAPI_API_KEY)
        subprocess.run(["curl","-s","-X","PATCH",f"{VAPI_BASE}/assistant/{row['vapi_assistant_id']}",
            "-H",f"Authorization: Bearer {VAPI_API_KEY}",
            "-H","Content-Type: application/json",
            "-d",json.dumps({
                "voice": {"provider": "elevenlabs", "voiceId": voice_id, "speed": voice_speed, "stability": 0.5, "similarityBoost": 0.7}
            })],
            capture_output=True)
    
    flash(f'✅ Voice set to {voice_id} at {voice_speed:.2f}x speed · {lang_map.get(language, language)}', 'success')
    return redirect('/?tab=settings')

@app.route('/api/test-voice', methods=['GET'])
def test_voice():
    """Generate a short test audio for a voice using edge-tts with mapped voices."""
    voice_id = request.args.get('voice_id', 'rachel')
    text = request.args.get('text', 'Hi, this is your AI voice assistant. How can I help you today?')
    speed = float(request.args.get('speed', 1.0))
    lang = request.args.get('lang', 'en')
    
    # Map ElevenLabs voice IDs to similar edge-tts voices
    EDGE_VOICE_MAP = {
        # Original voices
        "burt": "en-US-BrianNeural",           # Male, Professional
        "indy": "en-US-JennyNeural",           # Female, Warm
        "michael": "en-US-AndrewNeural",       # Male, Deep
        "emma": "en-US-EmmaNeural",            # Female, Friendly
        "antoni": "en-US-GuyNeural",           # Male, Calm
        # Premium voices (mapped to working edge-tts names)
        "rachel": "en-US-JennyNeural",         # Female, Warm
        "domi": "en-US-MichelleNeural",        # Female, Friendly
        "bella": "en-US-AriaNeural",           # Female, Melodic
        "elli": "en-US-AnaNeural",             # Female, Youthful
        "josh": "en-US-ChristopherNeural",     # Male, Deep
        "arnold": "en-US-EricNeural",          # Male, Authoritative
        "adam": "en-US-RogerNeural",           # Male, Confident
        "sam": "en-US-GuyNeural",              # Male, Warm
        "patrick": "en-US-AndrewNeural",       # Male, Professional
        "clyde": "en-US-RogerNeural",          # Male, Storytelling
        "alice": "en-US-JennyNeural",          # Female, Friendly
        # New UUID-based voices
        "TX3LPaxmHKxFdv7VOQHJ": "en-US-ChristopherNeural",  # Liam → energetic male
        "onwK4e9ZLuTAKqWW03F9": "en-US-EricNeural",         # Daniel → steady male
        "bIHbv24MWmeRgasZH58o": "en-US-AndrewNeural",       # Will → relaxed male
        "iP95p4xoKVk53GoZ742B": "en-US-RogerNeural",        # Chris → charming male
        "cjVigY5qzO86Huf0OWal": "en-US-GuyNeural",          # Eric → smooth male
        "cgSgspJ2msm6clMCkdW9": "en-US-AriaNeural",         # Jessica → playful female
        "XrExE9yKIg1WjnnlVkGX": "en-US-MichelleNeural",     # Matilda → professional female
        "pFZP5JQG7iQjIQuC4Bku": "en-US-AnaNeural",          # Lily → velvety female
        "CwhRBWXzGAHq8TQ4Fs17": "en-US-EricNeural",         # Roger → laid-back male
        "EXAVITQu4vr4xnSDxMaL": "en-US-JennyNeural",        # Sarah → reassuring female
        "IKne3meq5aSn9XLyUdCD": "en-US-AndrewNeural",       # Charlie → deep male
        "JBFqnCBsd6RMkjVDRZzb": "en-US-EricNeural",         # George → captivating male
        "SAz9YHcvj6GT2YYXdXww": "en-US-RogerNeural",        # River → neutral
        "N2lVS1w4EtoT3dr4eOWO": "en-US-ChristopherNeural",  # Callum → husky male
        "SOYHLrjzK2X1ezoPC6cr": "en-US-EricNeural",         # Harry → fierce male
        "nPczCjzI2devNBz1zQrb": "en-US-RogerNeural",        # Brian → resonant male
        "pqHfZKP75CvOlQylNhV4": "en-US-BrianNeural",        # Bill → wise male
        "FGY2WhTYpPnrIDTdsKH5": "en-US-AriaNeural",          # Laura → enthusiast female
        "pNInz6obpgDQGcFmaJgB": "en-US-RogerNeural",         # Adam → confident male
    }
    
    edge_voice = EDGE_VOICE_MAP.get(voice_id, "en-US-BrianNeural")
    
    import asyncio, os, uuid, edge_tts
    
    try:
        os.makedirs('/tmp/voice_previews', exist_ok=True)
        out_path = f'/tmp/voice_previews/{voice_id}_{uuid.uuid4().hex[:8]}.mp3'
        
        async def gen():
            kwargs = {'text': text, 'voice': edge_voice}
            if speed != 1.0:
                pct = int((speed - 1.0) * 100)
                kwargs['rate'] = f"{'+' if pct > 0 else ''}{pct}%"
            communicate = edge_tts.Communicate(**kwargs)
            await communicate.save(out_path)
        
        asyncio.run(gen())
        
        if not os.path.exists(out_path) or os.path.getsize(out_path) < 100:
            return jsonify({'error': 'Generated audio is empty'}), 500
        
        return send_file(out_path, mimetype='audio/mpeg', as_attachment=False, download_name=f'{voice_id}.mp3')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/call-logs')
@login_required
def api_call_logs():
    """Return call logs for live polling."""
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    since = request.args.get('since', '0')
    
    c.execute("""
        SELECT a.*, l.phone as lead_phone, l.name as lead_name, l.business_name as lead_biz,
               cl.transcript as call_transcript
        FROM appointments a
        LEFT JOIN leads l ON a.lead_id = l.id
        LEFT JOIN call_log cl ON a.call_log_id = cl.id
        WHERE a.business_id = ? AND a.status = 'booked'
        ORDER BY a.appointment_time ASC LIMIT 20
    """, (bid,))
    
    calls = [dict(r) for r in c.fetchall()]
    
    # Convert datetime objects to strings
    for call in calls:
        if hasattr(call.get('created_at'), 'strftime'):
            call['created_at'] = call['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify({'calls': calls})

@app.route('/update-settings', methods=['POST'])
@login_required
def update_settings():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("""UPDATE businesses SET 
        max_calls_per_day = ?, call_delay = ?, concurrency = ?, max_tokens = ?,
        voicemail_detection = ?, voicemail_action = ?, voicemail_message = ?,
        temperature = ?, silence_timeout = ?, interruption_sensitivity = ?
        WHERE id = ?""",
        (int(request.form.get('max_calls',20)), int(request.form.get('call_delay',60)),
         int(request.form.get('concurrency',5)), int(request.form.get('max_tokens',200)),
         request.form.get('voicemail_detection','google'),
         request.form.get('voicemail_action','hangup'),
         request.form.get('voicemail_message',''),
         float(request.form.get('temperature',0.3)),
         int(request.form.get('silence_timeout',10)),
         request.form.get('interruption_sensitivity','low'),
         bid))
    db.commit()
    
    # Also update VAPI assistant settings if one exists
    c.execute("SELECT vapi_assistant_id, name, industry, voice_id, voice_speed, language, script_template, knowledge_base FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if biz and biz['vapi_assistant_id']:
        import json
        name = biz['name'] or ''
        industry = biz['industry'] or 'general'
        voice_id = biz['voice_id'] or 'rachel'
        voice_speed = float(biz['voice_speed'] or 1.15)
        language = biz['language'] or 'en'
        script = biz['script_template'] or ''
        kb = biz['knowledge_base'] or ''
        temp = float(request.form.get('temperature',0.3))
        silence = int(request.form.get('silence_timeout',10))
        
        full_script = build_diazites_prompt(
            business_name=name,
            industry=industry,
            script=script,
            knowledge_base=kb
        )
        
        subprocess.run(["curl","-s","-X","PATCH",f"{VAPI_BASE}/assistant/{biz['vapi_assistant_id']}",
            "-H",f"Authorization: Bearer {VAPI_API_KEY}",
            "-H","Content-Type: application/json",
            "-d",json.dumps({
                "model": {
                    "provider": "xai",
                    "model": "grok-4.3",
                    "temperature": temp,
                    "maxTokens": int(request.form.get('max_tokens',200)),
                    "systemPrompt": full_script
                },
                "voice": {"provider": "11labs", "voiceId": voice_id, "speed": voice_speed, "stability": 0.5, "similarityBoost": 0.7},
                "silenceTimeoutSeconds": silence,
                "responseDelaySeconds": 0.1
            })],
            capture_output=True, text=True)
    
    flash('✅ Settings saved!', 'success')
    return redirect('/?tab=settings')

@app.route('/update-forwarding', methods=['POST'])
@login_required
def update_forwarding():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    enabled = 1 if request.form.get('forwarding_enabled') else 0
    c.execute("UPDATE businesses SET call_forwarding = ?, forward_to = ?, forward_when = ? WHERE id = ?",
        (enabled, request.form.get('forward_to',''), request.form.get('forward_when','after-hours'), bid))
    db.commit()
    flash('✅ Call forwarding updated!', 'success')
    return redirect('/?tab=forwarding')

@app.route('/update-sms-ai', methods=['POST'])
@login_required
def update_sms_ai():
    """Toggle AI SMS auto-replies for the logged-in business."""
    bid = session['business_id']
    enabled = 1 if request.form.get('sms_ai_enabled') == '1' else 0
    db = get_db()
    db.execute("UPDATE businesses SET sms_ai_enabled = ? WHERE id = ?", (enabled, bid))
    db.commit()
    db.close()
    flash(f'AI SMS replies {"enabled" if enabled else "disabled"}')
    return redirect('/?tab=settings')

@app.route('/update-voicemail-settings', methods=['POST'])
@login_required
def update_voicemail_settings():
    bid = session['business_id']
    vm_detection = request.form.get('voicemail_detection', 'google')
    vm_action = request.form.get('voicemail_action', 'hangup')
    vm_msg = request.form.get('voicemail_message', '')
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE businesses SET voicemail_detection=?, voicemail_action=?, voicemail_message=? WHERE id=?",
              (vm_detection, vm_action, vm_msg, bid))
    db.commit()
    
    # Update VAPI assistant voicemail settings
    c.execute("SELECT vapi_assistant_id FROM businesses WHERE id=?", (bid,))
    row = c.fetchone()
    if row and row['vapi_assistant_id']:
        payload = {"voichemailBaseline": True}
        subprocess.run(["curl","-s","-X","PATCH",f"{VAPI_BASE}/assistant/{row['vapi_assistant_id']}",
            "-H",f"Authorization: Bearer {VAPI_API_KEY}",
            "-H","Content-Type: application/json",
            "-d",json.dumps(payload)],
            capture_output=True)
    
    flash(f'✅ Voicemail: {vm_detection} · Action: {vm_action}', 'success')
    return redirect('/?tab=settings')

@app.route('/update-call-settings', methods=['POST'])
@login_required
def update_call_settings():
    bid = session['business_id']
    max_tokens = int(request.form.get('max_tokens', 200))
    silence_timeout = int(request.form.get('silence_timeout', 10))
    max_duration = int(request.form.get('max_duration', 300))
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE businesses SET max_tokens=?, silence_timeout=?, max_duration_seconds=? WHERE id=?",
              (max_tokens, silence_timeout, max_duration, bid))
    db.commit()
    
    # Update VAPI assistant
    c.execute("SELECT vapi_assistant_id FROM businesses WHERE id=?", (bid,))
    biz = c.fetchone()
    if biz and biz['vapi_assistant_id']:
        subprocess.run(["curl","-s","-X","PATCH",f"{VAPI_BASE}/assistant/{biz['vapi_assistant_id']}",
            "-H",f"Authorization: Bearer {VAPI_API_KEY}",
            "-H","Content-Type: application/json",
            "-d",json.dumps({
                "model": {"provider": "xai", "model": "grok-4.3", "maxTokens": max_tokens},
                "silenceTimeoutSeconds": silence_timeout,
                "maxDurationSeconds": max_duration,
            })], capture_output=True, text=True)
    
    flash('✅ Call settings saved!', 'success')
    return redirect('/?tab=settings')

@app.route('/update-voicemail', methods=['POST'])
@login_required
def update_voicemail():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE businesses SET voicemail_greeting = ? WHERE id = ?",
        (request.form.get('voicemail_greeting',''), bid))
    db.commit()
    flash('✅ Voicemail greeting saved!', 'success')
    return redirect('/?tab=forwarding')

@app.route('/update-hours', methods=['POST'])
@login_required
def update_hours():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE businesses SET call_window_start = ?, call_window_end = ? WHERE id = ?",
        (request.form.get('open_time','09:00'), request.form.get('close_time','17:00'), bid))
    db.commit()
    flash('✅ Business hours saved!', 'success')
    return redirect('/?tab=forwarding')

@app.route('/api/search-numbers')
@login_required
def api_search_numbers():
    """Search available phone numbers via Twilio."""
    area_code = request.args.get('area_code', '').strip()
    locality = request.args.get('locality', '').strip()
    region = request.args.get('region', '').strip()
    from twilio_helper import search_available_numbers
    nums, error = search_available_numbers(
        area_code=area_code if area_code else None,
        locality=locality if locality else None,
        region=region if region else None,
        limit=15)
    if error:
        return jsonify({'success': False, 'message': error})
    result = []
    for n in nums:
        result.append({
            'phone_number': n.get('phone_number', '?'),
            'friendly_name': n.get('friendly_name', n.get('phone_number', '?')),
            'locality': n.get('locality', ''),
            'region': n.get('region', ''),
            'postal_code': n.get('postal_code', ''),
            'rate_center': n.get('rate_center', ''),
            'capabilities': n.get('capabilities', {})
        })
    return jsonify({'success': True, 'numbers': result})

@app.route('/api/call/<call_id>/recording')
@login_required
def proxy_recording(call_id):
    """Proxy Vapi recording download through authenticated API endpoint.
    Vapi now requires auth for recordings - this fetches via the new endpoint.
    """
    import requests
    try:
        # Use the new authenticated endpoint (302 redirects to signed URL)
        resp = requests.get(
            f"https://api.vapi.ai/call/{call_id}/mono-recording",
            headers={"Authorization": f"Bearer {VAPI_API_KEY}"},
            timeout=15,
            allow_redirects=True
        )
        if resp.status_code == 200:
            return resp.content, 200, {
                'Content-Type': resp.headers.get('Content-Type', 'audio/mpeg'),
                'Content-Disposition': f'attachment; filename="call_{call_id[:12]}.mp3"'
            }
        return f"Recording not available (HTTP {resp.status_code})", 404
    except Exception as e:
        return f"Error fetching recording: {str(e)}", 500

@app.route('/buy-number', methods=['POST'])
@login_required
def buy_number():
    """Buy a phone number from Twilio and register with Vapi."""
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    
    # Check if they already have a number — allow buying another
    c.execute("SELECT *, number_paid, plan FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    
    if not biz or not biz['vapi_assistant_id']:
        return jsonify({'success': False, 'message': 'No AI assistant configured yet. Set up your assistant first.'})
    
    # Try to find an unassigned VAPI phone number first
    try:
        r = subprocess.run(["curl","-s",f"{VAPI_BASE}/phone-number",
            "-H",f"Authorization: Bearer {VAPI_API_KEY}"],
            capture_output=True, text=True, timeout=15)
        all_phones = json.loads(r.stdout)
        if isinstance(all_phones, list):
            for phone in all_phones:
                if not phone.get('assistantId') and phone.get('id'):
                    pid = phone['id']
                    pnumber = phone.get('number', '?')
                    c.execute("UPDATE businesses SET vapi_phone_id = ? WHERE id = ?", (pid, bid))
                    db.commit()
                    # Set inbound assistant
                    subprocess.run(["curl","-s","-X","PATCH",f"{VAPI_BASE}/phone-number/{pid}",
                        "-H",f"Authorization: Bearer {VAPI_API_KEY}",
                        "-H","Content-Type: application/json",
                        "-d",json.dumps({"assistantId": biz['vapi_assistant_id']})],
                        capture_output=True, text=True)
                    return jsonify({'success': True, 'message': f'✅ Assigned existing number {pnumber}!'})
    except:
        pass
    
    # Check payment status before buying - everyone pays
    biz_plan = biz['plan'] or ''
    number_paid = biz['number_paid'] or 0
    
    if not number_paid:
        # Redirect to Stripe checkout
        from premium_features import create_stripe_checkout
        from premium_features import load_stripe_config
        cfg = load_stripe_config()
        if not cfg.get('enabled'):
            return jsonify({'success': False, 'message': '💳 Stripe payments not configured. Contact admin.'})
        
        base = request.host_url.rstrip('/')
        customer_email = request.form.get('email', '').strip()
        checkout_url = create_stripe_checkout(
            business_id=bid,
            plan_name='Phone Number ($9.99/mo)',
            price_cents=999,
            email=customer_email or None,
            success_url=f'{base}/?tab=numbers&purchased=1',
            cancel_url=f'{base}/?tab=numbers&purchased=cancelled'
        )
        if checkout_url:
            return jsonify({'success': True, 'checkout_url': checkout_url, 'requires_payment': True,
                           'message': '💳 Please complete payment ($9.99/mo) to buy this number.'})
        return jsonify({'success': False, 'message': '❌ Could not create payment session. Try again.'})
    
    # Payment verified or admin — proceed to buy
    from twilio_helper import buy_twilio_number, register_with_vapi
    phone_number = request.form.get('phone_number', '').strip()
    area_code = request.form.get('area_code', '')
    
    if phone_number:
        # Buy specific number from search
        twilio_result, error = buy_twilio_number(phone_number)
        if error:
            return jsonify({'success': False, 'message': f'Twilio purchase failed: {error}'})
        # Register with Vapi
        vapi_result, error = register_with_vapi(phone_number, biz['vapi_assistant_id'])
        if error:
            return jsonify({'success': True, 'message': f'✅ Bought {phone_number} but Vapi registration failed: {error}'})
        phone_id = vapi_result.get('id', '')
        c.execute("UPDATE businesses SET vapi_phone_id = ? WHERE id = ?", (phone_id, bid))
        db.commit()
        return jsonify({'success': True, 'message': f'✅ {phone_number} bought & assigned!'})
    else:
        # Legacy: search and buy first available
        from twilio_helper import buy_and_assign_number
        phone_id, phone_number, error = buy_and_assign_number(biz['vapi_assistant_id'], area_code or None)
        if phone_id:
            c.execute("UPDATE businesses SET vapi_phone_id = ? WHERE id = ?", (phone_id, bid))
            db.commit()
            return jsonify({'success': True, 'message': f'✅ New number {phone_number} bought & assigned!'})
        else:
            return jsonify({'success': False, 'message': f'❌ Could not buy number: {error}'})

def load_twilio_config():
    """Load Twilio config from JSON file."""
    try:
        with open('/root/voice-agent-manager/twilio_config.json') as f:
            return json.load(f)
    except:
        return {}

# ── Two-Way SMS Inbox ──

def init_messages_table():
    """Create messages table if it doesn't exist."""
    db = get_db()
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            from_number TEXT NOT NULL,
            to_number TEXT NOT NULL,
            body TEXT NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('inbound','outbound')),
            status TEXT DEFAULT 'delivered',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_messages_biz ON messages(business_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
    db.commit()
    db.close()

@app.route('/api/messages')
@login_required
def api_messages_list():
    """List conversation threads for this business."""
    bid = session['business_id']
    init_messages_table()
    db = get_db()
    c = db.cursor()
    
    # Get all distinct threads with latest message preview, unread count, timestamp
    c.execute("""
        SELECT 
            m.thread_id,
            (CASE WHEN m.direction = 'inbound' THEN m.from_number ELSE m.to_number END) as contact_number,
            m.body as last_message,
            m.created_at as last_time,
            m.direction as last_direction,
            (SELECT COUNT(*) FROM messages m2 
             WHERE m2.thread_id = m.thread_id 
             AND m2.business_id = m.business_id 
             AND m2.direction = 'inbound' 
             AND m2.status = 'unread') as unread_count
        FROM messages m
        WHERE m.business_id = ?
        AND m.id IN (
            SELECT MAX(id) FROM messages 
            WHERE business_id = ? 
            GROUP BY thread_id
        )
        ORDER BY m.created_at DESC
    """, (bid, bid))
    
    threads = []
    for row in c.fetchall():
        threads.append({
            'thread_id': row['thread_id'],
            'contact_number': row['contact_number'],
            'last_message': row['last_message'][:80] + ('...' if len(row['last_message']) > 80 else ''),
            'last_time': row['last_time'],
            'unread_count': row['unread_count'],
            'last_direction': row['last_direction']
        })
    
    db.close()
    return jsonify({'threads': threads})

@app.route('/api/messages/<thread_id>')
@login_required
def api_messages_thread(thread_id):
    """Get all messages in a conversation thread."""
    bid = session['business_id']
    init_messages_table()
    db = get_db()
    c = db.cursor()
    
    c.execute("""
        SELECT * FROM messages 
        WHERE business_id = ? AND thread_id = ?
        ORDER BY created_at ASC
    """, (bid, thread_id))
    
    messages = []
    for row in c.fetchall():
        messages.append({
            'id': row['id'],
            'from_number': row['from_number'],
            'to_number': row['to_number'],
            'body': row['body'],
            'direction': row['direction'],
            'status': row['status'],
            'created_at': row['created_at']
        })
    
    # Get contact info
    contact_number = None
    if messages:
        m = messages[0]
        contact_number = m['from_number'] if m['direction'] == 'inbound' else m['to_number']
    
    # Mark inbound messages as read
    c.execute("""
        UPDATE messages SET status = 'read' 
        WHERE business_id = ? AND thread_id = ? AND direction = 'inbound' AND status = 'unread'
    """, (bid, thread_id))
    db.commit()
    db.close()
    
    return jsonify({
        'messages': messages,
        'contact_number': contact_number
    })

@app.route('/api/messages/send', methods=['POST'])
@login_required
def api_messages_send():
    """Send an SMS reply via Twilio."""
    bid = session['business_id']
    data = request.get_json(silent=True) or {}
    thread_id = data.get('thread_id', '')
    to_number = data.get('to_number', '')
    body = data.get('body', '').strip()
    
    if not to_number or not body:
        return jsonify({'success': False, 'error': 'Phone number and message body required'}), 400
    if not thread_id:
        thread_id = f"t_{bid}_{int(time.time())}"
    
    init_messages_table()
    
    # Send via sms-gate.app (primary SMS provider)
    try:
        from smsgate_sms import send_sms as smsgate_send
        ok = smsgate_send(to_number, body, business_id=bid)
        if not ok:
            return jsonify({'success': False, 'error': 'sms-gate.app send failed'}), 500
        from_number = "sms-gate"
        
        # Store outbound message
        db = get_db()
        c = db.cursor()
        c.execute("""
            INSERT INTO messages (business_id, thread_id, from_number, to_number, body, direction, status)
            VALUES (?, ?, ?, ?, ?, 'outbound', 'delivered')
        """, (bid, thread_id, from_number, to_number, body))
        db.commit()
        msg_id = c.lastrowid
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'SMS sent!',
            'msg_id': msg_id,
            'thread_id': thread_id,
            'provider': 'sms-gate'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'sms-gate error: {str(e)}'}), 500

@app.route('/api/messages/webhook', methods=['POST'])
def api_messages_webhook():
    """Twilio webhook endpoint for incoming SMS — routes to the same AI reply
    engine as sms-gate (business match by to_number -> run_in_background)."""
    # Twilio sends form-encoded data
    from_number = request.form.get('From', '').strip()
    to_number = request.form.get('To', '').strip()
    body = request.form.get('Body', '').strip()
    message_sid = request.form.get('MessageSid', '').strip()

    if not from_number or not body:
        return '<Response></Response>', 200

    init_messages_table()
    db = get_db()
    db.row_factory = sqlite3.Row
    c = db.cursor()

    # Match business by the number the customer texted (to_number).
    biz_id = None
    if to_number:
        c.execute("SELECT id FROM businesses WHERE phone_number = ? OR vapi_phone_id = ? LIMIT 1",
                  (to_number, to_number))
        row = c.fetchone()
        if row:
            biz_id = row['id']
    # Fallback: reply-matching via outgoing_sms (same as sms-gate path)
    if not biz_id and from_number:
        c.execute("""SELECT business_id FROM outgoing_sms 
                     WHERE phone = ? AND business_id IS NOT NULL
                     ORDER BY sent_at DESC LIMIT 1""", (from_number,))
        row = c.fetchone()
        if row:
            biz_id = row['business_id']
    # Last resort: only business
    if not biz_id:
        c.execute("SELECT id FROM businesses LIMIT 1")
        row = c.fetchone()
        if row:
            biz_id = row['id']
    if not biz_id:
        db.close()
        return '<Response></Response>', 200

    # Store in incoming_sms (same table the inbox + AI engine read)
    try:
        import hashlib as _smh
        msg_id = message_sid or f"twilio_{_smh.md5((from_number + body).encode()).hexdigest()[:12]}"
        c.execute("""INSERT OR IGNORE INTO incoming_sms 
                     (id, business_id, sender, recipient, body, msg_type, received_at)
                     VALUES (?, ?, ?, ?, ?, 'SMS', ?)""",
                  (msg_id, biz_id, from_number, to_number, body,
                   datetime.now().isoformat()))
        db.commit()
    except Exception as _se:
        print(f"⚠️ Twilio webhook store error: {_se}")
    db.close()

    # AI SMS reply (same engine as sms-gate)
    if body:
        try:
            from ai_sms_reply import run_in_background
            run_in_background(biz_id, from_number, body, None)
        except Exception as ai_e:
            print(f"⚠️ Twilio AI SMS trigger error: {ai_e}")
    return '<Response></Response>', 200

@app.route('/api/messages/mark-read', methods=['POST'])
@login_required
def api_messages_mark_read():
    """Mark all inbound messages in a thread as read."""
    bid = session['business_id']
    data = request.get_json(silent=True) or {}
    thread_id = data.get('thread_id', '')
    
    if not thread_id:
        return jsonify({'success': False, 'error': 'thread_id required'}), 400
    
    init_messages_table()
    db = get_db()
    c = db.cursor()
    c.execute("""
        UPDATE messages SET status = 'read' 
        WHERE business_id = ? AND thread_id = ? AND direction = 'inbound' AND status = 'unread'
    """, (bid, thread_id))
    db.commit()
    db.close()
    
    return jsonify({'success': True})

@app.route('/update-sms-settings', methods=['POST'])
@login_required
def update_sms_settings():
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("""UPDATE businesses SET 
        sms_after_call = ?, sms_reminders = ?, sms_missed = ?
        WHERE id = ?""", (
        '1' if request.form.get('sms_after_call') else '0',
        '1' if request.form.get('sms_reminders') else '0',
        '1' if request.form.get('sms_missed') else '0',
        bid
    ))
    db.commit()
    flash('✅ SMS settings saved!', 'success')
    return redirect('/?tab=calendar')


@app.route('/api/send-appointment-email', methods=['POST'])
@login_required
def api_send_appointment_email():
    """Manually send appointment confirmation email with .ics."""
    bid = session['business_id']
    data = request.get_json(silent=True) or {}
    appt_id = data.get('appointment_id')
    
    if not appt_id:
        return jsonify({'success': False, 'error': 'appointment_id required'}), 400
    
    db = get_db()
    c = db.cursor()
    c.execute("""
        SELECT a.*, l.email, l.name as lead_name, b.name as biz_name
        FROM appointments a
        LEFT JOIN leads l ON a.lead_id = l.id
        JOIN businesses b ON a.business_id = b.id
        WHERE a.id = ? AND a.business_id = ?
    """, (appt_id, bid))
    appt = c.fetchone()
    db.close()
    
    if not appt:
        return jsonify({'success': False, 'error': 'Appointment not found'}), 404
    
    if not appt['email']:
        return jsonify({'success': False, 'error': 'No email address for this lead'}), 400
    
    try:
        appt_dict = dict(appt)
        msg_id, thread_id = send_appointment_confirmation(
            to=appt_dict['email'],
            prospect_name=appt_dict.get('lead_name') or appt_dict.get('prospect_name') or 'there',
            business_name=appt_dict['biz_name'],
            appointment_time=appt_dict.get('appointment_time') or ''
        )
        return jsonify({'success': True, 'message_id': msg_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/send-appointment-email/<bid>/<appt_id>', methods=['POST'])
@admin_required
def admin_send_appointment_email(bid, appt_id):
    """Admin endpoint to send appointment confirmation email."""
    db = get_db()
    c = db.cursor()
    c.execute("""
        SELECT a.*, l.email, l.name as lead_name, b.name as biz_name
        FROM appointments a
        LEFT JOIN leads l ON a.lead_id = l.id
        JOIN businesses b ON a.business_id = b.id
        WHERE a.id = ? AND a.business_id = ?
    """, (appt_id, bid))
    appt = c.fetchone()
    db.close()
    
    if not appt:
        return jsonify({'success': False, 'error': 'Appointment not found'}), 404
    
    if not appt['email']:
        return jsonify({'success': False, 'error': 'No email address'}), 400
    
    try:
        appt_dict = dict(appt)
        msg_id, thread_id = send_appointment_confirmation(
            to=appt_dict['email'],
            prospect_name=appt_dict.get('lead_name') or appt_dict.get('prospect_name') or 'there',
            business_name=appt_dict['biz_name'],
            appointment_time=appt_dict.get('appointment_time') or ''
        )
        return jsonify({'success': True, 'message_id': msg_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/calendar/download/<call_log_id>')
@login_required
def download_calendar(call_log_id):
    """Download .ics calendar file for an appointment."""
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("""
        SELECT cl.*, l.name as prospect_name, b.name as biz_name
        FROM call_log cl
        LEFT JOIN leads l ON cl.lead_id = l.id
        JOIN businesses b ON cl.business_id = b.id
        WHERE cl.id = ? AND cl.business_id = ?
    """, (call_log_id, bid))
    row = c.fetchone()
    if not row:
        flash('Appointment not found', 'error')
        return redirect('/?tab=calendar')
    
    # Generate ICS
    from calendar_sms import generate_ics
    ics = generate_ics(
        row['appointment_time'] or datetime.now().isoformat(),
        row['biz_name'],
        row['prospect_name'] or 'Prospect'
    )
    
    from flask import Response
    return Response(
        ics,
        mimetype='text/calendar',
        headers={'Content-Disposition': f'attachment; filename=appointment_{call_log_id[:8]}.ics'}
    )

@app.route('/api/appointment/notes', methods=['POST'])
@login_required
def appointment_save_notes():
    """Save/update notes on a booked appointment."""
    bid = session['business_id']
    data = request.get_json(silent=True) or {}
    apt_id = (data.get('id') or '').strip()
    notes = (data.get('notes') or '').strip()[:2000]
    if not apt_id:
        return jsonify({'success': False, 'message': 'Missing appointment id'})
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE appointments SET notes=? WHERE id=? AND business_id=?", (notes, apt_id, bid))
    db.commit()
    if c.rowcount == 0:
        return jsonify({'success': False, 'message': 'Appointment not found'})
    return jsonify({'success': True, 'message': '✅ Notes saved', 'notes': notes})

@app.route('/api/analytics')
@login_required
def api_analytics():
    """JSON endpoint for analytics charts."""
    from premium_features import get_chart_data
    bid = session['business_id']
    return jsonify(get_chart_data(bid))

@app.route('/api/script-optimizer')
@login_required
def api_script_optimizer():
    from premium_features2 import analyze_script_performance
    bid = session['business_id']
    return jsonify(analyze_script_performance(bid))

@app.route('/api/call-status')
@login_required
def api_call_status():
    """Real-time call status polling."""
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT COUNT(*) FROM call_log WHERE business_id=? AND date(created_at)=?", (bid, today))
    recent = c.fetchone()[0]
    c.execute("SELECT created_at, outcome FROM call_log WHERE business_id=? ORDER BY created_at DESC LIMIT 1", (bid,))
    last = c.fetchone()
    c.execute("SELECT COUNT(*) FROM call_log WHERE business_id=? AND created_at > datetime('now', '-5 minutes')", (bid,))
    active = c.fetchone()[0] > 0
    db.close()
    return jsonify({
        'active_call': active,
        'started_at': '',
        'duration': 0,
        'recent_calls': recent,
        'last_call': f"{last['outcome']} at {last['created_at'][11:16]}" if last else None
    })

@app.route('/api/campaign-logs')
@login_required
def api_campaign_logs():
    """Return campaign live logs as JSON for auto-refresh."""
    bid = session['business_id']
    since = request.args.get('since', '0')
    db = get_db()
    c = db.cursor()
    if since and since.isdigit():
        c.execute("SELECT id, message, level, created_at FROM campaign_log WHERE business_id=? AND id > ? ORDER BY id ASC", (bid, int(since)))
    else:
        c.execute("SELECT id, message, level, created_at FROM campaign_log WHERE business_id=? ORDER BY id DESC LIMIT 50", (bid,))
    logs = [{'id': r[0], 'msg': r[1], 'level': r[2], 'time': r[3][11:19]} for r in c.fetchall()]
    if not since or since == '0':
        logs.reverse()
    db.close()
    return jsonify({'logs': logs})

@app.route('/api/update-followup', methods=['POST'])
@login_required
def api_update_followup():
    bid = session['business_id']
    enabled = '1' if request.json.get('enabled') else '0'
    db = get_db(); c = db.cursor()
    c.execute("UPDATE businesses SET followup_enabled=? WHERE id=?", (enabled, bid))
    db.commit()
    return jsonify({'saved': True})

@app.route('/api/stripe-checkout', methods=['POST'])
@login_required
def api_stripe_checkout():
    """Create Stripe checkout session."""
    from premium_features import create_stripe_checkout, load_stripe_config
    cfg = load_stripe_config()
    if not cfg.get('enabled'):
        return jsonify({'error': 'Stripe not configured. Contact admin.'}), 400
    
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("SELECT plan, monthly_price, email, name FROM businesses WHERE id=?", (bid,))
    biz = c.fetchone()
    if not biz:
        return jsonify({'error': 'Business not found'}), 404
    
    price_cents = int((biz['monthly_price'] or 197) * 100)
    base = request.host_url.rstrip('/')
    url = create_stripe_checkout(bid, biz['plan'] or 'pro', price_cents, biz['email'] or '',
        f"{base}/?tab=billing&stripe=success", f"{base}/?tab=billing&stripe=cancel")
    
    if url:
        return jsonify({'url': url})
    return jsonify({'error': 'Stripe checkout failed'}), 500


@app.route('/api/buy-minutes', methods=['POST'])
@login_required
def api_buy_minutes():
    """Buy extra minutes — creates a Stripe one-time checkout for payment."""
    data = request.get_json(silent=True) or {}
    minutes = int(data.get('minutes', 0))
    
    if minutes <= 0:
        return jsonify({'success': False, 'error': 'Invalid minutes'}), 400
    
    # Price maps
    price_cents = PRICES.get(minutes)
    if not price_cents:
        return jsonify({'success': False, 'error': 'Invalid minute package'}), 400
    
    bid = session['business_id']
    db = get_db()
    c = db.cursor()
    c.execute("SELECT email, name FROM businesses WHERE id=?", (bid,))
    biz = c.fetchone()
    db.close()
    
    if not biz:
        return jsonify({'success': False, 'error': 'Business not found'}), 404
    
    email = biz['email'] or ''
    base = request.host_url.rstrip('/')
    success_url = f"{base}/?tab=billing&stripe=success&minutes={minutes}"
    cancel_url = f"{base}/?tab=billing&stripe=cancel"
    
    from premium_features import create_extra_minutes_checkout
    checkout_url = create_extra_minutes_checkout(
        bid, minutes, price_cents, email, success_url, cancel_url
    )
    
    if checkout_url:
        return jsonify({'success': True, 'checkout_url': checkout_url})
    
    return jsonify({'success': False, 'error': 'Failed to create payment checkout. Try again later.'}), 500

@app.route('/clone-voice', methods=['POST'])
@login_required
def clone_voice():
    """Upload audio file and clone voice via ElevenLabs."""
    bid = session['business_id']
    if 'audio' not in request.files:
        flash('No audio file selected', 'error')
        return redirect('/?tab=settings')
    
    audio = request.files['audio']
    voice_name = request.form.get('voice_name', 'My Voice')
    
    if audio.filename == '':
        flash('No audio file selected', 'error')
        return redirect('/?tab=settings')
    
    # Save temp file
    ext = os.path.splitext(audio.filename)[1] or '.mp3'
    tmp_path = f"/tmp/clone_{bid}{ext}"
    audio.save(tmp_path)
    
    # Clone via ElevenLabs
    from premium_features import clone_voice_from_file
    voice_id = clone_voice_from_file(tmp_path, voice_name, bid)
    os.remove(tmp_path)
    
    if voice_id:
        # Update DB with cloned voice
        db = get_db()
        c = db.cursor()
        c.execute("UPDATE businesses SET voice_id = ? WHERE id = ?", (voice_id, bid))
        db.commit()
        flash(f'✅ Voice "{voice_name}" cloned! Using it now.', 'success')
    else:
        flash('❌ Voice cloning failed. Make sure ELEVENLABS_API_KEY is set.', 'error')
    
    return redirect('/?tab=settings')

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events (subscription payments)."""
    from premium_features import handle_stripe_webhook
    payload = request.get_data()
    sig = request.headers.get('Stripe-Signature', '')
    result = handle_stripe_webhook(payload, sig)
    if result:
        return jsonify({'received': True})
    return jsonify({'received': False}), 200

# ── INDUSTRY PRESETS ──
# These are short business context descriptions used with the Diazites voice framework.
# The framework handles personality, conversation rules, and tone automatically.
INDUSTRY_PRESETS = {
    "plumber": "We are a 24/7 emergency plumbing company. We handle burst pipes, water heater failures, drain cleaning, and general plumbing repairs. Same-day service available.",
    "dentist": "We are a dental practice offering cleanings, fillings, crowns, whitening, and emergency dentistry. New patients welcome. Most insurance accepted.",
    "hvac": "We are an HVAC company handling AC repair, furnace service, heat pump installation, and emergency heating/cooling calls. Serving residential and commercial customers.",
    "roofer": "We are a roofing company offering roof inspections, repairs, replacements, and storm damage restoration. Free estimates for all services.",
    "lawyer": "We are a law firm offering consultations for personal injury, family law, criminal defense, and business law. Free initial case review available.",
    "real_estate": "We are a real estate agency helping buyers find their dream home and sellers get top dollar. We also offer property management and home valuation services.",
    "auto_mechanic": "We are an auto repair shop offering diagnostics, oil changes, brake repair, engine work, transmission service, and vehicle inspections. All makes and models.",
    "cleaning": "We offer residential and commercial cleaning services including deep cleaning, move-in/move-out, recurring weekly/biweekly, and office cleaning.",
    "pest_control": "We are a pest control company handling termites, rodents, roaches, ants, bed bugs, and wildlife removal. Free inspections and same-day service available.",
    "landscaper": "We offer lawn mowing, landscaping design, tree trimming, mulch installation, irrigation systems, and seasonal yard clean-up services.",
    "solar": "We help homeowners switch to solar energy with affordable installation, financing options, and full warranty coverage. Free solar consultation and quote.",
    "health_insurance": "We help individuals, families, and small businesses find affordable health insurance plans including ACA, Medicare, Medicaid, and short-term coverage.",
    "general": "We offer quality products and services to our local community. Customer satisfaction is our top priority. Call us to learn more about what we offer."
}

@app.route('/load-preset', methods=['POST'])
@login_required
def load_preset():
    bid = session['business_id']
    preset = request.form.get('preset_industry', 'general')
    script = INDUSTRY_PRESETS.get(preset, INDUSTRY_PRESETS['general'])
    
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE businesses SET script_template = ?, industry = ? WHERE id = ?",
        (script, preset, bid))
    db.commit()
    flash(f'✅ {preset.replace("_"," ").title()} preset loaded! Customize your script in the script editor.', 'success')
    return redirect('/?tab=assistant')

@app.route('/test-call', methods=['POST'])
@login_required
def test_call():
    bid = session['business_id']
    phone = request.form.get('phone', '').strip()
    if not phone:
        flash('Phone number required', 'error')
        return redirect('/?tab=assistant')
    
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM businesses WHERE id = ?", (bid,))
    biz = c.fetchone()
    if not biz or not biz['vapi_assistant_id'] or not biz['vapi_phone_id']:
        flash('❌ AI agent not fully configured yet. Set up phone number first.', 'error')
        return redirect('/?tab=assistant')
    phone = request.form.get('phone', '').strip()
    
    try:
        r = subprocess.run(["curl","-s","-X","POST",f"{VAPI_BASE}/call",
            "-H",f"Authorization: Bearer {VAPI_API_KEY}",
            "-H","Content-Type: application/json",
            "-d",json.dumps({
                "assistantId": biz['vapi_assistant_id'],
                "phoneNumberId": biz['vapi_phone_id'],
                "customer": {"number": phone},
                "assistantOverrides": {
                    "variableValues": {
                        "business_name": biz['name'],
                        "industry": biz['industry'] or '',
                        "prospect_business": "test call"
                    }
                }
            })], capture_output=True, text=True, timeout=30)
        call_data = json.loads(r.stdout)
        call_id = call_data.get('id', '')
        if call_id:
            flash(f'📞 Test call placed! Check your phone in 10 seconds.', 'success')
        else:
            flash(f'❌ Call failed: {call_data.get("message","unknown error")}', 'error')
    except Exception as e:
        flash(f'❌ Call failed: {str(e)}', 'error')
    
    return redirect('/?tab=assistant')

# ── SCHEDULER THREAD ──
def campaign_scheduler():
    """Background thread that checks every 60 seconds for scheduled campaigns to start."""
    while True:
        try:
            db = sqlite3.connect(DB_PATH)
            c = db.cursor()
            c.execute("""
                SELECT c.business_id, c.schedule_time, c.schedule_days, c.timezone, b.vapi_assistant_id, b.vapi_phone_id
                FROM campaigns c JOIN businesses b ON c.business_id = b.id
                WHERE c.status IN ('idle','completed') AND c.schedule_enabled = 1
            """)
            now = datetime.now()
            current_day = now.strftime('%a').lower()[:3]  # mon, tue, etc.
            current_time = now.strftime('%H:%M')
            
            for row in c.fetchall():
                biz_id, sched_time, days_str, tz, asst_id, phone_id = row
                if not asst_id or not phone_id:
                    continue
                days = days_str.split(',') if days_str else []
                if current_day not in days:
                    continue
                if sched_time and sched_time <= current_time <= (datetime.strptime(sched_time, '%H:%M') + timedelta(minutes=5)).strftime('%H:%M'):
                    # Time to start!
                    c.execute("SELECT COUNT(*) FROM leads WHERE business_id=? AND state='NEW'", (biz_id,))
                    if c.fetchone()[0] > 0:
                        c.execute("UPDATE campaigns SET status='running', started_at=datetime('now') WHERE business_id=?", (biz_id,))
                        db.commit()
                        threading.Thread(target=run_campaign_bg, args=(biz_id,), daemon=True).start()
            db.close()
        except Exception as e:
            print(f"Campaign scheduler error: {e}")
        time.sleep(60)

# Start scheduler in background
# ── AI PRODUCT FACTORY ──

def product_type_icon(ptype):
    icons = {
        'prompt_pack': '🤖', 'template': '📋', 'ebook': '📚',
        'checklist': '✅', 'business_doc': '📄', 'marketing': '📢',
        'code': '💻', 'starter': '🚀'
    }
    return icons.get(ptype, '📦')

PRODUCT_TYPE_LABELS = {
    'prompt_pack': 'Prompt Pack', 'template': 'Template', 'ebook': 'eBook',
    'checklist': 'Checklist', 'business_doc': 'Document', 'marketing': 'Marketing Assets',
    'code': 'Code Snippet', 'starter': 'Starter Kit'
}

@app.route('/api/ai-factory/generate', methods=['POST'])
@login_required
def api_generate_product():
    """Generate a digital product using AI."""
    try:
        data = request.get_json() or {}
        ptype = data.get('product_type', 'prompt_pack')
        topic = data.get('topic', '').strip()
        price = float(data.get('price', 9.99))
        brief = data.get('brief', '')
        
        if not topic:
            return jsonify({'success': False, 'error': 'Topic is required'}), 400
        
        # Build AI prompt based on product type
        type_labels = PRODUCT_TYPE_LABELS
        type_label = type_labels.get(ptype, 'Digital Product')
        
        prompt = f"""You are an AI product creator. Generate a complete digital product with the following details:

Product Type: {type_label}
Topic: {topic}
Additional Details: {brief}

Generate a JSON response with these exact fields:
- title: A compelling, SEO-friendly product title (max 80 chars)
- description: A detailed 2-3 sentence product description
- content: The FULL product content. For prompt packs, list 10+ individual prompts. For templates, create a complete template structure. For eBooks, write chapter outlines + intro. For checklists, list 15+ items. Be thorough and valuable.
- seo_title: SEO-optimized title (max 60 chars)
- seo_description: SEO meta description (max 160 chars)
- seo_keywords: 5-7 comma-separated keywords
- category: one of: prompt-packs, templates, ebooks, business, code, marketing

Respond ONLY with valid JSON, no other text."""
        
        # Call AI via the chatbot config
        cfg = get_chatbot_config()
        provider_name = cfg.get('chatbot_provider', 'deepseek')
        api_key = cfg.get('chatbot_api_key', '')
        
        if not api_key:
            api_key = os.environ.get('DEEPSEEK_API_KEY', '')
        
        provider = CHATBOT_PROVIDERS.get(provider_name, CHATBOT_PROVIDERS['deepseek'])
        model = cfg.get('chatbot_model', provider['default_model'])
        
        import urllib.request, json as json_module
        
        payload = json_module.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 4000
        })
        
        req = urllib.request.Request(
            provider['api_url'],
            data=payload.encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': provider['auth_header'](api_key)
            }
        )
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json_module.loads(resp.read().decode())
        
        ai_text = result['choices'][0]['message']['content']
        
        # Extract JSON from response
        import re as json_re
        json_match = json_re.search(r'\{.*\}', ai_text, json_re.DOTALL)
        if not json_match:
            return jsonify({'success': False, 'error': 'AI returned invalid format'}), 500
        
        product_data = json_module.loads(json_match.group())
        
        # Save to DB
        import uuid
        pid = str(uuid.uuid4())[:12]
        db = get_db()
        c = db.cursor()
        
        c.execute("""INSERT INTO products 
            (id, title, description, price, category, tags, product_type, content,
             creator_id, creator_name, status, seo_title, seo_description, seo_keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)""",
            (pid, product_data.get('title', topic)[:200],
             product_data.get('description', '')[:500],
             price, product_data.get('category', 'prompt-packs'),
             product_data.get('seo_keywords', ''), ptype,
             product_data.get('content', ''),
             session.get('business_id', 'factory'),
             session.get('biz_name', 'AI Factory'),
             product_data.get('seo_title', '')[:200],
             product_data.get('seo_description', '')[:300],
             product_data.get('seo_keywords', '')))
        db.commit()
        db.close()
        
        return jsonify({'success': True, 'product_id': pid, 'title': product_data.get('title', topic)})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)[:200]}), 500

@app.route('/api/ai-factory/publish/<product_id>', methods=['POST'])
@login_required
def api_publish_product(product_id):
    """Publish a product to the store."""
    try:
        db = get_db()
        c = db.cursor()
        c.execute("UPDATE products SET status='published', published_at=datetime('now') WHERE id=?", (product_id,))
        db.commit()
        db.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/store')
def public_store():
    """Public storefront listing all published products."""
    db = get_db()
    c = db.cursor()
    category = request.args.get('category', '')
    search = request.args.get('q', '')
    
    if category:
        c.execute("SELECT * FROM products WHERE status='published' AND category=? ORDER BY created_at DESC", (category,))
    elif search:
        c.execute("SELECT * FROM products WHERE status='published' AND (title LIKE ? OR description LIKE ? OR tags LIKE ?) ORDER BY created_at DESC",
                 (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        c.execute("SELECT * FROM products WHERE status='published' ORDER BY created_at DESC")
    
    products = [dict(r) for r in c.fetchall()]
    c.execute("SELECT * FROM product_categories ORDER BY product_count DESC")
    categories = [dict(r) for r in c.fetchall()]
    db.close()
    
    
    # Build the complete HTML safely (no f-string backslash issues)
    all_link = '<a href="/store" class="px-4 py-2 rounded-full text-xs bg-[#a855f7]/20 text-[#c084fc] border border-[#252533] transition">All</a>' if not category else '<a href="/store" class="px-4 py-2 rounded-full text-xs bg-[#1a1a26] text-[#7a7a8e] hover:text-white border border-[#252533] transition">All</a>'
    
    cat_links = ''
    for cat in categories:
        cid = cat['id']
        cname = cat['name']
        cicon = cat['icon']
        active = 'bg-[#a855f7]/20 text-[#c084fc]' if category == cid else 'bg-[#1a1a26] text-[#7a7a8e] hover:text-white'
        cat_links += '<a href="/store?category=' + cid + '" class="px-4 py-2 rounded-full text-xs ' + active + ' border border-[#252533] transition">' + cicon + ' ' + cname + '</a>'
    
    prod_cards = ''
    for p in products:
        icon = product_type_icon(p['product_type'])
        pid = p['id']
        ptitle = p['title'][:60] if p['title'] else ''
        pdesc = (p['description'] or '')[:100]
        pprice = p['price']
        pdl = p['downloads_count']
        prod_cards += '<a href="/product/' + pid + '" class="card hover:border-[#a855f7] transition block group">'
        prod_cards += '<span class="text-3xl block mb-2">' + icon + '</span>'
        prod_cards += '<h3 class="font-semibold mb-1 group-hover:text-[#c084fc] transition">' + ptitle + '</h3>'
        prod_cards += '<p class="text-xs text-[#7a7a8e] mb-3 line-clamp-2">' + pdesc + '</p>'
        prod_cards += '<div class="flex items-center justify-between"><span class="text-lg font-bold text-[#a855f7]">$' + f'{pprice:.2f}' + '</span><span class="text-xs text-[#5c5c70]">⬇️ ' + str(pdl) + '</span></div></a>'
    
    no_products = '<div class="col-span-3 text-center py-16 text-[#5c5c70]"><i class="fas fa-box-open text-5xl mb-3"></i><p>No products yet. Coming soon!</p></div>'
    
    if not prod_cards:
        prod_cards = no_products
    if not cat_links:
        cat_links = ''
    
    html = '''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Digital Product Store — Diazites</title>
<meta name="description" content="Browse our marketplace of AI-generated digital products — prompt packs, templates, eBooks, and more.">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
*{font-family:Inter,sans-serif}body{background:#07070c;color:#f1f1f5}
.card{background:#0e0e16;border:1px solid #1e1e2e;border-radius:16px;padding:24px;}
.gradient-text{background:linear-gradient(135deg,#c084fc,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.btn-primary{background:linear-gradient(135deg,#a855f7,#ec4899);color:white;padding:12px 24px;border-radius:12px;font-weight:600;border:none;cursor:pointer;transition:all .3s;display:inline-flex;align-items:center;gap:8px;text-decoration:none;font-size:14px;}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(168,85,247,0.3);}
input,select{background:#0e0e16;border:1px solid #1e1e2e;border-radius:10px;padding:12px 16px;color:#f1f1f5;outline:none;font-size:14px;transition:border-color .2s;}
input:focus{border-color:#a855f7;box-shadow:0 0 0 3px rgba(168,85,247,0.15);}
</style></head>
<body class="min-h-screen">
<div class="max-w-6xl mx-auto p-4 sm:p-6">
  <nav class="flex items-center justify-between mb-8">
    <a href="/store" class="flex items-center gap-3"><div class="w-9 h-9 rounded-xl bg-gradient-to-br from-[#a855f7] to-[#ec4899] flex items-center justify-center text-white font-bold text-sm">D</div><span class="font-bold text-lg">Diazites Store</span></a>
    <div class="flex gap-3 text-sm">
      <a href="/store" class="text-[#7a7a8e] hover:text-white transition">Products</a>
    </div>
  </nav>

  <div class="text-center mb-10">
    <h1 class="text-4xl font-bold gradient-text mb-3">Digital Products Marketplace</h1>
    <p class="text-[#7a7a8e] max-w-lg mx-auto">AI-crafted prompt packs, templates, eBooks, and tools to supercharge your workflow.</p>
    <form method="GET" action="/store" class="max-w-md mx-auto mt-6 flex gap-2">
      <input type="text" name="q" placeholder="Search products..." value="''' + search + '''" class="flex-1">
      <button type="submit" class="btn-primary"><i class="fas fa-search mr-1"></i> Search</button>
    </form>
  </div>

  <div class="flex gap-3 mb-8 flex-wrap">
    ''' + all_link + cat_links + '''
  </div>

  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
    ''' + prod_cards + '''
  </div>
</div>
</body></html>'''
    return render_template_string(html)

@app.route('/product/<product_id>')
def product_detail(product_id):
    """Product detail page."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM products WHERE id=? AND status='published'", (product_id,))
    p = c.fetchone()
    if not p:
        return "<h1>Not Found</h1>", 404
    
    p = dict(p)
    content_preview = (p['content'] or '')[:1000]
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{p['seo_title'] or p['title']} — Diazites Store</title>
<meta name="description" content="{p['seo_description'] or (p['description'] or '')[:150]}">
<meta name="keywords" content="{p['seo_keywords'] or ''}">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>*{{font-family:'Inter',sans-serif}}body{{background:#07070c;color:#f1f1f5;}}
.card{{background:#0e0e16;border:1px solid #1e1e2e;border-radius:16px;padding:24px;}}
.btn-primary{{background:linear-gradient(135deg,#a855f7,#ec4899);color:white;padding:14px 28px;border-radius:12px;font-weight:600;border:none;cursor:pointer;transition:all .3s;display:inline-flex;align-items:center;gap:8px;text-decoration:none;font-size:15px;}}
.btn-primary:hover{{transform:translateY(-2px);box-shadow:0 8px 30px rgba(168,85,247,0.3);}}
.btn-secondary{{background:rgba(255,255,255,0.06);border:1px solid #1e1e2e;color:#f1f1f5;padding:14px 28px;border-radius:12px;font-weight:600;cursor:pointer;transition:all .3s;text-decoration:none;font-size:15px;display:inline-flex;align-items:center;gap:8px;}}
.btn-secondary:hover{{background:rgba(255,255,255,0.1);}}
</style></head>
<body>
<div class="max-w-4xl mx-auto p-4 sm:p-6">
  <nav class="flex items-center justify-between mb-8">
    <a href="/store" class="flex items-center gap-3"><div class="w-9 h-9 rounded-xl bg-gradient-to-br from-[#a855f7] to-[#ec4899] flex items-center justify-center text-white font-bold text-sm">D</div><span class="font-bold text-lg">Diazites Store</span></a>
    <a href="/store" class="text-[#7a7a8e] hover:text-white text-sm transition"><i class="fas fa-arrow-left mr-1"></i> Back</a>
  </nav>
  
  <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
    <div class="lg:col-span-3">
      <div class="card mb-4">
        <span class="text-5xl block mb-4">{product_type_icon(p['product_type'])}</span>
        <h1 class="text-2xl font-bold mb-2">{p['title']}</h1>
        <p class="text-[#7a7a8e] mb-4">{p['description'] or ''}</p>
        <div class="flex flex-wrap gap-2 mb-4">
          <span class="text-xs bg-[#1e1e2e] px-3 py-1 rounded-full text-[#7a7a8e]">{PRODUCT_TYPE_LABELS.get(p['product_type'], 'Product')}</span>
          <span class="text-xs bg-[#1e1e2e] px-3 py-1 rounded-full text-[#7a7a8e]">⬇️ {p['downloads_count']} downloads</span>
        </div>
      </div>
      <div class="card">
        <h3 class="font-bold mb-3">📄 Content Preview</h3>
        <pre class="text-sm text-[#b0b0c0] whitespace-pre-wrap font-sans leading-relaxed">{content_preview}{'...' if len((p['content'] or '')) > 1000 else ''}</pre>
      </div>
    </div>
    
    <div class="lg:col-span-2">
      <div class="card sticky top-6">
        <div class="text-3xl font-bold text-[#a855f7] mb-4">${p['price']:.2f}</div>
        <button onclick="buyProduct()" id="buyBtn" class="btn-primary w-full justify-center mb-3"><i class="fas fa-shopping-cart mr-1"></i> Buy Now — Instant Download</button>
        <div id="buyStatus" class="text-xs text-center text-[#7a7a8e]"></div>
        <div class="mt-4 p-3 bg-[#0a0a12] rounded-lg text-xs text-[#5c5c70]">
          <p class="mb-1"><i class="fas fa-check text-green-400 mr-1"></i> Instant digital delivery</p>
          <p class="mb-1"><i class="fas fa-check text-green-400 mr-1"></i> Secure checkout via Stripe</p>
          <p><i class="fas fa-check text-green-400 mr-1"></i> Lifetime access</p>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
async function buyProduct() {{
  const btn = document.getElementById('buyBtn');
  btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Redirecting...';
  try {{
    const r = await fetch('/api/checkout/product/{p["id"]}', {{method:'POST'}});
    const d = await r.json();
    if (d.url) window.location.href = d.url;
    else {{ document.getElementById('buyStatus').textContent = '❌ ' + (d.error||'Failed'); btn.disabled=false; btn.innerHTML = '<i class=\"fas fa-shopping-cart mr-1\"></i> Buy Now'; }}
  }} catch(e) {{ document.getElementById('buyStatus').textContent = '❌ Error'; btn.disabled=false; btn.innerHTML = '<i class=\"fas fa-shopping-cart mr-1\"></i> Buy Now'; }}
}}
</script>
</body></html>"""
    return render_template_string(html)

@app.route('/api/checkout/product/<product_id>', methods=['POST'])
def api_checkout_product(product_id):
    """Create Stripe checkout for a product purchase."""
    try:
        from premium_features import load_stripe_config
        import stripe
        
        cfg = load_stripe_config()
        if not cfg.get('enabled'):
            return jsonify({'error': 'Payments not configured'}), 400
        
        stripe.api_key = cfg['secret_key']
        
        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM products WHERE id=?", (product_id,))
        p = c.fetchone()
        if not p:
            return jsonify({'error': 'Product not found'}), 404
        
        base = request.host_url.rstrip('/')
        import uuid
        token = str(uuid.uuid4())[:16]
        
        session_data = stripe.checkout.Session.create(
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': p['title'][:100], 'description': (p['description'] or '')[:200]},
                    'unit_amount': int(p['price'] * 100),
                },
                'quantity': 1,
            }],
            metadata={'product_id': product_id, 'download_token': token},
            success_url=f"{base}/download/{token}?success=1",
            cancel_url=f"{base}/product/{product_id}?canceled=1",
        )
        
        return jsonify({'url': session_data.url})
    except Exception as e:
        return jsonify({'error': str(e)[:200]}), 500

@app.route('/download/<token>')
def download_product(token):
    """Download page after successful purchase."""
    db = get_db()
    c = db.cursor()
    c.execute("SELECT po.*, p.title, p.content, p.product_type, p.price FROM product_orders po JOIN products p ON po.product_id = p.id WHERE po.download_token=?", (token,))
    order = c.fetchone()
    
    success = request.args.get('success', '')
    
    if not order and success:
        # Payment just completed - create order
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Processing Payment...</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>*{{font-family:'Inter',sans-serif}}body{{background:#07070c;color:#f1f1f5;}}</style></head>
<body class="flex items-center justify-center min-h-screen">
<div class="text-center">
  <i class="fas fa-spinner fa-spin text-4xl text-[#a855f7] mb-4"></i>
  <h2 class="text-xl font-bold mb-2">Processing Your Purchase...</h2>
  <p class="text-[#7a7a8e]">Please wait a moment. You'll be redirected automatically.</p>
  <script>setTimeout(() => window.location.href='/store', 3000);</script>
</div></body></html>"""
    
    if not order:
        return "Invalid or expired download link.", 404
    
    order = dict(order)
    
    # Increment download count
    c.execute("UPDATE product_orders SET downloaded=1, download_count=download_count+1 WHERE download_token=?", (token,))
    c.execute("UPDATE products SET downloads_count=downloads_count+1 WHERE id=?", (order['product_id'],))
    db.commit()
    db.close()
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Download — {order['title']}</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>*{{font-family:'Inter',sans-serif}}body{{background:#07070c;color:#f1f1f5;}}
.card{{background:#0e0e16;border:1px solid #1e1e2e;border-radius:16px;padding:24px;}}
.btn-primary{{background:linear-gradient(135deg,#a855f7,#ec4899);color:white;padding:14px 28px;border-radius:12px;font-weight:600;border:none;cursor:pointer;transition:all .3s;display:inline-flex;align-items:center;gap:8px;text-decoration:none;}}
.btn-primary:hover{{transform:translateY(-2px);box-shadow:0 8px 30px rgba(168,85,247,0.3);}}
</style></head>
<body class="min-h-screen flex items-center justify-center p-4">
<div class="max-w-lg w-full">
  <div class="text-center mb-6">
    <div class="w-16 h-16 rounded-full bg-[#4ade80]/20 flex items-center justify-center mx-auto mb-3"><i class="fas fa-check text-3xl text-[#4ade80]"></i></div>
    <h1 class="text-2xl font-bold text-[#4ade80]">Purchase Complete!</h1>
    <p class="text-[#7a7a8e] mt-1">Thank you for your purchase</p>
  </div>
  <div class="card mb-4">
    <h2 class="font-bold text-lg mb-1">{order['title']}</h2>
    <p class="text-xs text-[#7a7a8e] mb-4">${order['price']:.2f} · Paid via Stripe</p>
    <div class="bg-[#0e0e16] border border-[#252533] rounded-lg p-4 mb-4 max-h-[400px] overflow-y-auto">
      <pre class="text-sm text-[#b0b0c0] whitespace-pre-wrap font-sans">{order['content'] or 'No content available.'}</pre>
    </div>
    <button onclick="copyContent()" class="btn-primary w-full justify-center mb-2"><i class="fas fa-copy mr-1"></i> Copy to Clipboard</button>
    <a href="/store" class="btn-secondary w-full justify-center text-center block" style="background:rgba(255,255,255,0.06);border:1px solid #1e1e2e;color:#f1f1f5;padding:14px 28px;border-radius:12px;font-weight:600;text-decoration:none;display:flex;align-items:center;justify-content:center;gap:8px;"><i class="fas fa-store mr-1"></i> Browse More Products</a>
  </div>
</div>
<script>
function copyContent() {{
  const el = document.querySelector('pre');
  navigator.clipboard.writeText(el.textContent).then(() => {{
    const btn = document.querySelector('.btn-primary');
    btn.innerHTML = '<i class=\"fas fa-check mr-1\"></i> Copied!';
    setTimeout(() => btn.innerHTML = '<i class=\"fas fa-copy mr-1\"></i> Copy to Clipboard', 2000);
  }});
}}
</script>
</body></html>"""
    return render_template_string(html)

# ── STRIPE WEBHOOK for product payments ──
@app.route('/stripe-product-webhook', methods=['POST'])
def stripe_product_webhook():
    """Handle Stripe checkout.session.completed for product purchases."""
    import stripe
    from premium_features import load_stripe_config
    
    cfg = load_stripe_config()
    if not cfg.get('secret_key'):
        return jsonify({'error': 'Not configured'}), 200
    
    stripe.api_key = cfg['secret_key']
    payload = request.get_data()
    sig = request.headers.get('Stripe-Signature', '')
    endpoint_secret = cfg.get('webhook_secret', '')
    
    try:
        event = stripe.Webhook.construct_event(payload, sig, endpoint_secret)
    except:
        return jsonify({'error': 'Invalid signature'}), 200
    
    if event['type'] == 'checkout.session.completed':
        session_data = event['data']['object']
        metadata = session_data.get('metadata', {})
        product_id = metadata.get('product_id')
        download_token = metadata.get('download_token')
        email = session_data.get('customer_details', {}).get('email', '') or session_data.get('customer_email', '')
        
        if product_id and download_token:
            import uuid
            db = get_db()
            c = db.cursor()
            c.execute("SELECT price FROM products WHERE id=?", (product_id,))
            p = c.fetchone()
            price = p[0] if p else 0
            
            c.execute("""INSERT OR IGNORE INTO product_orders 
                (id, product_id, customer_email, amount, stripe_session_id, download_token)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4())[:12], product_id, email, price, session_data.get('id', ''), download_token))
            db.commit()
            db.close()
    
    return jsonify({'received': True})

# ── SMS-GATE.APP INCOMING SMS (webhook + inbox) ──
def init_incoming_sms_table():
    """Ensure incoming_sms table exists."""
    db = get_db()
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS incoming_sms (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            sender TEXT,
            recipient TEXT,
            body TEXT,
            msg_type TEXT DEFAULT 'SMS',
            sim_number INTEGER,
            received_at TEXT,
            lead_id TEXT,
            processed INTEGER DEFAULT 0
        )
    """)
    db.commit()
    db.close()

init_incoming_sms_table()

# ── KB DOCUMENTS (menus / inventories / URLs the AI can search) ──
def init_kb_documents_table():
    """Ensure kb_documents table exists."""
    db = get_db()
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS kb_documents (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            doc_type TEXT DEFAULT 'file',
            name TEXT,
            content TEXT,
            created_at TEXT
        )
    """)
    db.commit()
    db.close()

init_kb_documents_table()


def get_kb_documents_text(bid, max_chars=60000):
    """Build a prompt-ready text block from all documents for a business."""
    if not bid:
        return ""
    try:
        db = get_db()
        c = db.cursor()
        rows = c.execute(
            "SELECT name, content FROM kb_documents WHERE business_id=? ORDER BY created_at",
            (bid,)).fetchall()
        db.close()
    except Exception:
        return ""
    parts, total = [], 0
    for r in rows:
        block = f"📄 {r['name']}:\n{r['content']}"
        if total + len(block) > max_chars:
            block = block[:max_chars - total]
        parts.append(block)
        total += len(block)
        if total >= max_chars:
            break
    return "\n\n".join(parts)


def extract_doc_text(filename, data):
    """Extract readable text from an uploaded file (.txt .md .csv .json .pdf)."""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext == 'pdf':
        import io
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or '')
            except Exception:
                continue
        return "\n".join(pages)
    if ext in ('csv', 'json', 'txt', 'md', 'text'):
        try:
            return data.decode('utf-8', errors='replace')
        except Exception:
            return data.decode('latin-1', errors='replace')
    return None


def fetch_url_text(url):
    """Fetch a URL and strip HTML to plain text (with curl-like UA for Cloudflare)."""
    import re as _re
    import html as _html
    try:
        r = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
        }, timeout=25)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        ct = r.headers.get('Content-Type', '')
        text = r.text
        if 'text/html' in ct or 'html' in ct or '<html' in text[:2000].lower():
            text = _re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>|<!--[\s\S]*?-->', ' ', text, flags=_re.I)
            text = _re.sub(r'<[^>]+>', ' ', text)
            text = _html.unescape(text)
        text = _re.sub(r'[ \t]+', ' ', text)
        text = _re.sub(r'\n\s*\n+', '\n', text).strip()
        return text[:100000], None
    except Exception as e:
        return None, str(e)


@app.route('/upload-kb-document', methods=['POST'])
@login_required
def upload_kb_document():
    bid = session['business_id']
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'success': False, 'error': 'No file selected'})
    data = f.read()
    if len(data) > 3 * 1024 * 1024:
        return jsonify({'success': False, 'error': 'File too large (max 3MB)'})
    text = extract_doc_text(f.filename, data)
    if text is None:
        return jsonify({'success': False, 'error': 'Unsupported file — use .txt, .md, .csv, .json or .pdf'})
    text = text.strip()
    if not text:
        return jsonify({'success': False, 'error': 'No readable text found in that file'})
    db = get_db()
    c = db.cursor()
    c.execute(
        "INSERT INTO kb_documents (id, business_id, doc_type, name, content, created_at) VALUES (?,?,?,?,?,?)",
        (uuid.uuid4().hex[:16], bid, 'file', f.filename[:120], text[:150000], datetime.now().isoformat()))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': f'📄 {f.filename} added — AI can now answer from it!'})


@app.route('/add-kb-url', methods=['POST'])
@login_required
def add_kb_url():
    bid = session['business_id']
    url = (request.get_json(silent=True) or {}).get('url', '').strip()
    if not url.startswith('http'):
        return jsonify({'success': False, 'error': 'Enter a valid URL (https://...)'})
    text, err = fetch_url_text(url)
    if err or not text:
        return jsonify({'success': False, 'error': f'Could not fetch that page: {err or "empty content"}'})
    name = url.replace('https://', '').replace('http://', '').rstrip('/')[:100]
    db = get_db()
    c = db.cursor()
    c.execute(
        "INSERT INTO kb_documents (id, business_id, doc_type, name, content, created_at) VALUES (?,?,?,?,?,?)",
        (uuid.uuid4().hex[:16], bid, 'url', name, text, datetime.now().isoformat()))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': f'🌐 {name} saved ({len(text):,} chars of text)'})


@app.route('/delete-kb-document', methods=['POST'])
@login_required
def delete_kb_document():
    bid = session['business_id']
    doc_id = (request.get_json(silent=True) or {}).get('id', '')
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM kb_documents WHERE id=? AND business_id=?", (doc_id, bid))
    db.commit()
    db.close()
    return jsonify({'success': True})

# ── AFFILIATE PROGRAM (sales people earn commission per signup) ──
def init_affiliates_table():
    """Ensure affiliates + affiliate_events tables exist."""
    db = get_db()
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS affiliates (
            id TEXT PRIMARY KEY,
            code TEXT UNIQUE,
            name TEXT,
            email TEXT,
            phone TEXT,
            commission_per_signup REAL DEFAULT 50,
            status TEXT DEFAULT 'active',
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS affiliate_events (
            id TEXT PRIMARY KEY,
            affiliate_id TEXT,
            event_type TEXT,
            business_id TEXT,
            business_name TEXT,
            commission REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            paid_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS affiliate_payouts (
            id TEXT PRIMARY KEY,
            affiliate_id TEXT,
            amount REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            paid_at TEXT
        )
    """)
    db.commit()
    db.close()

init_affiliates_table()


def _agentmail_key():
    """AGENTMAIL_API_KEY from env, then /root/.env (export syntax), then .env."""
    key = os.environ.get("AGENTMAIL_API_KEY", "")
    if not key:
        for p in ("/root/.env", os.path.join(os.path.dirname(__file__), ".env")):
            try:
                with open(p) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("AGENTMAIL_API_KEY="):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                continue
            if key:
                break
    return key


def send_email_via_smtp(to, subject, body):
    """Send email — AgentMail first (verified working), Resend SMTP fallback."""
    # 1) AgentMail (proven: appointment confirmations use this path)
    try:
        key = _agentmail_key()
        if key:
            payload = {"to": to, "subject": subject, "text": body}
            req = urllib.request.Request(
                "https://api.agentmail.to/v0/inboxes/aiworkers@agentmail.to/messages/send",
                data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                         "User-Agent": "DiazitesAffiliate/1.0"},
                method="POST")
            urllib.request.urlopen(req, timeout=15)
            return True
    except Exception:
        pass
    # 2) Resend SMTP fallback
    try:
        from smtplib import SMTP
        from email.mime.text import MIMEText
        cfg_path = '/root/voice-agent-manager/smtp_config.json'
        if not os.path.exists(cfg_path):
            return False
        with open(cfg_path) as f:
            cfg = json.load(f)
        if not cfg.get('host') or not cfg.get('email'):
            return False
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = cfg['email']
        msg['To'] = to
        with SMTP(cfg['host'], int(cfg.get('port', 587)), timeout=15) as server:
            if cfg.get('tls') != '0':
                server.starttls()
            if cfg.get('password'):
                smtp_user = 'resend' if 'resend' in cfg.get('host', '') else cfg['email']
                server.login(smtp_user, cfg['password'])
            server.send_message(msg)
        return True
    except Exception:
        return False


def site_base():
    """Public site base URL (real domain even when testing on localhost)."""
    base = request.host_url.rstrip('/')
    if '127.0.0.1' in base or 'localhost' in base:
        return 'https://diazites.online'
    # Force https for the public domain — never hand affiliates an http:// link
    return base.replace('http://', 'https://')


def get_affiliate_by_code(code):
    if not code:
        return None
    db = get_db()
    c = db.cursor()
    row = c.execute("SELECT * FROM affiliates WHERE code=? AND status='active'",
                    (str(code).strip().upper(),)).fetchone()
    db.close()
    return dict(row) if row else None


def gen_affiliate_code(cursor):
    import random as _r
    import string as _s
    for _ in range(50):
        code = ''.join(_r.choices(_s.ascii_uppercase + _s.digits, k=8))
        if not cursor.execute("SELECT 1 FROM affiliates WHERE code=?", (code,)).fetchone():
            return code
    return 'AF' + str(int(time.time()))[-6:]


AFFILIATE_LANDING = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diazites Affiliates — Earn $50 Per Signup</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;background:#0a0a16;color:#f1f1f5;margin:0}
.wrap{max-width:860px;margin:0 auto;padding:48px 20px}
.card{background:#12121f;border:1px solid #252533;border-radius:16px;padding:28px;margin-bottom:20px}
.gradient-text{background:linear-gradient(90deg,#818cf8,#a855f7);-webkit-background-clip:text;background-clip:text;color:transparent}
h1{font-size:34px;margin:0 0 8px}h2{font-size:22px;margin:0 0 12px}
p{color:#a1a1b5;line-height:1.6}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:20px 0}
.step{background:#1a1a26;border:1px solid #252533;border-radius:12px;padding:16px}
.btn{display:inline-block;background:linear-gradient(90deg,#818cf8,#a855f7);color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:600;border:none;cursor:pointer;font-size:14px}
input{width:100%;padding:10px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:14px;box-sizing:border-box;margin-bottom:10px}
label{font-size:12px;color:#7a7a8e;display:block;margin-bottom:4px}
.err{color:#f87171;font-size:13px;margin-bottom:10px}
.top{display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid #1a1a2e}
.top a{color:#818cf8;text-decoration:none;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px;border-bottom:1px solid #1a1a2e}
.badge{padding:2px 10px;border-radius:999px;font-size:11px}
.badge.green{background:rgba(74,222,128,.15);color:#4ade80}.badge.yellow{background:rgba(250,204,21,.15);color:#facc15}
.linkbox{background:#0c0c18;border:1px dashed #252533;border-radius:10px;padding:12px;font-size:14px;word-break:break-all;color:#818cf8;margin:12px 0}
.stat{display:inline-block;margin-right:28px}
.stat b{font-size:26px;display:block;color:#f1f1f5}</style></head><body>
<div class="top"><div><span style="font-weight:700">🎙️ Diazites</span> <span style="color:#7a7a8e;font-size:12px">Affiliate Program</span></div>
<div><a href="/affiliate/login">Affiliate Login</a> &nbsp; <a href="/">← Back to site</a></div></div>
<div class="wrap">
<div class="card"><h1>Earn <span class="gradient-text">$50</span> for every business you bring in</h1>
<p>Diazites gives local businesses AI voice agents that answer calls, book appointments, and never miss a lead. When a business signs up through your link, you earn <b>$50</b> — as many signups as you can bring.</p>
<div class="steps">
<div class="step"><b>1. Get your link</b><p style="font-size:13px;margin:6px 0 0">Sign up free and get your personal tracking link in seconds.</p></div>
<div class="step"><b>2. Share it</b><p style="font-size:13px;margin:6px 0 0">Share on social, with your network, or with local businesses.</p></div>
<div class="step"><b>3. Get paid</b><p style="font-size:13px;margin:6px 0 0">$50 per qualified signup. Track everything in your dashboard.</p></div>
</div>
<a class="btn" href="/affiliate/signup">🚀 Become an Affiliate</a> &nbsp; <a href="/affiliate/login" style="color:#818cf8;font-size:14px">Already have a code? Log in →</a>
</div>
<div class="card"><h2>Why Diazites</h2>
<p>Businesses pay $97–$497/mo for AI voice agents that answer every call, book appointments, and qualify leads — while they focus on their work. High-value product, high-converting offer, recurring revenue for us — and a flat $50 commission for you per signup.</p></div>
</div></body></html>"""

AFFILIATE_SIGNUP = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Affiliate Signup — Diazites</title><style>
body{font-family:system-ui,sans-serif;background:#0a0a16;color:#f1f1f5;margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#12121f;border:1px solid #252533;border-radius:16px;padding:32px;width:380px;max-width:92vw}
.gradient-text{background:linear-gradient(90deg,#818cf8,#a855f7);-webkit-background-clip:text;background-clip:text;color:transparent}
.btn{width:100%;background:linear-gradient(90deg,#818cf8,#a855f7);color:#fff;padding:12px;border-radius:10px;border:none;cursor:pointer;font-size:14px;font-weight:600}
input{width:100%;padding:10px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:14px;box-sizing:border-box;margin-bottom:10px}
label{font-size:12px;color:#7a7a8e;display:block;margin-bottom:4px}
.err{color:#f87171;font-size:13px;margin-bottom:10px}
a{color:#818cf8;text-decoration:none;font-size:13px}</style></head><body>
<div class="card"><h1 style="font-size:26px;margin:0 0 6px">Become an <span class="gradient-text">Affiliate</span></h1>
<p style="color:#a1a1b5;font-size:14px;margin:0 0 20px">Earn <b>$50</b> per business signup. Your personal link + live tracking dashboard included.</p>
<div class="err">{{ error }}</div>
<form method="POST">
<label>Full Name</label><input name="name" value="{{ values.get('name','') }}" required>
<label>Email</label><input type="email" name="email" value="{{ values.get('email','') }}" required>
<label>Phone (optional)</label><input name="phone" value="{{ values.get('phone','') }}">
<button class="btn">Create My Affiliate Link</button>
</form>
<p style="margin-top:14px"><a href="/affiliate/login">Already have a code? Log in →</a></p></div></body></html>"""

AFFILIATE_LOGIN = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Affiliate Login — Diazites</title><style>
body{font-family:system-ui,sans-serif;background:#0a0a16;color:#f1f1f5;margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#12121f;border:1px solid #252533;border-radius:16px;padding:32px;width:360px;max-width:92vw}
.btn{width:100%;background:linear-gradient(90deg,#818cf8,#a855f7);color:#fff;padding:12px;border-radius:10px;border:none;cursor:pointer;font-size:14px;font-weight:600}
input{width:100%;padding:10px 12px;border-radius:8px;border:1px solid #252533;background:#0c0c18;color:#f1f1f5;font-size:14px;box-sizing:border-box;margin-bottom:10px}
label{font-size:12px;color:#7a7a8e;display:block;margin-bottom:4px}
.err{color:#f87171;font-size:13px;margin-bottom:10px}
a{color:#818cf8;text-decoration:none;font-size:13px}</style></head><body>
<div class="card"><h1 style="font-size:24px;margin:0 0 6px">Affiliate Login</h1>
<p style="color:#a1a1b5;font-size:14px;margin:0 0 20px">Enter your affiliate code</p>
<div class="err">{{ error }}</div>
<form method="POST">
<label>Affiliate Code</label><input name="code" placeholder="e.g. AB12CD34" required style="text-transform:uppercase">
<button class="btn">View My Dashboard</button>
</form>
<p style="margin-top:14px"><a href="/affiliate/signup">No code? Become an affiliate →</a></p></div></body></html>"""

AFFILIATE_DASHBOARD = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Affiliate Dashboard — Diazites</title><style>
body{font-family:system-ui,sans-serif;background:#0a0a16;color:#f1f1f5;margin:0}
.wrap{max-width:900px;margin:0 auto;padding:32px 20px}
.card{background:#12121f;border:1px solid #252533;border-radius:16px;padding:24px;margin-bottom:18px}
.gradient-text{background:linear-gradient(90deg,#818cf8,#a855f7);-webkit-background-clip:text;background-clip:text;color:transparent}
.linkbox{background:#0c0c18;border:1px dashed #252533;border-radius:10px;padding:12px;font-size:14px;word-break:break-all;color:#818cf8;margin:12px 0}
.btn{display:inline-block;background:linear-gradient(90deg,#818cf8,#a855f7);color:#fff;text-decoration:none;padding:8px 18px;border-radius:8px;font-size:13px;font-weight:600;border:none;cursor:pointer}
.stat{display:inline-block;margin-right:32px}.stat b{font-size:28px;display:block}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px;border-bottom:1px solid #1a1a2e}
.badge{padding:2px 10px;border-radius:999px;font-size:11px}
.badge.green{background:rgba(74,222,128,.15);color:#4ade80}.badge.yellow{background:rgba(250,204,21,.15);color:#facc15}
.top{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;border-bottom:1px solid #1a1a2e}
.top a{color:#818cf8;text-decoration:none;font-size:13px}
.copy{font-size:12px;color:#4ade80;display:none}
</style></head><body>
<div class="top"><div><span style="font-weight:700">🎙️ Diazites</span> <span style="color:#7a7a8e;font-size:12px">Affiliate Dashboard</span></div>
<div><a href="/affiliate/logout">Logout</a></div></div>
<div class="wrap">
{% with messages = get_flashed_messages(with_categories=true) %}
{% for cat, m in messages %}
<div style="padding:12px 16px;border-radius:10px;margin-bottom:16px;font-size:14px;background:{{ 'rgba(74,222,128,.1)' if cat=='success' else 'rgba(248,113,113,.1)' }};border:1px solid {{ '#4ade80' if cat=='success' else '#f87171' }};color:{{ '#4ade80' if cat=='success' else '#f87171' }}">{{ m }}</div>
{% endfor %}
{% endwith %}
<div class="card"><h2 style="margin:0 0 4px">Hi, {{ aff.name }} 👋</h2>
<p style="color:#a1a1b5;font-size:14px;margin:0">Your affiliate code: <b>{{ aff.code }}</b></p>
<div class="linkbox">🔗 {{ link }}</div>
<div class="linkbox">📞 Demo line: <b>(786) 808-4099</b> — tell prospects to call it and hear Pablo answer</div>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin:12px 0">
<a class="btn" href="/affiliate/toolkit/social_kit.md">📱 Social Kit (reels + posts)</a>
<a class="btn" href="/affiliate/toolkit/outreach_scripts.md">✉️ Cold Outreach Scripts</a>
<a class="btn" href="/a/{{ aff.code }}">👀 Preview my page</a>
</div>
<div style="margin:12px 0">
<p style="font-size:13px;color:#a1a1b5;margin:0 0 10px"><b>📸 Instagram carousel</b> — tap any slide to view full size, or hold to save. Ready to post to your feed.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px">
{% for n in range(1, 6) %}
<a href="/affiliate/toolkit/carousel-{{ n }}.png" target="_blank" style="display:block;text-decoration:none">
<img src="/affiliate/toolkit/carousel-{{ n }}.png" alt="Slide {{ n }}" loading="lazy" style="width:100%;aspect-ratio:4/5;object-fit:cover;border-radius:12px;border:1px solid #252533;display:block">
</a>
{% endfor %}
</div>
</div>
<button class="btn" onclick="copyLink()">📋 Copy Link</button> <span id="copied" class="copy">Copied!</span></div>
<div class="card">
<div class="stat"><b>{{ clicks }}</b>Link Clicks</div>
<div class="stat"><b style="color:#facc15">${{ '%.0f' % total_pending }}</b>Pending</div>
<div class="stat"><b style="color:#4ade80">${{ '%.0f' % total_paid }}</b>Paid</div>
</div>
<div class="card"><h2>💰 Payouts</h2>
{% set has_open = payouts and payouts[0]['status'] == 'pending' %}
{% if total_pending > 0 and not has_open %}
<form method="POST" action="/affiliate/request-payout" style="margin-bottom:12px">
<button class="btn">💰 Request Payout (${{ '%.0f' % total_pending }})</button>
</form>
{% elif has_open %}
<p style="color:#facc15;font-size:13px">⏳ Payout request in progress — you'll be notified when it's paid.</p>
{% endif %}
{% if payouts %}
<table><tr><th>Amount</th><th>Status</th><th>Requested</th><th>Paid</th></tr>
{% for p in payouts %}
<tr><td>${{ '%.0f' % p['amount'] }}</td>
<td><span class="badge {{ 'green' if p['status']=='paid' else 'yellow' }}">{{ p['status'].upper() }}</span></td>
<td>{{ (p['created_at'] or '')[:10] }}</td>
<td>{{ (p['paid_at'] or '—')[:10] }}</td></tr>
{% endfor %}</table>
{% else %}
<p style="color:#7a7a8e;font-size:13px">No payout requests yet. Once you have pending commissions, request a payout here.</p>
{% endif %}
</div>
<div class="card"><h2>Signups &amp; Commissions</h2>
{% if signups %}
<table><tr><th>Business</th><th>Commission</th><th>Status</th><th>Date</th></tr>
{% for s in signups %}
<tr><td>{{ s['business_name'] or '—' }}</td><td>${{ '%.0f' % s['commission'] }}</td>
<td><span class="badge {{ 'green' if s['status']=='paid' else 'yellow' }}">{{ s['status'].upper() }}</span></td>
<td>{{ (s['created_at'] or '')[:10] }}</td></tr>
{% endfor %}</table>
{% else %}<p style="color:#7a7a8e;font-size:14px">No signups yet — share your link to start earning! 🚀</p>{% endif %}
</div>
<div class="card"><h2>How it works</h2>
<p style="font-size:13px;color:#a1a1b5">When someone clicks your link and signs up, the signup is automatically tracked to you and ${{ '%.0f' % aff.commission_per_signup }} is added as <b>Pending</b>. Commissions are paid out after review. One commission per new business.</p></div>
</div>
<script>function copyLink(){var t=document.createElement('textarea');t.value='{{ link }}';document.body.appendChild(t);t.select();document.execCommand('copy');document.body.removeChild(t);document.getElementById('copied').style.display='inline';setTimeout(function(){document.getElementById('copied').style.display='none'},1500);}</script>
</body></html>"""


TOOLKIT_DIR = "/root/voice-agent-manager/affiliate_toolkit"


@app.route('/a/<code>')
def affiliate_landing_page(code):
    """Per-affiliate personalized landing page: diazites.online/a/CODE"""
    aff = get_affiliate_by_code(code)
    if 'business_id' in session:
        return dashboard()
    page = LANDING_PAGE.replace('<!-- GSC_META -->', gsc_meta_tag())
    if aff:
        banner = ('<div style="background:linear-gradient(90deg,#6366f1,#8b5cf6);color:#fff;'
                  'text-align:center;padding:10px 16px;font-size:13px;font-weight:600;'
                  'font-family:Inter,sans-serif">🤝 You\'re here through <span style="text-decoration:underline">'
                  + str(aff['name']) + '</span> — get <b>14-day free trial</b> + <b>20% off</b> your first month!</div>')
        page = page.replace('<!-- NAV -->', banner + '\n<!-- NAV -->', 1)
        resp = make_response(render_template_string(page))
        resp.set_cookie('diazites_ref', aff['code'], max_age=60 * 60 * 24 * 90, samesite='Lax')
        try:
            db = get_db()
            c = db.cursor()
            if request.cookies.get('diazites_ref', '') != aff['code']:
                c.execute("INSERT INTO affiliate_events (id, affiliate_id, event_type, created_at) VALUES (?,?,?,datetime('now'))",
                          (uuid.uuid4().hex[:16], aff['id'], 'click'))
                db.commit()
            db.close()
        except Exception:
            pass
        return resp
    return render_template_string(page)


@app.route('/affiliate/toolkit/<name>')
def affiliate_toolkit(name):
    fp = os.path.join(TOOLKIT_DIR, os.path.basename(name))
    if os.path.exists(fp):
        ext = os.path.splitext(name)[1].lower()
        mimetype = 'image/png' if ext == '.png' else 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'text/markdown'
        return send_file(fp, mimetype=mimetype, as_attachment=False)
    return "Not found", 404


@app.route('/affiliate')
def affiliate_landing():
    ref = request.args.get('ref', '')
    aff = get_affiliate_by_code(ref) if ref else None
    if aff:
        resp = make_response(render_template_string(AFFILIATE_LANDING, ref=ref))
        resp.set_cookie('diazites_ref', aff['code'], max_age=60 * 60 * 24 * 90, samesite='Lax')
        try:
            db = get_db()
            c = db.cursor()
            if request.cookies.get('diazites_ref', '') != aff['code']:
                c.execute("INSERT INTO affiliate_events (id, affiliate_id, event_type, created_at) VALUES (?,?,?,datetime('now'))",
                          (uuid.uuid4().hex[:16], aff['id'], 'click'))
                db.commit()
            db.close()
        except Exception:
            pass
        return resp
    return render_template_string(AFFILIATE_LANDING, ref=ref or '')


@app.route('/affiliate/signup', methods=['GET', 'POST'])
def affiliate_signup():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        if not name or not email:
            return render_template_string(AFFILIATE_SIGNUP, error='Name and email are required', values=request.form)
        db = get_db()
        c = db.cursor()
        code = gen_affiliate_code(c)
        aid = uuid.uuid4().hex[:12]
        c.execute("INSERT INTO affiliates (id, code, name, email, phone, created_at) VALUES (?,?,?,?,?,datetime('now'))",
                  (aid, code, name, email, phone))
        db.commit()
        db.close()
        session['affiliate_id'] = aid
        # Email the affiliate their credentials + tracking link
        if email:
            link = f"{site_base()}/?ref={code}"
            try:
                send_email_via_smtp(email, '🎉 Welcome to the Diazites Affiliate Program!', f"""Hi {name},

Your affiliate account is ready — start earning $50 per business signup!

━━━━━━━━━━━━━━━━━━━━━━━━
🔗 YOUR AFFILIATE LINK
{link}
━━━━━━━━━━━━━━━━━━━━━━━━
🔐 Your affiliate code: {code}

Dashboard: {site_base()}/affiliate/login

How it works:
1. Share your link anywhere (social, networking, local businesses)
2. When a business signs up through it, you earn $50 per signup
3. Track clicks, signups and earnings in your dashboard

Questions? Just reply to this email.

— Diazites Team
""")
            except Exception:
                pass
        return redirect('/affiliate/dashboard')
    return render_template_string(AFFILIATE_SIGNUP, error='', values={})


@app.route('/affiliate/login', methods=['GET', 'POST'])
def affiliate_login():
    if request.method == 'POST':
        code = (request.form.get('code') or '').strip().upper()
        aff = get_affiliate_by_code(code)
        if aff:
            session['affiliate_id'] = aff['id']
            return redirect('/affiliate/dashboard')
        return render_template_string(AFFILIATE_LOGIN, error='Invalid affiliate code')
    return render_template_string(AFFILIATE_LOGIN, error='')


@app.route('/affiliate/dashboard')
def affiliate_dashboard():
    aid = session.get('affiliate_id')
    if not aid:
        return redirect('/affiliate/login')
    db = get_db()
    c = db.cursor()
    aff = c.execute("SELECT * FROM affiliates WHERE id=?", (aid,)).fetchone()
    if not aff:
        db.close()
        session.pop('affiliate_id', None)
        return redirect('/affiliate/login')
    clicks = c.execute("SELECT COUNT(*) FROM affiliate_events WHERE affiliate_id=? AND event_type='click'",
                       (aid,)).fetchone()[0]
    signups = c.execute("SELECT * FROM affiliate_events WHERE affiliate_id=? AND event_type='signup' ORDER BY created_at DESC",
                        (aid,)).fetchall()
    total_pending = sum(r['commission'] for r in signups if r['status'] == 'pending')
    total_paid = sum(r['commission'] for r in signups if r['status'] == 'paid')
    payouts = c.execute("SELECT * FROM affiliate_payouts WHERE affiliate_id=? ORDER BY created_at DESC",
                        (aid,)).fetchall()
    db.close()
    link = site_base() + '/a/' + aff['code']
    return render_template_string(AFFILIATE_DASHBOARD, aff=dict(aff), link=link, clicks=clicks,
                                  signups=signups, total_pending=total_pending, total_paid=total_paid,
                                  payouts=payouts)


@app.route('/affiliate/request-payout', methods=['POST'])
def affiliate_request_payout():
    aid = session.get('affiliate_id')
    if not aid:
        return redirect('/affiliate/login')
    db = get_db()
    c = db.cursor()
    aff = c.execute("SELECT * FROM affiliates WHERE id=?", (aid,)).fetchone()
    if not aff:
        db.close()
        return redirect('/affiliate/login')
    pending = c.execute(
        "SELECT COALESCE(SUM(commission),0) FROM affiliate_events WHERE affiliate_id=? AND event_type='signup' AND status='pending'",
        (aid,)).fetchone()[0]
    open_req = c.execute("SELECT 1 FROM affiliate_payouts WHERE affiliate_id=? AND status='pending'",
                         (aid,)).fetchone()
    if float(pending) <= 0:
        db.close()
        flash('No pending commissions to request yet!', 'error')
        return redirect('/affiliate/dashboard')
    if open_req:
        db.close()
        flash('You already have a payout request in progress!', 'error')
        return redirect('/affiliate/dashboard')
    pid = uuid.uuid4().hex[:16]
    c.execute("INSERT INTO affiliate_payouts (id, affiliate_id, amount, status, created_at) "
              "VALUES (?,?,?, 'pending', datetime('now'))", (pid, aid, float(pending)))
    db.commit()
    admin_email = os.environ.get('ADMIN_NOTIFY_EMAIL', 'digimiami@gmail.com')
    try:
        send_email_via_smtp(
            admin_email,
            f'💰 Payout Request: {aff["name"]} — ${float(pending):.0f}',
            f'Affiliate {aff["name"]} ({aff["email"] or "no email on file"}) requested a payout of ${float(pending):.0f}.\n\n'
            f'Approve here: {site_base()}/admin?tab=affiliates')
    except Exception:
        pass
    db.close()
    flash('💰 Payout requested! We\'ll process it shortly.', 'success')
    return redirect('/affiliate/dashboard')


@app.route('/affiliate/logout')
def affiliate_logout():
    session.pop('affiliate_id', None)
    return redirect('/affiliate')

@app.route('/sms-gate-webhook', methods=['POST'])
def sms_gate_webhook():
    """Receive incoming SMS from sms-gate.app webhook (event: sms:received)."""
    try:
        raw = request.get_data(as_text=True)
        # Log raw payload for debugging
        with open('/tmp/smsgate_webhook_last.json', 'w') as f:
            f.write(raw)
        data = request.get_json(silent=True) or {}
        # Handle both direct object and {data: {...}} / {message: {...}} wrappers
        if 'data' in data and isinstance(data['data'], dict):
            data = data['data']
        if 'message' in data and isinstance(data['message'], dict):
            data = data['message']
        # sms-gate.app real webhook shape: {event, id, webhookId, deviceId, payload: {message, sender, ...}}
        if 'payload' in data and isinstance(data['payload'], dict):
            payload = data['payload']
            sender = payload.get('sender', payload.get('phoneNumber', ''))
            recipient = payload.get('recipient', '')
            body = payload.get('message', payload.get('contentPreview', payload.get('text', '')))
            msg_type = payload.get('type', 'SMS')
            sim = payload.get('simNumber')
            msg_id = payload.get('messageId', data.get('id', ''))
            received_at = payload.get('receivedAt', data.get('createdAt', datetime.now().isoformat()))
        else:
            sender = data.get('sender', data.get('from', ''))
            recipient = data.get('recipient', data.get('to', ''))
            body = data.get('contentPreview', data.get('body', data.get('text', data.get('content', ''))))
            msg_type = data.get('type', 'SMS')
            sim = data.get('simNumber')
            msg_id = data.get('id', '')
            received_at = data.get('createdAt', datetime.now().isoformat())

        # Match to a business: FIRST try recipient (their device number matches a business
        # number — e.g. the demo line), then fall back to the outgoing-SMS reply log.
        bid = None
        lead_id = None
        db = get_db()
        db.row_factory = sqlite3.Row
        c = db.cursor()
        if recipient:
            c.execute("SELECT id FROM businesses WHERE phone_number = ? OR vapi_phone_id = ? LIMIT 1",
                      (recipient, recipient))
            row = c.fetchone()
            if row:
                bid = row['id']
        # Fallback: reply-matching — find the most recent SMS we sent to this sender
        if not bid and sender:
            c.execute("""SELECT business_id, lead_id FROM outgoing_sms 
                         WHERE phone = ? AND business_id IS NOT NULL
                         ORDER BY sent_at DESC LIMIT 1""", (sender,))
            row = c.fetchone()
            if row:
                bid = row['business_id']
                lead_id = row['lead_id']
        # Fallback: try to match sender to an existing lead
        if not lead_id and bid and sender:
            c.execute("SELECT id FROM leads WHERE business_id = ? AND phone = ? LIMIT 1", (bid, sender))
            row = c.fetchone()
            if row:
                lead_id = row['id']
        # Insert
        c.execute("""INSERT OR IGNORE INTO incoming_sms 
                     (id, business_id, sender, recipient, body, msg_type, sim_number, received_at, lead_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (msg_id or f"inc_{hashlib.md5((sender+body+received_at).encode()).hexdigest()[:12]}",
                   bid, sender, recipient, body, msg_type, sim, received_at, lead_id))
        db.commit()
        db.close()
        # AI SMS replies — auto-respond with the business knowledge base (background)
        if bid and body:
            try:
                from ai_sms_reply import run_in_background
                run_in_background(bid, sender, body, lead_id)
            except Exception as ai_e:
                print(f"⚠️ AI SMS trigger error: {ai_e}")
        return jsonify({'success': True, 'received': True})
    except Exception as e:
        print(f"❌ sms-gate webhook error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inbox', methods=['GET'])
def api_inbox():
    """List incoming + outgoing SMS for the logged-in business only (reply-matched)."""
    bid = session.get('business_id')
    if not bid:
        return jsonify({'error': 'Not logged in'}), 401
    db = get_db()
    db.row_factory = sqlite3.Row
    c = db.cursor()
    # Incoming messages
    c.execute("""SELECT * FROM incoming_sms WHERE business_id = ?
                 ORDER BY received_at DESC LIMIT 100""", (bid,))
    inc = [dict(r) for r in c.fetchall()]
    # Outgoing messages (from the reply-matching log)
    try:
        c.execute("""SELECT id, business_id, lead_id, phone, body, message_id, sent_at, saved
                     FROM outgoing_sms WHERE business_id = ?
                     ORDER BY sent_at DESC LIMIT 100""", (bid,))
        out = [dict(r) for r in c.fetchall()]
    except Exception:
        out = []
    db.close()
    # Merge, newest first
    merged = []
    for m in inc:
        merged.append({'id': m['id'], 'sender': m['sender'], 'recipient': m['recipient'],
                       'body': m['body'], 'received_at': m['received_at'], 'direction': 'IN',
                       'which': 'in', 'saved': m.get('saved', 0)})
    for m in out:
        merged.append({'id': m['id'], 'phone': m['phone'], 'body': m['body'],
                       'sent_at': m['sent_at'], 'direction': 'OUT',
                       'which': 'out', 'saved': m.get('saved', 0)})
    merged.sort(key=lambda x: x.get('received_at') or x.get('sent_at') or '', reverse=True)
    return jsonify({'messages': merged[:100], 'total': len(merged)})

@app.route('/api/sms/send', methods=['POST'])
@login_required
def api_sms_send():
    """Send an SMS from the dashboard (compose/reply)."""
    bid = session['business_id']
    phone = (request.form.get('phone', '') or '').strip()
    message = (request.form.get('message', '') or '').strip()
    if not phone or not message:
        return jsonify({'success': False, 'error': 'Phone and message required'}), 400
    # Clean phone to E.164 (US/CA 10-digit gets +1)
    from smsgate_sms import _clean_phone
    cleaned = _clean_phone(phone)
    # Try to match to a lead for this business
    lead_id = None
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id FROM leads WHERE business_id = ? AND phone = ? LIMIT 1", (bid, cleaned))
    row = c.fetchone()
    if row:
        lead_id = row['id']
    db.close()
    try:
        from smsgate_sms import send_sms
        ok = send_sms(cleaned, message, business_id=bid, lead_id=lead_id)
        if ok:
            return jsonify({'success': True, 'message': 'SMS sent'})
        return jsonify({'success': False, 'error': 'SMS provider failed to queue message'}), 502
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sms/delete', methods=['POST'])
@login_required
def api_sms_delete():
    """Delete an SMS (incoming or outgoing) belonging to this business."""
    bid = session['business_id']
    msg_id = (request.form.get('id', '') or '').strip()
    which = (request.form.get('which', '') or '').strip()  # 'in' or 'out'
    if not msg_id or which not in ('in', 'out'):
        return jsonify({'success': False, 'error': 'id and which (in|out) required'}), 400
    table = 'incoming_sms' if which == 'in' else 'outgoing_sms'
    db = get_db()
    c = db.cursor()
    c.execute(f"DELETE FROM {table} WHERE id = ? AND business_id = ?", (msg_id, bid))
    db.commit()
    deleted = c.rowcount
    db.close()
    return jsonify({'success': deleted > 0, 'deleted': deleted})

@app.route('/api/sms/save', methods=['POST'])
@login_required
def api_sms_save():
    """Toggle saved flag on an SMS (incoming or outgoing)."""
    bid = session['business_id']
    msg_id = (request.form.get('id', '') or '').strip()
    which = (request.form.get('which', '') or '').strip()
    saved = 1 if (request.form.get('saved', '') == '1') else 0
    if not msg_id or which not in ('in', 'out'):
        return jsonify({'success': False, 'error': 'id and which (in|out) required'}), 400
    table = 'incoming_sms' if which == 'in' else 'outgoing_sms'
    db = get_db()
    c = db.cursor()
    c.execute(f"UPDATE {table} SET saved = ? WHERE id = ? AND business_id = ?", (saved, msg_id, bid))
    db.commit()
    updated = c.rowcount
    db.close()
    return jsonify({'success': updated > 0, 'saved': saved})

@app.route('/api/sms/forward', methods=['POST'])
@login_required
def api_sms_forward():
    """Forward an SMS to another number."""
    bid = session['business_id']
    to_phone = (request.form.get('to', '') or '').strip()
    body = (request.form.get('body', '') or '').strip()
    if not to_phone or not body:
        return jsonify({'success': False, 'error': 'to and body required'}), 400
    from smsgate_sms import _clean_phone
    cleaned = _clean_phone(to_phone)
    # Try to match a lead for this business
    lead_id = None
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id FROM leads WHERE business_id = ? AND phone = ? LIMIT 1", (bid, cleaned))
    row = c.fetchone()
    if row:
        lead_id = row['id']
    db.close()
    try:
        from smsgate_sms import send_sms
        ok = send_sms(cleaned, body, business_id=bid, lead_id=lead_id)
        if ok:
            return jsonify({'success': True, 'message': 'SMS forwarded'})
        return jsonify({'success': False, 'error': 'SMS provider failed to queue message'}), 502
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── USER API KEY MANAGEMENT (for dashboard users) ──
def init_user_api_keys_table():
    """Ensure the api_keys table exists (used by dashboard users)."""
    db = get_db()
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_api_keys (
            id TEXT PRIMARY KEY,
            key_hash TEXT UNIQUE NOT NULL,
            raw_prefix TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            permissions TEXT DEFAULT 'read,write',
            created_at TEXT DEFAULT (datetime('now')),
            last_used_at TEXT,
            expires_at TEXT,
            active INTEGER DEFAULT 1,
            business_id TEXT NOT NULL
        )
    """)
    db.commit()
    db.close()

init_user_api_keys_table()

@app.route('/api/me/keys', methods=['GET'])
def api_me_list_keys():
    """List API keys for the logged-in user's business."""
    bid = session.get('business_id')
    if not bid:
        return jsonify({'error': 'Not logged in'}), 401
    db = get_db()
    db.row_factory = sqlite3.Row
    c = db.cursor()
    c.execute("""SELECT id, name, description, permissions, created_at, 
                 last_used_at, expires_at, active, raw_prefix
                 FROM user_api_keys WHERE business_id=? ORDER BY created_at DESC""", (bid,))
    keys = [dict(r) for r in c.fetchall()]
    db.close()
    return jsonify({'keys': keys, 'total': len(keys)})

@app.route('/api/me/keys/generate', methods=['POST'])
def api_me_generate_key():
    """Generate a new API key for the logged-in user's business."""
    bid = session.get('business_id')
    if not bid:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.get_json(silent=True) or {}
    name = data.get('name', 'My API Key').strip()
    description = data.get('description', '')
    if not name:
        return jsonify({'error': 'Key name is required'}), 400
    
    import uuid, hashlib
    raw_key = f"dz_{uuid.uuid4().hex}_{uuid.uuid4().hex[:16]}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_id = f"key_{uuid.uuid4().hex[:12]}"
    raw_prefix = raw_key[:16] + '...'
    
    db = get_db()
    c = db.cursor()
    c.execute("""INSERT INTO user_api_keys (id, key_hash, raw_prefix, name, description, permissions, business_id)
                 VALUES (?, ?, ?, ?, ?, 'read,write', ?)""",
              (key_id, key_hash, raw_prefix, name, description, bid))
    db.commit()
    db.close()
    
    git_auto_commit(f'user generated API key {name}')
    return jsonify({
        'success': True, 'key_id': key_id, 'api_key': raw_key,
        'name': name, 'raw_prefix': raw_prefix,
        'warning': 'Save this key now — it will not be shown again!'
    })

@app.route('/api/me/keys/<key_id>/revoke', methods=['POST'])
def api_me_revoke_key(key_id):
    """Revoke an API key."""
    bid = session.get('business_id')
    if not bid:
        return jsonify({'error': 'Not logged in'}), 401
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE user_api_keys SET active=0 WHERE id=? AND business_id=?", (key_id, bid))
    db.commit()
    affected = c.rowcount
    db.close()
    if affected == 0:
        return jsonify({'error': 'Key not found'}), 404
    git_auto_commit(f'revoked API key {key_id}')
    return jsonify({'success': True, 'message': 'Key revoked'})

@app.route('/api/me/keys/<key_id>/delete', methods=['DELETE'])
def api_me_delete_key(key_id):
    """Permanently delete an API key."""
    bid = session.get('business_id')
    if not bid:
        return jsonify({'error': 'Not logged in'}), 401
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM user_api_keys WHERE id=? AND business_id=?", (key_id, bid))
    db.commit()
    affected = c.rowcount
    db.close()
    if affected == 0:
        return jsonify({'error': 'Key not found'}), 404
    git_auto_commit(f'deleted API key {key_id}')
    return jsonify({'success': True, 'message': 'Key permanently deleted'})

@app.route('/api/me/keys/<key_id>/reactivate', methods=['POST'])
def api_me_reactivate_key(key_id):
    """Reactivate a revoked API key."""
    bid = session.get('business_id')
    if not bid:
        return jsonify({'error': 'Not logged in'}), 401
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE user_api_keys SET active=1 WHERE id=? AND business_id=?", (key_id, bid))
    db.commit()
    affected = c.rowcount
    db.close()
    if affected == 0:
        return jsonify({'error': 'Key not found'}), 404
    return jsonify({'success': True, 'message': 'Key reactivated'})

threading.Thread(target=campaign_scheduler, daemon=True).start()

if __name__ == '__main__':
    print("🚀 Diazites Dashboard")
    print(f"📊 DB: {DB_PATH}")
    print("🌐 http://localhost:8085")
    app.run(host='0.0.0.0', port=8085, debug=False)
