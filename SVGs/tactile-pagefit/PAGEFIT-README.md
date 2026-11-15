# Page-fit and native-display tactile collection

The requested collection is complete, with documented exceptions. Originals in the separate `tactile/` collection are unchanged.

- **898 meanings assessed; 0 pending.**
- **876 paper meanings fit:** 275 unchanged copies and 601 regenerated at no more than 170 × 200 mm.
- **22 paper exceptions** retain their original-size masters and exports byte-for-byte; they are not counted as page-fit successes.
- **Monarch:** 861 native exports (61 good digital designs, 800 simplified); 37 unsuitable.
- **Dot Pad:** 856 native exports (58 good digital designs, 798 simplified); 42 unsuitable.
- **4,411 SVG exports** in this collection, plus editable masters. The [separate display adaptations](../tactile-display-adaptations/README.md) cover all 42 meanings that were unsuitable on one or both single-frame grids, with 281 linked teaching frames and 546 device exports.

Open [index.html](index.html) for the keyboard-accessible gallery with closeable symbol popups, search and paging. See the [completion report](PAGEFIT-REPORT.html) for all exceptions and 20 substantially changed meanings to inspect first. The [complete simplification register](PAGEFIT-SIMPLIFICATIONS.html) explains all 601 paper remakes. The [display adaptation review](DISPLAY-ADAPTATION-REVIEW.html) records the design requirements that informed the separate adaptations. The [adaptation gallery](../tactile-display-adaptations/index.html) has the finished frames and their teaching keys.

## Purpose and interpretation

This experimental educational library explores tactile curriculum materials. It is not BANA certification, physical print/display approval or proof of learner recognition. Read the [teaching keys](PAGEFIT-TEACHING-KEYS.html), [known limitations](KNOWN-LIMITATIONS.html) and per-meaning catalogue notes before teaching from an image. Historical source dimensions and screen observations do not automatically apply to remade geometry. Actual calibration, touch testing and learner evaluation remain pending.

The page remakes retain physical stroke sizes, place fresh Index dots, simplify/rearrange meaningful parts, and explicitly document lost or changed representative detail. No new blanket colour-to-height mapping is invented. Paper exceptions must not be silently auto-shrunk. Printing titles, Braille keys and other page furniture requires the host application to manage the space outside the drawing.

## Folder layout

- `masters/`: 898 editable paper masters, each with the three authored paper profiles.
- `display-masters/`: shared masters for supplied native display profiles; unsuitable profiles have no export.
- `exports/`: swell-paper-v1, index-embossed-v1, viewplus-variable-height-v1, monarch-display-v1, dotpad-display-v1.
- `profiles/`: the five profile definitions and their nominal assumptions.
- `catalogue.json`: stable IDs, exact master/export hashes, fit outcomes, reasons, checks and recorded observations.
- `companions/` and `evidence/teaching-keys/`: retained necessary teaching material.
- `tools/`: self-contained Python exporters and verification/regeneration script.
- `instructions/`: ViewPlus guidance and semantic-region contract.

Catalogue path strings retain the `tactile-pagefit/` prefix for compatibility with the parent collection. The included regeneration tool resolves that prefix against this folder, so the standalone collection can be moved or renamed.

## Display format

Monarch is 96 × 40 pins; Dot Pad is 60 × 40 graphics pins, excluding its separate Braille line. Each raised pin is one black unit rectangle. The `data-pins` attribute has 40 top-to-bottom rows of 0/1 separated by spaces, with columns left-to-right; 1 means raised. The layers are separately authored and use a single binary height, not ViewPlus grey levels.

Monarch’s nominal pitch is approximately 25.4/9.7 mm from the source specification, not device calibration. Dot Pad physical pitch is unconfirmed; the design assumes equal unit pin spacing and makes no millimetre claim. See the profile files. Do not treat SVG screen dimensions as a printer command for a refreshable display.

## Reproduce all current exports

Python 3.9 or later; standard library only. From this folder:

```sh
python3 -B tools/regenerate-pagefit.py /absolute/path/to/new-output
```

The destination must not exist and must be outside this collection. The script checks catalogue master/export hashes, regenerates all supplied profiles and verifies byte-identical output. Use `--profile dotpad-display-v1` (or another exact profile ID) to select one profile. It does not invent unsuitable designs or rescale artwork. Final reproduction results are in [COLLECTION-VERIFICATION.json](COLLECTION-VERIFICATION.json).

For one new export:

```sh
python3 -B tools/tactile_master.py masters/category/name.svg --profile swell-paper-v1 --output /new/path/name.svg
```

Use the appropriate `display-masters/` path and native profile ID for a display export. This command overwrites its output, so choose a new path.

## Make further symbols or adaptations

Choose a clear teaching purpose, suitable reference and stable ID. Work in a new master/version. Preserve `data-master-schema="tactile-shared-v1"`, unique semantic region IDs, local geometry references, and one `data-output-profile` layer with its `data-export-root` per authored profile. The exporter selects authored geometry; it does not calculate readable simplifications or pin placement. Follow `instructions/svg-regions.json` and `instructions/VIEWPLUS-SHADING.txt`.

For paper, check physical dimensions, fixed strokes, dot diameter/cadence, meaningful contacts, unrelated clearances and retained material/height roles. For native displays, author discrete pins with closed shapes closed, openings open, one-pin lines, blank separation and at most three distinguishable textures. Inspect each whole profile separately. Updated geometry requires a fresh applicable assessment; never inherit perception claims from a previous image. Update hashes, fit reasons, teaching keys and limitations together.

A multipart display adaptation must have a distinct adaptation/frame identity linked to its parent meaning. Supply external accessible navigation, frame order, orientation and scale information. Preserve the required counts and connections across the sequence. Identify differently scaled details in the teaching keys. The completed frames have been digitally inspected. Physical device and learner testing remain pending. See the [collection-wide authoring guide](../instructions/HOW-TO-MAKE-MORE.txt) for the workflow.

## Copyright

Every SVG retains non-visible metadata: Copyright Sensory App House Ltd, CC BY-NC 4.0. Artwork licence: https://creativecommons.org/licenses/by-nc/4.0/ . This does not grant blanket rights to external source material. No visible text, Braille, logos or raster content is added to the symbol artwork.
