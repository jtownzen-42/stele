# STELE research follow-up: community demand and optical software

Checked 2026-10-26. This follow-up resolves the specific request to inspect DataHoarder, LocalLLaMA, CivitaiArchives and official burner pages. It does not revalidate the original report's STELE source audit, unrelated news, rankings, marketplace fees or sales status.

## Findings that change the assessment

**Verified observation:** LocalLLaMA has a discussion explicitly about preserving local LLMs on Blu-ray/M-DISC: 146 displayed votes and 68 comments. The earlier report's description of an unverified single anecdote understated the available evidence. This is a relevant customer-discovery signal, but no participant inspected expressed willingness to buy STELE or pay $29 for archival software.

**Verified vendor facts:** BurnAware Premium costs $29.95 and Professional $39.95 for a single-user perpetual license with one year of updates. Lifetime updates are an optional extra whose price was not checked. Its official documentation confirms UDF, Blu-ray, BDXL, M-DISC, ISO generation, disc spanning and verification. ImgBurn is free and documents image creation, Blu-ray writing, UDF and disc verification; its listed current release remains 2.5.8.0, dated June 16, 2013. CDBurnerXP's official features page returned HTTP 403 in both browser and web retrieval, so its claims remain unconfirmed in this pass.

**Commercial inference:** $29 has a close paid Windows utility benchmark, but the stronger competitor remains a free model downloader plus a free burner. STELE must demonstrate the value of its repository records, archive documentation and recovery process. ISO creation, M-DISC support and readback alone are already available elsewhere.

## Community evidence

Counts are observations, not audience size or unique buyers. Dates below come from rendered page time attributes where available. User claims about storage, missing downloads and media quality are reports from participants, not independent tests.

| Community / exact title | Date | Evidence and workaround | Customer signal / STELE relevance | Promotion status |
|---|---|---|---|---|
| LocalLLaMA: [I don’t know who needs to hear this but 128GB BD-R XL M-DISC is SOTA for consumer-available archival optical storage (for backing up your models)](https://www.reddit.com/r/LocalLLaMA/comments/1u4rarz/i_dont_know_who_needs_to_hear_this_but_128gb_bdr/) | 2026-06-13 | Browser: 146 votes, 68 comments. OP recommends optical copies to preserve model availability. Replies favor redundant HDDs/NAS or torrents and object to capacity, price and reader obsolescence. | Direct interest in optical model preservation; objections closely match STELE's sales problem. Interest does not establish a purchase. The title's 128GB M-DISC wording and longevity claims were not verified. | Restricted; see moderator evidence below. |
| LocalLLaMA: [Anyone else collecting and archiving models? It started with a 12TB drive and escalated to building an 8 drive 72TB NAS. Share your setup!](https://www.reddit.com/r/LocalLLaMA/comments/1hb4equ/anyone_else_collecting_and_archiving_models_it/) | 2024-12-10 | Browser: 471 votes, 127 comments. Participants describe NAS collections, avoiding repeated downloads, preserving access and potential sharing. Others consider older weights obsolete. | Demonstrated collection behavior. A directory/catalog workflow suits these users more broadly than a requirement to burn an entire collection. | Restricted. |
| DataHoarder: [Archive Generative AI Models/Tools](https://www.reddit.com/r/DataHoarder/comments/17jxhi9/) | Exact publication date not verified; page displays 3y ago | Web reader retrieved original post and replies; browser reached a human-verification challenge. OP asks what to preserve to retain access. Reply recommends complete repo downloads via Git/LFS or manual download, tool archives and testing models. Engagement count not verified. | Specific need for complete preservation plus tooling; good fit for HF repository documentation. No explicit optical choice or paid intent. | Unknown; current rules text not retrieved. |
| DataHoarder: [Quality scanning (LDC/BIS) M-Disc burns: who here does it? Worth it, for archiving data?](https://www.reddit.com/r/DataHoarder/comments/1vdrg66/quality_scanning_ldcbis_mdisc_burns_who_here_does/) | 2026-08-02 | Browser: 16 votes, 27 comments. OP plans separate burning/scanning drives and wants quality trends. Replies describe QPxTool, saved scan reports, multiple copies and ECC files. | Real optical archival effort, but generic data rather than AI weights. Suggests useful future verification history and report export. Scan thresholds, lifespan and hardware recommendations are participant claims, not validated guidance. | Unknown. |
| CivitaiArchives: [Does anyone have the Setsuna Tokage / 取蔭切奈 V1 LoRA?](https://www.reddit.com/r/CivitaiArchives/comments/1wn9ju7/) | 2026-09-22 | Browser post and comment read. Community feed displayed 1 vote, 2 comments; only one reply body retrieved. OP reports unavailable Civitai download and disabled PixAI download after finding a TensorArt reprint. Reply suggests CivArchive. | Concrete request for an exact version, with no confirmed recovery in the retrieved reply. STELE could help only if files were preserved beforehand; integrated Civitai acquisition is not established. | Unknown for commercial promotion. Sidebar shows resource and NSFW restrictions. |
| CivitaiArchives: [[ Removed by moderator ]](https://www.reddit.com/r/CivitaiArchives/comments/1k6uhiq/removed_by_moderator/) | Linked initiative dates to 2025-04-24; original body/date not verified on removed page | Web reader confirms removed and locked. Browser initially network-blocked. The historical link named a backup tips guide, but its body cannot be assessed. | Negative availability finding. Do not cite it as a currently readable guide or infer why it was removed. | Locked; unsuitable for posting. |
| StableDiffusion: [CivitAI backup initiative](https://www.reddit.com/r/StableDiffusion/comments/1k6gty2/) | 2025-04-24 | Search-indexed Reddit content: 494 votes. Organizes preservation activity and links the now-removed CivitaiArchives guide. Replies discuss metadata and torrents. Not directly inspected in browser. | Evidence of organized preservation activity; Civitai support remains a product-fit gap. | Unknown. |

### Interpretation and cautions

The optical-model thread supplies the strongest overlap with STELE's intended workflow. Its objections are commercially useful: users ask why they should pay more per TB, manage many discs, or depend on future readers. The NAS thread demonstrates an alternative behavior with practical benefits today. Neither thread supports a market-size forecast or a conversion estimate.

The optical thread contains technical errors or unverified assertions, including calling flash storage volatile and conflating BDXL capacity with M-DISC availability. Preserve the title as evidence of what was discussed; do not reuse its claims in product copy. Community price anecdotes are not current vendor prices.

The DataHoarder scanning thread demonstrates a desire to monitor optical media. A successful checksum readback establishes that retrieved bytes match a recorded reference; it does not predict remaining media life. STELE's earlier documented SHA-256/readback path should not be described as LDC/BIS quality scanning. Drive-specific quality scans and their interpretation would require separate investigation.

## Official burner checks

### BurnAware — primary sources verified

- [Pricing](https://www.burnaware.com/buy.html): Premium $29.95; Professional $39.95. Single-user perpetual licenses, one year of updates. Displayed dollar prices recorded as USD; taxes, local checkout currency and optional lifetime-update surcharge were not checked.
- [Edition comparison](https://www.burnaware.com/compare-editions.html): ISO creation/burning in Free, Premium and Professional; disc spanning in Premium/Professional; business use in Professional.
- [Features](https://www.burnaware.com/features.html): Blu-ray, BDXL and M-DISC; ISO creation and verification. These are vendor-documented capabilities, not physical tests by this investigation.
- [Data Disc manual](https://www.burnaware.com/help/data-disc.html): UDF, ISO or ISO+UDF; optional verification after burning. Its multisession check covers the latest written session.
- [Span Disc manual](https://www.burnaware.com/help/span-disc.html): add files across multiple discs and prompt for the next blank. **Oversized individual-file splitting and reassembly are not established by this documentation.**
- [Verify Disc manual](https://www.burnaware.com/help/verify-disc.html): byte-by-byte readability check that lists unreadable files. This does not establish validation against a user-supplied SHA-256 manifest.
- [Download page](https://www.burnaware.com/download.html): version 19.4 displayed; Free for personal use and seven-day Premium/Professional trials. Exact release date not verified.

### ImgBurn — primary source verified

[Official site](https://www.imgburn.com/): freeware by LIGHTNING UK!, with optional donations. The page documents building images or writing files directly, Blu-ray writing, readability verification and optional comparison to an image. Its release history documents UDF through 2.60. Current listed release is 2.5.8.0, June 16, 2013. Windows support listed through Windows 10; Windows 11 operation was not tested. The license prohibits bundling it with a commercial application. M-DISC-specific behavior, oversized-file splitting and physical drive compatibility were not verified.

### CDBurnerXP — blocked primary verification

[Official features page](https://cdburnerxp.se/en/features) returned 403 Forbidden. Do not promote earlier third-party feature, installer-bundling or maintenance claims to verified current facts. No alternative download was installed. Current official price, version and compatibility remain unresolved here.

## Community outreach suitability

LocalLLaMA has documented enforcement against excessive self-promotion and LLM-generated posts. An [October moderator removal](https://www.reddit.com/r/LocalLLaMA/comments/1x0bzh4/removed/) cites both Rule Three and Rule Four and a 10% participation threshold; another [moderator explanation](https://www.reddit.com/r/LocalLLaMA/comments/1v1v1je/removed/) says meaningful participation is necessary and commercial ties receive scrutiny. The public rules route returned an empty rules table, so these moderation actions establish restrictions without proving the full current rule text. Do not schedule an automated product pitch there.

[CivitaiArchives](https://www.reddit.com/r/CivitaiArchives/) currently describes finding lost models and shows rules titled “Providing a Resource” and “No More (NSFW) content. Reddit does not like it!” Full rule details and commercial-promotion permission were not established. Its removed guide is not a usable outreach destination. DataHoarder promotion permission also remains unknown. No posts, messages or reactions were made.

## Recommended next steps

1. Keep $29 as the working price. BurnAware supplies a comparable one-time paid utility price; free ImgBurn and BurnAware Free still exert strong pressure. This supports plausibility, not demonstrated willingness to pay.
2. Prioritize HF model collectors who want a small, selected cold archive and already have an optical drive. This is an evidence-supported targeting hypothesis; conversion remains untested. Avoid presenting mass multi-TB disc archiving as the economical default.
3. Make a concrete demonstration: preserve a commit, record included files and licenses, export/burn, read on a second machine, then restore and compare hashes. Measure operator time and record drive/media details. Do not claim the demonstration passed until performed.
4. For discovery interviews, ask about the last model they lost or repeatedly downloaded, collection size, current backup process, optical-drive ownership, needed metadata and the specific step they would pay to avoid. Distinguish willingness to try from a purchase.
5. Investigate importing existing local collections before expanding paid promises. These discussions show users already have directories and NAS copies. Local import is an opportunity, not a verified new STELE feature.
6. Assess oversized-file handling, optional redundancy and verification-history export. They address observed friction; spanning is already offered by BurnAware, so it is insufficient as the sole distinction.

## Access and research limits

The in-app browser successfully rendered BurnAware, ImgBurn, both LocalLLaMA discussions, the DataHoarder scanning discussion, the CivitaiArchives feed and the exact-version request. DataHoarder's older AI thread hit a CAPTCHA; its text was obtained through the web reader. The removed CivitaiArchives guide was verified through that reader. No CAPTCHA was completed or access control bypassed. CDBurnerXP remained inaccessible. This follow-up does not complete Etsy/Microsoft Store/itch.io marketplace verification, Discord/X research, or physical burner testing.
