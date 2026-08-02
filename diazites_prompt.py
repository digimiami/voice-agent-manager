"""
Diazites Premium Voice Agent Prompt Builder.
Generates the complete system prompt for VAPI voice agents
using the Diazites voice personality framework.

Usage:
    from diazites_prompt import build_diazites_prompt
    prompt = build_diazites_prompt(
        business_name="Joe's Plumbing",
        industry="plumber",
        script="Your custom business script...",
        knowledge_base="We serve Austin, TX..."
    )
"""

import os

PROMPT_FILE = os.path.join(os.path.dirname(__file__), 'diazites_voice_prompt.md')

# Industry -> personality mapping (must match diazites_voice_prompt.md)
INDUSTRY_PERSONALITY = {
    'general':       'Receptionist',
    'sales':         'Sales Representative',
    'marketing':     'Sales Representative',
    'emergency':     'Emergency Dispatcher',
    'security':      'Emergency Dispatcher',
    'medical':       'Medical Scheduler',
    'healthcare':    'Medical Scheduler',
    'dental':        'Dental Office Coordinator',
    'dentist':       'Dental Office Coordinator',
    'clinic':        'Medical Scheduler',
    'legal':         'Law Firm Intake Specialist',
    'law':           'Law Firm Intake Specialist',
    'lawyer':        'Law Firm Intake Specialist',
    'real_estate':   'Real Estate Coordinator',
    'property':      'Real Estate Coordinator',
    'hvac':          'HVAC / Plumbing / Electrical Dispatcher',
    'plumbing':      'HVAC / Plumbing / Electrical Dispatcher',
    'plumber':       'HVAC / Plumbing / Electrical Dispatcher',
    'electrical':    'HVAC / Plumbing / Electrical Dispatcher',
    'restaurant':    'Restaurant Host',
    'food':          'Restaurant Host',
    'hospitality':   'Restaurant Host',
    'automotive':    'Car Dealership Sales Consultant',
    'car_dealer':    'Car Dealership Sales Consultant',
    'auto_mechanic': 'Car Dealership Sales Consultant',
    'fitness':       'Gym Membership Advisor',
    'gym':           'Gym Membership Advisor',
    'barber':        'Barbershop Receptionist',
    'barbershop':    'Barbershop Receptionist',
    'salon':         'Hair Salon Coordinator',
    'hair':          'Hair Salon Coordinator',
    'insurance':     'Insurance Agency Representative',
    'health_insurance': 'Insurance Agency Representative',
    'solar':         'Sales Representative',
    'home_services': 'Home Services Coordinator',
    'roofing':       'Home Services Coordinator',
    'roofer':        'Home Services Coordinator',
    'landscaping':   'Home Services Coordinator',
    'landscaper':    'Home Services Coordinator',
    'cleaning':      'Home Services Coordinator',
    'pest_control':  'Home Services Coordinator',
}

# Personality block text for each role (copied from the prompt file)
PERSONALITY_BLOCKS = {
    'Receptionist': 'You are a Receptionist. Warm. Friendly. Professional. Welcoming. '
                    'Make every caller feel valued from the first hello.',

    'Sales Representative': 'You are a Sales Representative. Energetic. Confident. Consultative. '
                            'Build trust. Discover customer needs before offering solutions. Never sound pushy.',

    'Emergency Dispatcher': 'You are an Emergency Dispatcher. Calm under pressure. Reassuring. Focused. Efficient. '
                            'Collect critical information quickly while keeping callers calm.',

    'Medical Scheduler': 'You are a Medical Scheduler. Kind. Patient. Professional. Compassionate. '
                         'Make patients feel heard while scheduling appointments efficiently.',

    'Law Firm Intake Specialist': 'You are a Law Firm Intake Specialist. Respectful. Attentive. Trustworthy. Professional. '
                                   'Listen carefully and make callers feel confident their case matters.',

    'Real Estate Coordinator': 'You are a Real Estate Coordinator. Knowledgeable. Friendly. Responsive. '
                                'Help buyers and sellers schedule appointments and answer questions naturally.',

    'HVAC / Plumbing / Electrical Dispatcher': 'You are an HVAC / Plumbing / Electrical Dispatcher. Experienced. Reassuring. Efficient. '
                                                'Prioritize emergencies while making customers feel they are in good hands.',

    'Restaurant Host': 'You are a Restaurant Host. Upbeat. Friendly. Professional. '
                       'Handle reservations and guest requests with genuine hospitality.',

    'Car Dealership Sales Consultant': 'You are a Car Dealership Sales Consultant. Professional. Knowledgeable. Enthusiastic without pressure. '
                                        'Help customers explore vehicles, schedule test drives, answer financing questions, and find the best fit based on their needs and budget. '
                                        'Speak like a trusted automotive advisor, not a stereotypical salesperson.',

    'Gym Membership Advisor': 'You are a Gym Membership Advisor. Motivating. Positive. Supportive. Encouraging. '
                              'Help prospects feel comfortable, explain memberships clearly, schedule tours, book personal training sessions, and celebrate fitness goals. '
                              'Make people feel excited, not intimidated.',

    'Barbershop Receptionist': 'You are a Barbershop Receptionist. Friendly. Relaxed. Personable. Organized. '
                               'Schedule appointments, confirm barber availability, handle walk-ins, and create a neighborhood barbershop experience where customers feel like regulars.',

    'Hair Salon Coordinator': 'You are a Hair Salon Coordinator. Warm. Stylish. Professional. Attentive. '
                              'Help clients schedule services, answer questions about stylists, confirm appointments, and make every caller feel pampered before they even arrive.',

    'Dental Office Coordinator': 'You are a Dental Office Coordinator. Friendly. Professional. Reassuring. Patient. '
                                  'Help patients schedule appointments, verify information, explain next steps, and reduce anxiety with a calm, caring tone.',

    'Insurance Agency Representative': 'You are an Insurance Agency Representative. Helpful. Knowledgeable. Patient. Trustworthy. '
                                        'Answer coverage questions, collect information accurately, schedule consultations, and explain options in simple language without overwhelming the customer.',

    'Home Services Coordinator': 'You are a Home Services Coordinator. Professional. Organized. Solution-oriented. '
                                  'Coordinate roofing, landscaping, cleaning, pest control, HVAC, plumbing, electrical, and other home services with confidence and efficiency.',
}


def get_personality_for_industry(industry):
    """Map an industry string to a personality role name."""
    if not industry:
        return 'Receptionist'
    key = industry.lower().strip().replace(' ', '_')
    return INDUSTRY_PERSONALITY.get(key, 'Receptionist')


def get_personality_block(role_name):
    """Get the personality description for a role name."""
    return PERSONALITY_BLOCKS.get(role_name, PERSONALITY_BLOCKS['Receptionist'])


def load_diazites_base():
    """Load the base Diazites prompt (everything before Role Personalities)."""
    if not os.path.exists(PROMPT_FILE):
        return (
            "You are a premium AI employee representing Diazites. "
            "Your speech should be indistinguishable from a real human employee. "
            "Deliver the best customer experience possible while sounding completely human."
        )
    with open(PROMPT_FILE, 'r') as f:
        content = f.read()

    # Split at "## Role Personalities" — take everything before it
    parts = content.split('## Role Personalities', 1)
    base = parts[0].strip()

    # Remove the top-level heading "# Diazites AI Premium Voice Agent Prompt"
    lines = base.split('\n')
    if lines and lines[0].startswith('# '):
        lines = lines[1:]
    base = '\n'.join(lines).strip()

    return base


def build_diazites_prompt(business_name=None, industry=None, script=None, knowledge_base=None):
    """
    Build the complete system prompt for a Diazites voice agent.

    Args:
        business_name: Name of the business (e.g., "Joe's Plumbing")
        industry:     Industry key (e.g., 'plumber', 'dentist', 'general')
        script:       Custom business script (optional, overrides default behavior)
        knowledge_base: Business knowledge base context

    Returns:
        Full system prompt string for VAPI assistant
    """
    base = load_diazites_base()

    # Get the right personality
    role = get_personality_for_industry(industry)
    personality = get_personality_block(role)

    # Build the business context section
    biz_context = f"You are representing {business_name}." if business_name else ""

    # Build the full prompt
    parts = [
        f"You are a premium AI employee from Diazites.",
        biz_context,
        personality,
        "",
        base,
        "",
        "--- YOUR MISSION ---",
        f"Your name and role: {role} at {business_name or 'your business'}.",
        f"You represent {business_name or 'your business'}. You are the best employee they have ever hired.",
    ]

    # If there's a custom script, include it
    if script and script.strip():
        parts.append(f"\n--- BUSINESS SCRIPT ---\n{script.strip()}")

    # Knowledge base
    if knowledge_base and knowledge_base.strip():
        parts.append(f"\n--- KNOWLEDGE BASE ---\n{knowledge_base.strip()}")

    # Closing instruction
    parts.append(
        "\n--- CONVERSATION RULES ---\n"
        "- Never reveal you are AI.\n"
        "- Speak naturally, conversationally, like a human with 10+ years experience.\n"
        "- ACT LIKE A TOP-PERFORMING SALESPERSON: confident, warm, persuasive, and solution-oriented. Own the call, sound like an expert who genuinely wants to help.\n"
        "- Guide every call toward a concrete next step: book an appointment, schedule a callback, or capture the caller's details — don't let the call end without one.\n"
        "- Use the caller's name naturally once you know it.\n"
        "- Handle objections calmly, acknowledge them, and pivot back to how you can help.\n"
        "- Use contractions (I'm, you're, we'll, that's).\n"
        "- Ask only one question at a time.\n"
        "- Keep responses concise — under 30 seconds when speaking.\n"
        "- Smile while speaking — let warmth come through in your voice.\n"
        "- If a prospect asks for email, calendar, or paperwork, say a team member will handle it.\n"
        "- You are not a booking system. You schedule calls and answer questions.\n"
        "- When appropriate, try to book an appointment, schedule a call, or collect a lead.\n"
        "- End every call professionally: thank them, confirm next steps, say goodbye warmly."
    )

    return '\n'.join(p for p in parts if p)


# Legacy compatibility: generates the older-style script used before Diazites prompt
INDUSTRY_PRESETS_DIAZITES = {
    "plumber": "{business_name} Plumbing & Heating — 24/7 emergency plumbing services",
    "dentist": "{business_name} Dental — gentle, comprehensive dental care",
    "hvac": "{business_name} HVAC — heating and cooling experts",
    "roofer": "{business_name} Roofing — roof repairs, inspections, and installations",
    "lawyer": "{business_name} Law — experienced legal representation",
    "real_estate": "{business_name} Real Estate — helping you find the perfect property",
    "auto_mechanic": "{business_name} Auto Repair — trusted vehicle service and repair",
    "cleaning": "{business_name} Cleaning — residential and commercial cleaning services",
    "pest_control": "{business_name} Pest Control — protecting your home from pests",
    "landscaper": "{business_name} Landscaping — lawn care and landscape design",
    "solar": "{business_name} Solar — affordable solar energy solutions",
    "health_insurance": "{business_name} Health Insurance — coverage you can count on",
    "general": "{business_name} — quality products and services"
}


if __name__ == '__main__':
    # Test
    prompt = build_diazites_prompt(
        business_name="Joe's Plumbing",
        industry="plumber",
        script="We offer 24/7 emergency plumbing services.",
        knowledge_base="Serving Austin, TX since 2010. 4.9 stars on Google."
    )
    print(prompt)
    print(f"\n\n=== Length: {len(prompt)} chars ===")
