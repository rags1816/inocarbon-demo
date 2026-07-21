# i-NoCarbon Freemium — Methodology

## Origin

Developed by Vijay L Narasimhan / i-NoCarbon, 2025–26, as the free,
demo-facing entry point into the i-NoCarbon product suite — designed to be
shown live to prospects and used as a lead-generation tool, while still
producing a genuinely useful carbon footprint assessment rather than a
throwaway marketing gimmick.

## Problem this solves

Most carbon calculators are either too shallow to be credible (a handful of
sliders, a single vague number) or too complex for a first touchpoint (full
Scope 1/2/3 GHG Protocol entry, as used in the full ESG Hub carbon
calculator). This freemium app sits deliberately in between — detailed
enough to produce a genuinely personalised, AI-explained result, simple
enough to complete and demo in a single sitting, with a clear upgrade path
into the fuller ESG Hub carbon calculator for businesses that want the
complete Scope 1/2/3 treatment.

## Built on / credited frameworks

- **Household/business carbon footprint estimation** — follows the same
  general principle as standard household carbon calculators (energy,
  transport, food/diet, waste as the core drivers), simplified relative to
  the full GHG Protocol Scope 1/2/3 model used in the ESG Hub carbon
  calculator (see that repo's METHODOLOGY.md for the complete version)
- **Dual-provider AI architecture** — a deliberate resilience design
  (shared in spirit with the ESG Diagnostic Toolkit's AI-optional
  approach): if one AI provider fails or is unavailable, the other can
  serve the request, keeping the demo reliable in front of a live audience

## Core framework (your original model)

**Scoped conversational AI, not open-ended chat:** the "Ask i-NoCarbon"
drawer deliberately locks the assistant to seven specific topics
(Energy saving, Transport & EVs, Food & diet, Waste & recycling, Cost
reduction, Carbon offsetting, My results explained) rather than allowing
free-form conversation. This is a design choice, not a limitation — it
keeps the assistant's answers grounded in the user's actual assessment
results and prevents the demo from drifting into unrelated or unreliable
territory in front of a live audience.

**Demo-first infrastructure:** the ngrok + GitHub Pages landing page
pattern exists specifically to solve a real friction point — ngrok's free
tier shows an unavoidable interstitial warning page that looks
unprofessional in a live demo. Fronting it with a branded GitHub Pages
landing page removes that friction for anyone scanning the QR code or
following a shared link, without requiring paid tunnelling infrastructure.

**GDPR-conscious by design:** the email report feature requires explicit
consent capture before any email is sent — not a bolt-on afterthought, but
built into the report-request flow itself.

## Inputs → Process → Outputs

- **Inputs:** household/business carbon-driver data (energy, transport,
  food, waste), user email (optional, for report delivery, with consent)
- **Process:** footprint calculation against standard carbon-driver
  factors, AI-generated personalised recommendations (via whichever
  provider — Claude or Gemini — is active), scoped conversational support
- **Outputs:** carbon footprint result, personalised recommendations,
  browser-based PDF export, optional emailed report

## Why this approach (rationale)

A freemium demo tool has a different job than a production ESG platform —
its purpose is to be credible enough to convert a prospect into a fuller
engagement (the ESG Hub or a direct i-NoCarbon consultation), not to be
the final word on someone's carbon footprint. Keeping the AI assistant
topic-locked and the infrastructure demo-resilient (dual AI fallback,
warning-free access via GitHub Pages) reflects that this tool is optimised
for live, in-person or shared-link demonstration first, general-purpose use
second.

## Version history

- v1 [date]: core freemium assessment, dual AI provider panel,
  personalised recommendations, PDF/email reporting with GDPR consent,
  "Ask i-NoCarbon" scoped drawer, ngrok + GitHub Pages demo tunnelling
- **Roadmap (Phase 2/3, not yet built):** AI-generated quiz questions based
  on footprint weak spots, multi-turn "Ask i-NoCarbon" conversation, video/
  article relevance summaries, AI scenario recommendation narratives,
  server-generated PDFs, lead follow-up automation
