"""Complete scene-by-scene definitions & platform copy for all 5 Stele sales videos."""

from __future__ import annotations

from videos.config import (
    BRAND_EMAIL,
    DEFAULT_PAR2_PERCENT,
    GUMROAD_FREE_URL,
    GUMROAD_PRO_URL,
    PRO_MACHINES_COUNT,
    STELE_FREE_PRICE,
    STELE_PRO_PRICE,
)

VIDEO_SPECS = [
    # =========================================================================
    # VIDEO 1: THE HERO WORKFLOW ("Repo to Disc in One App") — 30.0s
    # =========================================================================
    {
        "slug": "stele_01_repo_to_disc",
        "title": "Repo to Disc in One Windows App",
        "eyebrow": "HUGGING FACE & CIVITAI ARCHIVER",
        "cover_lines": ["PIN MODELS", "TO DISC"],       # 4 words max, zero prices
        "cover_accent": "DISC",
        "cover_subhead": "Search, verify SHA-256, generate PDFs, and burn UDF media in one Windows app.",
        "cover_visual": {
            "kind": "ui_zoom",
            "capture": "ui_burn_pro",
            "cam": [1160, 620, 1440],
            "highlight_key": "burn_button",
            "highlight_label": "Verified UDF Burn",
            "window_label": "Stele Pro  ·  Build an archive",
        },
        "tick_windows": [(4.5, 10.0), (17.0, 24.0)],
        "scenes": [
            {
                "duration": 4.5,
                "kind": "ui_zoom",
                "badge": "STEP 1 · PIN",
                "headline": ["REPOS CHANGE.", "COMMITS DON'T."],
                "accent": "COMMITS",
                "capture": "ui_discover_hf",
                "window_label": "Stele  ·  Discover models",
                "cam_start": [1980, 1060, 1440],
                "cam_end": [1980, 1240, 1360],
                "highlight_key": "ack_checkbox",
                "highlight_label": "Pinned Commit + License",
                "caption": "Repos can go gated or change tomorrow. Stele pins the exact Hugging Face commit and checks the license first.",
            },
            {
                "duration": 5.5,
                "kind": "ui_zoom",
                "badge": "STEP 2 · VERIFY",
                "headline": ["ONE FILE", "AT A TIME"],
                "accent": "ONE FILE",
                "capture": "ui_queue_active",
                "window_label": "Stele  ·  Download queue",
                "cam_start": [1160, 860, 1500],
                "cam_end": [1140, 1060, 1380],
                "highlight_key": "files_table",
                "highlight_label": "HTTP Range + SHA-256",
                "caption": "Downloads run one file at a time on Windows with HTTP Range pause and resume, checking every SHA-256 hash.",
            },
            {
                "duration": 7.0,
                "kind": "docs_trio",
                "badge": "STEP 3 · DOCUMENT",
                "headline": ["DOCS WRITTEN", "BESIDE WEIGHTS"],
                "accent": "DOCS",
                "caption": "Alongside the model, Stele writes a technical spec PDF, a plain how-to guide, and printable disc and case labels.",
            },
            {
                "duration": 7.5,
                "kind": "ui_zoom",
                "badge": "STEP 4 · ARCHIVE",
                "headline": ["UDF BURN +", "READBACK CHECK"],
                "accent": "READBACK",
                "capture": "ui_burn_pro",
                "window_label": "Stele Pro  ·  Build an archive",
                "cam_start": [1220, 620, 1480],
                "cam_end": [1160, 630, 1340],
                "highlight_key": "verify_check",
                "highlight_label": "2x-4x Burn + Verify",
                "caption": "Export a single-disc UDF ISO free, or use Stele Pro to burn at 2x to 4x and verify the disc against checksums.sha256.",
            },
            {
                "duration": 5.5,
                "kind": "end_slate",
                "cta_headline": "One Windows app instead of six DIY tools",
                "honest_limit": "Windows desktop only. Stele does not grant redistribution rights and does not execute installers.",
            },
        ],
        "x_post": (
            "Backing up a Hugging Face model to optical media by hand usually takes 6 separate CLI and burner tools — "
            "and leaves zero notes on how to run it later.\n\n"
            "Stele fixes that in one Windows app: commit-pinned SHA-256 download, Spec + How-To PDFs, and verified UDF burn.\n\n"
            "Windows only. Does not grant redistribution rights."
        ),
        "x_reply": (
            f"Stele Free ({STELE_FREE_PRICE}, search + PDFs + single-disc ISO): {GUMROAD_FREE_URL}\n"
            f"Stele Pro ({STELE_PRO_PRICE}, burn + multi-disc + PAR2): {GUMROAD_PRO_URL}\n"
            f"Questions? {BRAND_EMAIL}"
        ),
        "shorts_title": "Archive Hugging Face Models to BD-R / M-DISC on Windows (Stele)",
        "shorts_desc": (
            "Pin an exact Hugging Face commit, verify SHA-256 hashes, generate Spec + How-To PDFs, "
            "and export a UDF ISO or burn verified optical discs on Windows.\n\n"
            "Windows desktop only. Stele does not grant redistribution rights.\n"
            f"Find Stele Free ({STELE_FREE_PRICE}) and Stele Pro ({STELE_PRO_PRICE}) via the Alexx Forge shop link on our channel.\n"
            f"Support: {BRAND_EMAIL}\n"
            "BUILD. CREATE. ELEVATE."
        ),
    },

    # =========================================================================
    # VIDEO 2: ZERO LOCK-IN ("What If Stele Disappears?") — 28.0s
    # =========================================================================
    {
        "slug": "stele_02_offline_restore",
        "title": "What If Stele Disappears? Plain Offline Restore",
        "eyebrow": "ZERO PROPRIETARY LOCK-IN",
        "cover_lines": ["NO STELE", "NEEDED"],         # 3 words, zero prices
        "cover_accent": "NO STELE",
        "cover_subhead": "Plain UDF folders, checksums.sha256, and offline PowerShell 5.1 restore.",
        "cover_visual": {
            "kind": "ui_zoom",
            "capture": "ui_runtimes",
            "cam": [1160, 580, 1440],
            "highlight_key": "table",
            "highlight_label": "Plain Files + Runtimes",
            "window_label": "Stele  ·  Runtime collection",
        },
        "tick_windows": [(4.5, 18.0)],
        "scenes": [
            {
                "duration": 4.5,
                "kind": "disc_tree",
                "badge": "PLAIN UDF 2.50",
                "headline": ["NO MYSTERY", "BACKUP FORMAT"],
                "accent": "NO MYSTERY",
                "caption": "What if Stele isn't on your next PC? Open any Stele disc in Windows Explorer — every file sits in plain UDF folders.",
            },
            {
                "duration": 6.5,
                "kind": "powershell",
                "badge": "OFFLINE SCRIPT",
                "headline": ["BUILT-IN", "POWERSHELL 5.1"],
                "accent": "POWERSHELL 5.1",
                "window_label": "Windows PowerShell 5.1  ·  No network required",
                "lines": [
                    ("cmd", "PS E:\\STELE> powershell -ExecutionPolicy Bypass -File .\\RESTORE.ps1 -Destination D:\\Restored"),
                    ("info", "Stele does not grant redistribution rights."),
                    ("accent", "Disc 1 of 1  ·  Reading checksums.sha256"),
                    ("info", "Copying MODELS/Qwen--Qwen2.5-7B-Instruct-GGUF/dd98b7684b25/..."),
                    ("info", "Copying DOCS/Qwen--Qwen2.5-7B-Instruct-GGUF_spec.pdf"),
                ],
                "caption": "Every disc includes RESTORE.ps1. It needs only built-in Windows PowerShell 5.1 — no internet and no Stele install.",
            },
            {
                "duration": 6.5,
                "kind": "powershell",
                "badge": "HASH VERIFIED",
                "headline": ["EVERY FILE", "SHA-256 CHECKED"],
                "accent": "SHA-256",
                "window_label": "Windows PowerShell 5.1  ·  Hash verification",
                "lines": [
                    ("cmd", "PS E:\\STELE> .\\RESTORE.ps1 -Destination D:\\Restored"),
                    ("info", "Copied and checked 6 file(s). 0 file(s) were already restored."),
                    ("ok", "Restore complete. Every file matched its SHA-256."),
                    ("accent", "LM Studio: point the app at D:\\Restored\\MODELS"),
                    ("info", "llama.cpp example: llama-cli -m <path-to-gguf>"),
                ],
                "caption": "RESTORE.ps1 checks every copied file against checksums.sha256 and stops with an exact list if any byte mismatches.",
            },
            {
                "duration": 5.5,
                "kind": "ui_zoom",
                "badge": "OPTIONAL RUNTIMES",
                "headline": ["PACK RUNTIMES", "BESIDE MODELS"],
                "accent": "RUNTIMES",
                "capture": "ui_runtimes",
                "window_label": "Stele  ·  Runtime collection",
                "cam_start": [1180, 580, 1480],
                "cam_end": [1140, 600, 1340],
                "highlight_key": "table",
                "highlight_label": "Archived, Never Executed",
                "caption": "Archive official llama.cpp, Ollama, or LM Studio Windows files in RUNTIME/. Stele stores them; it never runs installers.",
            },
            {
                "duration": 5.0,
                "kind": "end_slate",
                "cta_headline": "Archives that outlive the app that made them",
                "honest_limit": "Restores exact archived bytes offline; future OS or runtime compatibility is not promised.",
            },
        ],
        "x_post": (
            "Never lock cold archives inside a format that dies if the backup app disappears.\n\n"
            "Every disc Stele builds is a plain UDF folder tree (MODELS/, DOCS/, RUNTIME/, checksums.sha256) "
            "plus RESTORE.ps1 for built-in Windows PowerShell 5.1.\n\n"
            "Offline restore. Zero Stele install required. Never runs installers."
        ),
        "x_reply": (
            f"Stele Free ({STELE_FREE_PRICE}): {GUMROAD_FREE_URL}\n"
            f"Stele Pro ({STELE_PRO_PRICE}): {GUMROAD_PRO_URL}\n"
            f"Questions? {BRAND_EMAIL}"
        ),
        "shorts_title": "What If Your Backup App Disappears? How Stele Discs Restore Offline",
        "shorts_desc": (
            "Every Stele disc uses plain UDF folders, checksums.sha256, and a standalone PowerShell 5.1 "
            "RESTORE.ps1 script — zero internet and zero Stele installation needed to restore.\n\n"
            f"Get Stele Free ({STELE_FREE_PRICE}) or Stele Pro ({STELE_PRO_PRICE}) from Alexx Forge (link on channel).\n"
            f"Questions? {BRAND_EMAIL}\n"
            "BUILD. CREATE. ELEVATE."
        ),
    },

    # =========================================================================
    # VIDEO 3: CIVITAI CHECKPOINTS & LORAS ("Save Trigger Words") — 30.0s
    # =========================================================================
    {
        "slug": "stele_03_civitai_archive",
        "title": "Archive Civitai Models With Their Trigger Words",
        "eyebrow": "CIVITAI CHECKPOINTS & LORAS",
        "cover_lines": ["SAVE CIVITAI", "PROPERLY"],     # 3 words, zero prices
        "cover_accent": "CIVITAI",
        "cover_subhead": "Keep trigger words, base model, and SHA-256 beside every safetensors file.",
        "cover_visual": {
            "kind": "ui_zoom",
            "capture": "ui_discover_civitai",
            "cam": [1160, 560, 1440],
            "highlight_key": "source_combo",
            "highlight_label": "Civitai Source",
            "window_label": "Stele  ·  Discover Civitai models",
        },
        "tick_windows": [(11.5, 19.0)],
        "scenes": [
            {
                "duration": 5.0,
                "kind": "ui_zoom",
                "badge": "CIVITAI BUILT IN",
                "headline": ["BARE WEIGHTS", "LOSE CONTEXT"],
                "accent": "LOSE CONTEXT",
                "capture": "ui_discover_civitai",
                "window_label": "Stele  ·  Discover models (Civitai)",
                "cam_start": [1140, 560, 1460],
                "cam_end": [1120, 520, 1320],
                "highlight_key": "source_combo",
                "highlight_label": "Pick Civitai",
                "caption": "Six months later, a bare .safetensors file won't tell you its base model or trigger words. Switch Discover to Civitai.",
            },
            {
                "duration": 6.5,
                "kind": "ui_zoom",
                "badge": "EXACT VERSION",
                "headline": ["PIN VERSION +", "CIVITAI SHA-256"],
                "accent": "SHA-256",
                "capture": "ui_discover_civitai",
                "window_label": "Stele  ·  Civitai version preview",
                "cam_start": [1980, 980, 1440],
                "cam_end": [1980, 1140, 1360],
                "highlight_key": "files_table",
                "highlight_label": "Weights Ticked · SHA Checked",
                "caption": "Pick the exact version by name, ID, or URL. Stele checks each file against Civitai's SHA-256 and leaves training zips unticked.",
            },
            {
                "duration": 7.5,
                "kind": "civitai_json",
                "badge": "METADATA SAVED",
                "headline": ["TRIGGER WORDS", "STAY ON DISC"],
                "accent": "TRIGGER WORDS",
                "caption": "Stele writes civitai_model.json beside the weights — saving trigger words, base model, description, and creator permissions.",
            },
            {
                "duration": 5.5,
                "kind": "ui_zoom",
                "badge": "CREDENTIAL MANAGER",
                "headline": ["API KEYS NEVER", "HIT THE DISC"],
                "accent": "NEVER",
                "capture": "ui_settings_pro",
                "window_label": "Stele  ·  Workspace settings",
                "cam_start": [1160, 1240, 1440],
                "cam_end": [1120, 1280, 1320],
                "highlight_key": "license_status",
                "highlight_label": "Windows Credential Manager",
                "caption": "Your Civitai API key stays in Windows Credential Manager — sent only to civitai.com, never written to logs, PDFs, or discs.",
            },
            {
                "duration": 5.5,
                "kind": "end_slate",
                "cta_headline": "Archive Civitai LoRAs and checkpoints cleanly",
                "honest_limit": "Search hides NSFW models. Stele does not grant redistribution rights to archived creator weights.",
            },
        ],
        "x_post": (
            "A bare .safetensors file sitting on a drive 6 months from now won't tell you which base model it needs "
            "or what trigger words wake it up.\n\n"
            "Stele archives Civitai models by version, checks Civitai's published SHA-256, and writes civitai_model.json "
            "(trigger words, base model, creator permissions) right beside the weights.\n\n"
            "API keys stay in Windows Credential Manager. Does not grant redistribution rights."
        ),
        "x_reply": (
            f"Stele Free ({STELE_FREE_PRICE}, search + docs + single ISO): {GUMROAD_FREE_URL}\n"
            f"Stele Pro ({STELE_PRO_PRICE}, UDF burn + multi-disc + PAR2): {GUMROAD_PRO_URL}\n"
            f"Questions? {BRAND_EMAIL}"
        ),
        "shorts_title": "Archive Civitai LoRAs & Checkpoints With Trigger Words Intact",
        "shorts_desc": (
            "Stop losing trigger words and base-model notes on local .safetensors backups. "
            "Stele verifies Civitai SHA-256 hashes and saves civitai_model.json + offline How-To PDFs beside the weights.\n\n"
            "Search hides NSFW models. Stele does not grant redistribution rights.\n"
            f"Find Stele Free ({STELE_FREE_PRICE}) & Stele Pro ({STELE_PRO_PRICE}) on the Alexx Forge channel link.\n"
            "BUILD. CREATE. ELEVATE."
        ),
    },

    # =========================================================================
    # VIDEO 4: HEAVY IRON ("70B Models & Scratched Discs") — 32.0s
    # =========================================================================
    {
        "slug": "stele_04_split_and_par2",
        "title": "70B Models & Scratched Discs: Multi-Disc Split + PAR2",
        "eyebrow": "STELE PRO · COLD STORAGE",
        "cover_lines": ["SPLIT + PAR2", "RECOVERY"],     # 3 words, zero prices
        "cover_accent": "PAR2",
        "cover_subhead": "Span oversized GGUF files across 25 GB discs with offline PAR2 repair.",
        "cover_visual": {
            "kind": "ui_zoom",
            "capture": "ui_burn_pro",
            "cam": [1160, 620, 1420],
            "highlight_key": "recovery_check",
            "highlight_label": f"Add {DEFAULT_PAR2_PERCENT}% PAR2",
            "window_label": "Stele Pro  ·  PAR2 recovery & spanning",
        },
        "tick_windows": [(5.0, 12.5), (19.5, 26.5)],
        "scenes": [
            {
                "duration": 5.0,
                "kind": "split_par2",
                "focus_par2": False,
                "badge": "OVERSIZED WEIGHTS",
                "headline": ["BIGGER THAN A", "25 GB DISC?"],
                "accent": "25 GB",
                "caption": "What happens when a 70B GGUF file is 42.8 GB and your blank BD-R or M-DISC holds 25 GB?",
            },
            {
                "duration": 7.5,
                "kind": "split_par2",
                "focus_par2": True,
                "badge": "MULTI-DISC SETS",
                "headline": ["NUMBERED PARTS", "+ FULL SHA-256"],
                "accent": "FULL SHA-256",
                "caption": "Stele Pro splits oversized files into .part001, .part002 across discs and records every part hash plus the full-file SHA-256.",
            },
            {
                "duration": 7.0,
                "kind": "ui_zoom",
                "badge": "BUNDLED PAR2",
                "headline": [f"ADD {DEFAULT_PAR2_PERCENT}% PAR2", "PARITY BLOCKS"],
                "accent": f"{DEFAULT_PAR2_PERCENT}% PAR2",
                "capture": "ui_burn_pro",
                "window_label": "Stele Pro  ·  Build an archive",
                "cam_start": [1220, 620, 1480],
                "cam_end": [1140, 620, 1320],
                "highlight_key": "recovery_check",
                "highlight_label": "par2cmdline-turbo Included",
                "caption": f"Enable PAR2 recovery ({DEFAULT_PAR2_PERCENT}% default) and each disc reserves room under RECOVERY/ for standard parity files.",
            },
            {
                "duration": 7.0,
                "kind": "powershell",
                "badge": "SECTOR REPAIR",
                "headline": ["READS PAST", "BAD SECTORS"],
                "accent": "BAD SECTORS",
                "window_label": "RESTORE.ps1  ·  Copy-Tolerant + PAR2 repair + Rejoin",
                "lines": [
                    ("cmd", "PS E:\\STELE> .\\RESTORE.ps1 -Destination D:\\Restored"),
                    ("accent", "UNREADABLE (65536 bytes): MODELS/.../Llama-70B.gguf.part001"),
                    ("info", "Repairing with the PAR2 recovery data on this disc..."),
                    ("ok", "Repaired: Llama-70B.gguf.part001  ·  Joined & verified full SHA-256."),
                ],
                "caption": "If a disc gets scratched, RESTORE.ps1 reads past bad sectors, repairs scattered damage with PAR2, joins the parts, and re-hashes.",
            },
            {
                "duration": 5.5,
                "kind": "end_slate",
                "cta_headline": f"Stele Pro — one key covers {PRO_MACHINES_COUNT} machines",
                "honest_limit": "PAR2 repairs scattered damage up to roughly its % of the disc; it does not replace a second physical copy.",
            },
        ],
        "x_post": (
            "Two real headaches when archiving 70B+ local models to 25 GB BD-R or M-DISC:\n"
            "1. Single weight files larger than one blank disc\n"
            "2. Unreadable sectors from a scratch years later\n\n"
            f"Stele Pro splits oversized files across discs with part + whole-file SHA-256 hashes, "
            f"and bundles par2cmdline-turbo ({DEFAULT_PAR2_PERCENT}% default parity) so RESTORE.ps1 can repair scattered damage offline.\n\n"
            "PAR2 does not replace keeping a second copy."
        ),
        "x_reply": (
            f"Stele Pro ({STELE_PRO_PRICE}, {PRO_MACHINES_COUNT} machines): {GUMROAD_PRO_URL}\n"
            f"Try Stele Free first ({STELE_FREE_PRICE}, single-disc ISO): {GUMROAD_FREE_URL}\n"
            f"Support: {BRAND_EMAIL}"
        ),
        "shorts_title": "Fit 70B AI Models Across 25GB Blu-rays + PAR2 Scratch Repair",
        "shorts_desc": (
            "Stele Pro splits oversized GGUF/safetensors files across multi-disc sets, writes per-part and full-file "
            f"SHA-256 manifests, and adds PAR2 recovery data ({DEFAULT_PAR2_PERCENT}% default) for offline repair via RESTORE.ps1.\n\n"
            "PAR2 repairs scattered damage up to roughly its percentage of the disc and does not replace a second copy.\n"
            f"Stele Pro ({STELE_PRO_PRICE}) via Alexx Forge channel link.\n"
            "BUILD. CREATE. ELEVATE."
        ),
    },

    # =========================================================================
    # VIDEO 5: HONEST FREE VS. PRO ("Try Free First") — 26.0s
    # =========================================================================
    {
        "slug": "stele_05_free_vs_pro",
        "title": "Stele Free vs. Stele Pro — Plain Breakdown",
        "eyebrow": "HONEST LICENSING · NO SUBSCRIPTION",
        "cover_lines": ["FREE VS", "STELE PRO"],        # 4 words, zero prices
        "cover_accent": "STELE PRO",
        "cover_subhead": "Test the entire download, PDF, and UDF ISO workflow free on Windows.",
        "cover_visual": {
            "kind": "ui_zoom",
            "capture": "ui_burn_free",
            "cam": [1140, 620, 1440],
            "highlight_key": "iso_button",
            "highlight_label": "Free UDF ISO Export",
            "window_label": "Stele Free  ·  Single-volume ISO export",
        },
        "tick_windows": [(5.0, 11.5)],
        "scenes": [
            {
                "duration": 5.0,
                "kind": "free_vs_pro",
                "highlight_tier": "free",
                "badge": "NO CRIPPLED DEMO",
                "headline": ["TEST THE REAL", "WORKFLOW FREE"],
                "accent": "FREE",
                "caption": "You shouldn't have to pay upfront just to see if an archive workflow fits your Windows hardware.",
            },
            {
                "duration": 6.5,
                "kind": "ui_zoom",
                "badge": "STELE FREE",
                "headline": ["FREE SINGLE-DISC", "UDF ISO EXPORT"],
                "accent": "UDF ISO",
                "capture": "ui_burn_free",
                "window_label": "Stele (Free)  ·  Export ISO unlocked",
                "cam_start": [1200, 620, 1480],
                "cam_end": [1100, 630, 1320],
                "highlight_key": "iso_button",
                "highlight_label": "Free + USB Drive Friendly",
                "caption": "Stele Free searches Hugging Face and Civitai, verifies downloads, writes the PDFs, and exports a single-disc UDF ISO.",
            },
            {
                "duration": 5.5,
                "kind": "free_vs_pro",
                "highlight_tier": "pro",
                "badge": "STELE PRO",
                "headline": ["PRO ADDS BURN,", "SPAN + PAR2"],
                "accent": "BURN,",
                "caption": "Upgrade once to Stele Pro when you want direct IMAPI2 disc burning, multi-disc file splitting, and PAR2 recovery data.",
            },
            {
                "duration": 4.0,
                "kind": "ui_zoom",
                "badge": f"{PRO_MACHINES_COUNT} MACHINES · AIR-GAPPED",
                "headline": ["OFFLINE PC?", "STAYS ACTIVE."],
                "accent": "STAYS ACTIVE.",
                "capture": "ui_settings_pro",
                "window_label": "Stele Pro  ·  Offline-safe activation",
                "cam_start": [1160, 1240, 1440],
                "cam_end": [1120, 1280, 1320],
                "highlight_key": "license_status",
                "highlight_label": f"1 User · Up to {PRO_MACHINES_COUNT} PCs",
                "caption": f"One Pro key covers {PRO_MACHINES_COUNT} PCs. If an air-gapped archive workstation goes offline, Stele never revokes your key.",
            },
            {
                "duration": 5.0,
                "kind": "end_slate",
                "cta_headline": "Start with Stele Free — upgrade only if you burn",
                "honest_limit": "USB optical enclosures that fail Windows IMAPI2 should use Export ISO. DVD M-DISC needs an M-DISC-aware writer.",
            },
        ],
        "x_post": (
            "Plain breakdown of Stele Free vs. Stele Pro on Windows:\n\n"
            f"Free ({STELE_FREE_PRICE}):\n"
            "- Hugging Face + Civitai search & HTTP Range download\n"
            "- SHA-256 checks + Spec & How-To PDFs\n"
            "- Single-volume UDF ISO export (also the supported path for picky USB optical enclosures)\n\n"
            f"Pro ({STELE_PRO_PRICE}):\n"
            "- Direct UDF disc burn (2x-4x) + readback check\n"
            "- Multi-disc spanning & oversized-file splitting\n"
            "- PAR2 recovery data\n"
            f"- {PRO_MACHINES_COUNT} PCs, air-gapped offline safe"
        ),
        "x_reply": (
            f"Stele Free ({STELE_FREE_PRICE}): {GUMROAD_FREE_URL}\n"
            f"Stele Pro ({STELE_PRO_PRICE}): {GUMROAD_PRO_URL}\n"
            f"Questions? Email {BRAND_EMAIL}"
        ),
        "shorts_title": "Stele Free vs Pro: Honest AI Model Archiver Breakdown (Windows)",
        "shorts_desc": (
            f"Stele Free ({STELE_FREE_PRICE}) covers Hugging Face & Civitai search, HTTP Range downloads, "
            "SHA-256 verification, Spec + How-To PDFs, and single-disc UDF ISO export.\n"
            f"Stele Pro ({STELE_PRO_PRICE}) adds direct UDF burning, multi-disc splitting, and PAR2 recovery on up to {PRO_MACHINES_COUNT} PCs.\n\n"
            f"Links on the Alexx Forge channel · Questions? {BRAND_EMAIL}\n"
            "BUILD. CREATE. ELEVATE."
        ),
    },
]
