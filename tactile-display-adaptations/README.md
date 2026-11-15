# Separate tactile display adaptations

42 meanings, 281 linked teaching frames, 546 SVG exports. All requested adaptations have been authored and digitally inspected; physical device and learner evaluation remains pending.

Open **index.html** for a searchable, keyboard-operated viewer. Each meaning has an adaptation note; each frame has an external teaching key. Read these keys with the images. These are often sequences, registered layers or count models, not a single reduced copy of the original picture.

## Contents

- `exports/monarch-display-v1/`: 265 frames for 37 meanings, on a 96 × 40 grid.
- `exports/dotpad-display-v1/`: 281 frames for all 42 meanings, on a 60 × 40 grid.
- `masters/`: 281 editable tagged SVG masters, one per frame. The 37 shared-profile meanings include both profiles in the same frame master; five meanings needed adaptation only for Dot Pad.
- `recipes/`: editable semantic pin-coordinate sets, teaching keys, numerical checks and intentional-contact descriptions.
- `catalogue.json`: stable parent and frame IDs, keys, observations, paths, dimensions and SHA256 bindings.
- `source-bindings.json`: original and page-fit source/master hashes; original sources are not duplicated here or needed for export reproduction.
- `profiles/`: draft device assumptions, grid dimensions, binary pin encoding and pending calibration.
- `tools/regenerate.py`: reproduce and verify exports from the self-contained masters.
- `KNOWN-LIMITATIONS.md`: interpretation and testing limits.

## Using the SVGs

The SVG viewBox is the native pin grid. Each raised pin is one black unit rectangle at integer column/row coordinates. `data-pins` holds 40 top-to-bottom rows separated by spaces, with 1 raised and 0 lowered. No text, Braille, grey levels or extra drawing background is included. IDs use the original meaning ID plus `.display-adaptation.NN`; the parent ID remains in metadata.

Most shared frames use a 60 × 40 design centred on Monarch's wider grid by an 18-column offset. This deliberately retains identical geometry, counts and proportions across the two displays rather than stretching it horizontally. Widths are grid coordinates, not paper millimetres. Dot Pad pitch is unconfirmed; the profile records that limitation.

## Reproduce or make more

Run from this folder with Python 3:

```sh
python3 -B tools/regenerate.py --verify
python3 -B tools/regenerate.py --output /absolute/path/to/a/new/export-folder
```

Verification reads the catalogue, checks master/export/recipe hashes, reproduces each export in memory and checks its bytes and native pin encoding. A new output folder must not exist. The exporter needs only the masters; it does not fetch online sources or inspect old production queues. Do not resize these SVGs to invent a different pin grid.

To adapt a frame, edit a **copy** of its master, keeping semantic groups and native unit rectangles. Every profile layer's `data-export-root` contains its `data-pins`; update this encoding whenever pins change. Maintain unique IDs, no duplicate raised pins, required openings and intended contacts. Update the corresponding recipe/key and version the changed frame and catalogue hashes. Receive and inspect each changed whole exported profile before recording a new observation. Exact unchanged rendered canvases may reuse their recorded digital observation. Geometry/meaning changes require a new check; a successful export alone is not review.

For new meanings, start from the intended teaching objective and source definition. Split into keyed frames when necessary; preserve counts, connectivity and orientation, and explicitly explain changes of scale or representation. Keep at least one empty pin between unrelated parts, use clear intentional junctions, and check the result on the actual device with learners. Follow `instructions/svg-regions.json` for semantic tags. The recipes retain role-labelled pin coordinates as an editable design reference; masters are the authoritative reproducible export input.

The original `tactile/` and `tactile-pagefit/` collections are separate and unchanged. This collection supplements their unsuitable display entries; it does not overwrite their original fit classifications or turn the new adaptations into physically validated originals.

Copyright Sensory App House Ltd, CC BY-NC 4.0. The same non-visible notice is included in every SVG.
