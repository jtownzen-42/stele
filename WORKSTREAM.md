# WORKSTREAM: Claude — activation, licensing, security, EULA, tests, UI/UX
Worktree: H:\Projects\Stele-wt-claude  Branch: claude/activation-licensing
Status: HOLD — do not start until Martha/Jason release the board request. Nothing gets built yet.

## Rules
- Do NOT edit files owned by the other stream (list below). Need a change there? Note it in HANDOFF section and ask Martha.
- No publishing, no public posts, no live pricing, no git push, no purchases.
- Commit locally on your branch only. Keep tests green (python -m pytest).
- Never commit secrets or private keys.
- Full context: STELE_MASTER_LIST.md in repo root.

## Owned files
stele/license.py, any new stele/licensing/*, stele/ui/** (all UI incl theme.py, assets, pages, dialogs), stele/app.py, stele/burn/* gating hooks, tests/test_license*.py, tests/test_gating*.py, tests/test_ui*.py, LICENSE/EULA.txt, THIRD_PARTY_NOTICES.txt (text).
## Not yours (Codex-Work)
stele.spec, build_stele.py, run_stele.bat, README.md, stele/runtime/manifest.json, release/*, dist/build, listing files.
## Tasks (priority order)
1. B1 remove _OFFLINE_SECRET; drop offline keys or Ed25519 (public key only shipped).
2. B2 Gumroad verify with product_id; refunded/disputed/invalid handling; cached result + grace.
3. B3 enforce Free vs Pro: Free = search/download/docs/ISO export; Pro = burn + multi-disc spanning.
4. B4 tests: free gating, pro unlock (mocked), rejections, no-secret-in-source.
5. B5 write E2E plan (Gumroad test purchase+refund) — execution needs Jason.
6. A1 EULA (Free+Pro), A2 THIRD_PARTY_NOTICES text, A3 LM Studio opt-in UI + ack, A4 model-license ack test, A5 first-run EULA + About/Licenses.
## Product upgrades & UI/UX improvements (Martha)
- D1 UI/UX redesign: classic Windows application, but modern like current Linux desktops (GNOME/KDE Plasma): clean, restrained, purposeful; native-feeling widgets; clear hierarchy; sensible spacing; light/dark follows system. NOT AI-slop: no neon gradients, no glassmorphism, no generic chatbot-gray UI. Do after licensing/activation.
- (more items pending from Jason)
