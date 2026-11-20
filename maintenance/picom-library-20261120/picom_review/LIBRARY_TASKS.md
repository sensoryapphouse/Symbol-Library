# Symbol Library — task tracker

Goal: every symbol style in ONE folder, `~/Downloads/picom-ai-sommi-action-symbols/Library/<Style>/<category>/<name>.webp`,
backgrounds removed, **lossless**, with a manifest per style (`Library/_manifest/<Style>.csv`).
Design doc / history: `CONSOLIDATION_PLAN.md`. Memory notes: `aac-sommi-bg-removal.md`.

**How to use this file.** Work top to bottom. Status: `[ ]` todo · `[~]` in progress · `[x]` done (verified) · `[!]` blocked · `[-]` decided not to do.
Every task has a **gate**: what must be true before it counts as done. When we discover a new area to examine, add it under
**Discovered / backlog**, then promote it to a numbered task. Refresh the numbers with `python3 lib_status.py` (rewrites the STATUS block only).

## STATUS
**PAUSED 2026-11-03 (Paul).** Background removal COMPLETE for every set incl. Monster/Wood/Basic (published 2026-11-03). Task 5b vocab-gaps sorting DONE. Next when resuming: wait for any further new symbols; then Task 7 SVG pilot (30/style via vtracer_engine.py) -> Paul picks styles -> Tasks 8/9/10 -> Task 6 Q80 (after SVG) -> Task 5 copyright LAST. Open: set names (Basic vs Basic 1/2) to agree later; spiderman trademark.

<!-- STATUS-START -->
_Refreshed 2026-11-03 13:44 by `lib_status.py` (counts are measured, not remembered)._

**Library** (`~/Downloads/picom-ai-sommi-action-symbols/Library`):

| Style | Files | Manifest rows |
|---|---:|---:|
| .DS_Store | 0 | 0 |
| 3D animated cartoon | 42,538 | 42,538 |
| Basic | 3,095 | 3,095 |
| Classic flat TV cartoon | 30,982 | 30,982 |
| Clay plasticine | 30,982 | 30,982 |
| Doll | 3,151 | 3,151 |
| Flat outlined | 42,542 | 42,542 |
| Friendly aliens | 3,157 | 3,157 |
| Kawaii | 3,729 | 3,729 |
| Monkey | 3,151 | 3,151 |
| Monster | 3,094 | 3,094 |
| Robot | 3,152 | 3,152 |
| Simple anime | 3,349 | 3,349 |
| Sommi | 4,785 | 4,785 |
| Sommi clothed | 3,956 | 3,956 |
| Sommi companion objects | 39,210 | 39,210 |
| Teddy bear | 3,150 | 3,150 |
| Wood | 3,094 | 3,094 |
| **Total** | **227,117** | |

**Working sets** (`picom_review/wk_out/<tag>`):

| Set | Images | Finals built | Review queue | Reviewed | In Library |
|---|---:|---:|---:|---:|---:|

**Sources still to process** (webp counts in the source folders):

| Source | Files |
|---|---:|
| People/Sommi | 0 |
| People/Sommi clothed | 0 |
| People/3D animated cartoon | 0 |
| People/Flat outlined | 0 |
| People/Kawaii | 0 |
| People/Simple anime | 0 |
| Second batch/Classic flat TV cartoon/Non-people | 27,826 |
| Second batch/Vocabulary gaps/_Pending review | 741 |
| New non-people-2 / 3D animated cartoon | 39,183 |
| New non-people-2 / Flat outlined | 39,183 |
| New non-people-2 / Sommi companion objects | 39,179 |
| New non-people-2 / Kawaii | 381 |
<!-- STATUS-END -->

## Standing rules (apply to every task)
1. **Never publish unseen.** Montage (48 random + every hand-edited sample) looked at before anything enters the Library.
2. **Verify before publish.** Finals are pixel-compared with the checked output; copy is hash-verified; never overwrite (`wk_finish_set.py` enforces this and refuses on any mismatch).
3. **Sources are read-only** (`People`, `Second batch`, `New non-people-2`, generator `_runtime`). Work happens in `picom_review/wk_out/<tag>`.
4. **Policy by set type** (decide per set with a 400-image sample first):
   - *Constraint sets* (generated with "pure white = background only", e.g. teddy/doll/robot/monkey, clay objects): remove every enclosed white region; keep only self-outlined ones. Automatic.
   - *Mixed sets* (white content exists): scorer `wk_gap_rf3.pkl` (`--v2`) → auto-remove ≥ 0.7, auto-keep < 0.5, **review only 0.5–0.7** (regions ≥ 2,000 px). Calibrated on the cartoon review: 34 % of defaults wrong in 0.5–0.7, 2–7 % at ≥ 0.7, 9 % gaps left at 0.25–0.5.
5. **Shadows kept.** Lossless master, no compression until Paul says.
6. **Back up decisions** before restarting any review server; review servers: `bg_review_server.py --queue wk_out/<tag>/review_queue.json --port <p> --decisions wk_out/<tag>/decisions.json`.
7. **Battery/outage safe:** every publish step is resumable (`wk_apply` skips existing finals; `lib_publish` skips identical files). If a log lacks `PUBLISH DONE`, rerun the same command.

## Task 1 — Finish clay people and aliens  ✅ DONE
- [x] 1.1 Rescore with scorer v3, build narrow queues (aliens 89, clay people 20) — reviewed by Paul.
- [x] 1.2 Aliens finals built, montages checked (clean).
- [x] 1.3 Clay people finals built (6,712; 18 hand-edited), montages checked (clean).
- [x] 1.4 Published 2026-11-01 12:16: `Library/Friendly aliens` 3,099; `Library/Clay plasticine` 30,925 (24,213 objects + 6,712 people; manifest merged, 30,925 unique rows). First attempt was correctly REFUSED by the gate (decisions file not passed); `wk_finish_set.py` now verifies that every difference from the checked output has a review decision.
- Gate: Library counts = 3,099 aliens; clay = 24,213 + 6,712 = 30,925; manifests match.

## Task 2 — Four "transparent" People styles (3D animated cartoon, Flat outlined, Kawaii, Simple anime)
**Finding (2026-11-01):** NOT clean. Edge-backdrop scan is clean (0/13,212) but white remains in gaps (~1 in 5 images in 3D/Flat/anime, fewer in Kawaii — by eye). Rebuild from the white originals (`new <style> chatgpt`, 3,303 each, names identical to `People/<style>`), do not copy the other agent's transparent files.
- [~] 2.1 (running since 12:14, `wk_batch_stage2.log`) Run knockout from originals (4 × 3,303): tags `people3d_redo`, `peopleflat_redo`, `peoplekawaii_redo`, `peopleanime_redo` (chained after Task 1.4).
- [x] 2.2 Scored (scorer v3) + narrow queues built: 3D 78, Flat 106, Kawaii 127, Anime 114 (= 425 images).
- Finding: the confident band (≥ 0.7) is only ~85–95 % right in these styles (white signs, clock faces, screens, boards, aprons removed); the constraint-set "self-outlined" rule catches 0 of them. Paul chose option C: crop-sheet review of the confident band.
- [~] 2.2b Crop-sheet review: `lib_sheet_review.py` on http://localhost:8780 — 1,187 regions, 25 pages of 48 (images already in the per-image queues excluded). Click = KEEP (white object); Enter = page reviewed. Decisions in `wk_out/<tag>/sheet_decisions.json`; `wk_apply.py` and `wk_finish_set.py` honour them. **Build finals only after BOTH reviews are finished** (`wk_apply` skips existing finals). 2026-11-01: tiles now show the FINAL result on a grey checkerboard (all default removals applied, region outlined yellow; KEEP redraws it restored); T toggles the old yellow-tint view (Paul's idea; old version = lib_sheet_review.py.bak_tint).
- [~] 2.3 Paul reviews the four queues: 3D :8771, Flat :8772, Kawaii :8773, Anime :8774. Per-image page now defaults to a grey checkerboard background (B cycles Dark/Pastel/White; backup bg_review_server.py.bak_nochecker).
- [x] 2.3a VISION PRE-CHECK (DONE 2026-11-01: 3,456 judged → 1,350 gap / 1,910 object auto, 170 unclear → :8781; Paul rule 'doorways stay white, same as windows' → precheck/apply_house_rule.py settled 30 (27 unclear + 3 auto-GAP flipped), 3 out-of-office regions sent to Paul → 146 unclear; Paul REJECTED the region grid (:8781) - wants one image at a time + A for all → build_unclear_queue.py build → bg_review_server.py :8771 (118 images, current state in wk_out/<tag>/v3, verified = wk_apply output); afterwards `build_unclear_queue.py split` → wk_out/<tag>/decisions.json → wk_finish_set --decisions; audit 253/253 Sonnet≥90 right after adjudication) (Paul's request 2026-11-01: "checked more by you, unclear ones to me with a checkerboard"). `lib_precheck.py`:
  every queue + crop-sheet + low-band (<0.5, >=2,000 px) region of the 4 styles (3,456 regions, 576 sheets in precheck/people4) is judged
  GAP / OBJECT / UNSURE by vision agents using precheck/JUDGE_BRIEF.md (v2 = with Paul's house conventions: vehicle/booth windows and sign
  faces stay white). Calibration on 230 cartoon regions (answer key = Paul's decisions, 15 key errors corrected by eye, see below):
  Sonnet v2 at conf>=80 = 215/216 right, 14 to Paul. Confident verdicts -> wk_out/<tag>/precheck.json (`lib_precheck.py apply`);
  only the rest go to Paul in `lib_unclear_review.py` (:8781, checkerboard, answers in unclear_decisions.json). wk_apply precedence:
  default < pre-check < sheet KEEP < unclear review < per-image decisions; wk_finish_set accepts all of these as decisions.
  The old per-image queues (:8771-4) and crop sheet (:8780) are SUPERSEDED once the pre-check is applied (no decisions were made in them).
- [x] 2.3b **PUBLISHED DEFECTS FOUND:** the calibration showed Paul's cartoon review accepted removals of real white objects (paper sheet,
  2026-11-02: Paul OK on repair gallery EXCEPT door frames (→ see-through as published; precheck/doorway_revert.py, 21 regions, JUDGE_BRIEF + memory
  updated). Paul answered all 172 queue images → `build_unclear_queue.py split --with-old` → decisions_repair.json → `run_pub3_repair_final.sh`
  → wk_out/<tag>/final_repair. Verified: before = Library byte-identical (12,909); 199 images change (45/96/58), every one in Paul's queue (128) or a
  pre-check restoration (71), 0 without a recorded reason; doorway regions = published. Gallery :8790/published_repair/. AWAITING PAUL'S OK →
  `lib_republish.py --style <S> --staged wk_out/<tag>/final_repair --reason 'published repair 2.3b'` (moves old copies to Library/_replaced/<date>/).
  Same fix for the four People styles (published 11-02 with the old doorway rule): `precheck/doorway_revert_people4.py` (32 pre-check regions) +
  28 doorway slivers picked by eye (decisions.json note) → `run_people4_doorfix.sh` → final_door, 23 images, only doorway pixels changed.
  Gallery :8790/people4_doors/ AWAITING OK → lib_republish.py --staged wk_out/<tag>/final_door. Optional later: 5 clay doorway slivers that were
  ALREADY white when published (after-you-please #2-4, holding the door #1, removing-shoes #3) left as published.
  REPUBLISHED 2026-11-02 (Paul OK both galleries): `run_republish_20261102.sh` → replaced 45/96/58 (repair) + 5/6/6/6 (doors); old copies in
  Library/_replaced/2026-11-02/; Library == staged builds (0 differ). Housekeeping: wk_out/<tag>/final IS the Library again (previous finals renamed
  final_pub_20261101 / final_pub_doorwhite_20261102); pub3 decisions.json = decisions_repair.json (old kept as decisions_pre_repair_20261102.json).
  laptop screen, prohibition-sign faces, poster, angel robe, flag stripe, paddleboard/surfboard decks, water foam, fur trim, alb, apron) —
  verified: these are 0% opaque in Library/Classic flat TV cartoon now. Run the same pre-check on the PUBLISHED mixed People sets
  (cartoon_people, clay_people, aliens_people) and repair from v1 with Paul's sign-off (deploy gate). Lesson: on the dark background a
  removed white region is easy to miss — always review on the checkerboard.
  PROGRESS 2026-11-01: `lib_precheck.py pubbuild --run pub3` judged the 2,315 large regions that are SEE-THROUGH in the published finals
  (9 of 17 Sonnet batches used a templated default answer → set aside in pub3/sonnet_templated, re-run in 12-sheet batches with a strict
  brief; ALWAYS check judge outputs for repeated why/conf). Cascade: cartoon 328 gap / 32 OBJECT / 48 unclear; clay 1278 / 48 / 105;
  aliens 390 / 45 / 41; audit 111/111. 18 sampled OBJECTs checked by eye: all real holes. 124 of 125 OBJECTs came from accepted
  DEFAULT removals (wk_apply's pre-check precedence restores them); 1 was Paul's click (school-lunch apron) → sent to Paul.
  Unclear queue (172 images / 195 regions): `build_unclear_queue.py build --with-old --tags cartoon_people,clay_people,aliens_people --out wk_out/unclear_queue_pub3.json`
  → bg_review_server.py; afterwards `split --with-old --queue wk_out/unclear_queue_pub3.json --decisions wk_out/unclear_queue_pub3_decisions.json`
  → wk_out/<tag>/decisions_repair.json (decisions.json untouched) → wk_apply --decisions decisions_repair.json → gallery (before = final) → Paul OK → republish.
  STAGED 2026-11-01 evening: repair build wk_out/<tag>/final_repair_pre (= published + 124 pre-check restorations; differs from the live Library
  ONLY in 92 images / 124 regions, all 'now WHITE: pre-check'; 'before' = Library byte-identical, 92/92). Gallery http://localhost:8790/published_repair/
  (wk_out/galleries, serve: python3 -m http.server -d wk_out/galleries 8790). Unclear queue: bg_review_server.py --queue wk_out/unclear_queue_pub3.json
  --decisions wk_out/unclear_queue_pub3_decisions.json --port 8772 (172 images; queue images = repair build, verified 0 differ).
- [x] 2.4 Finals BUILT + VERIFIED 2026-11-01 (NOT published): `run_people4_finals.sh` → wk_out/<tag>/final, 3,303 each. Gate `wk_finish_set.py --no-publish`
  now checks PER REGION (every region whose state differs from v2 needs a pre-check/Paul decision; Paul-accepted queue images count; specks < 30 px and
  < 2000 px slivers beside a decided region are edge-matte effects). Result: differ from v2 = 313 / 346 / 218 / 356, DIFFER WITHOUT A DECISION = 0 all four.
  NB v2 ≠ defaults.csv for these redo sets (v2 kept the 427/… regions the redo scorer removes) — every one of them has a pre-check or Paul decision.
  Approval gallery: `finals_compare.py` → wk_out/compare_people4 (now served via wk_out/galleries → http://localhost:8790/people4/). 27 random pairs checked by Claude: clean.
- [x] 2.5 PUBLISHED 2026-11-02 (Paul OK): `run_people4_publish.sh` → `Library/3D animated cartoon`, `Flat outlined`, `Kawaii`, `Simple anime` — 3,303 each, all new (0 conflicts), byte-verified; manifests `Library/_manifest/<Style>.csv` 3,303 rows each. Gate re-run: 0 differ without a decision. (Trees later also receive the object sets, Task 4.)
- Gate: montage clean on dark AND pastel; 0 pixel mismatches at publish.
- Open question: keep the other agent's `People/<style>` files untouched (yes, read-only).

## Task 3 — Sommi and Sommi clothed  (corrected 2026-11-01 after a careful check — background work is essentially DONE)
Measured (`lib_qa/opaque_*.txt`): `People/Sommi` 5,986 + `People/Sommi clothed` 5,078 =
- 2,375 + 1,477 first generation (1024 px, lossless) — cleaned + reviewed by us 2026-10-31 ✅
- 2,376 + 2,450 second generation (`new chatgpt`; 512 px, lossy ALPH+VP8) — made transparent by the other agent; 96 sampled on dark: clean ✅
- 1,099 + 1,084 **`(1)` white-background duplicates**: each is the SAME picture as its transparent sibling (median diff 0.5/255, 300 compared) and identical to the first-generation original → **not work; exclude from the Library.**
- ~200 other `(n)` variants, already transparent.
- [x] 3.1 withdraw-cash: `sommi_withdraw_cash.py` (region 15 removed) → staging/sommi; Paul OK 2026-11-02; published as `ok:staged-fix`.
- [x] 3.2 Doubled-extension files: each was the cleaned version of a white `(n)` original (figure-pixel diff 0.0), so the cleaned file now sits in place of its own white original: `skateboard (1).webp`, `whisper (2).webp` (Paul: rename).
- [x] 3.3 Paul: delete → 2,181 PROVEN duplicates (pixel-identical inside the figure to the exact source of their cleaned sibling) + the 2 above MOVED (not erased) to `_backup_People_before_final/_deleted_white_duplicates_20261101/` (2,183 files; log `lib_qa/sommi_cleanup_log.csv`). People/Sommi now 4,889, Sommi clothed 3,994; only remaining opaque file: withdraw-cash.
- [x] 3.4 PUBLISHED 2026-11-02 (`lib_publish_sommi.py`): Library/Sommi 4,762 + Library/Sommi clothed 3,930, byte-verified, manifests complete
  (policy = sommi-<px>-<lossless|lossy>). The publish GATE (border ≥ 90 % see-through) found 283 files the 3.3 'opaque' lists missed:
  178 white `(n)` duplicates with a few semi-transparent pixels → same proof as 3.3 (`lib_qa/sommi_gate_dups.py`, all 178 proven) → EXCLUDED
  (source untouched; list lib_qa/sommi_publish_exclude.txt); 92 art-touches-edge files checked by eye (lib_qa/sommi_edge_grid_*.png) → published;
  **13 HELD** (lib_qa/sommi_publish_hold.txt): 9 white background with no twin (painting ×2, draw, concreting, gardening, presenting, gaming,
  write; clothed `any` half-removed) → need the pipeline like withdraw-cash; 4 torn white remnants (copy, if, admit; plasterer = Paul).
  6 base-figure cutouts (sommi/somme/sommi_m + _cupped, 171–254 px) at the Sommi root: Paul 2026-11-02 KEEP in Library.
  13 HELD → `lib_qa/sommi_held_stage.py` (all 13 were partly transparent with white/grey left: flattened on white) → wk_run_set tag
  sommi_held → Paul's per-image review (:8773, 10 images; copy/if/admit withheld: grey backdrop 229-234 is below flood/knockout limits):
  PUBLISHED 2026-11-02 write, draw, concreting (Sommi) + plasterer (clothed, wall kept by Paul); Paul DELETED presenting, gardening, painting ×2,
  gaming (excluded, sources untouched). Still HELD: copy, if, admit (regenerate or hand-clean) ; any = Paul: leave OUT.
- Note for Task 7: second-generation files are lossy — if Sommi becomes SVG, trace from the lossless originals, not these.
- Gate: no white-background file in Library/Sommi*; every file has a manifest row.

## Task 4 — Object sets (the large job, ~146,000 files)
**Paul 2026-11-02: FINISH ALL BACKGROUND REMOVAL BEFORE ANY OTHER TASK.**
**BACKGROUND REMOVAL COMPLETE 2026-11-02** (Paul skipped the small-gaps < 2000 px pass). Left: Sommi clothed copy/if/admit (grey backdrop,
regenerate or hand-clean); monumento-a-la-revolucion arch question. All wk_out working sets trashed; decisions kept in decisions_archive/. Remaining background work, in order:
  1. Phase 1 (outer background only): Flat ✅ PUBLISHED 14:30 (39,183 + 56 vocab; Library 42,542 = manifest) · 3D ✅ PUBLISHED 16:13 (39,183; Library 42,538 = manifest; 9.3 GB trashed) · Sommi companion ✅ PUBLISHED 18:07 (39,179; Library 39,210 = manifest; shadows kept)
     PHASE 1 COMPLETE for all object sets (2026-11-02). NEXT = phase 2 gap fixing: 3D first → Sommi witness → transfer to Flat (+ self-outlined guard) → vision → Paul; Cartoon/Kawaii scorer+vision+Paul. Paul: spider webs + sudoku boxes stay WHITE. · Classic flat TV cartoon ✅ PUBLISHED 16:09 (27,826; Library 30,982 = manifest; 5.9 GB trashed) · Kawaii ✅ PUBLISHED 16:09 (381 incl. stick insect 10,18 + guide-dog 23 see-through per Paul; Library 3,729 = manifest; spider webs/sudoku stay white)
     Cleanup is AUTOMATIC per set after Library byte-verify (lib_qa/cleanup_after_publish.py: final+v2 → Trash; v1+idx kept for phase 2). Flat: 7.9 GB trashed. No shadow removal (Paul).
     (`run_cartoon_objects_phase1.sh`) · Kawaii objects 381 queued (`run_kawaii_objects_phase1.sh`; white bg, not covered before).
  2. Vocabulary gaps `_Pending review` (~741 across 19 styles + 67 `_Transparent backgrounds`): mostly already transparent (28/30 sampled,
     another agent's cleanup) → QA per style (checkerboard sheets, enclosed-white check) → publish into each Library style.
  3. Phase 2 gap fixing: 3D/Flat/Sommi companion via twins (+ self-outlined guard) → vision → Paul; Cartoon + Kawaii via scorer + vision → Paul.

  PHASE 2 (2026-11-02): vision judges (Sonnet, JUDGE_BRIEF) on every white area >= 2000 px (purity >= 0.11) + Paul one-per-page review
  (bg_review_server) of unsure areas. Scripts: precheck/phase2_build|batches|score|decide|review_queue|stage|verify|twin_defaults|flat_transfer.py,
  lib_qa/cleanup_phase2.py. 3D ✅ REPUBLISHED 3,591 (Paul 244 pages). Cartoon ✅ REPUBLISHED 2,661 (Paul 428 pages).
  Sommi ✅ REPUBLISHED 3,564 (Paul 211 pages, 3D answers pre-filled). Flat ✅ REPUBLISHED 3,621 (3D transfer 72/73 calib, 0 wrong removals
  + vision + Paul 400 pages). Kawaii ✅ 2 (magpie legs, monkey tail). PHASE 2 COMPLETE for all object sets 2026-11-02; all object
  working sets, judge sheets, staging + _replaced copies trashed. NOT done (optional): white areas < 2000 px (e.g. sixteenth-note flag
  gap, small roller-coaster bits); monumento-a-la-revolucion arch left white (asked Paul).
  4. Sommi clothed copy / if / admit: grey backdrop (regenerate or hand-clean). Optional: B4 tiny gaps (teddy/doll/robot/monkey), 5 clay doorway slivers.
- [x] 4.0 **Per-set policy sample** DONE 2026-11-02: `run_obj_policy_sample.sh` (wk_run_set --sample 400) → wk_out/obj_*_s400; `lib_precheck.py objbuild --run obj4`
  (467 regions ≥ 2000 px, 78 sheets) judged by 8 Sonnet agents (no templating; 6/6 spot-checked right). RESULT: ALL FOUR ARE MIXED (none constraint-pure):
  | set | images with big region | regions → OBJECT / GAP | est. regions in full set |
  | Classic flat TV cartoon | 22 % | 65 % / 33 % | ~9,000 |
  | 3D animated cartoon | 17 % | 42 % / 55 % | ~9,400 |
  | Flat outlined | 26 % | 61 % / 37 % | ~16,200 |
  | Sommi companion | 12 % | 19 % / 81 % | ~7,500 |
  → neither 'remove all' nor 'keep all' is safe; Paul to choose the approach (see options in chat 2026-11-02). Verdicts precheck/obj4/sonnet/ = first labels for 4.6.
  Clay objects (published constraint policy, 33,112/33,123 removed) spot-check 12/12 true gaps → constraint-pure OK (white sculpted cream).
  Clay as a GAP GUIDE for other sets: NO (`precheck/clay_guide_test.py`): same names but DIFFERENT drawings (8/41 gaps found; clay_guide_pairs.png).
  BUT New non-people-2 3D / Flat outlined / Sommi companion = SAME COMPOSITIONS restyled (`precheck/objset_twin_test.py`: 400/400 twins,
  aligned IoU median 0.94 / 0.92) → decide gaps once per composition, transfer via align_ref; twin colour (white in Flat, cream in 3D) = object evidence.
  PAUL'S PLAN (2026-11-02): PHASE 1 = publish outer background only (all enclosed white kept), manifest policy 'outer-bg-only'; PHASE 2 = gaps
  per composition (Flat first: scorer + vision + Paul for unsure) → transfer to twins → republish via gallery + lib_republish.
  PHASE 1 Flat outlined RUNNING: `run_flat_objects_phase1.sh` → wk_out/flat_objects (39,183; 0 path collisions with Library/Flat outlined people).
  QUEUED after Flat: `run_objects_phase1_queue.sh` → wk_out/objects3d, wk_out/sommi_objects (stops if < 20 GB free).
  PHASE 2 ORDER (Paul 2026-11-02): decide on 3D first (+ Sommi as 2nd witness) and transfer to Flat - measured purity alone separates
  gap/object 92 % (3D), 95 % (Sommi) vs 70 % (Flat): 3D/Sommi shade white objects, Flat draws them pure white. Confirm on a bigger sample.
  FEASIBILITY 2026-11-02 (`precheck/twin_transfer_test.py`, 151 judged Flat regions): twin code map (bg / pure-white enclosed = GAP, shaded white
  or drawn = OBJECT) mapped into the Flat frame. 3D alone decides 89 % at 91 %; BOTH twins agree → 77 % decided at 93 %. Errors: one mis-matched
  image (laser grid ×5) + 3 pure-white self-outlined objects (speech bubble, sign face, badge) → add the constraint policy's self-outlined guard
  (wk_constraint_policy.py: thin wall + dark ring = OBJECT). Rest → vision → Paul.
  Classic flat TV cartoon objects are NOT twins of New non-people-2 (`precheck/cartoon_twin_test.py`: same names/paths, different drawings,
  IoU median 0.75, 15 % >= 0.9) → own route (scorer + vision + Paul).
- [ ] 4.1 Classic flat TV cartoon non-people (27,826) → `Library/Classic flat TV cartoon`.
- [ ] 4.2 New non-people-2 / 3D animated cartoon (39,183) → `Library/3D animated cartoon`.
- [ ] 4.3 New non-people-2 / Flat outlined (39,183) → `Library/Flat outlined`.
- [ ] 4.4 New non-people-2 / Sommi companion objects (39,179) → `Library/Sommi`.
- [-] 4.5 Kawaii objects (381): leave as they are (Paul).
- [ ] 4.6 Train/extend the scorer for objects (add labelled object regions; the people-trained scorer is the starting point).
- [ ] 4.7 **Regeneration option [!] blocked on ChatGPT credits + internet:** send the *unsure band* (0.5–0.7, plus anything the sampled QA flags) to ChatGPT with the original as pose reference and the constraint prompt ("pure white = background only; white objects in cream"). Export = per-style filename list + original path. Regenerated images come back constraint-pure → automatic policy. Measure the list size first (cartoon: ~85 images ≈ 3 %).
- Gate per set: sampled QA 1 % (≈ 25 montages for 39k) shows no systematic defect; unsure band reviewed or queued for regeneration.

## Pipeline index — USE THESE, DO NOT REINVENT (all located 2026-11-01; scripts verified present)
| Need | Existing pipeline | Where / how |
|---|---|---|
| fast yes/no review of many regions | `lib_sheet_review.py` (48 crops per page, click = keep) | built 2026-11-01; reuse for Task 4 object sets |
| bitmap → SVG | `vtracer_engine.py` (exact flags: `--colormode color --mode spline --hierarchical stacked --filter_speckle 16 --corner_threshold 60 --segment_length 10`; People sets used speckle **4** because 16 deletes dot-eyes) | `~/Desktop/Fleximbols/Animals/vtracer_engine.py`; binary `picom_review/vtracer`; flood-fill bg removal built in |
| SVG over 80 KB → fewer points | `svg_compressor_server.py` (port 8089): `clean_svg_noise` → grid-snap + **Visvalingam–Whyatt** point reduction → SVGO (`floatPrecision` 2, curves kept) | `~/Desktop/Fleximbols/svg_compressor_server.py`; presets 1 Light / 2 Medium / 3 Aggressive; backs up to `svg backup` |
| region tags for recolouring (skin/hair/top/bottom) | SegFormer on the same-pose 3D style → transfer to the other style | `mul_tag_v3.py`, `batch_mulberry.py` (memory: `aac-people-svg-tagging`) |
| person → new figure substitution (comparatives, pronouns, contractions) | `PRONOUN_SUBSTITUTION_METHOD.md` + **`ultimate_processor.py` (multi-figure: tags every >5-path `<g>` as target-person, swaps each)** — NOT `process_single.py`; `extract_base_figures.py`, `pronoun_substitute.py` | `picom_review/` + `~/Documents/Development/PWAs/To do next/PiCom Fluent Symbols``/ultimate_processor.py`; Fluent originals in `~/Documents/Development/PWAs/To do next/PiCom Fluent Symbols``/svgs/` (01 Comparatives 85, 02 Contractions 52, 09 Pronouns 115 files) |
| plurals | `make_plurals_flex.py` (green asterisk, viewBox-anchored, collision-aware) + `smart_shrink_plurals.py`; classification via `build_plural_candidates.py` → `generate_plurals.py`; spec `DO_PLURALS.MD` | 3,720 pluralise / 971 skip classification already exists (`plural_gen_manifest.json`) |
| tenses | `build_tenses.py` (conjugation + rollout, irregular dict) + `tense_annotate.py` (`clock(kind)` past/future/cont, viewBox-anchored) + `det_auxiliaries.py` (be/have/do); spec `DO_TENSES.MD`; modals `det_modals_extra.py`, `det_modals_symbolic.py` | clock graphics lifted from `~/Desktop/Emoji/Core symbols for all/Base/Modal/{did,will}.svg`. **3 known rollout bugs listed in DO_TENSES.MD — read first** |
| annotation arrows | `pathify_arrows.py`, `fill_arrowhead.py`, `fix_3line.py`, `fix_green_tick.py`, `hs_glyphs.py` (filled path + `#1a1a1a` outline sw7), `normalize_arrow_borders.py`, `t23_arrow_pop.py` / `t23_refit.py` (arrow size / 88 % fill) | **restored from git 2026-11-01** (my 10-31 cleanup had retired them); notes in `RETIRED_SCRIPTS.md` |
| SVG copyright stamp | `stamp_copyright.py` (`insert` / `undo`, idempotent) | text currently "All rights reserved" → must change to CC BY-NC 4.0 (Task 5) |
| webp metadata (no re-encode) | `webpmux -set xmp` + `exiftool` for verification | tested 2026-11-01: pixel-identical, +~450 bytes per file |
| SVG figure metadata | `det_meta.py` (`<metadata id="sah">`, `data-fig`) | |

## Task 5 — Copyright + licence in EVERY file  (requested 2026-11-01)
Required text: **"© Sensory App House Ltd, CC BY-NC 4.0"** (https://creativecommons.org/licenses/by-nc/4.0/) inside each individual file.
**Measured today:** 0 of 2,400 sampled webp (Library, People, Second batch, originals) carry any EXIF/XMP/ICC chunk — nothing is embedded anywhere. Existing SVG stamp (`stamp_copyright.py`) says "All rights reserved", which conflicts with CC BY-NC.
- [x] 5.1 Paul 2026-11-02: wording CONFIRMED "© Sensory App House Ltd, CC BY-NC 4.0" (+ licence URL). DO LAST - after any SVG conversion (Task 7). Was: Decide exact strings: `dc:rights`, `dc:creator`, `cc:license`, `xmpRights:Marked`, `xmpRights:WebStatement`, year (2026).
- [ ] 5.2 Write `lib_stamp.py`: `webpmux -set xmp` (no re-encode) + EXIF copyright; idempotent; verify pixel hash unchanged AND `exiftool` reads the licence; `undo` supported.
- [ ] 5.3 Update `stamp_copyright.py` TEXT/RDF to CC BY-NC 4.0 (SVG): `data-copyright`, comment, `<metadata>` with `cc:license`.
- [ ] 5.4 Wire into `lib_publish.py` as the LAST step (any later pixel edit or re-save strips metadata) and re-stamp already-published Library files (39,689+).
- [ ] 5.5 Decide scope: our generated styles = yes; **exclude** third-party material (ASL/BSL charts, original Mulberry, flags) as before.
- Gate: `exiftool -r` over `Library/` shows the licence on 100 % of files; count printed; pixel hashes unchanged.

## Task 5b — Sort the Vocabulary gaps symbols into their proper folders  (requested 2026-11-02)
- [x] 5b.1 DONE 2026-11-03: 671 files moved (lib_qa/vocabgap_sort.py + vocabgap_mapping.json, Paul approved mapping; new folders Numbers/Base colours/Sound Words/Rooms where missing; 0 clashes; manifests verified). Was: Every Library/<Style>/Vocabulary gaps/<sub>/<name> (published 2026-11-02, 13 styles + Flat outlined) -> the matching
  category folder used by the rest of that style (same tree as the other symbols); propose the mapping per sub-folder, Paul confirms,
  then move with manifest rows updated (rel changes; marks are path-keyed - check no review marks exist first). Keep (1) pairs.

## Task 6 — Compression: "are the webp reduced using Q80?"  (answer measured 2026-11-01)
**No.** All of `Library/` and the `People/` transparent styles are **lossless (VP8L)**; about half of `People/Sommi*` (the other agent's files) are lossy. The old plan spec was 512×512, Q80, method 6.
Measured on 40 Library files: lossless median **124 KB → Q80 median 17 KB (14 % of size)**, mean RGB error 3.6/255 on opaque pixels (alpha kept lossless). Library today ≈ 5.2 GB lossless vs ≈ 0.7 GB at Q80; projected ~190k files ≈ **25 GB vs ≈ 3 GB**.
- **RULE (Paul, 2026-11-01): Q80 is applied ONLY to files/styles that Task 7 has decided will NOT be converted to SVG.** Never before that decision — lossy artefacts compromise the SVG tracing. Task 6 therefore depends on Task 7.2.
- [-] 6.0 **Paul 2026-11-02: WAIT — more symbols are coming; Q80 comes AFTER SVG conversion (Task 7).**
- [ ] 6.1 Paul decides: keep lossless as master (current instruction "no compression yet") and add a separate **Q80 export** (`Library_export_q80/`, same tree) for apps — recommended — or compress in place (irreversible; not recommended).
- [ ] 6.2 If export: `cwebp`/PIL Q80 method 6, alpha_quality 100; visual check montage (dark + pastel); pixel-error report; stamp copyright (Task 5) on the export too.

## Task 7 — SVG conversion (decide which styles; keep files ≤ 80 KB)  (requested 2026-11-01)
Known: `People/Mulberry` already has 3,536 SVGs. Memory: flat Mulberry ≈ 6–15 KB, shaded 3D ≈ 50–125 KB.
**THE PIPELINE — VERIFIED 2026-11-01 from the scripts, the 16 Oct transcript and by measuring the shipped files:**
- *Bg removal:* flood-fill from the edges, R,G,B all > 240 → transparent (internal whites kept). (For Library styles the
  lossless master is ALREADY transparent → feed it straight in.)
- *Image size:* trace at the NATIVE size. Mulberry = 512 px (viewBox 0 0 512 512); Fluent = 1024. Tested 16 Oct on Mulberry:
  2× resolution recovered tiny eyes but made files ~6× bigger (≈150 KB) → REJECTED. No resize step exists in any script.
  Library masters are 1024 (Second batch) or 512 (People styles) — decide per style in the 7.1 pilot (1024 vs downscale-to-512).
- *vtracer* (`picom_review/vtracer`, 0.6.4): `--colormode color --mode spline --hierarchical stacked --filter_speckle N
  --corner_threshold 60 --segment_length 10`. **N = 16 for Fluent, 4 for Mulberry/figure styles** (16 DELETES dot-eyes and
  mouths; swept 16/8/4/2/0 on 16 Oct → 4 = sweet spot). Alt tested: `mulberry_both.py` hybrid (16 base + small dark paths cut in
  from a 4 trace) — built, outcome not recorded.
- *Shrink:* SVGO `convertPathData floatPrecision 2` (custom cfg in `mulberry_to_svg.py`), then **floatPrecision 0 if > 50 KB**
  (−30–35 %, faces intact). **Visvalingam (`svg_compressor_server.py`, :8089) is REJECTED for vtracer output** — its
  `simplify_d_points` mangles multi-subpath paths (scenes dissolve into streaks, tested 16 Oct). It is the tool Paul used by hand
  on Fluent files > 80 KB (Fluent paths differ); test it per style before trusting it.
- **Discrepancy found:** the FINAL tagged Mulberry batch (`batch_mulberry.py` → `mul_tag_v3.py`) ran SVGO with DEFAULT settings
  (3 decimals, measured on 270/300 files) and NO > 50 KB pass → 110 files > 50 KB, 17 > 80 KB, max 150 KB still unreduced.
  → 7.3 must re-shrink People/Mulberry too (fp2, then fp0 for > 50 KB, then re-check > 80 KB) — re-tag check after.
  STAGED 2026-11-01 (`mulberry_reshrink.py` → svg_reshrink/Mulberry + Mulberry_report.csv; source untouched): 110 files > 50 KB → 94 now ≤ 50 KB,
  2 still > 80 KB (midsummer-feast 99 KB, monreale-cathedral-mosaics 89 KB); tags unchanged in all 110; render diff max 0.91 % px; worst checked
  at 3× zoom = identical. Awaiting Paul's OK to copy over People/Mulberry; the 2 > 80 KB need the svg_compressor_server step.
  APPLIED 2026-11-02 (Paul OK): `mulberry_reshrink_apply.py` → 110 replaced, byte-verified; originals in People/_backup_mulberry_reshrink_20261102. Still > 80 KB: monreale 89 KB, midsummer-feast 100 KB → svg_compressor_server step.
  2026-11-02 `mulberry_big_reduce.py` (staged svg_reshrink/Mulberry_big/<level>/): the tool's apply_point_reduction as-is BREAKS SVGO'd
  paths (reads relative numbers as points + joins sub-paths: 55 % render diff); fixed by parsing (svgpathtools), sampling each sub-path
  and running the tool's visvalingam_simplify per sub-path. Tool grid-snap L1/L2 = visibly jagged → rejected by eye. Recommended
  'g1a10' (integer, area 10): midsummer 75 KB, monreale 70 KB, tags same, near-identical. Paul 2026-11-02 (page :8790/mulberry_big/): KEEP BOTH ORIGINALS as they are (over 80 KB accepted). 7.3 Mulberry DONE.
- Write-up for outsiders: `~/Downloads/createSVGS.md` (Fluent-flavoured: speckle 16, Visvalingam described as the key — see above).
- [ ] 7.1 **Pilot per style:** SPEC WRITTEN 2026-11-03 for hand-off to ChatGPT: `SVG_PILOT_SPEC.md` + `svg_pilot_kit/` (+ `svg_pilot_kit.zip`, 62 MB: recipe, metrics, 510-file sample, reference check). 3 speckle variants (4/8/16), 17 styles x 30.  30 random images × every Library style through `vtracer_engine.py` (exact flags). Record SVG size, point count, and a rendered-vs-webp visual diff.
- [ ] 7.2 **Suitability decision (Paul):** criteria = ≤ 80 KB after reduction, visually faithful, recolourable regions possible. Expectation (to be tested, not assumed): flat/outlined/cartoon/Mulberry/Kawaii suitable; 3D, clay, teddy fur, doll textures probably not.
- [ ] 7.3 For suitable styles: convert the whole style; every SVG **> 80 KB** → `svg_compressor_server.py` point reduction (Visvalingam + SVGO); re-check size and render; **do not write a new reducer**.
- [ ] 7.4 Region tagging (skin/hair/top/bottom) via the SegFormer transfer if recolouring is wanted (`mul_tag_v3.py`).
- [ ] 7.5 Publish as `Library/<Style>/…svg` alongside the webp (or `Library_svg/`); stamp copyright (Task 5.3).
- Dependency: needs Tasks 1–4 webp for the styles being converted; **feeds Task 6** (Q80 only for files decided NOT to become SVG); always trace from the LOSSLESS master; **Tasks 9 and 10 are done on SVGs**, so 7 comes first for any style that gets them.

## Task 8 — "01 Comparatives": appropriate downward arrows in ALL styles  (requested 2026-11-01)
Observed by Paul: some have a downward-facing arrow, some do not, some are too small. Counts today: Library 26 per style (Teddy, Doll, Robot, Monkey, Cartoon, Aliens-source 26), People 3D/Flat/Kawaii/Anime 52 each (incl. `(1)` variants), Mulberry 52, Sommi 98, Sommi clothed 102; Clay not yet; Fluent originals 85.
- [x] 8.1 Contact sheet of `01 Comparatives` per style (dark + pastel), with the Fluent original beside each; define per concept which arrow is required (Paul to confirm the rule: e.g. which comparatives need a DOWN arrow).
- [x] 8.2 Classify every file: arrow present and big enough / absent / too small / wrong direction — scripted measure of arrow area vs image, then eyes on the doubtful ones.
- [x] 8.3 Fix using the existing arrow tools (restored): `hs_glyphs.py` glyph, `t23_arrow_pop.py`/`t23_refit.py` for size, measured emptiest-corner placement. Raster styles need a composite step (decide: fix in SVG after Task 7, or composite onto webp).
- Gate: every comparative in every style has the correct arrow at ≥ the agreed minimum size; before/after sheet approved.

## Task 9 — Substitution technique: Comparatives, Pronouns, Contractions  (requested 2026-11-01) — COMPLETE 2026-11-19
Method = swap the person(s) in the **Fluent SVGs** for the style's own figure, **multi-figure** (`ultimate_processor.py`); possessed object sits on the chest (object centre ≈ 0.55–0.57 of figure height); no-person concepts copied; male = default name, female = `<name> (F)`.
- [x] 9.1 Inventory completed 2026-11-19: all 252 Fluent template renders inspected (85 Comparatives, 52 Contractions, 115 Pronouns). Corrected current Pronoun classification: 54 concepts = 21 single-person, 18 group, 15 no-person; `they-them` contains three people. People-only scope: 19 styles; non-People symbols and Sommi companion objects excluded. Evidence and all-style base proposal: `~/Documents/Development/PWAs/To do next/PiCom Symbols/task9_inventory_20261119/index.html`.
- [x] 9.2 Bases and variants: the 12 newly authorised People styles are completed using their own figures and poses; existing five-style choices are retained; Sommi/Sommi clothed remain completed. Native action comparisons use one available character variant; see the final 2026-11-19 checkpoint.
- [x] 9.3 Own-figure assets reused/composed for the 12 new styles, with complete source figures embedded in SVGs. Holding poses, hands, objects and age/action cues checked. Existing originals unchanged.
- [x] 9.4 Authorised rollout completed: 96 3D/Kawaii full-figure comparisons and 1,656 new outputs across the remaining 12 styles. Every changed result visually checked. The earlier pilot gate was superseded by Paul’s full-rollout approvals.
- [x] 9.5 Contractions: 28 person-containing outputs completed in each of the 12 new styles; the five saved styles’ 28 each are approved for reuse. Existing auxiliary marks retained. Publication of saved work remains under 9.6.
- [x] 9.6 Publication complete: all remaining five-style People substitutions published by reuse, including default/female they-them corrections. 634 final-pass files verified; all 96 previous 3D/Kawaii comparatives and 1,656 twelve-style outputs still match. All 19 People styles accounted for (Sommi/Sommi clothed previously complete). Q80 remains deferred to Task 12.
- Gate: every swapped figure sits correctly, arrow/object z-order intact, group counts right (everybody = 4, we/ours/theirs = 3); sampled montage clean.

## Task 10 — Plurals and tenses  (requested 2026-11-01)
Use the as-built pipelines; read `DO_PLURALS.MD` and `DO_TENSES.MD` first (they record the bugs: badge/clock must be **viewBox-anchored**; never truncate a same-name file; skip irregular forms and non-verbs).
- [ ] 10.1 Decide per style: SVG route (needs Task 7) or a raster composite of the badge/clock onto webp. (Existing code is SVG-anchored.)
- [ ] 10.2 Plurals: reuse the stored classification (3,720 pluralise / 971 skip) and map to each style's vocabulary; `make_plurals_flex.py` + `smart_shrink_plurals.py` (only shrink when the corner has ink).
- [ ] 10.3 Tenses: `build_tenses.py` conjugation + `tense_annotate.py` clock (past/future/continuous); be/have/do via `det_auxiliaries.py`; modals via `det_modals_*.py` (restored).
- [ ] 10.4 Pilot 20 per style → montage → approval → rollout into a separate `Plurals and tenses/` tree per style (kept out of the main set, as before).
- Gate: render-verify (no blanked files, clock/badge inside the viewBox, no garbage conjugations); sampled montage clean.

## Task 11 — Set names (decide at the time)
Some sets will be renamed **Basic 1** and **Basic 2** (which ones: decided at the time). Note 2026-11-03: a style folder `Library/Basic` (new People set) now exists — agree all names together with Paul later. Current Library style folders: see STATUS table.
- [ ] 11.1 Paul decides final names and the mapping old → new.
- [ ] 11.2 Rename LAST, with a script that updates folders, manifests and any paths in tracker/notes; APFS is case-insensitive — group by lower-case name and verify counts (lesson from `renumber_pcx.py`).
- Gate: manifests, `lib_status.py` and the Library agree after renaming.

## Task 12 — Final combined SVG-to-WebP Q80 conversion (deferred by Paul)

Added at the end of the numbered task list at Paul's request. Wait until the remaining symbol composition/editing work is complete, so the new substitutions and any later SVG compositions can be converted together. **Do not start now.** This is a final Library delivery-format pass, not whole-style vector tracing or a request to convert every existing native SVG collection.

- [ ] 12.1 Inventory the finished SVG compositions intended for WebP-based styles, including the new Task 9 symbols and relevant later outputs. Reuse completed conversions and skip existing Q80 files; resolve destination conflicts without blindly overwriting unrelated symbols.
- [ ] 12.2 Render at the corresponding Library image dimensions, preserving transparency, then encode once as WebP Q80. Verify arrows, hands, books, small details, layout, dimensions and alpha before replacing the corresponding newly composed Library SVGs.
- [ ] 12.3 Keep People originals and construction scripts/manifests. Publish in the final Library folders; leave no duplicate export tree, backup image collection or temporary review images. Record conversions so the pass resumes without recompressing completed files.
- [ ] 12.4 Apply or verify the required final copyright/licence metadata after encoding, coordinated with Task 5. Reconcile final counts and report total size savings.
- Gate: intended final symbols available as verified Q80 WebPs; People originals unchanged; conversion manifest complete; temporary and superseded delivery copies tidied.

## Discovered / backlog (add new areas here)
- [x] B1 Vocabulary gaps (671 in 14 styles; QA `lib_qa/vocab_gaps_check.py`): 67 white-bg files replaced by their `_Transparent backgrounds`
  version, 3 lot-count-many knocked out (outer bg only). Paul 2026-11-02: tags stripped, folder option A → Library/<style>/Vocabulary gaps/...,
  10 same-name pairs kept as name + 'name (1)'. PUBLISHED 13 styles (`lib_qa/vocab_gaps_publish.py`); Flat outlined (56) auto-publishes after
  the Flat objects publish (`run_vocab_flat_after.sh`). NOTE: Library/Sommi companion objects is a new style folder (31 so far; objects next).
- [ ] B2 Mulberry: 3,536 background-free **SVGs** in `People/Mulberry` — decision: bring SVGs into Library as-is, or also export PNG/webp?
- [ ] B3 Generator still adds files (clay, cartoon non-people): rerun is incremental (`wk_run_set` skips done) — re-check counts before declaring a set complete.
- [ ] B4 ~22 tiny string/chain gaps remain white in teddy/doll/robot/monkey (≤ 700 px, below display size) — accept or add a thin-gap rule.
- [ ] B5 Retrain scorer on all new review decisions (cartoon 496, aliens 89, clay 20, + the four People queues) → `wk_gap_rf4.pkl`; recheck calibration.
- [ ] B6 Housekeeping: `_sommi_archive` (2.9 GB), `_retire_pending` (335 MB), `wk_out/*/v1,v2,final` working copies (tens of GB) — delete only on Paul's word; keep manifests + decisions.
- [ ] B7 Pastel-background check of a montage per published style (Paul's display is pastel).
- [ ] B8 Commit the new scripts (`wk_*.py`, `lib_*.py`) to git (picom_review repo); 200+ unrelated uncommitted changes exist — stage only these paths.
- [ ] B9 Decide the final fate of `People/<style>` transparent files once the Library supersedes them.
  2026-11-02 measured (`lib_qa/style_copies_inventory.py`, `lib_qa/people_extras.py`): every People/<style> .webp for 3D/Flat/Kawaii/Anime is in
  the Library at the same path; Sommi/Sommi clothed extras = proven white dups + Paul-deleted/held only. UNIQUE in People: 233 substitution SVGs
  per style (Comparatives 109, Contractions 40, Pronouns 84; 21 Oct) → KEEP for Task 9 (Paul). People/Mulberry SVGs → keep (B2).
  Disk tidy 2026-11-02: 25.6 GB moved to ~/.Trash/picom_tidy_20261102 (`tidy_20261102.py`; finals byte-checked == Library first) - Paul empties Trash.
  People cut-outs (Paul yes): 22,095 .webp moved to ~/.Trash/picom_tidy_people_20261102 (`tidy_people_20261102.py`: each in Library, or proven dup with twin in Library, or listed with original on white). People now = substitution SVGs + Mulberry only.

## Decision log
- 2026-10-31 Library lives inside `picom-ai-sommi-action-symbols`; lossless; no compression yet.
- 2026-10-31 Kawaii objects stay at 381. Shadows kept. Workers: 4 allowed.
- 2026-10-31 Constraint sets (teddy, doll, robot, monkey, clay objects) accepted without per-image review.
- 2026-10-31 Regeneration of unsure images via ChatGPT (same pose reference) — deferred until credits/internet.
- 2026-11-01 Mixed-set policy: review only the 0.5–0.7 band (calibration from cartoon decisions).
- 2026-11-01 Four transparent People styles rebuilt from originals (QA found gaps).

- 2026-11-01 Requested tasks 5–11 added (copyright CC BY-NC 4.0 in every file, Q80 question, SVG suitability + 80 KB rule, comparatives arrows, substitution for comparatives/pronouns/contractions, plurals/tenses, set names Basic 1/2).
- 2026-11-01 My 10-31 cleanup had retired arrow/modal scripts needed here; restored from git (see RETIRED_SCRIPTS.md). Measured: Library is lossless, no webp has copyright metadata.

- 2026-11-01 Q80 only after the SVG decision, and only for files that will not become SVG (Paul). SVG tracing always uses the lossless master.

- 2026-11-01 Sommi re-checked: background work done; 2,183 opaque files are white `(1)` duplicates of cleaned symbols (exclude), 1 real leftover (withdraw-cash), 2 doubled extensions.

- 2026-11-01 Paul: delete the white `(1)` duplicates (moved aside, reversible) and rename the doubled-extension files (placed over their own white originals).

- 2026-11-01 Option C for the confident band: crop-sheet review (`lib_sheet_review.py`), reusable for the object sets.
- 2026-11-03 Monster 3,094 / Wood 3,094 / Basic 3,095 published (constraint rule + vision on every removed area ≥300 px + Paul's one-per-page review); working sets + judge sheets trashed, decisions + verdicts in decisions_archive/<tag>.
- 2026-11-03 Task 5b done: Vocabulary gaps sorted into category folders in all 14 styles (671 files); spiderman placed in Gaming & Hobbies/Niche Hobbies and Fandoms (trademark - Paul to decide).

## How to resume after an interruption
1. `python3 lib_status.py` — see what exists.
2. Check logs: `wk_batch_stage2.log`, `lib_publish_*.log`; any log without `PUBLISH DONE`/`STAGE2 DONE` stopped early → rerun its command.
3. Review servers: restart with the command in rule 6 (decisions are on disk).

## Decision update — 18 November 2026

Paul: no more whole-style SVG conversions. Retain existing native SVGs. Task 7 whole-style tracing/tagging rollout is cancelled. Finish the previously authorised remaining Q80 compression in Library in place (3D animated cartoon, Clay plasticine, Kawaii), preserving People originals and skipping already-completed file versions. No extra image backups or export copies. Preserve image dimensions, alpha and metadata. The comparative, pronoun, contraction, plural and tense tasks remain planned; whole-style tracing is not a prerequisite and raster-figure composition can be used when those tasks are implemented.

Background cleanup and final verification are complete. Detailed current decision and Q80 progress are saved under PiCom Symbols/restored_cleanup_pilot/people_cleanup; this update supersedes the earlier SVG-before-Q80 sequence.


## 2026-11-19 — Task 8 arrow audit ready; repairs NOT authorised yet

Paul authorised the comparative arrow audit across every style, requesting problems and proposed rules before any image changes. Audit complete: 730 targets across 19 styles (678 Library WebPs plus 52 retained native Mulberry SVGs); 85 Fluent references inspected. Findings: 205 missing selectors, 15 upward arrows above the taller person, 25 downward selectors below the proposed 40 px high / 24 px wide floor at a 512 px canvas. Proposed repair queue: 245; 485 retained under the proposal. All 815 source hashes unchanged. Sommi companion objects has no 01 Comparatives folder.

Review: /Users/paulblenkhorn/Documents/Development/PWAs/To do next/PiCom Symbols/comparative_arrow_audit_20261119/index.html
Evidence and exact paths: results.json, summary.json and verification.json in that same directory. All 730 target cells inspected on contact sheets; 52 native follow-ups; all 25 small-arrow cases also checked at 128 px on pastel and dark. No images modified. Rules, minimum size and repair scope await Paul’s approval; Task 8 repair gate is not complete. Do not begin Task 9 or later tasks from this audit alone.


## 2026-11-19 — Task 8 approved repairs COMPLETE

Paul approved the 245-image repair queue and deterministic Python/SVG edits. Completed and visually reviewed every output: 205 missing selectors added, 15 upward selectors redirected, 25 small selectors enlarged. Matching poses guided targets with per-file checks (Basic older selects right; the other 16 common-layout styles select left). 236 WebPs were replaced in Library in place at Q80. Nine native SVG finished versions were published to Library/Mulberry/01 Comparatives; all 52 People/Mulberry source SVG hashes remain unchanged. No full-size backup copies were created.

Verification: all 245 published hashes match reviewed outputs; all 485 targets outside the queue and 85 Fluent references retain their hashes. Alpha outside arrow edit regions is unchanged. Basic and Mulberry old-arrow remnants found during review were corrected and rechecked. Every batch’s staged images and temporary review sheets were deleted. The compact before/after illustration, code, per-file receipts and report are retained.

Finished review: /Users/paulblenkhorn/Documents/Development/PWAs/To do next/PiCom Symbols/comparative_arrow_repairs_20261119/index.html
Evidence: completion.json, published.jsonl, reviews/ and approval.json in that directory; canonical receipt Library/_manifest/comparative-arrow-repairs-20261119.jsonl.

Task 9 (comparatives/pronouns/contractions substitutions) and later tasks have NOT been started. Future inventories should use the nine corrected Library/Mulberry SVGs in preference to their matching People sources, without counting both versions as separate targets. The broader Mulberry import decision remains separate.


## Task 9 inventory checkpoint — 2026-11-19

Paul clarified: **People styles only**. Non-People symbols and Sommi companion objects are excluded. Destination is each style's root-level `Pronouns` folder, beside `09 Pronouns`, and equivalent root-level category folders. Existing `Pronouns` folders indicate earlier work to assess for reuse. Preserve all existing files and People originals; do not overwrite, create a parallel duplicate output tree, or start substitutions from this inventory approval alone.

Review: `~/Documents/Development/PWAs/To do next/PiCom Symbols/task9_inventory_20261119/index.html`. Machine-readable evidence: `base_proposals.json`, `existing_coverage.json`, `template_inventory.json`, `observed_issues.json`, `verification.json` in the same directory.

- Five People styles already hold 233 SVG outputs each: 3D animated cartoon, Flat outlined, Kawaii, Simple anime and Mulberry. Each has 84 Pronouns / 40 Contractions / 109 Comparatives. Their SVG metadata confirms earlier substitutions. These 1,165 SVGs are self-contained with no external image references. Prefer reuse and targeted correction over regenerating them; filename coverage is not visual acceptance.
- Library/Sommi/Pronouns has 29 files covering 27 concepts (includes one test file and a M/F pair); Sommi clothed has 22 files covering 22 concepts. Their numbered source drawings are not equivalent completed substitutions. Both also have 16 root-level Contractions.
- Library/3D animated cartoon/Comparatives and Library/Flat outlined/Comparatives each contain 83 object-based alternatives; those are not the People SVG substitutions and stay unchanged. Mulberry's full earlier outputs remain in People; nine corrected numbered Comparative SVGs are in Library/Mulberry. The separate broader Mulberry publication decision remains outstanding.
- Verified omissions: `People/{3D animated cartoon,Flat outlined,Kawaii,Simple anime,Mulberry}/Pronouns/they-them.svg` and `Library/Sommi/Pronouns/they-them.webp` still contain Fluent people. Sommi clothed root `Pronouns/my.webp` needs chest-placement review. The numbered Sommi clothed `09 Pronouns/I.webp` visibly contains an iStock mark and was excluded as a proposed base. No files changed.
- Inspected all 252 current Fluent template renders, candidate sources for all 19 People styles, all 12 saved Sommi root base assets and 75 earlier-output/source samples. This is an inventory and proposal, not a new full QA pass on all existing substitutions.
- Current comparative figure markup defeats the old >5-path-group detector. There are 24 full-body comparative templates plus 12 face/bust/simplified-body exceptions. Preserve comparative age/pose/body cues; a universal standing-body swap is inappropriate. Contractions include 40 full-figure template files plus the simplified-bust `who's` exception. Pronouns include 100 person-containing template files and 15 non-person files.
- Actual saved Sommi clothed standing bases are yellow neutral, blue male, pink female; the older hat description does not match them. Saved clothed female clutch assets exist; equivalent male/neutral cupped assets were not found among the root bases. Review before object-holding implementation.
- Task 9.1 complete; Task 9.2 awaiting review. Tasks 9.3–9.6 and Task 10 have not been started in this inventory. No new cutouts, source-image edits, substitutions, Q80 passes or Library folders were created. Source hash verification and temporary-sheet cleanup are recorded in the review directory.


## Task 9 reuse audit and scope clarification — 2026-11-19

Paul requested checking existing substitutions before doing new work. He then explicitly clarified that **Sommi and Sommi clothed are already done**. Keep both completed; exclude them from the new substitution/correction queue. Their read-only inspection did not modify any files and must not be treated as permission to redo them. Non-People styles and non-People illustrations remain excluded.

Reuse report: `~/Documents/Development/PWAs/To do next/PiCom Symbols/task9_reuse_audit_20261119/index.html`.
Machine-readable decisions and remaining work are in `files.json`, `summary.json`, `remaining_work.json`, `annotation_checks.json`, `acceptance_rules.json` and `verification.json` in that directory.

- **480 full-figure SVG substitutions recommended for reuse unchanged**: 68 Pronouns + 28 Contractions in each of 3D animated cartoon, Flat outlined, Kawaii, Mulberry and Simple anime. All were visually inspected. All 480 preserve every source annotation primitive; all 90 possessive files retain the held-object artwork. No regeneration or recompression is needed for these files.
- **Five they-them omissions** in those five styles can reuse the existing styled `they.svg` composition; current Fluent `they-them` and `they` have identical semantic arrow geometry and scene framing. A later approved correction can reuse that artwork; decide variant naming and preserve existing destination files. No corrections or new variants were created in this audit.
- **240 saved comparative adaptations** contain style-specific heads and recoloured posed bodies, rather than complete base-figure replacements. Preserve these useful compositions. Paul needs to decide whether the existing body treatment is acceptable; do not discard/rebuild them automatically or erase comparative pose/age/strength cues with identical standing figures.
- **65 generic face/bust/simple-body drawings** (13 per style: colder/coldest, hotter/hottest, fuller/fullest, newer/newest, noisier/noisiest, thinner/thinnest, who's): recommendation is to retain them unless Paul requests style-specific characters. They are not claimed to have undergone complete character substitution.
- **375 non-person components** in those five SVG collections are outside People replacement work and stay unchanged. The counts reconcile to 1,165 existing SVGs: 480 + 5 + 240 + 65 + 375.
- Root substitution outputs are still absent in People/Library for these **12 styles**: Basic, Classic flat TV cartoon, Clay plasticine, Doll, Friendly aliens, Monkey, Monster, Robot, Soccer player, Teddy bear, Wizard and Wood. Base/variant decisions remain pending. Preserve their numbered, cleaned source images. Do not redo background cleanup or non-People drawings.
- A wider folder search found another older Mulberry root-output copy: all 233 SVGs are byte-identical to People/Mulberry and add no unique work. Earlier Sommi source folders and nested Grammar & Language sources do not expand the new-work scope.
- Publication is not yet done. Five saved styles lack root Pronouns/Contractions in Library. Existing object-based root Comparatives in Library/3D and Library/Flat overlap 83 concept names per style with the complete saved SVG collections (different extensions do not resolve competing meanings). Preserve those existing files; determine the People-only destination mapping before publication. Keep People originals. No duplicate staging output tree.
- All 790 People-containing SVG outputs in the five saved collections were visually inspected. An additional 83 Sommi/Sommi clothed files had been inspected read-only before Paul's completed-status clarification; no follow-up work for those sets is queued. All 1,248 catalogued source hashes remained unchanged. The earlier machine classification of newer/newest (hat comparisons) was corrected to face/bust exceptions; all ten saved outputs were inspected explicitly.

**Explicit semantic-artifact acceptance rule from Paul:** future new/corrected symbols must preserve the held book/card or other possessed object, arrows, question marks, clocks, negation and auxiliary marks, and all comparative props/cues. Keep correct scale, placement and foreground layering; the possessive object belongs visibly on the chest with sensible hands/arms. Replace every intended figure and preserve group counts. Check every changed result side by side with its Fluent original. Merely preserving a shape somewhere in the file is insufficient if it becomes hidden or wrongly positioned.

Task 9 remains at reuse/base/design review. No new cutouts, substitutions, Q80 work or publication were performed. Do not begin implementation merely because the inventory/audit is complete.


## Task 9 comparative figure decision and eight previews — 2026-11-19

Paul chose complete figures for **3D animated cartoon and Kawaii** and to keep the existing comparative figure treatment for **Flat outlined, Mulberry and Simple anime**. This divides the 240 saved comparative adaptations into 96 for the full-figure direction and 144 to retain. Sommi and Sommi clothed remain completed and excluded. Non-People remain excluded.

Paul requested a few examples with arrows and other details preserved before doing all of them. Eight separate previews are ready: cleaner (M), cleanest (F), taller (M), wetter (F) in each of 3D and Kawaii. Existing complete native figures from saved Pronoun SVGs were reused. Original arrows, star, sparkles, water/ground/sun details, comparison fading and height contrast are preserved. Dirt was repositioned onto clothing, odour marks moved beside wider heads, and the crossed-out water drop raised clear of the wider head. Every preview was visually checked; all semantic annotation primitives remain, and all 12 input files retain their hashes. No People or Library source image was changed or published.

Review: ~/Documents/Development/PWAs/To do next/PiCom Symbols/task9_full_figure_preview_20261119/index.html
Evidence: decision.json, previews.json, source_hashes.json, verification.json, browser_check.json in the same folder.

**Await Paul's review before the full rollout.** These standing and height-comparison previews do not establish treatment of distinct poses or age/strength cues such as faster and stronger. Preserve those meanings with appropriate figures/poses rather than blindly applying a neutral standing body. Keep the original files safe. Destination mapping/publication conflicts recorded above remain unresolved. No other Task 9 work is authorised by this preview checkpoint alone.


## Task 9 — 96 full-figure comparatives complete; all People styles retained in scope — 2026-11-19

Paul approved full figures for 3D animated cartoon and Kawaii, preserving arrows, details and meaningful poses, with every changed image checked. Completed 96 SVGs: 24 concepts × two genders × two styles. Every output was compared visually to its saved source; posed parts preserve running/walking, strong/weak stance, age and size differences. Grey hair and walking sticks are retained for older figures. Dirt, odour and crossed-out drops were adjusted to the full bodies. All semantic annotation primitives remain; arrows/star geometry and scene opacity/transforms remain unchanged. Weak postures were refined and rechecked; all age cases were rechecked after aligning sticks with hands and ground.

Finished new files: Library/3D animated cartoon/Comparatives/People and Library/Kawaii/Comparatives/People. The People subfolder avoids mixing these with existing root-level object alternatives. No existing Library or People file was replaced. Accepted outputs were moved from staging, with no backup copies.

Review and evidence: ~/Documents/Development/PWAs/To do next/PiCom Symbols/task9_full_figures_20261119/index.html — published.json, visual_review_log.json, source_hashes.json, existing_hashes.json and people_style_status.json. Status for ALL 19 People styles is visible in this review. This completion supersedes the preview-only gate for these 96 files; it does not mark Task 9 complete.

Paul clarified that the full-figure question concerns the other People styles too, including Monkey, Friendly aliens, Robot and Doll. They were not excluded. Read-only assessment of proposed bases plus cleaner/faster/older in ALL 12 outstanding styles confirms useful full-character artwork and poses already exist in their numbered folders. Recommend reusing their own complete characters and posed artwork for missing root-level substitutions, retaining arrows/objects and characteristic tails/antennae/horns/robot joints/clothing/textures. No whole-style tracing or blanket replacement of good numbered drawings. Standing cutouts do not replace action poses.

**Outstanding style-root substitutions remain explicitly tracked for all 12:** Basic; Classic flat TV cartoon; Clay plasticine; Doll; Friendly aliens; Monkey; Monster; Robot; Soccer player; Teddy bear; Wizard; Wood. No new Pronouns, Contractions or Comparatives have been generated for those 12 in this pass. Base/variant choices and reuse of numbered artwork remain to be resolved. Do not confuse missing unnumbered folders with absence of numbered symbols, or mark those styles done.

**Existing work still to reuse/publish:** 480 approved People substitutions (340 Pronouns, 140 Contractions) in the five saved SVG styles; five they-them corrections remain. Flat outlined, Mulberry and Simple anime retain their 144 comparative adaptations under the earlier decision. Complete figures could also be considered for them, but no further edits were authorised or made here. The 65 generic drawings and 375 non-person components remain unchanged. Other publication mapping remains outstanding. Sommi and Sommi clothed remain completed and excluded from new work. Non-People are excluded. Task 10 (plurals/tenses) remains later; do not skip remaining Task 9 work.


## Task 9 — remaining 12 styles fully authorised — 2026-11-19

Paul authorised completing Basic, Classic flat TV cartoon, Clay plasticine, Doll, Friendly aliens, Monkey, Monster, Robot, Soccer player, Teddy bear, Wizard and Wood using their own full figures and poses. Reuse existing work; preserve arrows and objects; visually check every changed output; keep originals unchanged; remove temporary review/staging files after accepted batches. This approval supersedes the earlier preview-only gate for these 12 styles.

Working record: `~/Documents/Development/PWAs/To do next/PiCom Symbols/task9_remaining_people_20261119`. Scope: 70 Pronouns, 28 Contractions and 48 full-body Comparatives per style, 1,752 new outputs total, including both they-them variants. Self-contained SVG compositions embed existing WebP artwork unchanged alongside vector annotations; no whole-style vector tracing or recompression. New unnumbered root categories only. All original People and numbered Library files remain unchanged.

Checkpoint: preparation and pose-asset refinement; zero outputs published. Standing substitutions can proceed independently of held-object and articulated-pose refinement. Do not describe these 12 styles as completed until all outputs have passed review and publication. Other saved styles' publication and Task 10 remain later work.


## Task 9 — remaining 12 People styles completed — 2026-11-19

This checkpoint supersedes the zero-published checkpoint above. All 12 authorised styles are now completed: Basic; Classic flat TV cartoon; Clay plasticine; Doll; Friendly aliens; Monkey; Monster; Robot; Soccer player; Teddy bear; Wizard; Wood.

Published **1,656 new files**, 138 per style: 70 Pronouns, 28 Contractions and 40 Comparatives. New files are directly in Library/<style>/{Pronouns,Contractions,Comparatives}. No previous Library or People file was overwritten. All 1,656 outputs were visually inspected against the existing layout references on 79 cross-style review sheets, including each gender variant, group layout, held book, action and age comparison. Arrows, books, punctuation, clocks, negation, comparative stars, dirt/weather details, speed lines, tortoise and walking-stick geometry were preserved; placements and foreground hands were adjusted where required.

**Action variant detail:** the initial 1,752 count provisionally assumed two gender variants for all 24 comparative concepts. Existing intact running/walking and strong/weak sources generally provide one character variant. The implemented reuse assumption is one native version of each of those eight action concepts per style (96 outputs), avoiding fabricated or duplicate gender variants; this reduces the final total by 96 to 1,656. A preference question was asked, but no separate answer had arrived before completion. This was an implementation assumption under the full-figure/pose reuse approval, not an additional user decision. Male/female variants remain elsewhere, including age comparisons. Native pose clothing can differ from the standing base. Possessives reuse holding artwork with matching heads and foreground hands; Doll male uses adapted own-figure arms. Rejected articulated and head-swap action drafts were not published.

All 1,237 recorded original source hashes still match. All outputs are self-contained, internal image references resolve, and intended figure counts match their templates. Final SVGs embed raster artwork without recompressing it; no whole-style vector tracing was performed. Published output size is 72,452,304 bytes. Staging copies, review sheets and rejected temporary image drafts have been deleted; no backup image tree was retained. Small scripts, manifests and audit records remain.

Review: ~/Documents/Development/PWAs/To do next/PiCom Symbols/task9_remaining_people_20261119/index.html. It loads the finished Library files directly, without duplicate images. Evidence: published.json, visual_review_log.json, verification.json, sources.json, scope.json and progress.json in that directory.

This completes the authorised **12-style** work, not all of Task 9. The five earlier saved styles still have the recorded reuse/publication and five they-them corrections to resolve. The 144 retained comparative adaptations, 65 generic drawings and 375 non-person components are unchanged. Sommi and Sommi clothed remain completed and excluded. Task 10 remains later; do not start it automatically.


### Task 9 — explicit native-pose approval received

Paul answered the pending variant question: **“Reuse the existing complete poses (recommended)”**. This explicitly confirms the completed approach: reuse intact existing poses as drawn, without forcing separate male/female action versions. Pronouns and Contractions retain appropriate male/female figures; available age variants are also retained. The earlier implementation-assumption note is superseded by this approval. No images or output counts changed: 1,656 new symbols across the 12 styles remain complete.


## Task 9 — final reuse/publication complete — 2026-11-19

Paul authorised finishing Task 9. Published 634 files: 480 previously checked Pronouns/Contractions plus 144 retained comparative adaptations unchanged, and ten they-them outputs (default and female in each of the five saved styles) reusing their existing they compositions. Every corrected output visually checked against the prior Fluent composition; all arrows preserved and all three figures substituted. Reused files remain byte-identical to their reviewed source versions.

Final five-style coverage is 70 Pronouns + 28 Contractions + 48 Comparatives each. Flat outlined Comparatives/People avoids its existing object alternatives; 3D/Kawaii retain their already published Comparatives/People; Mulberry and Simple anime use their empty root Comparatives. No existing file was overwritten. People originals remain safe. All 1,166 protected sources and 262 pre-existing Library files match hashes; all 1,752 previously completed outputs also match. There are 2,386 tracked finished outputs across 17 styles, plus Sommi/Sommi clothed already completed per Paul. The 65 generic drawings and 375 nonperson components remain unchanged in their existing locations and outside this People-substitution publication.

Task 9 is complete. Temporary review images deleted; no staging/backup output copies retained. Final-pass files total 10,447,670 bytes. Review and evidence: ~/Documents/Development/PWAs/To do next/PiCom Symbols/task9_completion_20261119/index.html (published.json, verification.json, visual_review_log.json, people_style_status.json).

Next: Paul requested exact Task 10 pipeline, overlap/shrink behaviour, eligibility and destination clarification. Read-only investigation only; do not generate Task 10 symbols yet. Final Q80 delivery conversion remains Task 12.


## Task 10 — plural and tense layout methods approved — 2026-11-19

Paul explicitly selected **smart_shrink_plurals.py** for plurals and confirmed **“Tenses look fine.”** Use make_plurals_flex.make_plural for the anchored star composition, calling smart_shrink_plurals.process for content-aware minimal shrink toward bottom-left. Keep the star fixed and keep the symbol full-size when clear. Do not substitute the make_plurals.py → plural_recompose.py resizing/recentring route or reposition_only.py.

Retain tense_annotate.annotate and build_tenses conjugation logic: full-size when the clock area is clear, otherwise the existing 0.82 scale with viewBox-adjusted displacement; clock remains anchored top-right. Do not silently replace this with plural minimal-shrink logic.

This confirms the layout methods. Current Library symbol eligibility and output-folder mapping still need clarification; no Task 10 generation has started. The old batch drivers have historical hard-coded roots and must not be run unchanged against Fleximbols/Fluent. Preserve People originals, avoid duplicate image trees, and keep Q80 conversion deferred to Task 12. Exact chosen script paths and hashes are saved in ~/Documents/Development/PWAs/To do next/PiCom Symbols/task10_preparation_20261119/method_decision.json.


### Task 10 — per-style destination structure confirmed — 2026-11-19

Paul specified the Fluent `svgs/Plurals and tenses` layout and explicitly confirmed separate folders for each style. Destination: `Library/<style>/Plurals and tenses/<original category>/<original subcategory>/<inflected filename>.svg` during composition, with final WebP Q80 delivery deferred to Task 12. Mirror each source symbol's category/subcategory hierarchy under its own style's Plurals and tenses root; plurals and tenses share that tree. Base symbols remain untouched in their current folders. This is not one combined folder shared by all styles. Structure and layout methods are confirmed; eligible symbol selection/mapping remains to settle. No generation has started. The reference folder establishes structure, not automatic approval of every existing Fluent inflection.


### Task 10 — Mulberry SVG handling and reuse check — 2026-11-19

Paul reminded us that Mulberry requires SVG processing and may already have derivatives. Use SVG sources directly and preserve vector output; do not rasterise first or automatically include native Mulberry SVG material in Task 12's raster-style Q80 pass.

Read-only check: Library/Mulberry contains 155 SVGs; People/Mulberry contains 3,536 SVGs. Neither has a Plurals and tenses tree. The older new mulberry-like chatgpt folder (233 SVGs, 3,303 WebPs) likewise has no derivative tree; its single 04 Grammar/Tenses/doing-now-ing symbol is not a completed tense rollout. Desktop/Emoji/SymbolSets/Mulberry and Symboliser/SymbolSets/Mulberry each contain 3,436 native SVGs and no Plurals and tenses tree. This does not prove every individually named inflection is absent; eligibility/reuse inventory must check those before generating anything. Do not confuse native Mulberry with generated Mulberry-like sources. Library/Mulberry is only a partial publication: do not scope Task 10 to its 155 files alone. Record source-version mapping and prefer corrected Library versions where present. No generation or image modification performed.


### Task 10 — execution authorised; Fluent plural vocabulary confirmed — 2026-11-19

Paul said “so let's do 10 now”, then directed reuse of the Fluent plural vocabulary. Use the existing 11,719 Fluent plural files and exact spellings with the saved singular-to-plural mapping; no new noun classification. All 11,719 saved mappings were checked against real Fluent outputs. Use each current style's own matching source artwork, the approved smart_shrink layout, and the confirmed per-style Plurals and tenses tree. Initial exact-path inventory across all 20 Library styles (Mulberry SVG sources supplemented read-only from People) has 53,894 candidate derivatives, including tenses; these are not completed outputs. Ambiguities and exclusions are recorded, not silently converted. The reference tense list contains clearly invalid older forms; exclude non-verbs/already-inflected forms rather than propagate them. Existing source files remain untouched. One Python worker. Production records: ~/Documents/Development/PWAs/To do next/PiCom Symbols/task10_production_20261119. Q80 remains deferred.


### Task 10 — first validation batch published; Fluent-matched rollout active — 2026-11-19

All 400 selected jobs were checked across all 20 styles. 342 outputs passed automated checks and visual before/after inspection on 40 contact sheets, and were published into the new per-style Plurals and tenses folders. 57 adjective-clean forms were withheld and one wash-hair future clock collision was held. Temporary sample images and rejected staged files were deleted. Review page loads the actual Library sources/results directly: ~/Documents/Development/PWAs/To do next/PiCom Symbols/task10_production_20261119/index.html.

Plural rollout is active with one image worker using the existing Fluent vocabulary, exact spellings and pinned smart_shrink engine. Each production output is independently rendered and checked for subject preservation, missing annotations, overlap, clipping, external dependencies and source/output hashes. Visual review is explicitly recorded for the validation sample; do not claim every production output has been viewed. Source files are read-only; publication is no-clobber, with immediate staging removal. Q80 stays deferred.

Nine Sommi/Sommi clothed source ambiguities were resolved by inspecting complete own-style figure alternatives, adding 19 derivatives. The current queue has 53,913 rows: 37,683 plurals and 16,230 tense forms. Additional noun-sense bellow/scrape sources were withheld from tense generation. Explicit corrections to 265 unpublished tense filenames address errors in the saved conjugator (including debugging, panicking, scrubbing and coordinated verbs); pinned image-layout scripts remain unchanged. All corrections/exclusions are recorded.

Continuation is prepared: finish_rollout.py waits for the active worker lock, then drains the remaining authorised plural/tense queue with the same one-worker limit. Queue, progress, events and checkpoint are durable in task10_production_20261119. This is in progress, NOT Task 10 completion. Final held-case review, source/output reconciliation, and dedicated auxiliary/modal reuse reconciliation remain outstanding. Existing auxiliary/modal files were inventoried to avoid blindly duplicating or double-annotating them.


### Task 11 — agree names now for automatic execution after Task 10 — 2026-11-19

Paul requested agreeing Task 11 now so it can run automatically after Task 10 finishes. The earlier saved plan explicitly left the Basic 1/Basic 2 mapping undecided; no source-style mapping has yet been supplied. Asked which current styles become Basic 1 and Basic 2 and whether any other names change. All unspecified names stay unchanged. Conditional instruction saved in ~/Documents/Development/PWAs/To do next/PiCom Symbols/task11_preparation_20261119/decision.json. No renaming has started and no automatic rename runner is armed before the naming decision. Once names are agreed, prepare verified in-place Library renames plus affected active records/links, preserve People originals and avoid copies. Execute only after Task 10 is fully checked and complete and all Task 10 writers are finished, not merely when its main queue reaches zero. Task 10 continues unchanged.


### Task 11 — editable all-style naming sheet ready; rename after current run — 2026-11-19

Paul requested a sample sheet with every current style labelled and editable naming fields, then explicitly confirmed renaming after the current run to avoid confusion. Created and browser-verified all 20 cards in task11_preparation_20261119. The 19 People styles use their own holding sample; Sommi companion objects uses its own rice steamer. Samples are served directly from existing files, with no image copies. Local page URL is recorded in server_state.json (currently http://127.0.0.1:62043/). Drafts and confirmed choices persist in naming_choices.json; the Save names for Task 11 button validates all names and updates decision.json. This sheet never renames folders. A later edit invalidates the previous confirmation until saved again. Read the latest confirmed choices rather than inferring Basic 1/Basic 2 assignments. Apply the agreed names only after Task 10 and final checks are complete and all image writers have finished. Task 10 continues unchanged.


### Task 11 — retain both outlined collections — 2026-11-19

After reviewing 12 matched People pairs and 16 matched non-People pairs, Paul decided: “I think we should keep both sets.” Retain Flat outlined and Classic flat TV cartoon as separate complete sets. Do not merge them or delete either as redundant. Continue Task 10 for both. This is a retention decision, not a naming change; any final names selected through the naming sheet must preserve two distinct folders. Durable decision: ~/Documents/Development/PWAs/To do next/PiCom Symbols/task11_preparation_20261119/style_comparison/retention_decision.json.


### Tasks 11 → 12 → final licence pass authorised; exact names confirmed — 2026-11-19

Paul saved all 20 names in the naming sheet and instructed applying them after Task 10 finishes, then explicitly authorised Task 12 and the final copyright/licence pass one after another, with no rush. No additional routine approval is needed for this sequence. Task 10 must first finish its final checks and held-case/auxiliary reconciliation; do not rename while its writer is active.

Final name changes: 3D animated cartoon → 3D cartoon; Basic → Basic 1; Classic flat TV cartoon → Basic 2; Clay plasticine → Clay; Flat outlined → Basic 3; Friendly aliens → Alien; **Mulberry → Basic SVG**; Simple anime → Anime; Soccer player → Soccer; Sommi companion objects → Sommi objects. Other ten names remain unchanged. The later explicit chat correction **Basic SVG** supersedes the initial saved Mulberry → Basic selection. Basic SVG retains SVGs and is excluded from the raster-style Task 12 conversion. Both outlined sets remain separate.

After verified Task 10 completion: Task 11 renames Library folders in place and updates current indexes/links while preserving frozen historical provenance; People originals/folders remain untouched. Then Task 12 converts intended new compositions once to WebP Q80, skipping completed conversions, keeping no duplicate export/backup trees. Then Task 5 embeds and verifies the agreed final licence metadata, respecting existing third-party exclusions. Durable sequence: task11_preparation_20261119/authorised_sequence.json; confirmed choices: naming_choices.json; exact rename order/plan: rename_plan.json. These later stages are authorised and waiting; they have not been executed.


### Task 11 — deferred rename runner armed after isolated verification — 2026-11-19

rename_after_task10.py --wait is running idle, using the confirmed mapping including Mulberry → Basic SVG. It requires task10_production_20261119/completion.json with task10_complete, checks_complete, held_cases_disposed and auxiliary_modal_reconciled all true, exact final queue_counts, no pending/review/checked/processing rows, and exclusive access to the Task 10 worker lock. Only write that completion certificate after the checks are actually finished. Queue exhaustion alone does not trigger renaming. The completion-gate contract is recorded in Task 10 checkpoint.json.

Isolated tests passed for all ten renames, all twenty retained styles, plain/URI paths with spaces, original-content preservation, unchanged People paths, frozen manifest preservation, current registry/queue/review-link updates, and idempotent rerun. Renaming is in place, with no image copies. Original style CSVs and delivery JSONL remain frozen historical provenance; current-style-names.json maps original IDs to new Library folders. The live Task 10 queue preserves its original paths in a migration table before updating. Runner state/logs live in task11_preparation_20261119/rename_wait.json, rename_runner.json and rename.log. Task 12 and final Task 5 are authorised next; their execution must follow completed renaming and appropriate checks.


### Tasks 10 and 11 complete; continuous Tasks 12 → 5 delivery started — 2026-11-19

Task 10 completed at 19:58 Melbourne time: 53,826 queued plural/tense outputs plus 304 auxiliary/modal deliveries, 54,130 total. All 43,002 distinct queue source hashes and all published output hashes reconciled with no mismatch. 87 non-verb source candidates explicitly excluded (adjective clean, photographic bellow, injury scrape). All 306 clock repairs were visually checked and published; 17 unchanged saved schematic auxiliary masters were reviewed. Existing style modals reused, including native People/Mulberry reuse; no new stick figures introduced into the object-only style. Production review evidence is honestly scoped: 342 initial validation images plus 306 repairs and schematic masters were visually reviewed; remaining bulk outputs received independent render/geometry/integrity checks. Temporary review/staging images removed. Completion certificate: task10_production_20261119/completion.json.

Task 11 ran automatically when that certificate passed, completing at 19:58:39. All ten agreed directory renames completed; all twenty style directory identities verified; People originals/folders untouched. Mulberry is now Basic SVG. Both outlined collections remain separate as Basic 2 and Basic 3. Frozen historical manifests retained; current registry at Library/_manifest/current-style-names.json. Live Task 10 queue and current review paths migrated. Evidence: task11_preparation_20261119/execution.json.

Task 12 → final Task 5 now has an actual continuous local batch implementation, final_delivery_20261119/pipeline.py, rather than relying on another chat turn for its handoff. Started detached as PID 9315 at low priority, one image worker. It inventories intended Library SVG compositions, preserves Basic SVG as vector, converts raster-style compositions once to Q80 method 6 with lossless alpha, uses no-clobber publication and per-file restart records, removes the superseded composition SVG only after verified WebP publication, and leaves existing base WebPs and People originals unchanged. Task 10 source dimensions are retained; other compositions match standard Library 512×512 dimensions. No image backup/export tree.

After Task 12 output reconciliation, the SAME process automatically starts final Task 5. It adds the agreed “© Sensory App House Ltd, CC BY-NC 4.0” and licence URL to applicable final Library assets. WebP metadata uses webpmux without image recoding, verifies both compressed image payload and decoded pixel identity, and reads back XMP/EXIF. SVG metadata retains drawing content and verifies identical renders. Existing third-party attributions and the saved sign-language-chart/flag exclusions remain excluded and explicitly reported. No People originals are stamped. Final current delivery records are separate from frozen historical provenance.

Verification: isolated real stage-12-to-stage-5 execution and completed-job rerun passed; no-clobber and interrupted-publication recovery passed; metadata idempotence, exact alpha, decoded pixels and exiftool readback passed. 23 before/after Q80 examples covering all 19 raster styles, books/hands/arrows/stars/clocks visually accepted; temporary sheets deleted. Evidence: final_delivery_20261119/verification.json, handoff_verification.json, visual_acceptance.json. Monitor progress.json, delivery.sqlite and run.log. completion.json is written only after actual completion; the running stage is not yet complete. An exceptional failed file is retained and recorded; the licensing handoff requires conversion reconciliation. State is resumable; ordinary stage transitions require no further user prompt.


### Task 12 parallel encoding authorised and started — 2026-11-20

Paul requested parallel conversion across multiple cores, as in the earlier Q80 pass. The Mac has 10 cores; four low-priority local encoders are now authorised for Task 12. This supersedes the one-encoder limit for this compression stage only. One coordinator exclusively publishes files and updates SQLite; encoding workers only read their unique source and return validated bytes. At most four conversions are in flight. The final copyright/licence stage remains serial and starts automatically after full Q80 reconciliation. No change to Q80 quality 80/method 6, exact lossless alpha, dimensions, distortion/source-hash checks, no-clobber publication, People preservation, Basic SVG preservation or temporary-file removal.

Verified twelve scratch outputs byte-identical between serial and parallel conversion, recovery after interrupted publication, unchanged completed outputs on rerun, and preservation/reporting of a deliberate invalid SVG with completion correctly blocked. That failure test exposed and fixed an existing SQL quoting bug in error-status recording; no live failures had occurred. Evidence: final_delivery_20261119/parallel_verification.json.

Serial PID 9315 was replaced using the existing durable checkpoint, with 4,934 complete and 50,565 pending; no completed file was re-encoded. New detached PID 30854 runs PICOM_Q80_WORKERS=4 at nice 10. The singleton writer locks remain in force. Worker state: final_delivery_20261119/runner.json, progress.json, parallel_transition.json and run.log. This is CPU batch parallelism, not additional model/review sessions. The conversion batch itself uses no model credits. All agreed subsequent stages remain in the same continuous process.


### Explicit user pause — 2026-11-20, 05:30 Melbourne

Paul requested pausing Q80 and resuming later. The conversion coordinator and encoder process group were stopped. Durable checkpoint: 28,816 complete, 26,683 pending, no interrupted publications; SQLite integrity check passed. All later stages are paused too. This overrides prior keep-running instructions until Paul explicitly requests resume. final_delivery_20261119/pause.json records paused=true; pipeline startup now honours that guard. To resume after explicit authorisation, clear that guard and restart the existing pipeline with PICOM_Q80_WORKERS=4, low priority, keeping the same journal/checks and automatic final licence handoff. Do not recreate the queue or recompress completed files.


### Q80 resumed by explicit user instruction — 2026-11-20T06:49:49.826779+11:00

Paul requested resuming Q80 with four workers, proceeding through the agreed tasks automatically, skipping already completed files and tidying as work proceeds. This revokes the prior pause. Resume checkpoint: 28,816 complete (excluded from the encoding queue), 26,683 pending; no recorded failures or temporary review files. Detached coordinator PID 12663 runs at nice 10 with four encoders, one publisher, unchanged checks and per-file temporary/superseded SVG cleanup. Basic SVG remains native; People originals remain untouched. The same process automatically proceeds to final copyright/licence after Q80 verification. Evidence: final_delivery_20261119/resume_checkpoint.json, pause.json (paused=false), runner.json and live progress.json.


### Q80 accidental-stop recovery — 2026-11-20T07:34:49.961915+11:00

At Paul’s request to resume if accidentally stopped, verified the prior PID was absent and worker lock was free. No recorded conversion errors or exception event explained the interruption. SQLite integrity passed; checkpoint was 32,184 complete and 23,315 pending. Restarted the unchanged four-encoder/one-publisher pipeline at nice 10, PID 60626, skipping every completed row. Per-file tidying and automatic final copyright/licence handoff remain active. Do not infer a specific cause for the process exit from the available evidence.


### Task 12 complete; final copyright/licence pass automatically started — 2026-11-20

All 55,499 intended new raster-style compositions are converted to verified WebP Q80. Final source/output reconciliation passed at 2026-11-20T12:19:28.315776+11:00. Composition size changed from 4,482,875,179 to 1,030,575,786 bytes, saving 3,452,299,393 bytes (3.45 GB decimal). Basic SVG remains native vector and People originals remain untouched. Superseded composition SVGs and review images were removed as work completed. Evidence: final_delivery_20261119/task12_completion.json.

The SAME process automatically entered Task 5 at 12:19, without another approval or restart. It inventories 289,820 Library files: 289,796 applicable files and 24 excluded third-party sign-language-chart files. One Python worker, explicitly confirmed by Paul, performs metadata-only stamping and pixel/hash checks. Actual completed output metadata was independently read back with exiftool and contains the agreed owner and CC BY-NC 4.0 licence. Task 5 is running, NOT complete; see progress.json and delivery.sqlite. Continue automatically, keep People untouched, retain exclusions and remove temporary metadata files per file.


### Final copyright/licence pass complete and verified — 2026-11-20, 14:07 Melbourne

The authorised sequence Tasks 10 → 11 → 12 → final Task 5 is COMPLETE for the current Library. Final copyright/licence stamping completed for all 289,796 applicable files. The 24 recorded third-party sign-language-chart exclusions remain unchanged. No pending, failed or error rows remain. Every stamped file passed appearance/pixel checks during processing and the final all-file output-hash reconciliation passed at 14:07:38. The required wording is “© Sensory App House Ltd, CC BY-NC 4.0”, with https://creativecommons.org/licenses/by-nc/4.0/. WebPs were stamped without recompression; SVG drawing content was preserved. People originals remained untouched.

Final delivery index: Library/_manifest/final-delivery-20261119.jsonl, verified 289,820 records (289,796 complete + 24 exclusions). Completion certificate: final_delivery_20261119/completion.json; exclusion paths/reasons: licence_exclusions.json; final audit: final_audit.json. The background worker has exited and its lock is free. Temporary metadata/review files are gone and the empty temporary directory was removed. Saved scripts, decisions, construction records and SQLite audit are retained; no duplicate image export/backup tree was created.

Q80 was already complete and verified: 55,499 new raster-style compositions, 3,452,299,393 bytes saved. Basic SVG stays vector. All agreed names are in place. This closes this authorised execution sequence; it does not silently resolve or erase unrelated historical backlog items elsewhere in this master plan.
