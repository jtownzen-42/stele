# Stele — Master List (2026-10-16, compiled by Martha)
Status: NOTHING BUILT YET. Board posts HELD per Jason. Repo: H:\Projects\Stele (git, main @ snapshot commit).

## A. LICENSING DEAL — NON-NEGOTIABLE (owner: Claude)
- A1 EULA covering Free tier and Pro tier (LICENSE/EULA.txt): one-time $29 Pro, per-user, no redistribution, refund/support line, no warranty, model files belong to their licensors.
- A2 THIRD_PARTY_NOTICES.txt: PySide6/Qt (LGPLv3; onedir build so Qt DLLs are replaceable; link to source), huggingface_hub (Apache-2.0), ReportLab (BSD), keyring/comtypes/pywin32, httpx/requests, Ollama (MIT), llama.cpp (MIT).
- A3 LM Studio (proprietary): default OFF; opt-in with terms link + acknowledgment, or drop from runtime/manifest.json. Verify lmstudio.ai terms on archiving (Jason decides).
- A4 Model-license acknowledgment: keep enforced Acknowledge click + "Stele does not grant redistribution rights" on spec sheets/README_FIRST; add a test.
- A5 First-run EULA acceptance dialog; About/Licenses screen showing EULA + notices.

## B. ACTIVATION — NON-NEGOTIABLE (owner: Claude)
- B1 Remove plaintext _OFFLINE_SECRET (stele/license.py:31, HMAC) — it ships in the exe so anyone can mint keys. Drop offline keys for v1, or Ed25519 signatures with public key only in app (private key never in repo/exe). Note: secret is already in git history (commits 02c6696/a06edc0) and in the shipped exe → treat as burned; never reuse.
- B2 Gumroad verify: send product_id (not product_permalink "stele-studio", license.py:74-79); product_id as config constant; handle refunded/chargebacked/disputed, uses count, network errors, offline grace with cached signed result.
- B3 Gating: Free (no key) = search, download, docs, ISO export. Pro = disc burning + multi-disc spanning. Enforce in the burn/span code paths, not just the window title "[Unactivated]".
- B4 Tests: free-tier gating (burn/span blocked without license), Pro unlock with mocked Gumroad success, rejection on refunded/invalid/wrong product, no secret in source (grep test).
- B5 E2E verification plan: create Gumroad product (license keys on, draft), test purchase → activate → refund → confirm deactivation. NEEDS JASON'S OKAY (real money/listing action).
- B6 Optional $19 launch code (Gumroad offer code) — Jason decides; do not create live.

## C. BUILD / PACKAGING (owner: Codex-Work)
- C1 Rebuild Stele.zip from dist\Stele only (current 273.6 MB zip is the source folder + .venv/.pytest_cache, no exe). Also the Drive copy (Steele/Stele.zip) is the bad zip — replace only with Jason's okay.
- C2 stele.spec: onedir (LGPL), bundle EULA/notices/assets, exclude tests/caches; build_stele.py reproducible.
- C3 Runtime manifest: LM Studio opt-in flag (UI wiring in Claude's lane; manifest/packaging in Codex lane — see split).
- C4 SHA256SUMS for release zip + exe; VirusTotal scan prep (Jason uploads/okays); Defender false-positive submission if flagged.
- C5 Unsigned exe → SmartScreen FAQ line; evaluate Azure Trusted Signing (~$10/mo) — purchase needs Jason.
- C6 README: install, Free vs Pro, licensing, notices, SHA256 verification, support/refund.
- C7 Listing polish (/workspace/stele-launch/gumroad-listing.md, x-posts.md, cover-brief.md): Free vs Pro table, model-license note, SmartScreen FAQ; screenshots + 30s demo after UI redesign. No publishing.

## D. Product upgrades & UI/UX improvements (Martha)
- D1 UI/UX redesign — ASSIGNED TO CLAUDE. Direction: classic Windows application, but modern like current Linux desktops (GNOME / KDE Plasma): clean, restrained, purposeful; native-feeling widgets; clear hierarchy; sensible spacing; light/dark following the system theme. Explicitly NOT AI-slop: no neon gradients, no glassmorphism, no generic chatbot-gray UI.
- (More items pending from Jason — placeholder.)

## E. Open items / notes
- Repo had uncommitted UI work (stele/ui/theme.py, stele/ui/assets/, tests/test_ui_presentation.py, edits to app.py, main_window.py, burn_page.py, discover.py, stele.spec) — committed as a snapshot so both worktrees start equal; Claude reviews it under D1.
- TODO/FIXME grep across repo (excl .venv/dist/build): none found.
- Board: no active Stele thread; Codex 10-15 handback notes "Stele stays with its separate owning chat" (47 tests + Qt smoke reported, not rerun). Confirm ownership before release of board posts.
- Remote origin/main exists — NO push (Jason's rule).
- Drive: Steele folder has Stele.txt spec, bad Stele.zip, run_stele.bat; no other notes.
- Pricing (proposed, not live): $29 one-time Pro; Free tier as above; optional $19 launch code.

## F. Integration order
1. Claude: B1+B2+B3+B4 (license.py, gating) → merge to main first.
2. Claude: A1/A2/A4/A5 texts + dialogs → merge.
3. Codex: rebase on main, bundle EULA/notices in spec, LM Studio opt-in manifest, README → merge.
4. Claude: D1 UI redesign → merge (rebased on 3).
5. Codex: final dist build, zip, SHA256, VirusTotal prep, listing screenshots.
6. Jason: Gumroad test purchase + refund (B5), then go/no-go.
