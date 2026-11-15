# Editable native pin-grid masters

These 861 self-contained masters contain the supplied Monarch 96 × 40 and/or Dot Pad 60 × 40 profile layers. Some meanings are unsuitable on one or both devices; never assume a missing layer can be generated automatically. Per-device decisions are in ../catalogue.json.

From the collection folder:

```sh
python3 -B tools/tactile_master.py display-masters/category/name.svg --profile monarch-display-v1 --output /new/path/name.svg
```

Choose dotpad-display-v1 for an authored Dot Pad layer. Each export contains one black unit rectangle per raised pin and a matching data-pins grid. These are binary pin designs, not scaled paper or grey-height artwork.

Edit the discrete geometry and the layer’s export-root grid together, keeping semantic regions, stable IDs and copyright metadata. Recheck grid-to-rectangle identity and inspect the whole frame. Update hashes and per-device limitations. The [display adaptation review](../DISPLAY-ADAPTATION-REVIEW.html) records the requirements for the designs that needed alternatives. The finished alternatives, editable masters and teaching keys are in the [separate display adaptation collection](../../tactile-display-adaptations/README.md). Physical device and learner testing remain pending.
