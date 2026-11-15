# Tactile symbols: location and important features

## Where to find them

The working collection is stored at:

`/Users/paulblenkhorn/Downloads/picom-ai-sommi-action-symbols/SVGs/tactile/`

Open [index.html](index.html) to browse the symbols. The index has search and pagination; each symbol can be opened in a popup with a Close button. Its controls support keyboard use, including Tab, Shift+Tab, Enter/Space and Escape to close the popup and return focus.

The complete downloadable package is:

`/Users/paulblenkhorn/Documents/Codex/2026-10-22/continue-the-planning-discussion-for-a/symbols-current.zip`

Extract the ZIP before opening the index. The tactile collection is under `Symbols/tactile/`. Keep the extracted folder structure intact so that previews, masters and supporting documents remain linked. The package also contains the separate 1,000-meaning visual collection.

## What is included

There are **898 retained tactile meanings**, with **898 editable SVG masters** and **2,694 profile exports**: one export per meaning for each of three production media. The retained collection includes the simplified sunflower.

| Location within this folder | Contents |
| --- | --- |
| [masters/](masters/) | One tagged, editable SVG master per meaning, organised by subject/category. |
| [exports/swell-paper-v1/](exports/swell-paper-v1/) | 898 swell-paper variants. |
| [exports/index-embossed-v1/](exports/index-embossed-v1/) | 898 Index embossing variants. |
| [exports/viewplus-variable-height-v1/](exports/viewplus-variable-height-v1/) | 898 ViewPlus variants. |
| [catalogue.json](catalogue.json) | Stable meaning IDs, labels, categories, review basis, dimensions, file mappings and SHA256 hashes. |
| [profiles/](profiles/) | Medium-specific design assumptions, settings still requiring calibration and testing notes. |
| [companions/](companions/) and [evidence/teaching-keys/](evidence/teaching-keys/) | Available external teaching keys and supporting explanations. Use the catalogue and per-symbol links to find the relevant material. |

## Important design features

- **Native vector artwork:** the SVG geometry is editable and can be regenerated without the old production folders. Resizing remains possible, but changes physical line widths, dot sizes and spacing.
- **Stable identities and semantic tags:** `aac.*` and `edu.*` IDs distinguish meanings. Tagged regions identify relevant parts of the drawing and support further editing.
- **A shared master with three authored profiles:** compatible geometry is shared, with explicit differences for each medium. The exporter selects the authored profile; it does not automatically invent tactile design or convert an arbitrary picture into a usable tactile graphic.
- **Uncluttered artwork:** symbols contain no visible words or Braille, raster pictures, logos or decorative shadows. Titles, labels, orientation instructions and teaching keys belong alongside the graphic.
- **Educational models:** subjects include mathematics, science, anatomy, geography, objects and everyday concepts. These are simplified representations for selected teaching tasks, not claims that every diagram is required by a school curriculum.

## The three versions

**Swell paper** uses a black footprint on a white background. The intended raised areas are expressed by the black artwork; there is no assumed grey-to-height mapping. Paper, printer and heating settings require practical testing.

**Index** uses explicitly drawn dots for lines and areas, with a single-height design baseline. Meaning is not dependent on grey levels or presumed height differences. Dot patterns still need checking through the actual device's import and embossing route.

**ViewPlus** uses actual fill and stroke shades to express intended area and line distinctions. Grey areas can distinguish material, land or a selected region, while darker boundaries and features remain prominent and deliberate openings stay white. Semantic height-role metadata records intent; it does not itself instruct the printer to produce a calibrated height.

The ViewPlus shading update revised **163 symbols**, including three initial pilots; **735 kept their existing treatment**. Some unchanged variants already had grey areas. Others deliberately remain line diagrams because filling them could change a scientific convention, close an opening or obscure a relationship. All 163 changed variants received individual whole-image screen inspection. Assessment of all 898 meanings also used teaching subjects and SVG structure; this was not a fresh visual inspection of every unchanged symbol.

The shading update did not alter Index or swell-paper artwork. A subsequent copyright update added non-visible metadata to every profile, so file hashes changed without changing the drawings. See [ViewPlus shading guidance](VIEWPLUS-SHADING.html) for details. Preserve grayscale when preparing ViewPlus output; outline-only conversion would discard the intended area fills. The ViewPlus files do not imitate the Index dot grid: the selected ViewPlus print route determines its output dots.

## Status and limitations

Generation and packaging are complete. The collection remains an **experimental educational resource**. Earlier production reviews and human retention decisions are recorded in the catalogue; they do not establish physical readability. Human review of the later ViewPlus shading revisions remains pending.

Actual device calibration, supported page fit, tactile proofreading and learner evaluation remain pending. Nominal canvases vary; the profile template is not proof that every symbol fits a particular sheet or machine. Inspect the SVG dimensions before printing. Automatic fit-to-page changes the dimensions of lines, dots and clearances.

Use an appropriate teaching explanation and test representative output by touch with the intended medium and learner needs in mind. Where no suitable external key exists, one must still be prepared. The collection is not BANA-certified.

Read the [overview and group purposes](OVERVIEW.html) and [known limitations](KNOWN-LIMITATIONS.html). The overview explains the collection's origins, including APH's Tactile Graphics Image Library as a topic guide through BTactile; this does not imply endorsement or that every delivered graphic reproduces an APH source.

## Copyright and making more

Every SVG master and export includes this non-visible notice:

> Copyright Sensory App House Ltd, CC BY-NC 4.0.

See [LICENSE.txt](../LICENSE.txt). The notice does not appear in printed or embossed artwork.

To reproduce all tactile exports, run this from the collection root—the folder containing `tactile`, `visual`, `tools` and `instructions`:

```sh
python3 -B tools/regenerate.py tactile /path/to/new-tactile-output
```

The destination must not already exist. The tool checks the master hashes, regenerates all 2,694 exports and verifies exact output hashes against the catalogue. Edit masters rather than treating exported files as separate sources.

For new symbols or revisions, follow [HOW-TO-MAKE-MORE.txt](../instructions/HOW-TO-MAKE-MORE.txt), [ViewPlus printing guidance](../instructions/VIEWPLUS-SHADING.txt) and the [semantic-region guidance](../instructions/svg-regions.json). Retain stable IDs and the copyright metadata, update catalogue hashes, and evaluate any changed artwork on its intended medium.
