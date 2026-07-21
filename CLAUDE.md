# CLAUDE.md

Persistent context for Claude Code sessions in this repo. Read this before
starting work.

## Who this repo belongs to

Owned by Vijay L Narasimhan (GitHub: rags1816). Part of a wider portfolio
of applied tools — see the hub page at https://rags1816.github.io for the
full list. Each repo is independent but follows the same conventions below
for consistency across the portfolio.

## Repo structure convention

- **Root** — only the live app file(s) (e.g. `index.html`), `README.md`,
  `METHODOLOGY.md`, `LICENSE`, `.gitignore`. Keep root clean; nothing else
  belongs there.
- **`docs/`** — user guides, admin guides, reference guides, and any
  supporting documentation not needed to run the app.
- **`archive/`** — superseded versions, old HTML/app snapshots, deprecated
  scripts. Kept for history, not deleted, unless confirmed genuinely
  redundant (e.g. a byte-identical duplicate).
- **`tools/`** — utility/build scripts still actively used, if any (keep
  separate from `archive/`, which is for scripts no longer used).

## Documentation files — what each one is for

- **`README.md`** — what the app does, current status, tech stack, how to
  run it. Must end with a **Development note** section (see below) and a
  **Related** section pointing to METHODOLOGY.md.
- **`METHODOLOGY.md`** — the original framework/methodology behind the
  tool. This is the IP-protection document — states origin, credits any
  established frameworks the tool builds on (with clear attribution, e.g.
  Kraljic, Porter's Five Forces), and describes the original contribution
  clearly separated from the credited frameworks.
- **`LICENSE`** — explicit "All Rights Reserved" copyright, present in
  every repo individually (do not rely on inherited/default licensing —
  confirmed unreliable across this portfolio; always add the file
  directly). Exception: Raaga, which is deliberately MIT-licensed.

## Standard "Development note" section for README.md

Every README ends with this section, verbatim, before "Related":

```markdown
## Development note

Development assisted by Claude Code (Anthropic) under my direction. The
methodology, product design, and domain expertise reflected in this tool
are my own — see `METHODOLOGY.md` for the original framework.
```

## Workflow rules — always follow these

1. **Never commit without showing a diff first and waiting for explicit
   confirmation.** A stop-hook nudge about uncommitted changes is not
   confirmation — only an explicit go-ahead from Vijay counts.
2. **Never force-push** without explicit, separate confirmation — treat
   this as a distinct, higher-caution action from a normal push.
3. **Before any file reorg**, check whether files referenced by the live
   app (script tags, asset paths, sound files, etc.) would be affected.
   Search the app file for references before moving anything that could
   plausibly be a runtime dependency. Report findings before moving, don't
   assume.
4. **Work happens on a feature branch, then via PR into `main`.** Direct
   pushes to `main` should be avoided — branch protection may not be
   enabled on all repos yet, but the convention is PR-first regardless.
5. **After a PR merges, the remote feature branch is not auto-deleted.**
   Flag it and offer to delete it — if deletion 403s (a known permission
   gap with the current GitHub App install), tell Vijay to delete it
   manually via the repo's Branches page rather than retrying.
6. **Never hardcode API keys, passwords, or secrets into any file.** Keys
   are supplied at runtime (env vars, UI input, or session input) — this
   is a firm project-wide rule, not a per-repo preference.
7. **Flag, don't silently fix, anything that looks like real personal
   data, credentials, or PII** in any file being touched — stop and ask
   before proceeding, even if it seems like test data.

## Known environment quirks

- The GitHub App integration can push and merge but **cannot delete
  branches** (consistent 403) — this is expected, not a bug to keep
  retrying.
- Commit signing may show as unverifiable in local hooks even when the
  actual signature is present and GitHub verifies it server-side after
  push — don't treat a local signing-check failure as blocking on its own.

## When in doubt

Report findings and ask, rather than assuming — this repo (and the wider
portfolio) prioritises careful, reviewed changes over speed.
