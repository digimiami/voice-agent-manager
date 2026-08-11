# 🚀 Diazites Marketing Plan
## From $0 → $5K MRR in 30 Days

**Current State:**
- 19 trial users, **0 paid** — all on free trials
- 5 affiliates, 0 clicks, 0 conversions
- Landing page live at diazites.online with signup funnel
- Product works: VAPI voice agents, SMS, booking, multi-agent, squad transfers

---

## WEEK 1: Conversion Sprint (Fix the leak)

### 1. Trial → Paid Conversion Sequence
**Problem:** 19 trial users, zero paying. The trial doesn't convert.
**Fix:** Build a 5-day email/SMS sequence:

| Day | Action | Channel |
|-----|--------|---------|
| Day 1 | Welcome + setup guide | Email |
| Day 2 | "Upload 10 leads + start your first campaign" | Email |
| Day 3 | "Here's a call recording from another {industry} business" | SMS |
| Day 4 | "Your trial ends in 3 days — here's what you're missing" | Email |
| Day 5 | "Last chance: 20% off first month if you upgrade today" | Email + SMS |

**Implementation:** Add `trial_day` column to businesses table, cron job runs daily to check trial age and trigger sequences.

### 2. Personal Outreach to Existing Trials
- Call/SMS each of the 19 trial users PERSONALLY
- Ask: "How's the AI agent working? Want me to help set up your first campaign?"
- Goal: Convert 5 to paid within 7 days = **$485-$985 MRR instantly**

---

## WEEK 2: Traffic Engines

### 3. Cold Outreach Automation
**Target:** Local businesses in high-intent verticals (auto dealers, plumbers, dentists, roofers)
**Method:**
- Scrape Google Maps for businesses WITHOUT websites/booking systems
- Cold DM on Instagram/Facebook: "We answer your missed calls 24/7 with AI — 3-day free trial"
- Follow-up sequence automated via cron

**Script:** Already have `maps_scraper.py` — extend it to output a DM list.

### 4. Content Marketing Machine
**Platform:** YouTube Shorts + TikTok + Instagram Reels
**Content types:**
- "AI answers a real plumber's call" (record actual VAPI calls, edit as shorts)
- "How much revenue this dentist lost from missed calls"
- "We replaced a receptionist with AI — here's what happened"
- Behind-the-scenes: "Building an AI call center in 60 seconds"

**Volume:** 3 shorts/day × 3 platforms = 9 posts/day
**Cron:** Daily at 9 AM, 12 PM, 6 PM via Zernio

### 5. Reddit Growth
Subreddits: r/sweatystartup, r/smallbusiness, r/Entrepreneur, r/plumbing, r/HVAC, r/autodetailing
**Strategy:** Provide VALUE first, soft-sell in comments
- "I built a free tool that answers missed calls for contractors — DM me"
- Answer questions about phone systems, customer service, automation
- Post case studies: "How a roofing company booked 12 jobs from missed calls"

---

## WEEK 3: Paid Acquisition

### 6. Facebook/Instagram Ads
**Budget:** $20/day test → scale winners
**Targeting:**
- Small business owners (auto dealers, contractors, dentists)
- Ages 25-55, US only
- Interests: "Small business", "Entrepreneur", industry-specific

**Creative:** Split test 3 angles:
1. "Never miss a customer call again" (pain point)
2. "This AI booked 47 appointments last week" (social proof)
3. "Try our AI receptionist free for 3 days" (offer)

**Landing page:** diazites.online (already built)

### 7. Google Ads — High Intent
**Keywords:** "AI phone answering service", "virtual receptionist for contractors", "AI call center for small business", "answer missed calls automatically"
**Budget:** $30/day
**Target:** US, mobile + desktop

---

## WEEK 4: Scale & Automate

### 8. Affiliate Program Push
You have 5 affiliates, 0 activity. Activate them:
- Send welcome email with swipe copy + creatives
- Offer 30% recurring commission (on $97-497/mo plans = $29-$149/mo per referral)
- Create a leaderboard + monthly bonus for top affiliate

### 9. Partnership Outreach
- **Integration partners:** CRM companies, booking software, website builders
- **Industry influencers:** YouTubers in plumbing/HVAC/auto niches
- **Offer:** "White-label our AI agent for your audience — you keep 50%"

### 10. Referral Program for Users
- "Refer a business, get 1 month free"
- Automated via unique referral link in dashboard
- Track in `referrals` table

---

## Automation Pipeline (Cron Jobs to Build)

| Job | Schedule | What it does |
|-----|----------|-------------|
| `diazites-trial-nurture` | Daily 9 AM | Email/SMS trial users based on day |
| `diazites-content-factory` | Daily 9 AM, 12 PM, 6 PM | Generate + post 3 shorts |
| `diazites-lead-scraper` | Daily 6 AM | Scrape 100 local businesses for outreach |
| `diazites-cold-outreach` | Daily 10 AM | DM scraped leads on Instagram |
| `diazites-reddit-engager` | Every 4h | Find relevant posts, draft replies |
| `diazites-weekly-report` | Monday 8 AM | MRR, trials, conversions, churn report |

---

## KPI Targets (30-Day)

| Metric | Current | 30-Day Target |
|--------|---------|---------------|
| Trial users | 19 | 100 |
| Paid subscribers | 0 | 15 |
| MRR | $0 | $2,500 |
| Trial → Paid rate | 0% | 15% |
| Affiliate conversions | 0 | 10 |
| Social followers | ? | 1,000 |

---

## Priority Order (Do THIS today)

1. **Call 5 trial users personally** — ask how it's going, help them set up
2. **Set up trial nurture emails** — at minimum Day 3 and Day 5 reminders
3. **Record 1 demo call** — turn it into a short, post to TikTok/Reels
4. **Scrape 50 local businesses** — have the list ready for outreach tomorrow
