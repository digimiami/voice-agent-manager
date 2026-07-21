@app.route('/membership')
def membership_page():
    """Membership plans page."""
    import datetime
    now = datetime.datetime.now().strftime('%b %d, %Y')
    
    plans = [
        {'name': 'Free', 'price': 0, 'period': 'forever', 'desc': 'Get started with basic access', 'color': '#5c5c70', 'icon': '\U0001f4aa', 'features': ['5 downloads/month', 'Basic AI assistant', 'Community access', 'Email support']},
        {'name': 'Creator', 'price': 29, 'period': 'month', 'desc': 'For creators building a business', 'color': '#a855f7', 'icon': '\U0001f680', 'features': ['Unlimited downloads', 'Publish products', 'AI optimization', 'Analytics dashboard', 'Priority support', 'Commercial license'], 'popular': True},
        {'name': 'Pro', 'price': 99, 'period': 'month', 'desc': 'For power users and teams', 'color': '#38bdf8', 'icon': '\U0001f52e', 'features': ['Everything in Creator', 'AI agents access', 'Automation tools', 'Advanced analytics', 'API access', 'Team seats (3)', 'Dedicated support'], 'popular': False},
        {'name': 'Enterprise', 'price': 499, 'period': 'month', 'desc': 'For organizations scaling AI', 'color': '#4ade80', 'icon': '\U0001f3db\ufe0f', 'features': ['Everything in Pro', 'Private marketplace', 'Custom AI agents', 'White-label option', 'Custom domain', 'SAML/SSO', 'Unlimited team seats', 'SLA guarantee', 'Dedicated account manager'], 'popular': False}
    ]
    
    cards = ''
    for plan in plans:
        border = 'border-[#a855f7]/50' if plan.get('popular') else 'border-[#252533]'
        badge = '<div class="text-[10px] font-semibold text-[#a855f7] bg-[#a855f7]/10 px-3 py-1 rounded-full mb-3 inline-block">Most Popular</div>' if plan.get('popular') else ''
        features = ''.join(f'<div class="flex items-center gap-2 text-xs text-[#b0b0c0]"><i class="fas fa-check text-[{plan["color"]}] text-[10px]"></i>{f}</div>' for f in plan['features'])
        price_display = 'Free' if plan['price'] == 0 else f'${plan["price"]}<span class="text-sm text-[#5c5c70] font-normal">/{plan["period"]}</span>'
        btn = '<a href="/creator/signup" class="w-full block text-center py-3 rounded-lg text-sm font-semibold transition" style="background:linear-gradient(135deg,' + plan['color'] + ',transparent);border:1px solid ' + plan['color'] + '">Get Started</a>' if plan['price'] > 0 else '<a href="/" class="w-full block text-center py-3 rounded-lg text-sm font-semibold border border-[#252533] hover:border-white/20 transition">Browse Free</a>'
        
        cards += f'''<div class="card relative flex flex-col" style="padding:24px;border-color:{border}">
  {badge}
  <div class="text-2xl mb-2">{plan["icon"]}</div>
  <h3 class="font-bold text-lg">{plan["name"]}</h3>
  <p class="text-xs text-[#5c5c70] mb-4">{plan["desc"]}</p>
  <div class="text-3xl font-black mb-2" style="color:{plan['color']}">{price_display}</div>
  <div class="flex-1 space-y-2 my-4">{features}</div>
  {btn}
</div>'''
    
    return f'''{LAYOUT_HEAD}
{TOP_NAV}
<div class="max-w-5xl mx-auto px-4 sm:px-6 pb-12">

  <!-- Header -->
  <div class="text-center py-10 mb-8">
    <span class="text-4xl mb-4 block">🚀</span>
    <h1 class="text-3xl sm:text-4xl font-black mb-3">Hermes Membership</h1>
    <p class="text-sm text-[#5c5c70] max-w-lg mx-auto">Join the fastest-growing community of AI creators, developers, and digital entrepreneurs. Choose your plan.</p>
  </div>

  <!-- Plans Grid -->
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">{cards}</div>

  <!-- Comparison Table -->
  <div class="card" style="padding:24px">
    <h2 class="font-bold text-lg mb-4">Plan Comparison</h2>
    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <thead><tr class="text-[#5c5c70] border-b border-[#1e1e2e]"><th class="text-left py-2 pr-4">Feature</th><th class="py-2 px-2">Free</th><th class="py-2 px-2 text-[#a855f7]">Creator</th><th class="py-2 px-2 text-[#38bdf8]">Pro</th><th class="py-2 px-2 text-[#4ade80]">Enterprise</th></tr></thead>
        <tbody>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">Downloads / month</td><td class="py-2 px-2 text-center">5</td><td class="py-2 px-2 text-center">Unlimited</td><td class="py-2 px-2 text-center">Unlimited</td><td class="py-2 px-2 text-center">Unlimited</td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">Publish products</td><td class="py-2 px-2 text-center">—</td><td class="py-2 px-2 text-center">✅</td><td class="py-2 px-2 text-center">✅</td><td class="py-2 px-2 text-center">✅</td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">AI optimization</td><td class="py-2 px-2 text-center">—</td><td class="py-2 px-2 text-center">✅</td><td class="py-2 px-2 text-center">✅</td><td class="py-2 px-2 text-center">✅</td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">AI agents</td><td class="py-2 px-2 text-center">Basic</td><td class="py-2 px-2 text-center">Standard</td><td class="py-2 px-2 text-center">Advanced</td><td class="py-2 px-2 text-center">Custom</td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">Analytics</td><td class="py-2 px-2 text-center">—</td><td class="py-2 px-2 text-center">Basic</td><td class="py-2 px-2 text-center">Advanced</td><td class="py-2 px-2 text-center">Custom</td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">API access</td><td class="py-2 px-2 text-center">—</td><td class="py-2 px-2 text-center">—</td><td class="py-2 px-2 text-center">✅</td><td class="py-2 px-2 text-center">✅</td></tr>
          <tr class="border-b border-[#1e1e2e]"><td class="py-2 pr-4">Team seats</td><td class="py-2 px-2 text-center">1</td><td class="py-2 px-2 text-center">1</td><td class="py-2 px-2 text-center">3</td><td class="py-2 px-2 text-center">Unlimited</td></tr>
          <tr><td class="py-2 pr-4">Support</td><td class="py-2 px-2 text-center">Email</td><td class="py-2 px-2 text-center">Priority</td><td class="py-2 px-2 text-center">Dedicated</td><td class="py-2 px-2 text-center">Account Manager</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- FAQ -->
  <div class="mt-8">
    <h2 class="font-bold text-lg mb-4">Frequently Asked Questions</h2>
    <div class="space-y-3">
      <div class="card p-4"><p class="font-semibold text-sm mb-1">Can I switch plans anytime?</p><p class="text-xs text-[#5c5c70]">Yes! You can upgrade, downgrade, or cancel your subscription at any time. Changes take effect immediately.</p></div>
      <div class="card p-4"><p class="font-semibold text-sm mb-1">What payment methods do you accept?</p><p class="text-xs text-[#5c5c70]">We accept all major credit cards, PayPal, and cryptocurrency through Stripe. Enterprise customers can request invoicing.</p></div>
      <div class="card p-4"><p class="font-semibold text-sm mb-1">Can I publish products with any plan?</p><p class="text-xs text-[#5c5c70]">Creator plan and above allow you to publish products. Free users can browse and download products.</p></div>
      <div class="card p-4"><p class="font-semibold text-sm mb-1">What is Hermes AI?</p><p class="text-xs text-[#5c5c70]">Hermes AI is our autonomous business engine that helps create, optimize, and market products. Pro and Enterprise plans get advanced AI agent access.</p></div>
    </div>
  </div>

</div>
{LAYOUT_FOOT}'''
