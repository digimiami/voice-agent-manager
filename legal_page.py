"""Legal pages for Shopzario - Terms, Privacy, Refund Policy"""
import datetime as _dt

def legal_page():
    """Render a combined Legals page with all policies."""
    now = _dt.datetime.now()
    year = now.year
    Q = chr(39)
    
    sections = [
        ("terms", "Terms of Service"),
        ("privacy", "Privacy Policy"),
        ("refund", "Refund & Cancellation Policy"),
        ("cookie", "Cookie Policy"),
        ("gdpr", "GDPR Compliance"),
        ("eula", "End User License Agreement"),
        ("disclaimer", "Disclaimer"),
    ]
    
    # Tab navigation for legal sections
    tabs = "".join([f'<button class="tab text-xs font-semibold px-4 py-2.5 rounded-xl text-gray-400 hover:text-white hover:bg-white/5 transition-all" data-tab="{tid}">{tname}</button>' for tid, tname in sections])
    
    # ── Terms of Service ──
    terms = f"""<div class="space-y-6"><div class="card"><h1 class="text-2xl font-black text-white mb-2">Terms of Service</h1><p class="text-xs text-gray-500">Last updated: {year}</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">1. Acceptance of Terms</h2><p class="text-xs text-gray-400 leading-relaxed">By accessing or using ShopZario (shopzario.com), you agree to be bound by these Terms of Service. If you do not agree, do not use our platform. We reserve the right to update these terms at any time; continued use constitutes acceptance.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">2. Account Registration</h2><p class="text-xs text-gray-400 leading-relaxed">You must provide accurate, current information when creating an account. You are responsible for maintaining confidentiality of your login credentials. You must be at least 18 years old to use our services.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">3. Purchases & Payments</h2><p class="text-xs text-gray-400 leading-relaxed">All prices are in USD. Payments are processed securely via Stripe. Upon successful payment, you receive instant access to digital downloads. We reserve the right to refuse or cancel orders.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">4. Digital Products</h2><p class="text-xs text-gray-400 leading-relaxed">All products are digital and delivered electronically. Due to the nature of digital goods, all sales are final unless covered by our refund policy. Products are licensed, not sold.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">5. User Conduct</h2><p class="text-xs text-gray-400 leading-relaxed">You agree not to: resell, redistribute, or share downloaded files; attempt to circumvent security; use the platform for illegal purposes; harass other users; or engage in fraudulent activity.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">6. Intellectual Property</h2><p class="text-xs text-gray-400 leading-relaxed">ShopZario and its content are protected by copyright and other laws. Our name, logo, and design are trademarks. Products retain their respective license terms.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">7. Limitation of Liability</h2><p class="text-xs text-gray-400 leading-relaxed">ShopZario is provided "as is" without warranties. We are not liable for damages arising from use of our platform. Our maximum liability is limited to the amount paid for the product in question.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">8. Termination</h2><p class="text-xs text-gray-400 leading-relaxed">We may terminate or suspend accounts for violation of these terms. Upon termination, your right to access the platform ceases immediately.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">9. Contact</h2><p class="text-xs text-gray-400 leading-relaxed">For questions about these terms: support@shopzario.com</p></div></div>"""

    # ── Privacy Policy ──
    privacy = f"""<div class="space-y-6"><div class="card"><h1 class="text-2xl font-black text-white mb-2">Privacy Policy</h1><p class="text-xs text-gray-500">Last updated: {year}</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">1. Information We Collect</h2><p class="text-xs text-gray-400 leading-relaxed">We collect: name, email address, billing information (processed by Stripe, never stored by us), IP address, browser type, pages visited, and purchase history. This data is collected when you create an account, make a purchase, or browse our platform.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">2. How We Use Your Data</h2><p class="text-xs text-gray-400 leading-relaxed">Your data is used to: process purchases, deliver downloads, send order confirmations, improve our platform, provide customer support, send occasional marketing (with consent), and prevent fraud.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">3. Data Sharing</h2><p class="text-xs text-gray-400 leading-relaxed">We do not sell your personal information. We share data only with: Stripe (payment processing), our hosting provider, and as required by law. Third parties have their own privacy policies.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">4. Data Retention</h2><p class="text-xs text-gray-400 leading-relaxed">We retain your data as long as your account is active. You may request deletion at any time. Payment data is retained only as required by tax laws.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">5. Your Rights</h2><p class="text-xs text-gray-400 leading-relaxed">You have the right to: access your data, correct inaccurate data, delete your data, object to processing, and export your data. Contact support@shopzario.com to exercise these rights.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">6. Security</h2><p class="text-xs text-gray-400 leading-relaxed">We use SSL encryption, secure payment processing via Stripe, and industry-standard security practices. No method of transmission is 100% secure, but we strive to protect your data.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">7. Children</h2><p class="text-xs text-gray-400 leading-relaxed">Our platform is not intended for users under 18. We do not knowingly collect data from children.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">8. Updates</h2><p class="text-xs text-gray-400 leading-relaxed">We may update this policy. Material changes will be notified via email or site notice.</p></div></div>"""

    # ── Refund Policy ──
    refund = f"""<div class="space-y-6"><div class="card"><h1 class="text-2xl font-black text-white mb-2">Refund & Cancellation Policy</h1><p class="text-xs text-gray-500">Last updated: {year}</p></div>

<div class="card" style="border-left:3px solid #4ade80"><h2 class="font-bold text-white text-base mb-3">30-Day Money-Back Guarantee</h2><p class="text-xs text-gray-400 leading-relaxed">We stand behind every product on ShopZario. If you are not completely satisfied with your purchase, we offer a full refund within 30 days of purchase. No questions asked.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">How to Request a Refund</h2><p class="text-xs text-gray-400 leading-relaxed">Email support@shopzario.com with your order ID and reason for refund. We process refunds within 3-5 business days. The refund is issued to your original payment method via Stripe.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">Eligibility</h2><p class="text-xs text-gray-400 leading-relaxed">Refunds are available for all digital products within 30 days of purchase. After 30 days, refunds are reviewed on a case-by-case basis. We reserve the right to deny refunds for abuse of this policy.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">Cancellations</h2><p class="text-xs text-gray-400 leading-relaxed">Since all purchases are one-time payments for digital downloads, there are no recurring subscriptions to cancel. Your purchase provides lifetime access to the product files.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">Chargebacks</h2><p class="text-xs text-gray-400 leading-relaxed">Initiating a chargeback without contacting us first may result in account suspension. Please contact us first — we will resolve any issue.</p></div></div>"""

    # ── Cookie Policy ──
    cookie = f"""<div class="space-y-6"><div class="card"><h1 class="text-2xl font-black text-white mb-2">Cookie Policy</h1><p class="text-xs text-gray-500">Last updated: {year}</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">What Are Cookies</h2><p class="text-xs text-gray-400 leading-relaxed">Cookies are small text files stored on your device by your browser. They help us remember your preferences, login status, and improve your experience.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">How We Use Cookies</h2><p class="text-xs text-gray-400 leading-relaxed">We use: essential cookies (login, security), preference cookies (remember settings), analytics cookies (page views, usage patterns via basic logging), and payment cookies (Stripe session handling).</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">Managing Cookies</h2><p class="text-xs text-gray-400 leading-relaxed">You can control cookies through your browser settings. Disabling cookies may affect site functionality. We do not use third-party tracking cookies for advertising.</p></div></div>"""

    # ── GDPR ──
    gdpr = f"""<div class="space-y-6"><div class="card"><h1 class="text-2xl font-black text-white mb-2">GDPR Compliance</h1><p class="text-xs text-gray-500">Last updated: {year}</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">Your Rights Under GDPR</h2><p class="text-xs text-gray-400 leading-relaxed">If you are in the European Economic Area, you have: right to access, right to rectification, right to erasure ({Q}right to be forgotten{Q}), right to restrict processing, right to data portability, right to object, and rights related to automated decision-making.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">Data Controller</h2><p class="text-xs text-gray-400 leading-relaxed">ShopZario is the data controller. Contact: support@shopzario.com. We process data based on: consent (marketing), contractual necessity (purchases), and legitimate interests (security).</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">Data Transfers</h2><p class="text-xs text-gray-400 leading-relaxed">Your data may be transferred to and processed in the United States. We use Standard Contractual Clauses for such transfers.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">Complaints</h2><p class="text-xs text-gray-400 leading-relaxed">You have the right to lodge a complaint with your local data protection authority.</p></div></div>"""

    # ── EULA ──
    eula = f"""<div class="space-y-6"><div class="card"><h1 class="text-2xl font-black text-white mb-2">End User License Agreement</h1><p class="text-xs text-gray-500">Last updated: {year}</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">License Grant</h2><p class="text-xs text-gray-400 leading-relaxed">Upon purchase, you receive a non-exclusive, non-transferable license to use the digital product for personal or commercial projects as specified by the product{Q}s license type (Standard, Commercial, or Extended).</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">Permitted Uses</h2><p class="text-xs text-gray-400 leading-relaxed">You may: use the product in personal projects, use in commercial client work (per license), modify and customize the files, create derivatives for your projects, and install on multiple devices you own.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">Prohibited Uses</h2><p class="text-xs text-gray-400 leading-relaxed">You may NOT: resell or redistribute the raw files, share your download link, claim the work as your own creation for resale, sublicense the product, or use in a way that competes with ShopZario.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">License Types</h2><p class="text-xs text-gray-400 leading-relaxed"><strong>Standard:</strong> Personal + commercial use in projects. Cannot resell raw files.<br><strong>Commercial:</strong> Full commercial use. Unlimited projects, client work included.<br><strong>Extended:</strong> Extended commercial. Incorporate into products you sell.</p></div></div>"""

    # ── Disclaimer ──
    disclaimer = f"""<div class="space-y-6"><div class="card"><h1 class="text-2xl font-black text-white mb-2">Disclaimer</h1><p class="text-xs text-gray-500">Last updated: {year}</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">General Disclaimer</h2><p class="text-xs text-gray-400 leading-relaxed">ShopZario provides digital products "as is" without warranty of any kind. We do not guarantee that products will meet your specific requirements or expectations.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">AI-Generated Content</h2><p class="text-xs text-gray-400 leading-relaxed">Some products may contain AI-generated content. While we strive for quality, AI-generated materials should be reviewed and customized before use in critical applications.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">No Professional Advice</h2><p class="text-xs text-gray-400 leading-relaxed">Products are not a substitute for professional legal, financial, or medical advice. Consult qualified professionals for specific needs.</p></div>

<div class="card"><h2 class="font-bold text-white text-base mb-3">External Links</h2><p class="text-xs text-gray-400 leading-relaxed">Our platform may link to third-party sites. We are not responsible for their content or practices.</p></div></div>"""

    # Tab content
    tab_content = f"""
    <div id="tab-terms" class="tab-content">{terms}</div>
    <div id="tab-privacy" class="tab-content hidden">{privacy}</div>
    <div id="tab-refund" class="tab-content hidden">{refund}</div>
    <div id="tab-cookie" class="tab-content hidden">{cookie}</div>
    <div id="tab-gdpr" class="tab-content hidden">{gdpr}</div>
    <div id="tab-eula" class="tab-content hidden">{eula}</div>
    <div id="tab-disclaimer" class="tab-content hidden">{disclaimer}</div>
    """
    
    html = """
    <div class="max-w-4xl mx-auto px-4 sm:px-6 py-6 md:py-10">
    <nav class="flex items-center gap-1.5 text-[11px] text-gray-500 mb-6">
    <a href="/" class="hover:text-purple-300 transition">Marketplace</a><span class="mx-1">/</span>
    <span class="text-gray-400 font-medium">Legals</span></nav>
    
    <div class="card mb-6">
    <h1 class="text-2xl md:text-3xl font-black text-white mb-2">Legal Information</h1>
    <p class="text-sm text-gray-400">Our policies, terms, and agreements</p>
    </div>
    
    <nav class="flex flex-wrap gap-2 mb-8 p-2 rounded-2xl bg-black/40 border border-white/10" role="tablist">""" + tabs + """</nav>
    """ + tab_content + """
    </div>
    
    <script>
    document.querySelectorAll('[data-tab]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            document.querySelectorAll('[data-tab]').forEach(function(b) {
                b.classList.remove('bg-[#a855f7]/15', 'text-white');
                b.classList.add('text-gray-400');
            });
            this.classList.add('bg-[#a855f7]/15', 'text-white');
            document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.add('hidden'); });
            document.getElementById('tab-' + this.dataset.tab).classList.remove('hidden');
        });
    });
    </script>
    """
    return html
