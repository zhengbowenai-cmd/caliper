# Brand assets

| File | Use |
|------|-----|
| `banner.svg`       | Hero banner at top of README (light background) |
| `banner-dark.svg`  | Same banner, dark-mode variant — picked via `<picture>` in the main README |
| `logo.svg`         | 512×512 square logomark for social cards, favicon, GitHub app icons |

## Regenerating raster versions

SVG renders natively on GitHub. If you need PNG for tweets, docs servers
without SVG support, or favicon.ico, convert with either:

```bash
# 1. inkscape (best rendering quality)
inkscape assets/banner.svg -o assets/banner.png -w 1200

# 2. rsvg-convert (fast, part of librsvg)
rsvg-convert -w 1200 assets/banner.svg -o assets/banner.png

# 3. Python via cairosvg
pip install cairosvg
python -c "import cairosvg; cairosvg.svg2png(url='assets/banner.svg', write_to='assets/banner.png', output_width=1200)"
```

## Design system

- **Palette (light):** `#FBFAF6` bg, `#1E2A32` primary, `#C4442D` accent, `#E9D48A` readout
- **Palette (dark):** `#0E1619` bg, `#F0EDE5` primary, `#E07856` accent
- **Typography:** System sans-serif stack (Inter / -apple-system / Segoe UI),
  monospace stack (JetBrains Mono / Menlo / Consolas)
- **Metaphor:** precision caliper measuring a `SKILL.md` token;
  red = moving jaw = the candidate being measured against the fixed
  reference.
