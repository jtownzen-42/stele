# STELE Studio — Competitive Intelligence & Positioning Report

> Follow-up (2026-10-26): [Community and official burner verification](STELE_RESEARCH_FOLLOWUP_2026-10-26.md) updates the demand evidence and burner comparisons below. Other product, marketplace and news claims retain their original verification limits.

Evidence date: 2026-10-26. Scope: best-effort web pass plus the local STELE clone at `H:\projects\Stele` (the GitHub MCP connection failed, so the private remote was not accessed; findings are from the local `main` @ a0bdd4c).

Labels: **[F]** verified fact · **[I]** source-supported inference · **[E]** estimate · **[R]** recommendation · **[H]** unverified hypothesis.
This is not exhaustive. Initial pass: Reddit, X and Discord were not directly retrievable. Follow-up: several Reddit threads now read in-browser; X and Discord remain unresolved. "Not verified" means exactly that, not "absent".

---
## Part I — Executive Assessment
- **[F]** I found **no product that does STELE's whole job** (Hub acquisition → docs → UDF ISO/disc burn → readback → offline restore script) in one Windows app. I also found no GitHub project that burns HF weights to disc (one search; not proof of absence).
- **[I]** The real competitor is the **free DIY toolchain**: `hf download --revision --local-dir` + `hf cache verify` + 7-Zip/PAR2 + a burner (BurnAware/CDBurnerXP/ImgBurn). It beats STELE on flexibility and price, loses on integration and effort.
- **[F]** Timing tailwinds are real, not hypothetical: NVIDIA agreed to acquire Hugging Face (announced Sept 3 2026, close expected H1 2027); HF disclosed a breach (reported Jul 20 2026); "Pirate Face" (torrent mirror of HF models "against deletion") hit Hacker News Sept 20–21 2026. These prove *anxiety about hub permanence*, not buyers of an optical-disc tool.
- **[F]** Direct *willingness to pay* evidence: **none found.** Optical-specific interest is now verified: a LocalLLaMA thread explicitly discusses model backups to Blu-ray/M-DISC (146 displayed votes, 68 comments). Paid demand remains unproven; see follow-up.
- **[R]** Viable as a small niche utility; $29 is defensible but not a volume play. Biggest product risks: no real-world E2E release validation, no oversized-file splitting, and a **burned license secret** (see Part XIII).

## Part II — STELE Baseline (source-verified, local clone)
| Claim | Status |
|---|---|
| HF search/inspect, resumable Range downloads (no `snapshot_download`), vault + SQLite, commit-pinned `MODELS/<org>--<repo>/<commit>/` | README documents; code present **[F]** |
| UDF ISO + IMAPI2 burn, optional readback vs `checksums.sha256` | `burn/imapi.py` (`burn_directory`, `verify_volume`) — **Implemented but unverified in the field** |
| Multi-disc packing | `burn/span.py`: largest-first best-fit, **never splits a file**; errors if a file > disc. **[F]** |
| `RESTORE.ps1`, manifest, VOLUME.json, spec/how-to PDFs, labels | code present (`restore/`, `docs/`) |
| PAR2, hubs other than HF, oversized-file splitting | **Missing [F]** (grep of source; README confirms no split) |
| Free/Pro gating (burn + spanning = Pro) | **Plan only** (Master List B3, dated 2026-10-16, says "NOTHING BUILT YET"). Not current functionality. |
| Licensing | `license.py` has Gumroad verify using `product_permalink` and a plaintext HMAC `_OFFLINE_SECRET` (line 31) in repo history and shipped exe — Master List already flags it as burned |
| Tests | 47 reported by prior owner, not rerun by me; none download or touch a drive |

## Part III — Competitor Inventory (verified)
Dates: all checked 2026-10-26. Stars were only readable where noted; releases/commit dates **Not verified** (fetch showed no release data).

| Product | URL | Category | Platform | Price | Overlap | Notes / evidence |
|---|---|---|---|---|---|---|
| huggingface_hub / `hf` CLI | huggingface.co/docs/huggingface_hub/guides/cli | Direct/OSS | Win/mac/Linux, CLI | Free | Partly (acquisition+verify) | `--revision` (commit/branch/tag), `--local-dir`, `--include/--exclude`, `--token`, `--dry-run`; `hf cache verify` checks local files against Hub checksums incl. `--local-dir`. No archive/optical output. |
| HuggingFaceModelDownloader (bodaay) | github.com/bodaay/HuggingFaceModelDownloader | Direct/OSS | Win/mac/Linux/Docker, CLI+web UI | Free, Apache-2.0 | Partly | 1.2k stars/130 forks; LFS SHA256 always, `--verify none/size/etag/sha256`, `--revision`, writes commit to `hfd.yaml`, auto-resume, winget available. No optical. |
| Rodel Downloader | github.com/Richasy/Rodel.Downloader | Direct/OSS | Windows only (UI + CLI, .NET 8) | Free, GPL-3.0 | Partly | aria2-based; HF (+HF-Mirror), ModelScope, Civitai; 113 stars/9 forks/18 commits; no hashing documented. **Only verified multi-hub Windows GUI** — beats STELE on hub coverage. |
| HuggingHack | github.com/qasidah7544/HuggingHack | Direct | Windows GUI | Not verified | Partly | download + library view; archive features not found. |
| Pirate Face | pirateface.co | Preservation | Web/CLI/pip | Free to browse/download | Partly (different mechanism) | Torrent mirror of HF models with HF SHA-256; Apache/MIT/WTFPL/OpenMDW/Gemma/LFM/Muse; "Rescued" status when HF source gone; availability depends on seeders; HN #1 Sept 20–21 2026 (points differ by mirror: 436/133 vs 256/97). |
| aimm `hf-backup` (BAUER GROUP) | pypi.org/project/bg-ai-model-management | Direct/OSS | Python | Free, MIT | Partly | Backs up HF/ModelScope repos to S3-compatible storage. Only seen via search snippet — **Not verified** beyond that. |
| CivArchive | civitaiarchive.com/about | Adjacent | Web | Free | Loosely | Indexes Civitai models by SHA256; hosts no files. |
| Civitai Data Manager | selfhostyourself.com/services/civitai-data-manager | Adjacent | CLI | Free | Loosely | Archives metadata for local safetensors. |
| ComfyUI-Lora-Manager | github.com/willmiao/ComfyUI-Lora-Manager | Adjacent | plugin | Free | Loosely | Metadata archive DB for models deleted from Civitai. |
| Stability Matrix | github.com/LykosAI/StabilityMatrix | Adjacent | Win/others | Free | Loosely | Model browser for CivitAI + HF, shared model folder. |
| LM Studio | lmstudio.ai | Adjacent | Win/mac/Linux | Free for personal and work (Jul 2025 post) | Loosely | Runner; also a candidate STELE runtime-pack item (Master List A3 flags its terms). |
| BurnAware | burnaware.com | Optical | Windows | Free personal / Premium $29.95 / Professional $39.95 | Partly | Official sources now confirm BDXL/M-DISC, UDF, ISO, verification and spanning (Premium+). Perpetual paid license, one year updates; see follow-up. |
| CDBurnerXP | (AlternativeTo listing only) | Optical | Windows | Free | Partly | Blu-ray, ISO, spanning, verify per listing; installer bundles adware per listing. Official features page returned 403 in follow-up; third-party claims remain unverified. |
| ImgBurn | https://www.imgburn.com/ | Optical | Windows; Windows 11 not tested | Freeware / optional donations | Partly | Officially documents Blu-ray, image build/write, UDF and verify/compare. Current listed release 2.5.8.0 (2013-06-16). No commercial bundling; see follow-up. |
| AnyBurn, PowerISO, UltraISO, Express Burn | — | Optical | Windows | mixed | Partly | Named in AlternativeTo only; **not individually verified.** |
| Ollama tools (ollama-toolkit, ollama_utils) | PyPI/GitHub (search snippets) | Adjacent | CLI | Free | Partly | tar.gz export of Ollama models; no official export command found. **Not verified.** |
| ModelScope CLI, kagglehub | PyPI | Direct | CLI | Free | Partly | Provide the other hubs STELE lacks. |

**Marketplaces (Part VII summary):** One search for paid AI-model backup tools on Gumroad/itch.io/Lemon Squeezy returned **no listings**; every Windows-capable result was free/OSS. That is a weak negative (one query, search engine rather than storefront search) — **no verified paid competitor found; Etsy and Microsoft Store not checked.**

## Part IV — Feature Matrix (STELE vs closest)
Y=documented, P=partial, N=no, ?=unknown. STELE column = code/README, not field-tested.

| Feature | STELE | hf CLI | bodaay | Rodel | Pirate Face | BurnAware |
|---|---|---|---|---|---|---|
| Native Windows GUI | Y | N | N (web UI) | Y | N | Y |
| HF integration | Y | Y | Y | Y | Y | N |
| Other hubs | N | N | N | Y (MS, Civitai) | N | N |
| Revision pinning | Y | Y | Y | ? | ? | N |
| Resumable | Y | P (skips up-to-date) | Y | Y (aria2) | Y (torrent) | N |
| Gated repos/token | Y | Y | Y | ? | ? | N |
| SHA-256 | Y | Y | Y | N/? | Y | ? |
| Generated tech docs | Y | N | N | N | N | N |
| Local catalog | Y | P (cache scan) | P | ? | N | N |
| ISO export | Y | N | N | N | N | Y |
| Optical burn | Y | N | N | N | N | Y |
| M-DISC | P (treated as plain BD-R) | N | N | N | N | Y (officially documented) |
| Capacity planning / multi-volume | Y | N | N | N | N | Y (spanning, Premium+) |
| Oversized-file split | **N** | N | N | N | N | ? |
| Offline restore script | Y | N | N | N | N | N |
| Restore verification | P (readback; restore itself unverified) | P (`cache verify`) | Y | N | Y | ? |
| Archived runtimes | Y | N | N | N | N | N |
| Open-format recovery | Y (plain files + sha256) | Y | Y | Y | Y | Y |
| Source available | ? (private) | Y | Y | Y | partial | N |

## Part V — Top Ten (weighted)
Scores are **[E]** my 0–10 judgments from documented features, weights per your brief. STELE for reference scores ~6.5 (unreleased; commercial 2).

| # | Competitor | Acq 20 | Arch 25 | Optical 20 | Win 10 | Integ 10 | Meta 10 | Comm 5 | **Total** |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **DIY toolchain** (hf CLI + 7-Zip/PAR2 + burner) — a workflow, not a product | 9 | 7 | 8 | 3 | 7 | 5 | 8 | **7.1** |
| 2 | HF CLI / huggingface_hub | 9 | 4 | 0 | 4 | 7 | 6 | 10 | 5.0 |
| 3 | bodaay HF Model Downloader | 9 | 4 | 0 | 5 | 8 | 6 | 6 | 5.0 |
| 4 | Pirate Face | 6 | 6 | 0 | 3 | 7 | 4 | 6 | 4.4 |
| 5 | BurnAware (rescored after official-source check: optical 7→8, commercial 7→8) | 0 | 3 | 8 | 8 | 4 | 0 | 8 | 4.0 |
| 6 | Rodel Downloader | 7 | 2 | 0 | 8 | 2 | 3 | 5 | 3.5 |
| 7 | Stability Matrix | 5 | 2 | 0 | 8 | 2 | 5 | 8 | 3.4 |
| 8 | Civitai tools (CivArchive/Data Manager) | 3 | 4 | 0 | 3 | 6 | 7 | 3 | 3.4 |
| 9 | CDBurnerXP (**unconfirmed**: official page returned 403; scores rest on third-party listings) | 0 | 2 | 5 | 7 | 4 | 0 | 6 | 2.9 |
| 10 | LM Studio | 4 | 1 | 0 | 9 | 2 | 3 | 9 | 2.9 |

Why it matters: #1 is free and covers every STELE step; the 7.1 vs 6.5 gap is exactly "setup effort" STELE sells. #2–3 challenge acquisition/verification and are free (no price pressure room — STELE can't charge for downloading). #4 attacks the *reason to archive* (permanence) with a free, no-hardware alternative, but only for permissive licenses and seeder-dependent. #5/#9 compete for the burn step; STELE's advantage is model-aware layout/docs/restore, not burning. BurnAware ($29.95 Premium, same price point as STELE) officially offers UDF, BDXL/M-DISC, spanning and byte-by-byte verify, so ISO, M-DISC and readback alone are not differentiators. ImgBurn (free; UDF, Blu-ray, verify/compare; last release 2013; license bars bundling it in a commercial app) is unranked: it is a free burner, not a model workflow. Neither documents oversized-file splitting or SHA-256 manifest validation. #6 is the one to watch for multi-hub Windows GUI.

## Part VI — Free Alternative Analysis
Workflow **[E]**: (1) `pip install huggingface_hub`, `hf auth login`; (2) `hf download org/repo --revision <sha> --local-dir X`; (3) `hf cache verify … --local-dir X`; (4) generate SHA256SUMS, optionally PAR2; (5) split files > disc capacity (7-Zip volumes) and plan discs by hand; (6) build UDF ISO and burn with a burner (free: ImgBurn, BurnAware Free; paid: BurnAware $29.95+); (7) write your own restore notes. ~6 tools, 30–60 min first time for a technical user **[E, unmeasured]**; per-model repeat cost mostly manual disc packing. Hidden gaps: no documentation/license record, no catalog, manual capacity maths, and splitting oversized files — which **STELE doesn't do either**, so DIY is actually ahead there.

## Part VIII — Demand Signals (verified links only)
| Source | Item | Date | Signal | Intent level |
|---|---|---|---|---|
| Hacker News / press | "Pirate Face Rescues LLM Models from Deletion" (via [explainx](https://www.explainx.ai/blog/pirate-face-torrent-ai-model-preservation-2026), [pirateface.co](https://pirateface.co)) | 2026-09-20/21 | Strong public interest in surviving model removal; article cites **no actual deleted-model incident** | Curiosity/concern, not purchase |
| News | [NVIDIA–Hugging Face deal](https://www.phoronix.com/news/NVIDIA-Hugging-Face) | 2026-09-03 | Ownership-change anxiety | Context |
| News | [HF breach](https://techcrunch.com/2026/07/20/hugging-face-confirms-breach-affected-internal-datasets-and-credentials-urges-users-to-take-action/) | 2026-07-20 | Trust/security concern; no tampering reported in article | Context |
| HF Forums | [Local Model Backups](https://discuss.huggingface.co/t/local-model-backups/171119) | 2025-12-03 | LoRA user can't safely copy models; answers: 7-Zip, SHA-256, central folder | Real problem (copy integrity), unresolved; 11 replies |
| Press/Civitai | [Decrypt on Civitai policy](https://decrypt.co/317460/civitais-users-angry-ban-kinky-content-ai-art); [CivArchive about](https://civitaiarchive.com/about) | 2025 | Removals triggered panic-downloading and archive sites; r/CivitaiArchives mentioned (thread not opened) | Genuine preservation behavior, but Civitai — STELE doesn't support it |
| Blog | [Think Different backup post](https://www.thinkdifferent.blog/blog/the-backup-strategy-for-people-with-500gb-of-ai-models/) | 2026-07-19 | Mainstream advice is *don't back up weights*; re-download | **Counter-signal** |
| HF Forums | [MLbackup org](https://huggingface.co/MLbackup) | ~Feb | Community members mirror creators' deleted-risk models | Preservation behavior |
| Reddit / LocalLLaMA | [Optical model backup discussion](https://www.reddit.com/r/LocalLLaMA/comments/1u4rarz/i_dont_know_who_needs_to_hear_this_but_128gb_bdr/) | 2026-06-13 | Browser: 146 votes, 68 comments; optical interest plus cost/capacity/reader objections; thread contains technical errors, don't reuse its claims | Relevant workflow interest; no paid intent |
| Reddit / LocalLLaMA | [Collecting and archiving models](https://www.reddit.com/r/LocalLLaMA/comments/1hb4equ/anyone_else_collecting_and_archiving_models_it/) | 2024-12-10 | 471 votes, 127 comments; NAS collections | Collection behavior; NAS is the alternative |
| Reddit / DataHoarder | [Archive Generative AI Models/Tools](https://www.reddit.com/r/DataHoarder/comments/17jxhi9/) | date unverified ("3y ago") | Asks what to preserve; reply: full repo via Git/LFS | Specific need, no optical/paid intent |
| Reddit / DataHoarder | [M-Disc burn quality scanning](https://www.reddit.com/r/DataHoarder/comments/1vdrg66/quality_scanning_ldcbis_mdisc_burns_who_here_does/) | 2026-08-02 | 16 votes, 27 comments; generic data, not AI | Optical archival effort; wants scan reports |
| Reddit / CivitaiArchives | [Request for a lost LoRA version](https://www.reddit.com/r/CivitaiArchives/comments/1wn9ju7/) | 2026-09-22 | 1 vote, 2 comments; unrecovered | Concrete loss, tiny engagement |
| Reddit / StableDiffusion | [CivitAI backup initiative](https://www.reddit.com/r/StableDiffusion/comments/1k6gty2/) | 2025-04-24 | ~494 votes (search-indexed, not browser-inspected) | Organized preservation |

**No expressed willingness to pay found. Optical-specific interest is verified; a paying optical-software buyer is not.** The follow-up adds direct LocalLLaMA, DataHoarder and CivitaiArchives evidence. Discord/X remain unresolved.

## Part IX — Segments (ranked by evidence + fit)
1. **HF model collectors with an optical drive** (follow-up hypothesis, untested): want a small, selected cold archive. Evidence: LocalLLaMA optical-backup thread (2026-06-13, 146 votes/68 comments) and collector thread (2024-12-10, 471/127). Replies object on capacity, cost per TB and reader obsolescence; replies favor NAS/HDD/torrents. No purchase intent seen.
2. **Air-gapped/offline & IT admins** [H]: need verifiable, portable, license-documented media; STELE's disc tree + restore script fits, but no demand evidence found.
3. **Data hoarders / digital archivists**: DataHoarder threads show real optical effort (M-DISC burn scanning, ECC files, multiple copies; 2026-08-02, 16 votes/27 comments) and a request for complete AI-model preservation (older thread, date unverified). Price-sensitive; will compare with free toolchain. Want verification history/reports, which readback does not provide.
4. **Civitai/SD hoarders**: strongest *behavior* evidence (CivitaiArchives requests, 2025 backup initiative), but STELE lacks Civitai support → fix before targeting.
5. **Local LLM users**: huge, many satisfied with NAS/re-download; low urgency.
6. **Researchers/institutions**: reproducibility needs (pinned commits + docs) but prefer institutional storage; EULA/per-seat questions.
Objections common to all: free scripts, SSD/cloud simpler, M-DISC longevity claims vendor-sourced.

## Part X — Price Assessment
- Fees **[F]**: Gumroad 10% + $0.50 direct (30% Discover), merchant of record since 2025 → ~$3.40 on $29 before possible processing fees (sources conflict). Lemon Squeezy 5% + 50¢ (+ possible extras) → ~$1.95; license keys built in. Microsoft Store individual registration now free; commission figures not confirmed (older reports: 15% via MS commerce, own-commerce 100%). itch.io default 10% (2015 announcement; not rechecked).
- Anchors: free OSS tools above; BurnAware Premium $29.95 / Professional $39.95 (official pricing, 2026-10-26; see follow-up); media cost **[F]** 100 GB M-DISC BD-R XL ≈ $13–17/disc, so archiving a 70 GB model ≈ one disc ≈ $13–17 **in media alone**; Glacier Deep Archive ~$0.00099/GB-mo storage but retrieval $0.02/GB (secondary sources).
- **Verdict [R]:** $29 is *fair/slightly low* for a one-time utility that saves hours of toolchain work; $19 only as launch/anchor, $39 only after field validation + PAR2/splitting. Do not charge for downloading or plain ISO export — free tools already do; the Master List's plan (Free = ISO export, Pro = burn) puts the paywall on the commodity step. **[R]** Consider Free = search/download/docs; Pro = capacity planning, multi-disc, restore-verified archives, PAR2. No conversion forecast offered.

## Part XI — Gaps & Roadmap
| Opportunity | Status | Priority [R] |
|---|---|---|
| Model-aware optical workflow (docs + restore + catalog) | Implemented, unverified | Core pitch |
| Real E2E validation (burn → read on another PC → restore) | Missing evidence | **Do first** |
| Oversized-file splitting + rejoin script | Missing | High (blocks 70B+ models on 25 GB; DIY ahead) |
| PAR2 redundancy | Missing | High, differentiator for archivists |
| Restore-time hash verification in RESTORE.ps1 | Verify in code | High |
| Civitai / ModelScope / Ollama sources | Missing | Medium-high (Civitai has strongest preservation behaviour) |
| Import existing local model collections/directories | Proposed (not a STELE feature) | Medium-high (collector threads show users already hold NAS copies) |
| Verification-history/report export | Proposed | Medium (DataHoarder scanning thread) |
| Periodic disc re-verify reminder; printed index | Proposed | Medium |
| Open-source or auditable restore script | Proposed | Medium (answers "what if STELE disappears") |

## Part XII — Positioning & Sales
- **Value prop:** "Turn a Hugging Face repo into a self-describing, checksum-verified disc set you can restore without STELE or the internet."
- **Vs:** HF CLI/bodaay = downloaders (use them to fetch; STELE finishes the job); Stability Matrix/LM Studio = run models; BurnAware = generic burner, not model-aware.
- **Headlines:** (1) "Carve the model into stone." (brand) (2) "Your model, pinned to a commit, on a disc." (3) "If the repo vanishes, the disc doesn't." — avoid absolutes (4) "Verified offline archives of Hugging Face models" (best for buyers: plain, searchable) (5) "Model archives that restore with PowerShell — no STELE required." **Best: #4 for search/landing, #5 for the trust objection.**
- **Objections:** HF CLI → it downloads; STELE packages, documents, burns, verifies. SSD → fine, SSDs aren't write-once/offline-isolated but optical is slower/pricier; be honest. M-DISC → vendor claim, longevity not independently verified here; recommend periodic verify. Restore years later → files restore; **inference compatibility not guaranteed** (runtimes archived but not executed). $29 vs script → pay for time, not capability. STELE disappears → plain files + sha256 + PowerShell.
- **Channels [R]:** Lemon Squeezy or Gumroad direct (LS cheaper, license keys native); Microsoft Store optional later; write a comparison page + "how to archive a HF model to Blu-ray" tutorial. Community promotion: **LocalLLaMA is restricted** (moderator removals cite self-promotion/LLM-post rules and a 10% participation threshold; full rule text not retrieved), r/CivitaiArchives has resource/NSFW rules and a locked guide, DataHoarder rules not retrieved. Don't pitch; use discovery interviews and a concrete demo instead.
- **Objection-handling note:** don't claim readback equals media-quality scanning (LDC/BIS); a SHA-256 match shows bytes matched, not remaining media life.

## Part XIII — Risks / Unknowns
- **Security [F]:** `_OFFLINE_SECRET` in `stele/license.py:31` lets anyone mint keys; remove before any sale.
- Gumroad verify uses `product_permalink` (Master List B2 says use `product_id`).
- No field validation of burn/readback; USB enclosure incompatibility documented.
- Model licenses: archiving gated/restricted weights is user's responsibility; Pirate Face shows the licensing minefield.
- Market: disc capacity (25–100 GB) vs 70B+ models; consumer burner availability; HF/NVIDIA outcome unknown; mainstream guidance says "just re-download".
- Resolved in follow-up: BurnAware price/UDF/verify and selected Reddit demand threads. Still unresolved: Microsoft Store current commission; itch.io current terms; paid demand; Discord demand; whether any paid niche competitor exists off-search.
- Completed follow-up: selected DataHoarder/LocalLLaMA/CivitaiArchives pages and official BurnAware/ImgBurn pages. CDBurnerXP returned 403. Storefront-native searches on Gumroad/itch/Etsy/MS Store remain outstanding.

## Part XIV — Verdict
STELE has a real but narrow, **defensible-only-through-integration** position: no verified single product replaces it, but a free ~6-tool workflow does, and nobody has *demonstrated* paying demand for optical model archives. Commercially viable as a niche $29 tool if (1) the license hole is closed, (2) an end-to-end real-disc restore is proven, (3) file splitting + PAR2 land, and (4) Civitai/other hub support broadens the audience. Lead with trust/verifiability, not "M-DISC lasts forever."

## Sources
huggingface.co/docs/huggingface_hub/guides/cli · github.com/bodaay/HuggingFaceModelDownloader · github.com/Richasy/Rodel.Downloader · pirateface.co · explainx.ai Pirate Face article · phoronix.com NVIDIA–HF · techcrunch.com HF breach · discuss.huggingface.co/t/local-model-backups/171119 · decrypt.co Civitai · civitaiarchive.com/about · thinkdifferent.blog · gumroad.com/pricing · lemonsqueezy.com/pricing · burnaware.com (buy, compare-editions, features, help/data-disc, span-disc, verify-disc) · imgburn.com · STELE_RESEARCH_FOLLOWUP_2026-10-26.md and the Reddit threads linked in Part VIII · SHI/eBay M-DISC BD-R XL listings · Windows Dev blog (free registration, 2025-09-10 / 2026-05-07) · Gumroad/LS fee blogs (secondary).
