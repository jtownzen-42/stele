# WORKSTREAM: OpenAI/Codex-Work — build & packaging
Worktree: H:\Projects\Stele-wt-openai  Branch: openai/build-packaging
Status: HOLD — do not start until Martha/Jason release the board request. Nothing gets built yet.

## Rules
- Do NOT edit files owned by the other stream (list below). Need a change there? Note it in HANDOFF section and ask Martha.
- No publishing, no public posts, no live pricing, no git push, no purchases.
- Commit locally on your branch only. Keep tests green (python -m pytest).
- Never commit secrets or private keys.
- Full context: STELE_MASTER_LIST.md in repo root.

## Owned files
stele.spec, build_stele.py, run_stele.bat, README.md, stele/runtime/manifest.json (data only), release/* (zip, SHA256SUMS, VT notes), docs/listing/*.
## Not yours (Claude)
stele/license.py, stele/ui/**, stele/app.py, stele/burn/*, tests/test_license*/gating*/ui*, EULA.txt, THIRD_PARTY_NOTICES.txt text (you bundle them, Claude writes them).
## Tasks
1. C1 rebuild zip from dist\Stele only (after Claude's merge; build only when released).
2. C2 spec: onedir (LGPL), bundle EULA/notices/assets, exclude tests/caches.
3. C3 manifest: LM Studio flagged opt_in/proprietary with terms URL.
4. C4 SHA256SUMS + VirusTotal prep (upload needs Jason).
5. C5 SmartScreen FAQ; signing options memo (purchase needs Jason).
6. C6 README: install, Free vs Pro, licenses, SHA256 verify, support/refund.
7. C7 listing polish (draft only, from /workspace/stele-launch).
## Product upgrades & UI/UX improvements (Martha)
- (UI redesign is Claude's; more items pending from Jason)
