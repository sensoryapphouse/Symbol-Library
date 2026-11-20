# Symbol-library consolidation plan — 2026-10-31

Goal: every symbol style in `~/Downloads/picom-ai-sommi-action-symbols` in ONE folder, with backgrounds removed,
backed by a manifest. Nothing in this document has been executed. All counts below were measured today
(`lib_survey.py`, `lib_overlap.py`, `lib_bgstate_scan.py` in picom_review); estimates are labelled.

## 1. What exists (webp images; survey sample 40/set for background state)

### A. Already transparent — needs only a remnant QA pass
| Set | Images | Note |
|---|---|---|
| People/Sommi (transparent part) | 4,886 | 2,375 reviewed+published by us today; 2,511 made transparent earlier by the other agent, NOT reviewed by us |
| People/Sommi clothed (transparent part) | 3,994 | 1,477 ours; 2,517 unreviewed |
| People/3D animated cartoon | 3,303 | QA status unknown |
| People/Flat outlined | 3,303 | QA status unknown |
| People/Kawaii | 3,303 | QA status unknown |
| People/Simple anime | 3,303 | QA status unknown |
| Second batch/Vocabulary gaps/_Pending review | 721 | other agent's bg removal, unverified |
| **Subtotal** | **~22,800** | |

### B. White background — needs primary background removal
| Set | Images | Size | Kind |
|---|---|---|---|
| People/Sommi (opaque part) | 1,100 | 1024 | people |
| People/Sommi clothed (opaque part) | 1,084 | 1024 | people |
| ~~new mulberry-like chatgpt~~ | 3,303 | 512 | ALREADY DONE: every name has a background-free SVG in People/Mulberry (3,211 SVGs); treat the webp folder as a source backup (section C). Raster export from SVG is a separate decision. |
| Second batch/Classic flat TV cartoon/People | 3,098 | 512 | people |
| Second batch/Clay plasticine/People | 6,598 | 512 | people (includes relocated files; check dups) |
| Second batch/Doll, Friendly aliens, Monkey, Robot, Teddy bear (People) | 3,094–3,099 each ≈ 15,480 | 512 | people |
| New non-people-2/_Pending review/3D animated cartoon | 39,183 | 512 | objects |
| New non-people-2/_Pending review/Flat outlined | 39,183 | 512 | objects |
| New non-people-2/_Pending review/Sommi companion objects | 39,179 | 512 | objects (Sommi style) |
| New non-people-2/_Pending review/Kawaii | 381 | 512 | objects — INCOMPLETE (381 of ~39k) |
| Second batch/Classic flat TV cartoon/Non-people | 27,826 | 512 | objects, still generating |
| Second batch/Clay plasticine/Non-people | 24,327 | 512 | objects, still generating |
| **Subtotal** | **~200,700 (+ ~26k still to be generated)** | | |

### C. Source backups of sets already in A — keep, do not process
`New` (2,498), `New Clothed` (1,492), `new chatgpt` (3,622), `new clothed chatgpt` (3,622),
`new 3d animated cartoon / flat outlined / kawaii / simple anime chatgpt` (3,316 each).
Filename overlap with their People counterparts is 100% (3,303/3,303 etc.). They are the white-bg originals.

### D. Ignore
`SVGs`, `Style explorations`, `Style pilots`, `Prompt tests`, `_generation_batches` (packed sheets + 140k json),
`*/_runtime`, `_backup_People_before_final`, `People/Mulberry` (3,536 SVG — separate decision).

## 2. Findings that shape the approach

1. **The white-bg sets have near-pure white backgrounds.** Border-connected background: 5th-percentile min-channel
   ≈ 253 in every set (sample 60 each). No grey vignette like the old Sommi remnants (which sat at ~233).
   A border flood at threshold ~245 isolates the background cleanly. The ONLY hard problem is the same one the
   Sommi review solved: enclosed white regions (between legs / under arms = remove; sheets, plates, white
   clothes = keep) plus edge matting.
2. **Category trees are identical across styles** (e.g. Sommi ∩ 3D = 3,303/3,303 by relative path).
   So one consolidated tree `Library/<Style>/<category>/<name>.webp` works with people and objects merged per style.
3. **Scale rules out Sommi-style click review for everything.** Sommi: 1,295 clicks for 3,867 images (33%),
   ~170 decisions/hour. 200k images at 33% would be 66k clicks. The pipeline must be more automatic, and QA must be
   by sampling for the object sets.
4. **Outlined styles are easier.** Flat outlined and Classic flat TV cartoon have dark outlines: an enclosed white
   region bounded by outline is content; one reachable from the border without crossing a dark line is background.
   That rule can be exact for those two styles (~70k images) — to be verified in the pilot.
5. **Object sets rarely have limb gaps.** Expect a much lower flag rate than people. Measure in pilot, don't assume.
6. **Pose prior from the finished People sets (Paul's idea, measured 2026-10-31).** The Second-batch characters and
   Mulberry-like were drawn to the same poses as the People sets. Silhouette IoU after bounding-box alignment, best
   reference per style: Classic flat TV cartoon→Flat outlined 0.88, Clay→Flat outlined 0.84, Mulberry-like→Flat
   outlined 0.80, Doll→3D 0.79, Teddy→3D 0.74, Robot→3D 0.73, Aliens→Flat outlined 0.73, Monkey→3D 0.70
   (Sommi is a weak reference, ~0.45, and some pairs are mirrored). Name coverage is 99.9% once names are normalised
   (case, punctuation, "(n)" suffix). Mechanism (loose, as agreed): align by bbox, try the mirror image too, blur the
   reference transparency into a soft gap-likelihood map, and score each enclosed white region in the new image by the
   fraction of its area under that map. It is one feature beside the Sommi geometric rules, never a verdict alone.
   Scripts: `lib_pose_match.py`, `lib_pose_bestref.py`.

## 2b. Pipeline status (2026-10-31 afternoon)
- `wk_knockout.py`: border flood (≥245) + exact edge matte; enclosed regions scored against up to TWO same-name references
  (main-figure alignment, mirror tested, IoU gate 0.75, reference grown 6 px). Auto-remove only when both references agree;
  keep when the primary says solid (≤0.45) or the region is tiny; otherwise FLAG for the click tool.
- Two earlier rule versions auto-removed white shoes/bubbles/casts; caught by crop sheets of the removals before anything
  was published. Rule: every rule change gets a "removes" crop sheet before it runs on a set.
- `wk_run_set.py` → `wk_out/<set>/{v1 (bg only), v2 (defaults), idx/ (exact region maps), review_queue.json}`;
  `bg_review_server.py` reads the sidecar; `wk_apply.py` builds finals (verified identical to v2 with no decisions).
- Flag defaults in v2: removed when a reference informed the flag; kept when no usable reference (mostly white shoes).

## 2c. Progress (2026-10-31 evening)
- PUBLISHED to `Library/`: Teddy bear, Doll, Robot, Monkey (12,378 lossless files, hash-verified, manifests).
- Policy split confirmed: constraint-generated sets (pure white = background only) are automatic; mixed sets use the
  reference-free gap scorer (wall thickness, outline ring, Sommi edge features; references dropped) + visibility floor
  2,000 px + review of the 0.25+ band. Cartoon queue = 496 images (in review). Clay objects running under constraint policy.
- Decision pending (Paul, when ChatGPT credits return): regenerate the unsure band with the constraint prompt using the
  original as pose reference, instead of hand review.

## 3. Target

```
Library/
  <Style>/<category path>/<name>.webp        (people + objects merged; same tree for every style)
  _manifest/<Style>.csv                      (rel path, source path, source sha256, output sha256, pipeline version,
                                              qa: auto|reviewed|sampled, decision, date)
```
Styles (14): Sommi, Sommi clothed, 3D animated cartoon, Flat outlined, Kawaii, Simple anime, Mulberry-like,
Classic flat TV cartoon, Clay plasticine, Doll, Friendly aliens, Monkey, Robot, Teddy bear.
Rules: copy + byte-verify, never overwrite, dedupe only byte-identical same-path files, keep `(1)` variants,
originals untouched, every transform is a saved script, master format decision in §6.

## 4. Recommended order and task list

**Answer to "people first?": yes — but start with a 3-style pilot, and run the cheap QA scan of the
already-transparent sets in parallel.** Reasons: the people pipeline and click tool are proven; the people sets
are small (~30k) and finished generating; the object sets are 6× larger, still growing, and need the
automated-plus-sampled approach that the pilot has to validate first.

### Phase 0 — manifest and QA of what is already transparent (cheap, local, no decisions needed)
- T0.1 Build the master manifest: every image in A+B with sha256, set, style, kind, bg state. (~1 h machine time, est.)
- T0.2 Run the existing residual-white flagger (`bg_review_queue.py`) over set A (~22.8k, ~0.2 s/img ≈ 75 min est.).
  Report flagged counts per style. Apply the proven S9b + dust + speck rules (`bg_apply_rule.py`,
  `bg_detached_apply.py`, `bg_speck_remove.py`) to task copies; click-review only the residual flags.
  Gate: Paul sees a per-style dark montage before anything is published.

### Phase 1 — pilot the white-knockout pipeline (the decision point for everything else)
- T1.1 Write `wk_knockout.py`: border flood (≤245 → background), enclosed-region classifier reusing the Sommi features
  (`bg_features.py`), edge matte for the 1–2 px anti-aliased band (un-mix from white), shadows kept, lossless output,
  main component never removed, outlined-style exact rule (finding 4).
- T1.2 Pilot on 3 × 64 images: Classic flat TV cartoon/People (outlined people), Clay plasticine/People (soft people),
  New non-people-2/3D (objects). Dark before/after sheets with flagged regions marked.
- T1.3 Measure: % images with no enclosed region (fully automatic), % auto-classified, % flagged for click.
  Gate: Paul reviews the sheets; we set the click budget from the measured flag rate (target ≤10% on people,
  ≤2% on objects — targets, not promises).

### Phase 2 — people sets with white backgrounds (~30k)
- T2.1 Remaining Sommi 2,184 (1024 px) → merge with today's published Sommi.
- T2.2 Mulberry-like 3,303.
- T2.3 Second batch characters: Classic flat TV, Clay, Doll, Friendly aliens, Monkey, Robot, Teddy (~25k).
  Each: pipeline → flagger → click review of flags (existing `bg_review_server.py`, with the A key) →
  `bg_apply_decisions.py` → dark montage → publish to `Library/<Style>/`. One style at a time; gate per style.

### Phase 3 — object sets (~170k now, ~196k when generation finishes)
- T3.1 New non-people-2: 3D, Flat outlined, Sommi companion objects (117.5k). Pipeline + sampled QA
  (1% dark montage ≈ 1,200 tiles ≈ 25 sheets) + click review only of hard flags.
- T3.2 Second batch Non-people (Classic flat TV, Clay): manifest-driven and incremental — process what exists,
  never reprocess a hash already done, pick up new files when generation finishes. Read-only on the generator's folders.
- T3.3 Kawaii objects: decide (question 1 below) before building.

### Phase 4 — consolidate and retire
- T4.1 Copy everything verified into `Library/` with manifests; byte-verify; dedupe byte-identical same-path.
- T4.2 Move source folders (A, B originals, C backups) into one dated archive; nothing deleted until Paul says.

## 5. Effort (estimates, not measurements)
- Machine: knockout at 512 px est. 0.2–0.4 s/img single core → 200k ≈ 11–22 core-hours
  (single core throttled ≈ 1–2 days; 4 workers ≈ 3–6 h). Pipeline A on 1024 px measured 0.78 s/img.
- Clicks: depends entirely on the pilot's flag rate. At 10% of 30k people = 3k decisions ≈ 18 h at the measured
  170/h. At 33% (Sommi's rate) it would be 10k ≈ 60 h — that is why the pilot must drive the rate down.
- Disk: lossless 512 webp ≈ 100–150 KB each (est.) → 200k ≈ 20–30 GB; Q80 ≈ 3–4 GB. 122 GB free now.

## 6. Decisions (Paul, 2026-10-31)
- Kawaii objects: keep the 381 as they are; no generation.
- Master format: lossless, no compression yet.
- Concurrency: 4 workers allowed (Duet finishing soon).
- Shadows: keep.
- Open: Library/ location; click budget.

### Original questions
1. Kawaii objects: only 381 of ~39k exist. Abandoned, or to be generated? (Decides whether Kawaii is a full style.)
2. Master format: lossless (archival, ~25 GB est.) or Q80 (as the earlier plan proposed, ~4 GB)?
   Recommendation: lossless master, export Q80 for apps later.
3. Location of `Library/` (inside picom-ai-sommi-action-symbols, or elsewhere)?
4. Click budget: roughly how many hours of review are acceptable? Sets the automation threshold.
5. Shadows: keep, as with Sommi? (Assumed yes.)
6. Concurrency: stay single-core/throttled while Duet runs, or allow 4 workers overnight?

## 7. Model tiering
Rule design, pilot judgement, gates: Fable (this chat). Bulk runs, montages, manifests, publish steps: Sonnet agents
from a written brief, one style at a time. No Opus needed.
