# Editable paper masters

These 898 self-contained tagged SVG masters contain authored swell-paper, Index embossed and ViewPlus layers. There are 275 unchanged copies, 601 page-fit remakes and 22 original-size exceptions. Consult ../catalogue.json before treating a master as page-fit.

From the collection folder, export a new destination with:

```sh
python3 -B tools/tactile_master.py masters/category/name.svg --profile swell-paper-v1 --output /new/path/name.svg
```

Use the corresponding Index or ViewPlus profile ID for the other outputs. The exporter does not resize artwork or calculate new dot placement. Full reproduction: `python3 -B tools/regenerate-pagefit.py /new/output/folder`.

Keep source geometry editable, stable concept/semantic-region IDs and copyright metadata. Alter a new version, re-author physical detail for a new size, inspect each profile, then update catalogue hashes. Read ../PAGEFIT-README.md and ../instructions/VIEWPLUS-SHADING.txt. Physical testing remains pending.
