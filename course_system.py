#!/usr/bin/env python3
"""ShopZario Course System — Full LMS: lessons, quizzes, workbooks, slides, certificates, AI generators, member area."""
import os, sys, json, sqlite3, uuid, re, io, base64, hashlib, hmac, datetime
from flask import Blueprint, render_template_string, jsonify, request, redirect, session, url_for, send_file, make_response

DB_PATH = "/root/voice-agent-businesses.db"
COURSE_FILES_DIR = "/root/voice-agent-manager/static/course_files"
os.makedirs(COURSE_FILES_DIR, exist_ok=True)
os.makedirs(COURSE_FILES_DIR + "/workbooks", exist_ok=True)
os.makedirs(COURSE_FILES_DIR + "/slides", exist_ok=True)
os.makedirs(COURSE_FILES_DIR + "/certificates", exist_ok=True)

_LAYOUT_HEAD = ""
_TOP_NAV = ""
_LAYOUT_FOOT = ""

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS course_lessons (
        id TEXT PRIMARY KEY, product_id TEXT NOT NULL, module_num INTEGER DEFAULT 1,
        title TEXT, slug TEXT, content TEXT, video_url TEXT DEFAULT '',
        duration_min INTEGER DEFAULT 0, lesson_type TEXT DEFAULT 'text',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS course_quizzes (
        id TEXT PRIMARY KEY, course_id TEXT NOT NULL, module_id TEXT,
        title TEXT DEFAULT 'Quiz', passing_score INTEGER DEFAULT 70,
        time_limit_min INTEGER DEFAULT 0, attempts_allowed INTEGER DEFAULT 3,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS quiz_questions (
        id TEXT PRIMARY KEY, quiz_id TEXT NOT NULL,
        question_text TEXT NOT NULL, question_type TEXT DEFAULT 'multiple_choice',
        options TEXT DEFAULT '[]', correct_answer TEXT,
        points INTEGER DEFAULT 10, sort_order INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS quiz_attempts (
        id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, quiz_id TEXT NOT NULL,
        score INTEGER DEFAULT 0, total_questions INTEGER DEFAULT 0,
        correct_count INTEGER DEFAULT 0, answers TEXT DEFAULT '[]',
        passed INTEGER DEFAULT 0, attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS course_workbooks (
        id TEXT PRIMARY KEY, course_id TEXT NOT NULL, title TEXT,
        file_path TEXT, file_size INTEGER DEFAULT 0,
        description TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS course_slides (
        id TEXT PRIMARY KEY, course_id TEXT NOT NULL, module_id TEXT,
        title TEXT, file_path TEXT, file_size INTEGER DEFAULT 0,
        slides_count INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS course_certificates (
        id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, course_id TEXT NOT NULL,
        cert_number TEXT UNIQUE, issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_modules INTEGER DEFAULT 0, quiz_avg_score INTEGER DEFAULT 0
    )""")
    try:
        c.execute("ALTER TABLE course_progress ADD COLUMN quiz_score INTEGER DEFAULT 0")
    except: pass
    try:
        c.execute("ALTER TABLE course_progress ADD COLUMN quiz_passed INTEGER DEFAULT 0")
    except: pass
    conn.commit(); conn.close()

def get_customer_id():
    return session.get('customer_id')

def admin_check():
    return session.get('admin_logged_in')

# ── MEMBER AREA DASHBOARD ──
def member_dashboard():
    cid = get_customer_id()
    if not cid: return redirect('/account/login?next=/member')
    db = get_db()
    courses = db.execute("""
        SELECT p.id, p.title, p.slug, p.hero_image_url, ca.granted_at,
               (SELECT COUNT(*) FROM course_modules WHERE product_id=p.id) as total_mods,
               (SELECT COUNT(*) FROM course_progress cp JOIN course_modules cm ON cp.module_id=cm.id WHERE cm.product_id=p.id AND cp.customer_id=? AND cp.completed=1) as done_mods
        FROM course_access ca JOIN products p ON ca.product_id=p.id
        WHERE ca.customer_id=? ORDER BY ca.granted_at DESC
    """, (cid, cid)).fetchall()
    orders = db.execute("""
        SELECT po.id, p.title, p.product_type, po.amount, po.created_at, p.id as pid
        FROM product_orders po JOIN products p ON po.product_id=p.id
        WHERE po.customer_email=(SELECT email FROM customer_accounts WHERE id=?)
        ORDER BY po.created_at DESC LIMIT 10
    """, (cid,)).fetchall()
    customer = db.execute("SELECT name, email, created_at FROM customer_accounts WHERE id=?", (cid,)).fetchone()
    db.close()

    course_cards = ""
    for c in courses:
        pct = int((c[5]/max(c[4],1))*100) if c[4] else 0
        course_cards += f'''<a href="/course/{c[0]}/" class="card p-4 hover:border-purple-500/40 transition block">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center text-xl">📖</div>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-semibold text-white truncate">{c[1][:60]}</div>
              <div class="text-xs text-[#7a7a8e]">{c[5]}/{c[4]} modules</div>
              <div class="mt-1 h-1.5 bg-[#1a1a26] rounded-full overflow-hidden"><div class="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full" style="width:{pct}%"></div></div>
            </div>
            <span class="text-purple-400">&rarr;</span>
          </div>
        </a>'''

    order_rows = ""
    for o in orders:
        order_rows += f'''<tr class="border-b border-[#1a1a26]">
            <td class="py-2 text-xs">{o["title"][:40]}</td>
            <td class="py-2 text-xs text-[#7a7a8e]">${o["amount"]:.2f}</td>
            <td class="py-2 text-xs text-[#5c5c70]">{(o["created_at"] or "")[:10]}</td>
            <td class="py-2 text-right"><a href="/product/{o["pid"]}" class="text-xs text-purple-400 hover:underline">View</a></td>
        </tr>'''

    name = customer["name"] if customer else "Member"
    email = customer["email"] if customer else ""
    member_since = (customer.get("created_at","") or "")[:10] if customer else ""
    initial = name[0].upper() if name else "M"

    html = f'''{_LAYOUT_HEAD}
<div class="min-h-screen" style="background:#07070c">
  <div class="sticky top-0 z-40 glass border-b border-[#1e1e2e]">
    <div class="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <a href="/" class="text-sm font-bold flex items-center gap-1.5"><span class="w-6 h-6 rounded-md bg-gradient-to-br from-[#a855f7] to-[#ec4899] flex items-center justify-center text-white text-[10px]">S</span>ShopZario</a>
        <span class="text-xs text-[#5c5c70]">/</span>
        <span class="text-sm text-white font-medium">Member Area</span>
      </div>
      <div class="flex items-center gap-3">
        <a href="/my-courses/" class="nav-link text-xs"><i class="fas fa-book-open mr-1"></i>My Courses</a>
        <a href="/account/logout" class="text-xs text-red-400 hover:text-red-300"><i class="fas fa-sign-out-alt mr-1"></i>Logout</a>
      </div>
    </div>
  </div>

  <div class="max-w-6xl mx-auto px-4 py-6">
    <div class="card p-6 mb-6 bg-gradient-to-r from-[#1a0a2e] to-[#0e0e16]">
      <div class="flex items-center gap-4">
        <div class="w-14 h-14 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-2xl font-bold text-white">{initial}</div>
        <div>
          <h1 class="text-xl font-bold">Welcome, {name.split()[0] if name else "Member"}!</h1>
          <p class="text-xs text-[#7a7a8e]">{email} &middot; Member since {member_since}</p>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-bold text-sm"><i class="fas fa-book-open text-purple-400 mr-1"></i> My Courses</h2>
          <a href="/" class="text-xs text-purple-400 hover:underline">Browse All</a>
        </div>
        <div class="space-y-3">
          {course_cards if course_cards else '<div class="card p-8 text-center"><div class="text-4xl mb-3">📚</div><p class="text-sm text-[#5c5c70]">No courses yet. <a href="/" class="text-purple-400 hover:underline">Browse courses</a></p></div>'}
        </div>
      </div>

      <div>
        <div class="card p-4 mb-4">
          <h3 class="font-bold text-xs text-[#7a7a8e] uppercase tracking-wider mb-3">Quick Links</h3>
          <div class="space-y-2">
            <a href="/my-courses/" class="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 text-sm"><span class="w-7 h-7 rounded-lg bg-purple-500/10 flex items-center justify-center text-xs">📖</span> My Courses</a>
            <a href="/account/orders" class="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 text-sm"><span class="w-7 h-7 rounded-lg bg-blue-500/10 flex items-center justify-center text-xs">🛒</span> Order History</a>
            <a href="/account/settings" class="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 text-sm"><span class="w-7 h-7 rounded-lg bg-green-500/10 flex items-center justify-center text-xs">⚙️</span> Account Settings</a>
            <a href="/certificates" class="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 text-sm"><span class="w-7 h-7 rounded-lg bg-amber-500/10 flex items-center justify-center text-xs">🏆</span> My Certificates</a>
          </div>
        </div>

        <div class="card p-4">
          <h3 class="font-bold text-xs text-[#7a7a8e] uppercase tracking-wider mb-3">Recent Orders</h3>
          <table class="w-full">
            <thead><tr class="text-[10px] text-[#5c5c70] uppercase"><th class="text-left py-1">Item</th><th class="text-left py-1">Price</th><th class="text-left py-1">Date</th><th></th></tr></thead>
            <tbody>{order_rows if order_rows else '<tr><td colspan="4" class="py-4 text-center text-xs text-[#5c5c70]">No orders yet</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>
{_LAYOUT_FOOT}'''
    return html

# ── COURSE SALES PAGE ──
def course_sales_page(product_id):
    db = get_db()
    p = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not p: db.close(); return "Course not found", 404
    p = dict(p)
    modules = db.execute("SELECT id, module_num, title FROM course_modules WHERE product_id=? ORDER BY module_num ASC", (product_id,)).fetchall()
    quizzes = db.execute("SELECT id, title, passing_score FROM course_quizzes WHERE course_id=?", (product_id,)).fetchall()
    wbs = db.execute("SELECT title, description FROM course_workbooks WHERE course_id=?", (product_id,)).fetchall()
    cid = get_customer_id()
    has_access = False
    if cid:
        a = db.execute("SELECT id FROM course_access WHERE customer_id=? AND product_id=?", (cid, product_id)).fetchone()
        if a: has_access = True
    db.close()

    mod_list = ""
    for i, m in enumerate(modules):
        hl = "bg-purple-500/5 border border-purple-500/10" if i == 0 else "hover:bg-white/5"
        mod_list += f'<div class="flex items-center gap-3 p-3 rounded-lg {hl}"><span class="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center text-xs font-bold text-purple-300">M{m[1]:02d}</span><span class="text-sm">{m[2][:60]}</span><span class="ml-auto text-xs text-[#5c5c70]"><i class="far fa-file-alt"></i></span></div>'

    features = f'''<div class="flex flex-wrap gap-2 mb-4">
      <span class="tag tag-purple"><i class="far fa-file-alt mr-1"></i>{len(modules)} lessons</span>'''
    if quizzes:
        features += f'<span class="tag tag-amber"><i class="fas fa-question-circle mr-1"></i>{len(quizzes)} quizzes</span>'
    if wbs:
        features += f'<span class="tag tag-green"><i class="fas fa-download mr-1"></i>{len(wbs)} workbooks</span>'
    features += '<span class="tag tag-blue"><i class="fas fa-award mr-1"></i>Certificate</span><span class="tag tag-green"><i class="fas fa-infinity mr-1"></i>Lifetime access</span></div>'

    btn = f'<a href="/course/{product_id}/" class="btn-primary w-full justify-center text-base" style="padding:16px"><i class="fas fa-play-circle mr-2"></i> Continue Learning</a>' if has_access else f'<form action="/api/checkout/{product_id}" method="POST"><button type="submit" class="btn-primary w-full justify-center text-base" style="padding:16px"><i class="fas fa-shopping-cart mr-2"></i> Enroll Now — ${p.get("price",0):.2f}</button></form>'

    html = f'''{_LAYOUT_HEAD}{_TOP_NAV}
<div class="max-w-5xl mx-auto px-4 py-6">
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <div class="lg:col-span-2">
      <div class="card p-6">
        <div class="text-3xl mb-3">📚</div>
        <h1 class="text-2xl font-bold text-white mb-2">{p["title"]}</h1>
        {features}
        <div class="text-sm text-[#c0c0d0] leading-relaxed mt-4">{p.get("description","") or ""}</div>
      </div>
      <div class="card p-6 mt-4">
        <h2 class="font-bold text-lg mb-4"><i class="fas fa-list text-purple-400 mr-2"></i>Course Curriculum</h2>
        <div class="space-y-1">{mod_list}</div>
      </div>
      <div class="card p-6 mt-4">
        <h2 class="font-bold text-lg mb-4"><i class="fas fa-gift text-purple-400 mr-2"></i>What's Included</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div class="flex items-start gap-3 p-3 rounded-lg bg-white/5"><span class="text-lg mt-0.5">📹</span><div><div class="text-sm font-semibold">Video Lessons</div><div class="text-xs text-[#7a7a8e]">Professional video walkthroughs</div></div></div>
          <div class="flex items-start gap-3 p-3 rounded-lg bg-white/5"><span class="text-lg mt-0.5">📝</span><div><div class="text-sm font-semibold">Quizzes</div><div class="text-xs text-[#7a7a8e]">Test your knowledge</div></div></div>
          <div class="flex items-start gap-3 p-3 rounded-lg bg-white/5"><span class="text-lg mt-0.5">📄</span><div><div class="text-sm font-semibold">Workbooks</div><div class="text-xs text-[#7a7a8e]">Hands-on exercises</div></div></div>
          <div class="flex items-start gap-3 p-3 rounded-lg bg-white/5"><span class="text-lg mt-0.5">📊</span><div><div class="text-sm font-semibold">Slides</div><div class="text-xs text-[#7a7a8e]">Presentation decks</div></div></div>
          <div class="flex items-start gap-3 p-3 rounded-lg bg-white/5"><span class="text-lg mt-0.5">🏆</span><div><div class="text-sm font-semibold">Certificate</div><div class="text-xs text-[#7a7a8e]">Upon completion</div></div></div>
          <div class="flex items-start gap-3 p-3 rounded-lg bg-white/5"><span class="text-lg mt-0.5">♾️</span><div><div class="text-sm font-semibold">Lifetime Access</div><div class="text-xs text-[#7a7a8e]">Learn at your own pace</div></div></div>
        </div>
      </div>
    </div>
    <div>
      <div class="card p-6 sticky" style="top:90px">
        <div class="text-center mb-4">
          <div class="w-full h-40 rounded-xl bg-gradient-to-br from-purple-500/15 to-pink-500/15 flex items-center justify-center text-5xl mb-4">📚</div>
          <div class="text-3xl font-black text-white">${p.get("price",0):.2f}</div>
          <div class="text-xs text-[#5c5c70] mt-1">One-time payment, lifetime access</div>
        </div>
        {btn}
        <div class="mt-4 space-y-2 text-xs text-[#5c5c70]">
          <div class="flex items-center gap-2"><i class="fas fa-check-circle text-green-400 w-4"></i> Instant access</div>
          <div class="flex items-center gap-2"><i class="fas fa-check-circle text-green-400 w-4"></i> Downloadable materials</div>
          <div class="flex items-center gap-2"><i class="fas fa-check-circle text-green-400 w-4"></i> 30-day refund guarantee</div>
        </div>
      </div>
    </div>
  </div>
</div>
{_LAYOUT_FOOT}'''
    return html

# ── COURSE PLAYER ──
def course_player_view(product_id, module_slug=None):
    cid = get_customer_id()
    if not cid: return redirect('/account/login?next=/course/' + product_id)
    db = get_db()
    access = db.execute("SELECT id FROM course_access WHERE customer_id=? AND product_id=?", (cid, product_id)).fetchone()
    if not access:
        order = db.execute("SELECT co.id FROM customer_orders co JOIN products p ON co.product_id=p.id WHERE co.customer_id=? AND co.product_id=? AND co.status='completed'", (cid, product_id)).fetchone()
        if order:
            aid = str(uuid.uuid4())[:12]
            db.execute("INSERT INTO course_access (id, customer_id, product_id, order_id) VALUES (?,?,?,?)", (aid, cid, product_id, order[0]))
            db.commit()
        else:
            db.close()
            return (f'''{_LAYOUT_HEAD}{_TOP_NAV}<div class="max-w-xl mx-auto px-4 py-20 text-center">
              <div class="text-5xl mb-4">🔒</div><h1 class="text-xl font-bold text-white mb-2">Access Required</h1>
              <p class="text-sm text-[#7a7a8e] mb-6">Purchase this course to access modules.</p>
              <a href="/product/{product_id}" class="btn-primary">View Course</a></div>{_LAYOUT_FOOT}''')
    product = db.execute("SELECT id, title FROM products WHERE id=?", (product_id,)).fetchone()
    if not product: return "Not found", 404
    modules = db.execute("SELECT id, module_num, title, slug FROM course_modules WHERE product_id=? ORDER BY module_num ASC", (product_id,)).fetchall()
    current = None
    if module_slug:
        current = db.execute("SELECT * FROM course_modules WHERE product_id=? AND slug=?", (product_id, module_slug)).fetchone()
    if not current and modules:
        current = db.execute("SELECT * FROM course_modules WHERE product_id=? ORDER BY module_num ASC LIMIT 1", (product_id,)).fetchone()
    if not current: db.close(); return "No modules found", 404
    current = dict(current)

    progress = {}; quiz_scores = {}
    for m in modules:
        done = db.execute("SELECT completed, quiz_score, quiz_passed FROM course_progress WHERE customer_id=? AND module_id=?", (cid, m[0])).fetchone()
        if done:
            progress[m[0]] = done[0]
            quiz_scores[m[0]] = {"score": done[1] or 0, "passed": done[2] or 0}
        else:
            progress[m[0]] = 0; quiz_scores[m[0]] = {"score": 0, "passed": 0}

    if not progress.get(current['id']):
        if not db.execute("SELECT id FROM course_progress WHERE customer_id=? AND module_id=?", (cid, current['id'])).fetchone():
            db.execute("INSERT OR IGNORE INTO course_progress (id, customer_id, module_id) VALUES (?,?,?)", (str(uuid.uuid4())[:12], cid, current['id']))
            db.commit()

    all_quizzes = {q["module_id"]: dict(q) for q in db.execute("SELECT * FROM course_quizzes WHERE course_id=?", (product_id,)).fetchall()}
    workbooks = db.execute("SELECT * FROM course_workbooks WHERE course_id=?", (product_id,)).fetchall()
    slides = db.execute("SELECT * FROM course_slides WHERE module_id=? OR (module_id='' AND course_id=?) ORDER BY created_at ASC", (current['id'], product_id)).fetchall()
    current_quiz = all_quizzes.get(current['id'])
    all_done = all(progress[m[0]] for m in modules) if modules else False

    if all_done and all_quizzes:
        quizzes_passed = True
        for q in all_quizzes.values():
            last = db.execute("SELECT passed FROM quiz_attempts WHERE customer_id=? AND quiz_id=? ORDER BY attempted_at DESC LIMIT 1", (cid, q["id"])).fetchone()
            if not last or not last[0]: quizzes_passed = False; break
        if quizzes_passed:
            existing = db.execute("SELECT id FROM course_certificates WHERE customer_id=? AND course_id=?", (cid, product_id)).fetchone()
            if not existing:
                cert_num = "CERT" + uuid.uuid4().hex[:10].upper()
                avg_score = 0; qcount = 0
                for q in all_quizzes.values():
                    last = db.execute("SELECT score FROM quiz_attempts WHERE customer_id=? AND quiz_id=? ORDER BY attempted_at DESC LIMIT 1", (cid, q["id"])).fetchone()
                    if last: avg_score += last[0]; qcount += 1
                avg_score = avg_score // qcount if qcount else 0
                db.execute("INSERT INTO course_certificates (id, customer_id, course_id, cert_number, completed_modules, quiz_avg_score) VALUES (?,?,?,?,?,?)",
                          (str(uuid.uuid4())[:12], cid, product_id, cert_num, len(modules), avg_score))
                db.commit()
    db.close()

    sidebar = ""
    for m in modules:
        mid = m[0]; num = m[1]; t = m[2]; su = m[3]
        active = "bg-purple-500/10 border-purple-500/30" if mid == current['id'] else "hover:bg-white/5 border-transparent"
        icon = "✅" if progress.get(mid) else ("🔄" if mid == current['id'] else "○")
        q_icon = ""
        if mid in all_quizzes:
            qs = quiz_scores.get(mid, {})
            if qs.get("passed"): q_icon = ' <span class="text-green-400 text-[10px]">✓Quiz</span>'
            elif qs.get("score", 0) > 0: q_icon = f' <span class="text-amber-400 text-[10px]">{qs["score"]}%</span>'
            else: q_icon = ' <span class="text-[#5c5c70] text-[10px]">📝</span>'
        sidebar += f'''<a href="/course/{product_id}/{su}" class="flex items-center gap-2 p-2.5 rounded-lg text-sm transition {active}">
          <span class="text-xs">{icon}</span>
          <span class="text-xs text-[#5c5c70] shrink-0">M{num:02d}</span>
          <span class="text-xs text-white truncate flex-1">{t[:40]}</span>{q_icon}</a>'''

    content_html = current.get("content", "") or ""
    content_html = re.sub(r'<script[^>]*>.*?</script>', '', content_html, flags=re.DOTALL)

    quiz_section = ""
    if current_quiz:
        qid = current_quiz["id"]
        last_attempt = db.execute("SELECT * FROM quiz_attempts WHERE customer_id=? AND quiz_id=? ORDER BY attempted_at DESC LIMIT 1", (cid, qid)).fetchone()
        attempts = db.execute("SELECT COUNT(*) FROM quiz_attempts WHERE customer_id=? AND quiz_id=?", (cid, qid)).fetchone()[0]
        remaining = max(0, (current_quiz["attempts_allowed"] or 3) - attempts)
        if last_attempt and last_attempt["passed"]:
            quiz_section = f'''<div class="mt-6 p-4 rounded-xl bg-green-500/10 border border-green-500/20">
              <div class="flex items-center gap-3"><span class="text-2xl">🎉</span><div><div class="font-bold text-sm text-green-400">Quiz Passed!</div>
              <div class="text-xs text-[#7a7a8e]">Score: {last_attempt["score"]}% ({last_attempt["correct_count"]}/{last_attempt["total_questions"]})</div></div></div></div>'''
        elif last_attempt and not last_attempt["passed"]:
            quiz_section = f'''<div class="mt-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
              <div class="flex items-center gap-3"><span class="text-2xl">😅</span><div><div class="font-bold text-sm text-amber-400">Score: {last_attempt["score"]}%</div>
              <div class="text-xs text-[#7a7a8e]">{remaining} attempt(s) remaining</div></div></div></div>'''
        if remaining > 0 or not last_attempt:
            quiz_section += f'''<div class="mt-4 p-4 rounded-xl bg-white/5 border border-white/10">
              <h3 class="font-bold text-sm mb-3"><i class="fas fa-question-circle text-purple-400 mr-1"></i> Module Quiz — {current_quiz["title"]}</h3>
              <div class="text-xs text-[#7a7a8e] mb-3">Passing score: {current_quiz["passing_score"]}% &middot; Attempts left: {remaining}</div>
              <button onclick="loadQuiz('{qid}')" class="btn-primary text-xs" style="padding:10px 20px"><i class="fas fa-play mr-1"></i> Start Quiz</button>
              <div id="quizContainer"></div></div>'''

    materials_section = ""
    if workbooks or slides:
        wb_items = ""
        for wb in workbooks:
            size = wb["file_size"] or 0
            sz = f"{size//1024}KB" if size > 1024 else f"{size}B"
            wb_items += f'''<a href="/course/download/workbook/{wb["id"]}" class="flex items-center gap-3 p-3 rounded-lg hover:bg-white/5">
              <span class="text-lg">📄</span><div class="flex-1"><div class="text-sm font-medium">{wb["title"]}</div><div class="text-xs text-[#5c5c70]">{sz}</div></div>
              <span class="text-purple-400 text-xs"><i class="fas fa-download"></i></span></a>'''
        sl_items = ""
        for sl in slides:
            sl_items += f'''<a href="/course/download/slides/{sl["id"]}" class="flex items-center gap-3 p-3 rounded-lg hover:bg-white/5">
              <span class="text-lg">📊</span><div class="flex-1"><div class="text-sm font-medium">{sl["title"]}</div><div class="text-xs text-[#5c5c70]">{sl.get("slides_count",0)} slides</div></div>
              <span class="text-purple-400 text-xs"><i class="fas fa-download"></i></span></a>'''
        if wb_items or sl_items:
            materials_section = f'''<div class="mt-6 p-4 rounded-xl bg-white/5 border border-white/10">
              <h3 class="font-bold text-sm mb-3"><i class="fas fa-download text-green-400 mr-1"></i> Course Materials</h3>{wb_items}{sl_items}</div>'''

    prev_link = next_link = ""
    for i, m in enumerate(modules):
        if m[0] == current['id']:
            if i > 0: prev_link = f'<a href="/course/{product_id}/{modules[i-1][3]}" class="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1"><span>&larr;</span> {modules[i-1][2][:30]}</a>'
            if i < len(modules)-1: next_link = f'<a href="/course/{product_id}/{modules[i+1][3]}" class="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1">{modules[i+1][2][:30]} <span>&rarr;</span></a>'
            break

    page = _LAYOUT_HEAD.replace('</head>', '''<style>
.course-content h1{font-size:1.5rem;font-weight:700;margin:1.5rem 0 0.5rem;color:#f1f1f5}
.course-content h2{font-size:1.25rem;font-weight:600;margin:1.25rem 0 0.4rem;color:#e8e8f0}
.course-content h3{font-size:1.1rem;font-weight:600;margin:1rem 0 0.3rem;color:#d0d0e0}
.course-content p{margin:0.5rem 0;line-height:1.7;color:#c0c0d0}
.course-content ul,.course-content ol{margin:0.5rem 0 0.5rem 1.5rem;line-height:1.7}
.course-content code{background:#1a1a26;padding:0.15rem 0.4rem;border-radius:4px;font-size:0.85em;color:#a855f7}
.course-content pre{background:#0e0e16;padding:1rem;border-radius:12px;overflow-x:auto;margin:0.8rem 0;border:1px solid #1a1a26}
.course-content blockquote{border-left:3px solid #a855f7;padding-left:1rem;margin:0.8rem 0;color:#8080a0;font-style:italic}
.course-content img{max-width:100%;border-radius:12px;margin:1rem 0}
.quiz-option{padding:12px 16px;border-radius:10px;cursor:pointer;transition:all .2s;border:1px solid #1e1e2e}
.quiz-option:hover{background:rgba(168,85,247,0.08);border-color:#a855f7}
</style></head>''') + _TOP_NAV + f'''
<div class="max-w-7xl mx-auto px-4 py-6">
  <div class="flex items-center gap-2 text-xs text-[#5c5c70] mb-4">
    <a href="/member" class="hover:text-purple-400">Member Area</a><span>/</span>
    <a href="/my-courses/" class="hover:text-purple-400">My Courses</a><span>/</span>
    <span class="text-white">{product["title"][:40]}</span>
  </div>
  <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
    <div class="lg:col-span-1">
      <div class="card p-3 space-y-0.5 sticky" style="top:80px">
        <div class="flex items-center gap-2 text-xs font-semibold text-[#7a7a8e] uppercase tracking-wider mb-2 px-2"><i class="fas fa-list"></i> Modules</div>
        {sidebar}
      </div>
    </div>
    <div class="lg:col-span-3">
      <div class="card p-6 md:p-8">
        <h1 class="text-lg font-bold text-white mb-4">M{current["module_num"]:02d}: {current["title"]}</h1>
        {f'<div class="mb-6 aspect-video rounded-xl overflow-hidden bg-black"><iframe class="w-full h-full" src="'+current.get("video_url","")+'" frameborder="0" allowfullscreen></iframe></div>' if current.get("video_url") else ""}
        <div class="course-content">{content_html}</div>
        {quiz_section}
        {materials_section}
        <div class="mt-10 pt-6 border-t border-[#1a1a26]">
          <div class="flex items-center justify-between">
            <div>{prev_link}</div>
            <form method="POST" action="/course/{product_id}/{current["slug"]}/complete">
              <button type="submit" class="btn-primary text-xs">{"✅ Mark Complete" if not progress.get(current["id"]) else "✅ Completed"}</button>
            </form>
            <div>{next_link}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
async function loadQuiz(quizId){{
  const c = document.getElementById('quizContainer');
  c.innerHTML = '<div class="text-center py-4"><i class="fas fa-spinner fa-spin text-purple-400"></i><p class="text-xs text-[#7a7a8e] mt-2">Loading quiz...</p></div>';
  try{{
    const r = await fetch('/api/quiz/'+quizId+'/questions');
    const data = await r.json();
    if(data.error){{c.innerHTML='<p class="text-red-400 text-xs">'+data.error+'</p>';return;}}
    let html = '<div class="quiz-form mt-3 space-y-4">';
    data.questions.forEach((q,i)=>{{
      html += '<div class="p-4 rounded-xl bg-[#0e0e16] border border-[#1e1e2e]">';
      html += '<div class="text-sm font-medium mb-2">'+(i+1)+'. '+q.question_text+'</div><div class="space-y-1.5">';
      const opts = JSON.parse(q.options||'[]');
      opts.forEach(o=>{{
        const v = btoa(o).replace(/=/g,'');
        html += '<label class="quiz-option flex items-center gap-3"><input type="radio" name="q_'+q.id+'" value="'+v+'" class="accent-purple-500"><span class="text-sm">'+o+'</span></label>';
      }});
      html += '</div></div>';
    }});
    html += '<button onclick="submitQuiz(\\''+quizId+'\\')" class="btn-primary w-full justify-center mt-3" style="padding:12px"><i class="fas fa-check-circle mr-1"></i> Submit Answers</button>';
    html += '<div id="quizResult"></div></div>';
    c.innerHTML = html;
  }}catch(e){{c.innerHTML='<p class="text-red-400 text-xs">Error loading quiz</p>';}}
}}
async function submitQuiz(quizId){{
  const form = document.querySelector('.quiz-form');
  const answers = [];
  form.querySelectorAll('input[type=radio]:checked').forEach(inp=>{{
    answers.push({{question_id: inp.name.replace('q_',''), answer: atob(inp.value)}});
  }});
  const r = await fetch('/api/quiz/'+quizId+'/submit',{{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{answers:answers}})
  }});
  const data = await r.json();
  const div = document.getElementById('quizResult');
  if(data.passed){{
    div.innerHTML = '<div class="mt-3 p-4 rounded-xl bg-green-500/10 border border-green-500/20 text-center"><div class="text-3xl mb-2">🎉</div><div class="font-bold text-green-400">Passed! '+data.score+'%</div><div class="text-xs text-[#7a7a8e] mt-1">'+data.correct+'/'+data.total+' correct</div><button onclick="location.reload()" class="btn-primary text-xs mt-3" style="padding:8px 20px">Continue</button></div>';
  }}else{{
    div.innerHTML = '<div class="mt-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-center"><div class="text-3xl mb-2">😅</div><div class="font-bold text-amber-400">Score: '+data.score+'%</div><div class="text-xs text-[#7a7a8e] mt-1">'+data.correct+'/'+data.total+' correct &middot; Passing: 70%</div><button onclick="loadQuiz(\\''+quizId+'\\')" class="btn-outline text-xs mt-3" style="padding:8px 20px">Retry</button></div>';
  }}
}}
</script>
{_LAYOUT_FOOT}'''
    return page

# ── QUIZ API ──
def api_quiz_questions(quiz_id):
    db = get_db()
    q = db.execute("SELECT * FROM course_quizzes WHERE id=?", (quiz_id,)).fetchone()
    if not q: db.close(); return jsonify({"error":"Quiz not found"})
    questions = db.execute("SELECT id, question_text, options, points, sort_order FROM quiz_questions WHERE quiz_id=? ORDER BY sort_order ASC", (quiz_id,)).fetchall()
    db.close()
    return jsonify({"quiz": dict(q), "questions": [dict(r) for r in questions]})

def api_quiz_submit(quiz_id):
    cid = get_customer_id()
    if not cid: return jsonify({"error":"Not logged in"}),401
    data = request.get_json() or {}
    answers = data.get("answers", [])
    db = get_db()
    q = db.execute("SELECT * FROM course_quizzes WHERE id=?", (quiz_id,)).fetchone()
    if not q: return jsonify({"error":"Quiz not found"}),404
    attempts = db.execute("SELECT COUNT(*) FROM quiz_attempts WHERE customer_id=? AND quiz_id=?", (cid, quiz_id)).fetchone()[0]
    if attempts >= (q["attempts_allowed"] or 3):
        db.close(); return jsonify({"error":"No attempts remaining"}),403
    questions = db.execute("SELECT id, correct_answer, points FROM quiz_questions WHERE quiz_id=?", (quiz_id,)).fetchall()
    total = sum(r[2] or 10 for r in questions)
    correct = 0; earned = 0; answer_records = []
    for q_row in questions:
        qid = q_row["id"]; ca = q_row["correct_answer"]; pts = q_row["points"] or 10
        user_ans = ""
        for a in answers:
            if a.get("question_id") == qid: user_ans = a.get("answer",""); break
        is_ok = user_ans.strip().lower() == ca.strip().lower() if ca else False
        if is_ok: correct += 1; earned += pts
        answer_records.append({"qid":qid,"user":user_ans,"correct":ca,"ok":is_ok})
    score = int((earned/max(total,1))*100) if total else 0
    passed = 1 if score >= (q["passing_score"] or 70) else 0
    aid = str(uuid.uuid4())[:12]
    db.execute("INSERT INTO quiz_attempts (id,customer_id,quiz_id,score,total_questions,correct_count,answers,passed) VALUES (?,?,?,?,?,?,?,?)",
              (aid, cid, quiz_id, score, len(questions), correct, json.dumps(answer_records), passed))
    db.commit()
    if passed:
        mod = db.execute("SELECT module_id FROM course_quizzes WHERE id=?", (quiz_id,)).fetchone()
        if mod:
            db.execute("UPDATE course_progress SET quiz_score=?, quiz_passed=1 WHERE customer_id=? AND module_id=?", (score, cid, mod[0]))
            db.commit()
    db.close()
    return jsonify({"score":score,"correct":correct,"total":len(questions),"earned":earned,"max":total,"passed":bool(passed),"attempt":attempts+1})

# ── CERTIFICATES ──
def certificates_page():
    cid = get_customer_id()
    if not cid: return redirect('/account/login?next=/certificates')
    db = get_db()
    certs = db.execute("SELECT cc.*, p.title as course_title, p.slug FROM course_certificates cc JOIN products p ON cc.course_id=p.id WHERE cc.customer_id=? ORDER BY cc.issued_at DESC", (cid,)).fetchall()
    db.close()
    rows = ""
    for cert in certs:
        rows += f'''<div class="card p-5 flex items-center gap-4">
          <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-amber-500/20 to-yellow-500/20 flex items-center justify-center text-2xl">🏆</div>
          <div class="flex-1"><h3 class="font-bold text-sm">{cert["course_title"]}</h3>
          <div class="text-xs text-[#7a7a8e]">Cert: {cert["cert_number"]} &middot; {(cert["issued_at"] or "")[:10]}</div></div>
          <div class="text-right"><div class="text-xs text-green-400 mb-1">Completed</div>
          <a href="/certificate/view/{cert["id"]}" class="btn-primary text-xs" style="padding:8px 16px" target="_blank"><i class="fas fa-award mr-1"></i> View</a></div></div>'''
    if not rows:
        rows = '<div class="text-center py-16 text-[#5c5c70]"><div class="text-5xl mb-4">🏆</div><h2 class="text-lg font-bold text-white mb-2">No Certificates Yet</h2><p class="text-sm mb-6">Complete a course to earn your certificate.</p><a href="/my-courses/" class="btn-primary">My Courses</a></div>'
    html = f'''{_LAYOUT_HEAD}
<div class="sticky top-0 z-40 glass border-b border-[#1e1e2e]">
  <div class="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
    <div class="flex items-center gap-3"><a href="/" class="text-sm font-bold flex items-center gap-1.5"><span class="w-6 h-6 rounded-md bg-gradient-to-br from-[#a855f7] to-[#ec4899] flex items-center justify-center text-white text-[10px]">S</span>ShopZario</a>
    <span class="text-xs text-[#5c5c70]">/</span><span class="text-sm text-white font-medium">Certificates</span></div>
    <a href="/member" class="nav-link text-xs"><i class="fas fa-arrow-left mr-1"></i>Back to Member Area</a>
  </div>
</div>
<div class="max-w-4xl mx-auto px-4 py-8"><div class="space-y-4">{rows}</div></div>
{_LAYOUT_FOOT}'''
    return html

def certificate_view(cert_id):
    cid = get_customer_id()
    if not cid: return redirect('/account/login')
    db = get_db()
    cert = db.execute("SELECT cc.*, p.title as course_title, p.slug, p.description, ca.name as student_name, ca.email FROM course_certificates cc JOIN products p ON cc.course_id=p.id JOIN customer_accounts ca ON cc.customer_id=ca.id WHERE cc.id=? AND cc.customer_id=?", (cert_id, cid)).fetchone()
    db.close()
    if not cert: return "Certificate not found", 404
    name = cert["student_name"] or cert["email"].split("@")[0]
    html = f'''<!DOCTYPE html><html lang="en"><head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Certificate — {cert["course_title"]}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>@page{{size:landscape;margin:0}}body{{margin:0;padding:40px;background:#0a0a14;font-family:'Inter',sans-serif}}
    .cborder{{border:3px solid #a855f7;border-radius:20px;padding:8px;background:linear-gradient(135deg,#1a0a2e,#0e0e16)}}
    .cinner{{border:1px solid rgba(168,85,247,0.3);border-radius:14px;padding:60px;text-align:center}}</style></head><body>
    <div class="cborder"><div class="cinner">
        <div class="text-6xl mb-6">🏆</div>
        <div class="text-xs uppercase tracking-[0.3em] text-purple-400 mb-2">Certificate of Completion</div>
        <h1 class="text-4xl font-black text-white mb-2" style="font-family:'Playfair Display',serif">{cert["course_title"]}</h1>
        <div class="w-24 h-0.5 bg-gradient-to-r from-purple-500 to-pink-500 mx-auto my-6"></div>
        <p class="text-sm text-[#7a7a8e] mb-4">This certifies that</p>
        <h2 class="text-3xl font-bold text-white mb-4" style="font-family:'Playfair Display',serif">{name}</h2>
        <p class="text-sm text-[#7a7a8e] mb-6">has successfully completed the full course including all modules and assessments.</p>
        <div class="flex items-center justify-center gap-8 text-xs text-[#5c5c70]">
          <div><div class="font-semibold text-white">{cert["completed_modules"]}</div>Modules</div><div>|</div>
          <div><div class="font-semibold text-white">{cert["quiz_avg_score"]}%</div>Avg Score</div><div>|</div>
          <div><div class="font-semibold text-white">{cert["cert_number"]}</div>Cert #</div><div>|</div>
          <div><div class="font-semibold text-white">{(cert["issued_at"] or "")[:10]}</div>Issued</div>
        </div>
        <div class="mt-8 pt-6 border-t border-[#1e1e2e]">
          <div class="text-[10px] text-[#5c5c70]">ShopZario &middot; shopzario.com &middot; ID: {cert["cert_number"]}</div>
        </div>
    </div></div>
    <div class="text-center mt-4"><button onclick="window.print()" class="px-6 py-3 bg-purple-600 text-white rounded-xl text-sm font-semibold hover:bg-purple-700 transition cursor-pointer"><i class="fas fa-print mr-1"></i> Print Certificate</button></div>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    </body></html>'''
    return html

# ── DOWNLOADS ──
def download_workbook(wb_id):
    db = get_db()
    wb = db.execute("SELECT * FROM course_workbooks WHERE id=?", (wb_id,)).fetchone()
    db.close()
    if not wb or not wb["file_path"]: return "File not found", 404
    if not os.path.exists(wb["file_path"]): return "File not found on disk", 404
    return send_file(wb["file_path"], as_attachment=True, download_name=os.path.basename(wb["file_path"]))

def download_slides(sl_id):
    db = get_db()
    sl = db.execute("SELECT * FROM course_slides WHERE id=?", (sl_id,)).fetchone()
    db.close()
    if not sl or not sl["file_path"]: return "File not found", 404
    if not os.path.exists(sl["file_path"]): return "File not found on disk", 404
    return send_file(sl["file_path"], as_attachment=True, download_name=os.path.basename(sl["file_path"]))

# ── AI GENERATORS ──
def course_ai_generator(product_id):
    if not admin_check(): return redirect('/login')
    db = get_db()
    p = db.execute("SELECT id, title FROM products WHERE id=?", (product_id,)).fetchone()
    modules = db.execute("SELECT id, module_num, title FROM course_modules WHERE product_id=? ORDER BY module_num ASC", (product_id,)).fetchall()
    db.close()
    if not p: return "Course not found", 404
    mod_options = ""
    for m in modules:
        t = m["title"].replace("'","&#39;").replace('"',"&quot;")
        mod_options += f'<option value="{m["id"]}">M{m["module_num"]}: {t[:50]}</option>'
    html = f'''{_LAYOUT_HEAD}{_TOP_NAV}
<div class="max-w-6xl mx-auto px-4 py-6">
  <div class="flex items-center gap-2 text-xs text-[#5c5c70] mb-4">
    <a href="/hermes/products" class="hover:text-purple-400">Products</a><span>/</span>
    <a href="/hermes/product/{product_id}" class="hover:text-purple-400">{p["title"][:40]}</a><span>/</span>
    <span class="text-white">AI Generators</span>
  </div>
  <h1 class="text-xl font-bold mb-6"><i class="fas fa-wand-magic-sparkles text-purple-400 mr-2"></i> AI Course Generators</h1>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
    <div class="card p-5">
      <div class="text-2xl mb-2">📝</div><h3 class="font-bold text-sm mb-1">Lesson Content</h3>
      <p class="text-xs text-[#5c5c70] mb-3">Generate full lesson content with AI</p>
      <select id="aiModule" class="text-xs mb-2">{mod_options}</select>
      <input id="aiTopic" class="text-xs mb-2" placeholder="Lesson topic / keywords">
      <button onclick="genLesson()" class="btn-primary text-xs w-full justify-center" style="padding:10px"><i class="fas fa-wand-magic-sparkles mr-1"></i> Generate</button>
      <div id="lessonResult" class="mt-3"></div>
    </div>
    <div class="card p-5">
      <div class="text-2xl mb-2">📋</div><h3 class="font-bold text-sm mb-1">Quiz Questions</h3>
      <p class="text-xs text-[#5c5c70] mb-3">Auto-generate quiz from module content</p>
      <select id="aiQuizModule" class="text-xs mb-2">{mod_options}</select>
      <input id="aiQuizCount" class="text-xs mb-2" placeholder="Number of questions" value="5">
      <button onclick="genQuiz()" class="btn-primary text-xs w-full justify-center" style="padding:10px"><i class="fas fa-wand-magic-sparkles mr-1"></i> Generate Quiz</button>
      <div id="quizGenResult" class="mt-3"></div>
    </div>
    <div class="card p-5">
      <div class="text-2xl mb-2">💼</div><h3 class="font-bold text-sm mb-1">Sales Copy</h3>
      <p class="text-xs text-[#5c5c70] mb-3">Generate compelling course sales copy</p>
      <input id="aiSalesAngle" class="text-xs mb-2" placeholder="Sales angle / USP">
      <button onclick="genSales()" class="btn-primary text-xs w-full justify-center" style="padding:10px"><i class="fas fa-wand-magic-sparkles mr-1"></i> Generate</button>
      <div id="salesGenResult" class="mt-3"></div>
    </div>
  </div>
  <div class="card p-5 hidden" id="previewArea">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-bold text-sm" id="previewTitle">Generated Content</h3>
      <div class="flex gap-2">
        <button onclick="copyContent()" class="btn-secondary text-xs" style="padding:6px 12px"><i class="fas fa-copy mr-1"></i> Copy</button>
        <button onclick="saveContent()" class="btn-primary text-xs" style="padding:6px 12px"><i class="fas fa-save mr-1"></i> Save</button>
      </div>
    </div>
    <textarea id="previewContent" class="text-xs w-full" rows="15" style="font-family:monospace"></textarea>
  </div>
</div>
<script>
var lastGen = {{type:'', content:'', moduleId:''}};
async function genLesson(){{
  var m = document.getElementById('aiModule').value, t = document.getElementById('aiTopic').value;
  if(!m||!t) return alert('Select module and enter topic');
  var btn=event.target; btn.disabled=true; btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> Generating...';
  try{{
    var r = await fetch('/api/ai/generate-lesson',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{product_id:'{product_id}',module_id:m,topic:t}})}});
    var d = await r.json();
    if(d.content){{document.getElementById('previewArea').classList.remove('hidden');document.getElementById('previewTitle').textContent='📝 Lesson: '+t;document.getElementById('previewContent').value=d.content;lastGen={{type:'lesson',content:d.content,moduleId:m}};}}
    else alert('Error: '+(d.error||'Unknown'));
  }}catch(e){{alert('Error generating');}}finally{{btn.disabled=false;btn.innerHTML='<i class="fas fa-wand-magic-sparkles mr-1"></i> Generate';}}
}}
async function genQuiz(){{
  var m = document.getElementById('aiQuizModule').value, c = parseInt(document.getElementById('aiQuizCount').value)||5;
  if(!m) return alert('Select module');
  var btn=event.target; btn.disabled=true; btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> Generating...';
  try{{
    var r = await fetch('/api/ai/generate-quiz',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{product_id:'{product_id}',module_id:m,count:c}})}});
    var d = await r.json();
    if(d.questions){{document.getElementById('previewArea').classList.remove('hidden');document.getElementById('previewTitle').textContent='📋 Quiz: '+c+' questions';document.getElementById('previewContent').value=JSON.stringify(d.questions,null,2);lastGen={{type:'quiz',content:d.questions,moduleId:m}};}}
    else alert('Error: '+(d.error||'Unknown'));
  }}catch(e){{alert('Error generating');}}finally{{btn.disabled=false;btn.innerHTML='<i class="fas fa-wand-magic-sparkles mr-1"></i> Generate Quiz';}}
}}
async function genSales(){{
  var a = document.getElementById('aiSalesAngle').value;
  var btn=event.target; btn.disabled=true; btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> Generating...';
  try{{
    var r = await fetch('/api/ai/generate-sales',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{product_id:'{product_id}',angle:a||''}})}});
    var d = await r.json();
    if(d.content){{document.getElementById('previewArea').classList.remove('hidden');document.getElementById('previewTitle').textContent='💼 Sales Copy';document.getElementById('previewContent').value=d.content;lastGen={{type:'sales',content:d.content,moduleId:''}};}}
    else alert('Error: '+(d.error||'Unknown'));
  }}catch(e){{alert('Error generating');}}finally{{btn.disabled=false;btn.innerHTML='<i class="fas fa-wand-magic-sparkles mr-1"></i> Generate';}}
}}
function copyContent(){{var ta=document.getElementById('previewContent');ta.select();document.execCommand('copy');alert('Copied!');}}
function saveContent(){{
  if(lastGen.type=='lesson'&&lastGen.moduleId){{
    fetch('/api/ai/save-lesson',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{module_id:lastGen.moduleId,content:lastGen.content}})}}).then(r=>r.json()).then(d=>{{alert('Saved to module!');}}).catch(e=>alert('Error'));
  }}else if(lastGen.type=='quiz'){{
    fetch('/api/ai/save-quiz',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{product_id:'{product_id}',module_id:lastGen.moduleId,questions:lastGen.content}})}}).then(r=>r.json()).then(d=>{{alert('Quiz saved!');}}).catch(e=>alert('Error'));
  }}else alert('Copy manually');
}}
</script>
{_LAYOUT_FOOT}'''
    return html

# ── AI API ──
def api_generate_lesson():
    data = request.get_json() or {}
    topic = data.get("topic",""); module_id = data.get("module_id")
    db = get_db()
    mod = db.execute("SELECT title, content FROM course_modules WHERE id=?", (module_id,)).fetchone()
    product = db.execute("SELECT title FROM products WHERE id=?", (data.get("product_id",""),)).fetchone()
    db.close()
    prompt = f'Generate a professional lesson in HTML for the course "{product["title"] if product else "Course"}". Module: {mod["title"] if mod else topic}. Topic: {topic}. Include learning objectives, main content with examples, key takeaways, and a practice exercise. Use proper HTML: h2/h3/p/ul/ol/code/pre.'
    return jsonify({"content": _call_ai(prompt)})

def api_generate_quiz():
    data = request.get_json() or {}
    count = min(int(data.get("count",5)),15); module_id = data.get("module_id")
    db = get_db()
    mod = db.execute("SELECT title, content FROM course_modules WHERE id=?", (module_id,)).fetchone()
    db.close()
    if not mod: return jsonify({"error":"Module not found"})
    prompt = f'Generate {count} multiple-choice quiz questions for module "{mod["title"]}". Context: {(mod["content"] or "")[:500]}. Return ONLY a JSON array: [{{"question_text":"...","options":["A) ...","B) ...","C) ...","D) ..."],"correct_answer":"A) ...","points":10}}]'
    result = _call_ai_json(prompt)
    if isinstance(result, list) and len(result) > 0: return jsonify({"questions": result})
    return jsonify({"error":"Failed to generate valid questions","raw":str(result)[:200]})

def api_save_lesson():
    data = request.get_json() or {}
    mid = data.get("module_id"); content = data.get("content","")
    if not mid or not content: return jsonify({"error":"Missing data"})
    db = get_db(); db.execute("UPDATE course_modules SET content=? WHERE id=?", (content, mid)); db.commit(); db.close()
    return jsonify({"success":True})

def api_save_quiz():
    data = request.get_json() or {}
    pid = data.get("product_id"); module_id = data.get("module_id",""); questions = data.get("questions",[])
    if not pid or not questions: return jsonify({"error":"Missing data"})
    db = get_db()
    quiz = db.execute("SELECT id FROM course_quizzes WHERE course_id=? AND module_id=?", (pid, module_id)).fetchone()
    if quiz: qid = quiz[0]; db.execute("DELETE FROM quiz_questions WHERE quiz_id=?", (qid,))
    else: qid = str(uuid.uuid4())[:12]; db.execute("INSERT INTO course_quizzes (id,course_id,module_id,title,passing_score) VALUES (?,?,?,?,?)", (qid,pid,module_id,"Module Quiz",70))
    for i,q in enumerate(questions):
        qid2 = str(uuid.uuid4())[:12]
        opts = q.get("options",[])
        db.execute("INSERT INTO quiz_questions (id,quiz_id,question_text,question_type,options,correct_answer,points,sort_order) VALUES (?,?,?,?,?,?,?,?)",
                  (qid2, qid, q.get("question_text",""), "multiple_choice", json.dumps(opts), q.get("correct_answer",""), q.get("points",10), i))
    db.commit(); db.close()
    return jsonify({"success":True,"quiz_id":qid})

def api_generate_sales():
    data = request.get_json() or {}
    pid = data.get("product_id"); angle = data.get("angle","")
    db = get_db(); p = db.execute("SELECT title, description, price FROM products WHERE id=?", (pid,)).fetchone(); db.close()
    if not p: return jsonify({"error":"Product not found"})
    prompt = f'Write HTML sales copy for course "{p["title"]}" (${p["price"]:.2f}). Angle: {angle or "General"}. Include headline, pain-agitation-solution, curriculum overview, testimonial-style social proof, guarantee, strong CTA. 300-600 words conversion-optimized.'
    return jsonify({"content": _call_ai(prompt)})

def _call_ai(prompt, system="You are an expert course creator. Write clear, professional content."):
    import requests
    try:
        import premium_features
        cfg = premium_features.load_stripe_config()
    except: cfg = {}
    api_key = os.environ.get("DEEPSEEK_API_KEY", "") or os.environ.get("XAI_API_KEY", "")
    if api_key:
        try:
            resp = requests.post("https://api.deepseek.com/chat/completions",
                headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
                json={"model":"deepseek-chat","messages":[{"role":"system","content":system},{"role":"user","content":prompt}],"max_tokens":4096,"temperature":0.7}, timeout=60)
            if resp.status_code == 200: return resp.json()["choices"][0]["message"]["content"]
        except: pass
        try:
            resp = requests.post("https://api.x.ai/v1/chat/completions",
                headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
                json={"model":"grok-4-mini","messages":[{"role":"system","content":system},{"role":"user","content":prompt}],"max_tokens":4096,"temperature":0.7}, timeout=60)
            if resp.status_code == 200: return resp.json()["choices"][0]["message"]["content"]
        except: pass
    return f"<p>Generated content for: {prompt[:100]}...</p><p>Configure AI provider in Settings for live generation.</p>"

def _call_ai_json(prompt, system="Output ONLY valid JSON, no other text."):
    result = _call_ai(prompt, system)
    try:
        match = re.search(r'\[[\s\S]*\]', result)
        return json.loads(match.group()) if match else json.loads(result)
    except: return result

# ── ADMIN COURSE BUILDER ──
def course_builder(product_id):
    if not admin_check(): return redirect('/login')
    db = get_db()
    p = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not p: db.close(); return "Course not found", 404
    p = dict(p)
    modules = db.execute("SELECT * FROM course_modules WHERE product_id=? ORDER BY module_num ASC", (product_id,)).fetchall()
    quizzes = db.execute("SELECT cq.*, (SELECT COUNT(*) FROM quiz_questions WHERE quiz_id=cq.id) as qcount FROM course_quizzes cq WHERE cq.course_id=? ORDER BY cq.created_at ASC", (product_id,)).fetchall()
    workbooks = db.execute("SELECT * FROM course_workbooks WHERE course_id=? ORDER BY created_at DESC", (product_id,)).fetchall()
    slides = db.execute("SELECT cs.*, cm.title as mod_title FROM course_slides cs LEFT JOIN course_modules cm ON cs.module_id=cm.id WHERE cs.course_id=? ORDER BY cs.created_at DESC", (product_id,)).fetchall()
    db.close()
    mod_select = ""
    for m in modules:
        t = m["title"].replace("'","&#39;")
        mod_select += f'<option value="{m["id"]}">M{m["module_num"]}: {t[:40]}</option>'
    mod_rows = ""
    for m in modules:
        m = dict(m)
        safe_title = m["title"].replace("'", "&#39;").replace('"', "&quot;")
        safe_slug = m["slug"].replace("'", "&#39;")
        safe_vid = (m.get("video_url","") or "").replace("'", "&#39;")
        content_preview = str(m.get("content","") or "")[:40]
        mod_rows += f'''<tr class="border-b border-[#1e1e2e]"><td class="p-2 text-xs text-center">{m["module_num"]}</td>
        <td class="p-2 text-xs">{m["title"][:40]}</td>
        <td class="p-2 text-xs text-[#5c5c70]">{m["slug"]}</td>
        <td class="p-2 text-xs text-[#5c5c70]">{content_preview}...</td>
        <td class="p-2 text-right">
          <a href="/course/builder/edit-module/{m["id"]}" class="text-xs text-[#38bdf8] hover:underline mr-2"><i class="fas fa-edit"></i></a>
          <button onclick="delMod('{m["id"]}')" class="text-xs text-red-400 hover:underline"><i class="fas fa-trash"></i></button>
        </td></tr>'''
    quiz_rows = ""
    for q in quizzes:
        q = dict(q)
        quiz_rows += f'''<tr class="border-b border-[#1e1e2e]"><td class="p-2 text-xs">{q["title"][:40]}</td>
        <td class="p-2 text-xs text-center">{q.get("qcount",0)}</td>
        <td class="p-2 text-xs text-center">{q["passing_score"]}%</td>
        <td class="p-2 text-xs text-center">{q.get("attempts_allowed",3)}</td>
        <td class="p-2 text-right"><button onclick="delQuiz('{q["id"]}')" class="text-xs text-red-400 hover:underline"><i class="fas fa-trash"></i></button></td></tr>'''
    wb_rows = ""
    for wb in workbooks:
        wb = dict(wb); sz = f"{wb.get('file_size',0)//1024}KB" if wb.get('file_size') else "-"
        wb_rows += f'''<tr class="border-b border-[#1e1e2e]"><td class="p-2 text-xs">{wb["title"]}</td>
        <td class="p-2 text-xs text-[#5c5c70]">{sz}</td>
        <td class="p-2 text-xs text-[#5c5c70]">{(wb.get("created_at","") or "")[:10]}</td>
        <td class="p-2 text-right"><button onclick="delWB('{wb["id"]}')" class="text-xs text-red-400 hover:underline"><i class="fas fa-trash"></i></button></td></tr>'''
    sl_rows = ""
    for sl in slides:
        sl = dict(sl); mod_name = sl.get("mod_title") or "All"
        sl_rows += f'''<tr class="border-b border-[#1e1e2e]"><td class="p-2 text-xs">{sl["title"]}</td>
        <td class="p-2 text-xs text-[#5c5c70]">{mod_name}</td>
        <td class="p-2 text-xs text-center">{sl.get("slides_count",0)}</td>
        <td class="p-2 text-right"><button onclick="delSL('{sl["id"]}')" class="text-xs text-red-400 hover:underline"><i class="fas fa-trash"></i></button></td></tr>'''

    html = f'''{_LAYOUT_HEAD}<style>
.tab-btn2{{padding:10px 20px;border-radius:10px;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s;border:1px solid transparent;background:transparent;color:#7a7a8e}}
.tab-btn2.active2{{background:rgba(168,85,247,0.12);color:#c084fc;border-color:rgba(168,85,247,0.2)}}
.tab-btn2:hover{{color:#f1f1f5}}
</style>{_TOP_NAV}
<div class="max-w-6xl mx-auto px-4 py-6">
  <div class="flex items-center gap-2 text-xs text-[#5c5c70] mb-4">
    <a href="/hermes/products" class="hover:text-purple-400">Products</a><span>/</span>
    <a href="/hermes/product/{product_id}" class="hover:text-purple-400">{p["title"][:40]}</a><span>/</span><span class="text-white">Course Builder</span>
  </div>
  <div class="flex items-center gap-3 mb-6">
    <span class="text-3xl">📚</span>
    <div><h1 class="text-xl font-bold">{p["title"]}</h1><p class="text-xs text-[#5c5c70]">Lessons, quizzes, materials & AI tools</p></div>
    <div class="ml-auto flex gap-2">
      <a href="/course/{product_id}/" class="btn-secondary text-xs" style="padding:8px 16px" target="_blank"><i class="fas fa-eye mr-1"></i> Preview</a>
      <a href="/course/builder/ai/{product_id}" class="btn-primary text-xs" style="padding:8px 16px"><i class="fas fa-wand-magic-sparkles mr-1"></i> AI Generators</a>
    </div>
  </div>
  <div class="flex gap-2 mb-4 border-b border-[#1e1e2e] pb-2">
    <button class="tab-btn2 active2" onclick="swT('lessons',this)"><i class="fas fa-list mr-1"></i> Lessons ({len(modules)})</button>
    <button class="tab-btn2" onclick="swT('quizzes',this)"><i class="fas fa-question-circle mr-1"></i> Quizzes ({len(quizzes)})</button>
    <button class="tab-btn2" onclick="swT('materials',this)"><i class="fas fa-download mr-1"></i> Materials</button>
    <button class="tab-btn2" onclick="swT('settings',this)"><i class="fas fa-cog mr-1"></i> Settings</button>
  </div>
  <div id="btab-lessons">
    <div class="flex items-center justify-between mb-3">
      <h2 class="font-bold text-sm"><i class="fas fa-list text-purple-400 mr-1"></i> Course Lessons</h2>
      <a href="/course/builder/add-module/{product_id}" class="btn-primary text-xs" style="padding:8px 16px"><i class="fas fa-plus mr-1"></i> Add Lesson</a>
    </div>
    <div class="card p-0 overflow-hidden"><table class="w-full">
      <thead><tr class="text-xs text-[#5c5c70] uppercase border-b border-[#1e1e2e]"><th class="p-2 text-center w-12">#</th><th class="p-2">Title</th><th class="p-2">Slug</th><th class="p-2">Preview</th><th class="p-2 text-right">Actions</th></tr></thead>
      <tbody>{mod_rows if mod_rows else '<tr><td colspan="5" class="p-6 text-center text-xs text-[#5c5c70]">No lessons yet.</td></tr>'}</tbody>
    </table></div>
  </div>
  <div id="btab-quizzes" class="hidden">
    <div class="flex items-center justify-between mb-3">
      <h2 class="font-bold text-sm"><i class="fas fa-question-circle text-amber-400 mr-1"></i> Quizzes</h2>
      <button onclick="showAddQuiz()" class="btn-primary text-xs" style="padding:8px 16px"><i class="fas fa-plus mr-1"></i> Add Quiz</button>
    </div>
    <div class="card p-0 overflow-hidden"><table class="w-full">
      <thead><tr class="text-xs text-[#5c5c70] uppercase border-b border-[#1e1e2e]"><th class="p-2">Title</th><th class="p-2 text-center">Questions</th><th class="p-2 text-center">Pass</th><th class="p-2 text-center">Attempts</th><th class="p-2 text-right"></th></tr></thead>
      <tbody>{quiz_rows if quiz_rows else '<tr><td colspan="5" class="p-6 text-center text-xs text-[#5c5c70]">No quizzes yet.</td></tr>'}</tbody>
    </table></div>
  </div>
  <div id="btab-materials" class="hidden">
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="card p-5">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-bold text-sm"><i class="fas fa-file-pdf text-green-400 mr-1"></i> Workbooks</h3>
          <form method="POST" action="/course/builder/{product_id}/upload-workbook" enctype="multipart/form-data" class="flex items-center gap-2">
            <input type="text" name="title" class="text-xs" placeholder="Title" style="width:120px">
            <input type="file" name="file" accept=".pdf,.docx,.xlsx" class="text-xs" style="width:auto" required>
            <button class="btn-primary text-xs" style="padding:6px 12px"><i class="fas fa-upload"></i></button>
          </form>
        </div>
        <div class="card p-0" style="background:#0a0a12"><table class="w-full"><thead><tr class="text-xs text-[#5c5c70] uppercase"><th class="p-2">Title</th><th class="p-2">Size</th><th class="p-2">Added</th><th></th></tr></thead><tbody>{wb_rows or '<tr><td colspan="4" class="p-4 text-center text-xs text-[#5c5c70]">No workbooks</td></tr>'}</tbody></table></div>
      </div>
      <div class="card p-5">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-bold text-sm"><i class="fas fa-file-powerpoint text-blue-400 mr-1"></i> Slides</h3>
          <form method="POST" action="/course/builder/{product_id}/upload-slides" enctype="multipart/form-data" class="flex items-center gap-2 flex-wrap">
            <select name="module_id" class="text-xs" style="width:100px"><option value="">All</option>{mod_select}</select>
            <input type="text" name="title" class="text-xs" placeholder="Title" style="width:80px">
            <input type="file" name="file" accept=".pdf,.pptx" class="text-xs" style="width:auto" required>
            <button class="btn-primary text-xs" style="padding:6px 12px"><i class="fas fa-upload"></i></button>
          </form>
        </div>
        <div class="card p-0" style="background:#0a0a12"><table class="w-full"><thead><tr class="text-xs text-[#5c5c70] uppercase"><th class="p-2">Title</th><th class="p-2">Module</th><th class="p-2 text-center">Slides</th><th></th></tr></thead><tbody>{sl_rows or '<tr><td colspan="4" class="p-4 text-center text-xs text-[#5c5c70]">No slides</td></tr>'}</tbody></table></div>
      </div>
    </div>
  </div>
  <div id="btab-settings" class="hidden">
    <div class="card p-5">
      <h3 class="font-bold text-sm mb-4"><i class="fas fa-cog text-purple-400 mr-1"></i> Settings</h3>
      <form method="POST" action="/course/builder/{product_id}/update-settings" class="space-y-3">
        <div class="grid grid-cols-2 gap-3">
          <div><label class="text-xs text-[#5c5c70] block mb-1">Price ($)</label><input name="price" value="{p.get("price",0)}" class="text-xs" type="number" step="0.01"></div>
          <div><label class="text-xs text-[#5c5c70] block mb-1">Status</label><select name="status" class="text-xs"><option value="draft" {"selected" if p.get("status")=="draft" else ""}>Draft</option><option value="published" {"selected" if p.get("status")=="published" else ""}>Published</option></select></div>
        </div>
        <div><label class="text-xs text-[#5c5c70] block mb-1">Description</label><textarea name="description" class="text-xs" rows="6">{(p.get("description","") or "").replace("</textarea>","")}</textarea></div>
        <button class="btn-primary text-xs" style="padding:10px 24px"><i class="fas fa-save mr-1"></i> Save</button>
      </form>
    </div>
  </div>
</div>
<div id="addQuizModal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center hidden" style="padding:20px">
  <div class="bg-[#0e0e16] border border-[#1e1e2e] rounded-2xl p-6 max-w-lg w-full">
    <div class="flex items-center justify-between mb-4">
      <h3 class="font-bold text-sm"><i class="fas fa-plus-circle text-amber-400 mr-1"></i> Add Quiz</h3>
      <button onclick="closeM()" class="text-[#5c5c70] hover:text-white text-lg">&times;</button>
    </div>
    <form method="POST" action="/course/builder/{product_id}/add-quiz" class="space-y-3">
      <div><label class="text-xs text-[#5c5c70] block mb-1">Module</label><select name="module_id" class="text-xs" required>{mod_select}</select></div>
      <div><label class="text-xs text-[#5c5c70] block mb-1">Title</label><input name="title" class="text-xs" value="Module Quiz" required></div>
      <div class="grid grid-cols-2 gap-3"><div><label class="text-xs text-[#5c5c70] block mb-1">Pass %</label><input name="passing_score" class="text-xs" type="number" value="70"></div>
      <div><label class="text-xs text-[#5c5c70] block mb-1">Attempts</label><input name="attempts_allowed" class="text-xs" type="number" value="3"></div></div>
      <button class="btn-primary w-full justify-center" style="padding:12px">Create Quiz</button>
    </form>
  </div>
</div>
<script>
function swT(t,b){{document.querySelectorAll('.tab-btn2').forEach(x=>x.classList.remove('active2'));b.classList.add('active2');document.querySelectorAll('[id^=btab-]').forEach(x=>x.classList.add('hidden'));document.getElementById('btab-'+t).classList.remove('hidden');}}
function showAddQuiz(){{document.getElementById('addQuizModal').classList.remove('hidden');}}
function closeM(){{document.getElementById('addQuizModal').classList.add('hidden');}}
function delMod(id){{if(confirm('Delete this lesson?'))fetch('/course/builder/{product_id}/delete-module',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{module_id:id}})}}).then(r=>r.json()).then(d=>{{if(d.success)location.reload();else alert('Error');}});}}
function delQuiz(id){{if(confirm('Delete quiz?'))fetch('/course/builder/{product_id}/delete-quiz',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{quiz_id:id}})}}).then(r=>r.json()).then(d=>{{if(d.success)location.reload();else alert('Error');}});}}
function delWB(id){{if(confirm('Delete workbook?'))fetch('/course/builder/{product_id}/delete-workbook',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{wb_id:id}})}}).then(r=>r.json()).then(d=>{{if(d.success)location.reload();else alert('Error');}});}}
function delSL(id){{if(confirm('Delete slides?'))fetch('/course/builder/{product_id}/delete-slides',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{slides_id:id}})}}).then(r=>r.json()).then(d=>{{if(d.success)location.reload();else alert('Error');}});}}
</script>
{_LAYOUT_FOOT}'''
    return html

# ── BUILDER API ──
def builder_add_module(product_id):
    if not admin_check(): return 'Unauthorized', 401
    db = get_db()
    mid = str(uuid.uuid4())[:12]
    num = int(request.form.get("module_num",1))
    title = request.form.get("title","New Lesson")
    slug = request.form.get("slug","lesson-"+str(num))
    video_url = request.form.get("video_url","")
    content = request.form.get("content","")
    db.execute("INSERT INTO course_modules (id,product_id,module_num,title,slug,content,video_url) VALUES (?,?,?,?,?,?,?)", (mid,product_id,num,title,slug,content,video_url))
    db.commit(); db.close()
    return redirect('/course/builder/' + product_id)

def builder_add_module_edit(product_id, module_id):
    if not admin_check(): return 'Unauthorized', 401
    db = get_db()
    mod = db.execute("SELECT * FROM course_modules WHERE id=? AND product_id=?", (module_id, product_id)).fetchone()
    if not mod: db.close(); return "Module not found", 404
    mod = dict(mod)
    modules = db.execute("SELECT id, module_num, title, slug FROM course_modules WHERE product_id=? ORDER BY module_num ASC", (product_id,)).fetchall()
    mod_select = ""
    for m in modules:
        t = m["title"].replace("'","&#39;")
        mod_select += f'<option value="{m["id"]}" {"selected" if m["id"]!=module_id else ""}>M{m["module_num"]}: {t[:40]}</option>'
    html = f'''{_LAYOUT_HEAD}{_TOP_NAV}
<div class="max-w-4xl mx-auto px-4 py-6">
  <div class="flex items-center gap-2 text-xs text-[#5c5c70] mb-4">
    <a href="/course/builder/{product_id}" class="hover:text-purple-400">Course Builder</a><span>/</span>
    <span class="text-white">Edit Lesson</span>
  </div>
  <div class="card p-6">
    <h1 class="text-lg font-bold mb-4"><i class="fas fa-edit text-purple-400 mr-1"></i> Edit Lesson</h1>
    <form method="POST" action="/course/builder/{product_id}/save-module/{module_id}" class="space-y-3">
      <div class="grid grid-cols-3 gap-3">
        <div><label class="text-xs text-[#5c5c70] block mb-1">Module #</label><input name="module_num" value="{mod["module_num"]}" class="text-xs" type="number" min="1" required></div>
        <div><label class="text-xs text-[#5c5c70] block mb-1">Slug</label><input name="slug" value="{mod["slug"]}" class="text-xs" required></div>
        <div><label class="text-xs text-[#5c5c70] block mb-1">Video URL</label><input name="video_url" value="{mod.get("video_url","")}" class="text-xs" placeholder="https://youtube.com/embed/..."></div>
      </div>
      <div><label class="text-xs text-[#5c5c70] block mb-1">Title</label><input name="title" value="{mod["title"]}" class="text-xs" required></div>
      <div><label class="text-xs text-[#5c5c70] block mb-1">Content (HTML)</label>
        <textarea name="content" class="text-xs w-full" rows="18" style="font-family:monospace">{(mod.get("content","") or "").replace("</textarea>","")}</textarea>
      </div>
      <div class="flex gap-3">
        <button class="btn-primary" style="padding:12px 24px"><i class="fas fa-save mr-1"></i> Save Lesson</button>
        <a href="/course/builder/{product_id}" class="btn-secondary" style="padding:12px 24px">Cancel</a>
      </div>
    </form>
  </div>
</div>
{_LAYOUT_FOOT}'''
    return html

def builder_save_module(product_id, module_id):
    if not admin_check(): return 'Unauthorized', 401
    db = get_db()
    num = int(request.form.get("module_num",1))
    title = request.form.get("title","")
    slug = request.form.get("slug","")
    video_url = request.form.get("video_url","")
    content = request.form.get("content","")
    db.execute("UPDATE course_modules SET module_num=?,title=?,slug=?,video_url=?,content=? WHERE id=? AND product_id=?", (num,title,slug,video_url,content,module_id,product_id))
    db.commit(); db.close()
    return redirect('/course/builder/' + product_id)

def builder_delete_module(product_id):
    if not admin_check(): return jsonify({"error":"Unauthorized"}),401
    data = request.get_json() or {}
    mid = data.get("module_id")
    if not mid: return jsonify({"error":"Missing module_id"})
    db = get_db()
    db.execute("DELETE FROM course_progress WHERE module_id=?", (mid,))
    db.execute("DELETE FROM course_modules WHERE id=?", (mid,))
    db.commit(); db.close()
    return jsonify({"success":True})

def builder_add_quiz(product_id):
    if not admin_check(): return 'Unauthorized', 401
    db = get_db()
    qid = str(uuid.uuid4())[:12]
    db.execute("INSERT INTO course_quizzes (id,course_id,module_id,title,passing_score,attempts_allowed) VALUES (?,?,?,?,?,?)",
              (qid, product_id, request.form.get("module_id",""), request.form.get("title","Quiz"),
               int(request.form.get("passing_score",70)), int(request.form.get("attempts_allowed",3))))
    db.commit(); db.close()
    return redirect('/course/builder/' + product_id)

def builder_delete_quiz(product_id):
    if not admin_check(): return jsonify({"error":"Unauthorized"}),401
    data = request.get_json() or {}; qid = data.get("quiz_id")
    if not qid: return jsonify({"error":"Missing quiz_id"})
    db = get_db()
    db.execute("DELETE FROM quiz_questions WHERE quiz_id=?", (qid,))
    db.execute("DELETE FROM quiz_attempts WHERE quiz_id=?", (qid,))
    db.execute("DELETE FROM course_quizzes WHERE id=?", (qid,))
    db.commit(); db.close()
    return jsonify({"success":True})

def builder_upload_workbook(product_id):
    if not admin_check(): return 'Unauthorized', 401
    title = request.form.get("title","Workbook")
    file = request.files.get("file")
    if not file: return "No file", 400
    ext = file.filename.rsplit('.',1)[-1] if '.' in file.filename else 'pdf'
    wbid = str(uuid.uuid4())[:12]
    fpath = os.path.join(COURSE_FILES_DIR, "workbooks", f"wb_{wbid}.{ext}")
    file.save(fpath)
    db = get_db()
    db.execute("INSERT INTO course_workbooks (id,course_id,title,file_path,file_size) VALUES (?,?,?,?,?)", (wbid,product_id,title,fpath,os.path.getsize(fpath)))
    db.commit(); db.close()
    return redirect('/course/builder/' + product_id)

def builder_upload_slides(product_id):
    if not admin_check(): return 'Unauthorized', 401
    title = request.form.get("title","Slides")
    module_id = request.form.get("module_id","")
    file = request.files.get("file")
    if not file: return "No file", 400
    ext = file.filename.rsplit('.',1)[-1] if '.' in file.filename else 'pdf'
    slid = str(uuid.uuid4())[:12]
    fpath = os.path.join(COURSE_FILES_DIR, "slides", f"sl_{slid}.{ext}")
    file.save(fpath)
    db = get_db()
    db.execute("INSERT INTO course_slides (id,course_id,module_id,title,file_path,file_size,slides_count) VALUES (?,?,?,?,?,?,?)", (slid,product_id,module_id,title,fpath,os.path.getsize(fpath),0))
    db.commit(); db.close()
    return redirect('/course/builder/' + product_id)

def builder_delete_workbook(product_id):
    if not admin_check(): return jsonify({"error":"Unauthorized"}),401
    data = request.get_json() or {}; wbid = data.get("wb_id")
    if not wbid: return jsonify({"error":"Missing wb_id"})
    db = get_db()
    wb = db.execute("SELECT file_path FROM course_workbooks WHERE id=?", (wbid,)).fetchone()
    if wb and wb[0] and os.path.exists(wb[0]):
        try: os.remove(wb[0])
        except: pass
    db.execute("DELETE FROM course_workbooks WHERE id=?", (wbid,))
    db.commit(); db.close()
    return jsonify({"success":True})

def builder_delete_slides(product_id):
    if not admin_check(): return jsonify({"error":"Unauthorized"}),401
    data = request.get_json() or {}; slid = data.get("slides_id")
    if not slid: return jsonify({"error":"Missing slides_id"})
    db = get_db()
    sl = db.execute("SELECT file_path FROM course_slides WHERE id=?", (slid,)).fetchone()
    if sl and sl[0] and os.path.exists(sl[0]):
        try: os.remove(sl[0])
        except: pass
    db.execute("DELETE FROM course_slides WHERE id=?", (slid,))
    db.commit(); db.close()
    return jsonify({"success":True})

def builder_update_settings(product_id):
    if not admin_check(): return 'Unauthorized', 401
    db = get_db()
    db.execute("UPDATE products SET price=?,status=?,description=? WHERE id=?", (float(request.form.get("price",0)), request.form.get("status","draft"), request.form.get("description",""), product_id))
    db.commit(); db.close()
    return redirect('/course/builder/' + product_id)

# ── REGISTER ALL ROUTES ──
def register_routes(app, layout_head="", top_nav="", layout_foot=""):
    global _LAYOUT_HEAD, _TOP_NAV, _LAYOUT_FOOT
    _LAYOUT_HEAD = layout_head
    _TOP_NAV = top_nav
    _LAYOUT_FOOT = layout_foot
    init_tables()

    app.add_url_rule('/member', 'member_dashboard', member_dashboard)
    app.add_url_rule('/product/<product_id>/course', 'course_sales_page', course_sales_page)
    app.add_url_rule('/course/<product_id>/', 'course_player_view', course_player_view)
    app.add_url_rule('/course/<product_id>/<module_slug>', 'course_player_view_slug', course_player_view)
    app.add_url_rule('/certificates', 'certificates_page', certificates_page)
    app.add_url_rule('/certificate/view/<cert_id>', 'certificate_view', certificate_view)
    app.add_url_rule('/course/download/workbook/<wb_id>', 'download_workbook', download_workbook)
    app.add_url_rule('/course/download/slides/<sl_id>', 'download_slides', download_slides)
    app.add_url_rule('/api/quiz/<quiz_id>/questions', 'api_quiz_questions', api_quiz_questions)
    app.add_url_rule('/api/quiz/<quiz_id>/submit', 'api_quiz_submit', api_quiz_submit, methods=['POST'])
    app.add_url_rule('/course/builder/ai/<product_id>', 'course_ai_generator', course_ai_generator)
    app.add_url_rule('/api/ai/generate-lesson', 'api_generate_lesson', api_generate_lesson, methods=['POST'])
    app.add_url_rule('/api/ai/generate-quiz', 'api_generate_quiz', api_generate_quiz, methods=['POST'])
    app.add_url_rule('/api/ai/generate-sales', 'api_generate_sales', api_generate_sales, methods=['POST'])
    app.add_url_rule('/api/ai/save-lesson', 'api_save_lesson', api_save_lesson, methods=['POST'])
    app.add_url_rule('/api/ai/save-quiz', 'api_save_quiz', api_save_quiz, methods=['POST'])
    app.add_url_rule('/course/builder/<product_id>', 'course_builder', course_builder)
    app.add_url_rule('/course/builder/<product_id>/add-module', 'builder_add_module', builder_add_module, methods=['POST'])
    app.add_url_rule('/course/builder/<product_id>/delete-module', 'builder_delete_module', builder_delete_module, methods=['POST'])
    app.add_url_rule('/course/builder/<product_id>/add-quiz', 'builder_add_quiz', builder_add_quiz, methods=['POST'])
    app.add_url_rule('/course/builder/<product_id>/delete-quiz', 'builder_delete_quiz', builder_delete_quiz, methods=['POST'])
    app.add_url_rule('/course/builder/<product_id>/upload-workbook', 'builder_upload_workbook', builder_upload_workbook, methods=['POST'])
    app.add_url_rule('/course/builder/<product_id>/upload-slides', 'builder_upload_slides', builder_upload_slides, methods=['POST'])
    app.add_url_rule('/course/builder/<product_id>/delete-workbook', 'builder_delete_workbook', builder_delete_workbook, methods=['POST'])
    app.add_url_rule('/course/builder/<product_id>/delete-slides', 'builder_delete_slides', builder_delete_slides, methods=['POST'])
    app.add_url_rule('/course/builder/<product_id>/update-settings', 'builder_update_settings', builder_update_settings, methods=['POST'])
    app.add_url_rule('/course/builder/add-module/<product_id>', 'builder_add_module_page', builder_add_module_page)
    app.add_url_rule('/course/builder/edit-module/<module_id>', 'builder_add_module_edit', builder_add_module_edit)
    app.add_url_rule('/course/builder/<product_id>/save-module/<module_id>', 'builder_save_module', builder_save_module, methods=['POST'])

def builder_add_module_page(product_id):
    if not admin_check(): return redirect('/login')
    db = get_db()
    p = db.execute("SELECT id, title FROM products WHERE id=?", (product_id,)).fetchone()
    modules = db.execute("SELECT id, module_num, title, slug FROM course_modules WHERE product_id=? ORDER BY module_num ASC", (product_id,)).fetchall()
    db.close()
    if not p: return "Course not found", 404
    html = f'''{_LAYOUT_HEAD}{_TOP_NAV}
<div class="max-w-4xl mx-auto px-4 py-6">
  <div class="flex items-center gap-2 text-xs text-[#5c5c70] mb-4">
    <a href="/course/builder/{product_id}" class="hover:text-purple-400">Course Builder</a><span>/</span>
    <span class="text-white">New Lesson</span>
  </div>
  <div class="card p-6">
    <h1 class="text-lg font-bold mb-4"><i class="fas fa-plus-circle text-green-400 mr-1"></i> Add New Lesson</h1>
    <form method="POST" action="/course/builder/{product_id}/add-module" class="space-y-3">
      <div class="grid grid-cols-3 gap-3">
        <div><label class="text-xs text-[#5c5c70] block mb-1">Module #</label><input name="module_num" class="text-xs" type="number" min="1" value="{len(modules)+1}" required></div>
        <div><label class="text-xs text-[#5c5c70] block mb-1">Slug</label><input name="slug" class="text-xs" placeholder="lesson-{len(modules)+1}"></div>
        <div><label class="text-xs text-[#5c5c70] block mb-1">Video URL</label><input name="video_url" class="text-xs" placeholder="https://youtube.com/embed/..."></div>
      </div>
      <div><label class="text-xs text-[#5c5c70] block mb-1">Title</label><input name="title" class="text-xs" placeholder="Lesson title" required></div>
      <div><label class="text-xs text-[#5c5c70] block mb-1">Content (HTML)</label>
        <textarea name="content" class="text-xs w-full" rows="18" style="font-family:monospace"></textarea>
      </div>
      <button class="btn-primary" style="padding:12px 24px"><i class="fas fa-check mr-1"></i> Create Lesson</button>
    </form>
  </div>
</div>
{_LAYOUT_FOOT}'''
    return html
