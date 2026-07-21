# i-NoCarbon Freemium

A free-tier carbon footprint assessment app for businesses and households —
built as the demo/lead-generation entry point into the wider i-NoCarbon
product suite (see also the ESG Diagnostic Toolkit and ESG Hub).

## What it does

- **Carbon footprint assessment** — guided input covering the core
  household/business carbon drivers
- **Dual AI provider panel** — Gemini and Claude both available, with a
  dual AI status line showing which provider is active and responding
- **Personalised recommendations** — AI-generated suggestions based on the
  user's specific footprint inputs
- **PDF report** — browser print-to-PDF export of results and
  recommendations
- **Email report** — sends results to the user's email, with explicit GDPR
  consent capture before sending
- **"Ask i-NoCarbon" drawer** — an in-app chat assistant scoped to a locked
  set of topics (Energy saving, Transport & EVs, Food & diet, Waste &
  recycling, Cost reduction, Carbon offsetting, My results explained) —
  deliberately topic-limited rather than open-ended
- **SQLite storage** — lightweight local persistence for the demo
  environment

## Status

Demo / freemium. Deployed for live demonstrations (ngrok tunnel +
branded GitHub Pages landing page as intermediary) as well as hosted
post-demo via Render.

## Tech stack

Flask (Python) backend, SQLite storage, dual AI integration (Anthropic
Claude + Google Gemini). Demo access via ngrok tunnel fronted by a GitHub
Pages landing page (avoids ngrok's free-tier browser warning friction); QR
code (`qrco.de/INCFreemium`) routes to the same landing page. A
`start_demo.bat` script provides one-click local demo launch.

## How to run locally

Requires Python/Flask environment setup — see in-repo setup notes for
dependency installation and environment variable configuration (AI API
keys are supplied at runtime, never hardcoded).

## Development note

Development assisted by Claude Code (Anthropic) under my direction. The
methodology, product design, and domain expertise reflected in this tool
are my own — see `METHODOLOGY.md` for the original framework.

## Related

See [`METHODOLOGY.md`](./METHODOLOGY.md) for the underlying carbon
assessment approach and recommendation logic. Part of a wider suite — see
also the [ESG Diagnostic Toolkit](https://github.com/rags1816/ESGdiagnostics)
and [ESG Hub](https://github.com/rags1816/ESG_BcorpHub).
