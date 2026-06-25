# i-NoCarbon Freemium — Handover Document
**Date:** 25 June 2026
**Prepared by:** Claude (Anthropic) — Session handover for future conversations
**Owner:** Vijay L Narasimhan, i-NoCarbon Limited
**Status:** FROZEN — Demo-ready baseline for 8 July 2026

---

## FREEZE RECORD — 25 Jun 2026

| File | MD5 | Bytes |
|---|---|---|
| `index.html` | `a9c9c24f76fcf830dc032bbc6258a488` | 342,320 |
| `run_freemium.py` | `e748ae2b01c05b8fc51d11588d8495bc` | 104,644 |

---

## 1. File Structure

```
C:\iNoCarbon-Platform\freemium\
  run_freemium.py              ← Flask backend (Python)
  templates\
    index.html                 ← Main app (Jinja2 template)
    privacy.html
    upgrade.html
  static\
    icon-192.png
    icon-32.png
    favicon.ico
    apple-touch-icon.png
    manifest.json
    mobile.js
  .env                         ← Environment variables (never commit)
  freemium.db                  ← SQLite database (leads, session data)
  requirements.txt
```

---

## 2. Environment Variables (.env)

```
ADMIN_USER=admin
ADMIN_PASS=iN0carb0N@2020
FREEMIUM_PORT=5002
AI_MAX_PER_HOUR=20
ACTIVE_AI_PROVIDER=gemini
AI_ENTRY_ENABLED=0
```

---

## 3. All Four Access Methods

| # | Method | URL / Command | Permanent? |
|---|---|---|---|
| 1 | Localhost | http://localhost:5002 | ✅ Always |
| 2 | GitHub Pages | https://rags1816.github.io/inocarbon-demo | ✅ Always (landing page) |
| 3 | Cloudflare tunnel | cloudflared tunnel --url http://localhost:5002 | ❌ Changes on restart |
| 4 | ngrok tunnel | ngrok http 5002 | ❌ Changes on restart |

**Pre-session routine (every demo):**
1. `python run_freemium.py` in Terminal 1
2. `cloudflared tunnel --url http://localhost:5002` in Terminal 2
3. Copy the tunnel URL
4. Update `DEMO_URL` in GitHub Pages index.html and push
5. Test tunnel URL in browser
6. Admin login → set AI key → turn AI ON

---

## 4. Admin Credentials

`admin / iN0carb0N@2020`

Admin Panel: click the ⚙️ icon in the header (admin session only)

---

## 5. What Was Built — 25 June 2026 Session

### Demo Tour (13 steps, Tour X of 13 counter)
- Tour counter changed from "Step X of Y" to "Tour X of Y" — disambiguates from calculator's own Step 1–5 labels
- Step 2 (AI Quick Entry): delayed scroll (500ms) so AI panel is visible before card renders; text updated to mention Gemini/Claude by name and note that parse skips if no key active
- Step 3 (Parsing): clarified AI fills all fields in one go
- Step 4 post-parse success message: references AI status badge and active provider
- Step 8 completion message: now says "open the 📉 Scenarios panel" not "explore Smart Optimisation"
- NEW Step 9 (pre-Scenarios warning): tells user what Scenarios panel does before it auto-opens; highlights the drawer button
- Step 10 (Scenarios): renamed to "📉 Scenarios Panel — Smart Optimisation"; text names the panel correctly
- NEW Step 12 (Ask i-NoCarbon): shows purple 💬 panel, explains topic dropdown and footprint-grounded answers, mentions adding own key to unlock

### AI Status — 5 badge locations
- Green summary band: `🤖 AI recommendations: Personalised via Gemini` or `Off — add a free Gemini key to unlock personalised actions`
- Actions drawer button: `✨ AI` (green) or `⚠️ AI off` (grey)
- Actions drawer interior: green `✨ Personalised by AI` or amber `⚠️ AI is off` banner
- Scenarios drawer button: `💡 AI picks best` or hidden
- Carbon Quiz drawer button: `✨ AI questions` or hidden
- Ask i-NoCarbon button: `✨ AI on` (purple) or `⚠️ needs AI key` (grey) — note: "AI key" not just "key"

### Tour AI Auto-Restore (backend)
- `/api/tour-start` (POST, admin only): snapshots AI state before tour begins
- `/api/tour-ai-reset` (POST, any session): if AI was OFF before tour, turns it back off on exit
- `_tour_ai_was_on` variable in run_freemium.py holds snapshot (in-process memory)
- On tour exit: `_adminAiOn = false`, all badges update, Admin Panel reloads if open

### Welcome Popup (post-reset)
- Triggers after tour exit (400ms delay) and after User Mode badge reset (300ms delay)
- Three prompts: Review Assumptions, Enter figures, Optional AI key
- "Got it — let's go! 🚀" button dismisses and scrolls to Assumptions & Settings
- Overlay with blur backdrop; fully responsive

### Ask i-NoCarbon (9th drawer, full-width purple button)
- Topic dropdown: Energy saving, Transport & EVs, Food & diet, Waste & recycling, Cost reduction, Carbon offsetting, My results explained
- Footprint context (energy/transport/food/hotel kg CO₂e) sent automatically with question
- AI answers in 3–5 sentences, on-topic only
- Badge: `✨ AI on` / `⚠️ needs AI key`

### User Mode Badge
- Clickable reset button in header (non-tour sessions only)
- Confirm prompt if data entered; immediate reset if blank
- Disappears during tour; reappears on exit

### PDF Report & Email Capture
- `📄 Download My Carbon Report` in header and drawer grid
- Email panel with GDPR consent checkbox (unchecked by default)
- Leads stored in freemium.db; notification to info@i-nocarbon.com if SMTP configured
- View leads: `/admin/leads?key=YOUR_ADMIN_KEY`

### Backend (run_freemium.py)
- `mode: freetext` for Ask i-NoCarbon — plain text response
- Provider priority: Admin key → User Gemini → User Anthropic
- Anthropic retry: `claude-haiku-4-5-20251001` → `claude-sonnet-4-6` → `claude-opus-4-7`
- Gemini retry: `gemini-3.1-flash-lite` → `gemini-2.5-flash` → `gemini-3.5-flash`
- Retry codes: 400, 404, 429, 500, 529 (both providers)
- ProxyFix(x_proto=1, x_host=1) for Cloudflare/ngrok HTTPS
- before_request skips POST — login works correctly over tunnels
- Admin leads f-string null-safe
- `/api/tour-start` and `/api/tour-ai-reset` endpoints

---

## 6. Key Design Decisions

- **Admin always wins**: when both admin and user keys are set, admin key is used
- **User key = sessionStorage only**: cleared on tab close, never stored server-side except per-request
- **Tour counter = "Tour X of 13"**: avoids confusion with calculator's Step 1–5 labels
- **Tour without AI**: tour runs fine without a key — parse step skips silently
- **AI auto-off after tour**: only fires if admin had AI OFF before starting tour
- **Welcome popup**: shown after tour exit AND after User Mode badge reset
- **Never open index.html as a local file**: Jinja2 template — always serve via python run_freemium.py

---

## 7. Known Limitations (pre-cloud)

- Cloudflare/ngrok URL changes every restart — must update GitHub Pages DEMO_URL each session
- `_tour_ai_was_on` is in-process memory — lost if server restarts mid-demo
- SQLite freemium.db resets on Render redeploy (future)
- Hardcoded Windows paths must be removed before cloud deployment

---

## 8. Post-Demo Roadmap

### Phase 2 — Quick Wins
- AI quiz questions from footprint weak spots (`/api/ai-quiz` endpoint)
- Ask i-NoCarbon multi-turn conversation (JS history)
- Suggested questions based on footprint profile

### Phase 3 — Later
- Server-generated branded PDF (proper PDF with logo)
- AI scenario recommendation narrative
- Video/article relevance summaries
- Lead follow-up automation

### Hosting
- Now: Cloudflare/ngrok tunnel (demo sessions)
- Next: Render free tier
- Future: Render paid ($7/mo) + demo.i-nocarbon.com via Krystal

---

## 9. Contact & Resources

- **Owner:** Vijay L Narasimhan — lvijayaraghavan@hotmail.com
- **Notify email:** info@i-nocarbon.com
- **GitHub:** rags1816
- **GitHub Pages:** https://rags1816.github.io/inocarbon-demo
- **Gemini keys:** https://aistudio.google.com/apikey
- **Anthropic keys:** https://console.anthropic.com/settings/keys
- **Cloudflare dashboard:** https://dash.cloudflare.com
- **ngrok dashboard:** https://dashboard.ngrok.com
