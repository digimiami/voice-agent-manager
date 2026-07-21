#!/usr/bin/env python3
"""
--- Part 2: Multi-Language, Follow-ups, Recording, Script Optimizer ---
Appended imports & functions for the premium features.
"""

import json, sqlite3, os, time, random
from datetime import datetime, timedelta
DB_PATH = "/root/voice-agent-businesses.db"

# ═══════════════════════════════════════════════
# MULTI-LANGUAGE SUPPORT
# ═══════════════════════════════════════════════

LANGUAGES = [
    {"code": "multi", "name": "Multilingual (Auto-Detect)", "flag": "🌐", "model": "gpt-4o-mini"},
    {"code": "en", "name": "English", "flag": "🇺🇸", "model": "gpt-4o-mini"},
    {"code": "es", "name": "Spanish", "flag": "🇪🇸", "model": "gpt-4o-mini"},
    {"code": "fr", "name": "French", "flag": "🇫🇷", "model": "gpt-4o-mini"},
    {"code": "de", "name": "German", "flag": "🇩🇪", "model": "gpt-4o-mini"},
    {"code": "pt", "name": "Portuguese", "flag": "🇧🇷", "model": "gpt-4o-mini"},
    {"code": "zh", "name": "Chinese", "flag": "🇨🇳", "model": "gpt-4o-mini"},
    {"code": "ar", "name": "Arabic", "flag": "🇸🇦", "model": "gpt-4o-mini"},
    {"code": "hi", "name": "Hindi", "flag": "🇮🇳", "model": "gpt-4o-mini"},
    {"code": "ko", "name": "Korean", "flag": "🇰🇷", "model": "gpt-4o-mini"},
    {"code": "ja", "name": "Japanese", "flag": "🇯🇵", "model": "gpt-4o-mini"},
]

def update_assistant_language(assistant_id, lang_code, api_key):
    """Update VAPI assistant with language-specific settings.
    Appends language instruction to existing system prompt without overwriting other settings."""
    import requests, json as j
    
    system_prompt_suffix = {
        "en": "",
        "multi": "\n\nIMPORTANT: You are a MULTI-LINGUAL assistant. Detect the caller's language and respond in that same language. You speak: English, Spanish, French, German, Portuguese, Chinese, Arabic, Hindi, Korean, Japanese. Switch languages naturally when the caller switches.",
        "es": "\n\nIMPORTANTE: Eres un asistente MULTILINGÜE. Detecta el idioma del cliente y responde en ese mismo idioma. Hablas: español, inglés, francés, alemán, portugués, chino, árabe, hindi, coreano, japonés. Cambia de idioma naturalmente cuando el cliente cambie.",
        "fr": "\n\nIMPORTANT: Vous êtes un assistant MULTILINGUE. Détectez la langue de l'appelant et répondez dans cette même langue. Vous parlez: français, anglais, espagnol, allemand, portugais, chinois, arabe, hindi, coréen, japonais. Changez de langue naturellement lorsque l'appelant change.",
        "de": "\n\nWICHTIG: Sie sind ein MEHRSPRACHIGER Assistent. Erkennen Sie die Sprache des Anrufers und antworten Sie in derselben Sprache. Sie sprechen: Deutsch, Englisch, Spanisch, Französisch, Portugiesisch, Chinesisch, Arabisch, Hindi, Koreanisch, Japanisch. Wechseln Sie natürlich die Sprache, wenn der Anrufer wechselt.",
        "pt": "\n\nIMPORTANTE: Você é um assistente MULTILÍNGUE. Detecte o idioma do cliente e responda nesse mesmo idioma. Você fala: português, inglês, espanhol, francês, alemão, chinês, árabe, hindi, coreano, japonês. Mude de idioma naturalmente quando o cliente mudar.",
        "zh": "\n\n重要提示：您是一位多语言助手。请检测来电者的语言，并用该语言回复。您可以说：中文、英语、西班牙语、法语、德语、葡萄牙语、阿拉伯语、印地语、韩语、日语。当来电者切换语言时，请自然切换。",
        "ar": "\n\nمهم: أنت مساعد متعدد اللغات. اكتشف لغة المتصل ورد بنفس اللغة. تتحدث: العربية، الإنجليزية، الإسبانية، الفرنسية، الألمانية، البرتغالية، الصينية، الهندية، الكورية، اليابانية. غير اللغة بشكل طبيعي عندما يغير المتصل.",
        "hi": "\n\nमहत्वपूर्ण: आप एक बहुभाषी सहायक हैं। कॉल करने वाले की भाषा का पता लगाएं और उसी भाषा में उत्तर दें। आप बोलते हैं: हिंदी, अंग्रेजी, स्पेनिश, फ्रेंच, जर्मन, पुर्तगाली, चीनी, अरबी, कोरियाई, जापानी। जब कॉल करने वाला बदले तो स्वाभाविक रूप से भाषा बदलें।",
        "ko": "\n\n중요: 당신은 다국어 지원 어시스턴트입니다. 발신자의 언어를 감지하고 동일한 언어로 응답하세요. 당신은 한국어, 영어, 스페인어, 프랑스어, 독일어, 포르투갈어, 중국어, 아랍어, 힌디어, 일본어를 구사합니다. 발신자가 변경하면 자연스럽게 언어를 전환하세요.",
        "ja": "\n\n重要: あなたは多言語対応アシスタントです。発信者の言語を検出し、同じ言語で応答してください。あなたは日本語、英語、スペイン語、フランス語、ドイツ語、ポルトガル語、中国語、アラビア語、ヒンディー語、韓国語を話します。発信者が切り替えたら自然に言語を切り替えてください。",
    }
    
    suffix = system_prompt_suffix.get(lang_code, system_prompt_suffix['multi'])
    
    # First, fetch current assistant config to preserve existing settings
    try:
        r_get = requests.get(
            f"https://api.vapi.ai/assistant/{assistant_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10
        )
        current = r_get.json()
    except:
        current = {}
    
    # Preserve existing model config
    current_model = current.get('model', {})
    model_provider = current_model.get('provider', 'openai')
    model_name = current_model.get('model', 'gpt-4o-mini')
    current_max_tokens = current_model.get('maxTokens', 300)
    current_temp = current_model.get('temperature', 0.35)
    
    # Preserve existing system prompt and append language suffix
    existing_prompt = current_model.get('systemPrompt', '')
    # Remove any existing language suffix to avoid duplication
    for code, old_suffix in system_prompt_suffix.items():
        if old_suffix and old_suffix in existing_prompt:
            existing_prompt = existing_prompt.replace(old_suffix, '').strip()
    
    if suffix:
        new_prompt = existing_prompt + suffix if existing_prompt else suffix
    else:
        new_prompt = existing_prompt
    
    # Preserve existing voice config
    current_voice = current.get('voice', {})
    voice_id = current_voice.get('voiceId', 'burt')
    voice_speed = current_voice.get('speed', 1.0)
    voice_stability = current_voice.get('stability', 0.5)
    voice_similarity = current_voice.get('similarityBoost', 0.7)
    
    # Preserve silence/timeout settings
    silence_timeout = current.get('silenceTimeoutSeconds', 5)
    response_delay = current.get('responseDelaySeconds', 0.1)
    max_duration = current.get('maxDurationSeconds', 900)
    first_msg = current.get('firstMessage', '')
    first_msg_mode = current.get('firstMessageMode', 'assistant-speaks-first')
    
    patch_payload = {
        "model": {
            "model": model_name,
            "provider": model_provider,
            "maxTokens": current_max_tokens,
            "temperature": current_temp,
            "systemPrompt": new_prompt
        },
        "voice": {
            "provider": "11labs",
            "voiceId": voice_id,
            "speed": voice_speed,
            "stability": voice_stability,
            "similarityBoost": voice_similarity
        },
        "silenceTimeoutSeconds": silence_timeout,
        "responseDelaySeconds": response_delay,
        "maxDurationSeconds": max_duration
    }
    if first_msg:
        patch_payload["firstMessage"] = first_msg
        patch_payload["firstMessageMode"] = first_msg_mode
    
    r = requests.patch(
        f"https://api.vapi.ai/assistant/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=patch_payload
    )
    return r.status_code == 200

# ═══════════════════════════════════════════════
# SMART FOLLOW-UP SEQUENCES
# ═══════════════════════════════════════════════

def ensure_followups_table():
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS followups (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            lead_id TEXT,
            lead_phone TEXT,
            lead_name TEXT,
            sequence_step INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            last_action TEXT,
            next_action_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(business_id) REFERENCES businesses(id)
        )
    """)
    db.commit()
    db.close()

ensure_followups_table()

def trigger_followup(business_id, lead_id, lead_phone, lead_name, outcome):
    """Start a follow-up sequence based on call outcome."""
    if outcome not in ("customer-ended-call", "customer-didnt-answer", "no-answer"):
        return
    
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    
    # Check if business has follow-ups enabled
    c.execute("SELECT sms_missed, sms_after_call FROM businesses WHERE id=?", (business_id,))
    biz = c.fetchone()
    if not biz:
        db.close()
        return
    
    followup_id = str(uuid.uuid4())[:12]
    next_time = (datetime.now() + timedelta(hours=1)).isoformat()
    
    c.execute("""INSERT OR IGNORE INTO followups 
        (id, business_id, lead_id, lead_phone, lead_name, sequence_step, status, next_action_at)
        VALUES (?, ?, ?, ?, ?, 1, 'pending', ?)""",
        (followup_id, business_id, lead_id, lead_phone, lead_name, next_time))
    db.commit()
    db.close()

def process_followups():
    """Process pending follow-up sequences. Call this every 15 min."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    now = datetime.now().isoformat()
    
    c.execute("""SELECT f.*, b.sms_missed, b.sms_after_call, b.name as biz_name, b.phone_number as biz_phone
        FROM followups f JOIN businesses b ON f.business_id = b.id
        WHERE f.status = 'pending' AND f.next_action_at <= ?""", (now,))
    rows = [dict(r) for r in c.fetchall()]
    
    for f in rows:
        step = f['sequence_step']
        phone = f['lead_phone']
        name = f['lead_name'] or 'there'
        biz_name = f['biz_name']
        biz_phone = f.get('biz_phone', '')
        
        # Get Twilio config
        try:
            with open('/root/voice-agent-manager/twilio_config.json') as tf:
                twilio = json.load(tf)
        except:
            twilio = {'enabled': False}
        
        sent = False
        msg = ""
        
        if step == 1:
            msg = f"Hi {name}! We missed your call at {biz_name}. Want us to call you back? Reply YES"
        elif step == 2:
            if f.get('last_response') == 'YES':
                msg = f"Great! We'll call you shortly from {biz_phone}"
            else:
                msg = f"Hi {name}, still interested in {biz_name} services? Reply BOOK and we'll call you"
        elif step == 3:
            msg = f"Last chance {name}! Get in touch with {biz_name} for a free quote. Reply STOP to opt out"
        
        if msg and twilio.get('enabled') and twilio.get('account_sid'):
            try:
                from twilio.rest import Client
                client = Client(twilio['account_sid'], twilio['auth_token'])
                client.messages.create(body=msg, from_=twilio['from_number'], to=phone)
                sent = True
            except:
                pass
        
        if sent:
            next_step = step + 1
            if next_step > 3:
                c.execute("UPDATE followups SET status='completed', last_action='final_sms' WHERE id=?", (f['id'],))
            else:
                next_time = (datetime.now() + timedelta(hours=24)).isoformat()
                c.execute("""UPDATE followups SET sequence_step=?, last_action='sms', next_action_at=? WHERE id=?""",
                    (next_step, next_time, f['id']))
        else:
            c.execute("UPDATE followups SET status='failed' WHERE id=?", (f['id'],))
    
    db.commit()
    db.close()
    return len(rows)

# ═══════════════════════════════════════════════
# CALL RECORDING
# ═══════════════════════════════════════════════

def enable_recording(assistant_id, api_key):
    """Enable call recording for a VAPI assistant."""
    import requests
    r = requests.patch(
        f"https://api.vapi.ai/assistant/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"recordingEnabled": True, "recordingFormat": "mp3"}
    )
    return r.status_code == 200

# ═══════════════════════════════════════════════
# AI SCRIPT OPTIMIZER
# ═══════════════════════════════════════════════

def analyze_script_performance(business_id):
    """Analyze which script patterns lead to bookings."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    
    c.execute("""SELECT outcome, transcript FROM call_log 
        WHERE business_id = ? AND transcript != '' AND transcript IS NOT NULL
        ORDER BY created_at DESC LIMIT 50""", (business_id,))
    calls = [dict(r) for r in c.fetchall()]
    
    if len(calls) < 3:
        db.close()
        return {"error": "Need at least 3 calls with transcripts"}
    
    booked = [c for c in calls if c['outcome'] == 'appointment_booked']
    missed = [c for c in calls if c['outcome'] in ('customer-ended-call', 'no-answer')]
    
    # Simple keyword analysis
    book_keywords = {}
    miss_keywords = {}
    
    for c in booked:
        for w in (c['transcript'] or '').lower().split():
            if len(w) > 3:
                book_keywords[w] = book_keywords.get(w, 0) + 1
    
    for c in missed:
        for w in (c['transcript'] or '').lower().split():
            if len(w) > 3:
                miss_keywords[w] = miss_keywords.get(w, 0) + 1
    
    # Find winning and losing words
    win_words = []
    lose_words = []
    all_words = set(list(book_keywords.keys()) + list(miss_keywords.keys()))
    
    for w in all_words:
        b_rate = book_keywords.get(w, 0) / max(len(booked), 1)
        m_rate = miss_keywords.get(w, 0) / max(len(missed), 1)
        diff = b_rate - m_rate
        if diff > 0.15 and book_keywords.get(w, 0) >= 2:
            win_words.append({"word": w, "score": round(diff, 2), "count": book_keywords[w]})
        elif diff < -0.15 and miss_keywords.get(w, 0) >= 2:
            lose_words.append({"word": w, "score": round(diff, 2), "count": miss_keywords[w]})
    
    win_words.sort(key=lambda x: -x['score'])
    lose_words.sort(key=lambda x: x['score'])
    
    suggestions = []
    if win_words:
        top = win_words[0]['word']
        suggestions.append(f"💡 Top booking keyword: \"{top}\" — mention this early in calls")
    if lose_words:
        bot = lose_words[0]['word']
        suggestions.append(f"⚠️ Avoid overusing: \"{bot}\" — may cause disinterest")
    
    suggestions.append(f"📞 You have {len(booked)} successful calls out of {len(calls)} total")
    
    if len(booked) >= 2 and len(missed) >= 2:
        suggestions.append(f"🎯 Booking conversion: {len(booked)/len(calls)*100:.0f}% — focus on what works")
    
    db.close()
    return {
        "total_analyzed": len(calls),
        "booked": len(booked),
        "missed": len(missed),
        "winning_keywords": win_words[:5],
        "losing_keywords": lose_words[:5],
        "suggestions": suggestions,
    }
