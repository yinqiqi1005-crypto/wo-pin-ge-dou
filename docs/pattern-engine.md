# Pattern engine

The pattern engine is a deterministic Python service. It has no dependency on Django,
the database, page rendering, membership rules, or an AI provider.

## Processing order

1. Read the image and apply EXIF orientation.
2. Convert the source to RGBA.
3. Reject images whose shortest side is below the configured minimum.
4. Create a centered square crop.
5. Resize to a supported bead grid.
6. Quantize the RGB image to the selected color limit.
7. Match quantized colors to the active bead palette in Lab color space.
8. Restore transparent pixels as empty cells.
9. Clean only fully isolated cells that have a clear neighboring majority.
10. Validate palette membership, color limits, and material-count consistency.

## Source of truth

`PatternGrid` is the only source of truth for previews and material counts. Rendered
images are derived artifacts and must never be used to recalculate the pattern.

## Supported v1 defaults

- Grid sizes: 30×30, 50×50, 70×70.
- Color limits: 12, 24, 36.
- Palette: `WPD-GENERIC-V1`, containing 36 internal product colors.

All defaults will later be exposed through the product configuration layer.

