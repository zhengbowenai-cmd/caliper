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

Editorial minimalism — feels like an academic journal or an instrument
manual more than a tech-marketing splash.

- **Palette (light):** `#F7F1E3` warm cream bg · `#1A1A1A` primary
  text · `#A84E2E` terracotta accent · `#8A857B` quiet gray
- **Palette (dark):**  `#131210` warm black bg · `#F0EBE0` ivory text
  · `#D4825E` brighter terracotta accent · `#6B6760` quiet gray
- **Typography:** Inter (headline, tight kerning) + JetBrains Mono
  (instrument readouts) + PingFang / Noto Serif SC (Chinese tagline)
- **Visual language:** faint graph-paper grid, small technical corner
  marks like those on engineering drawings, instrument-signature
  numbers (`± 0.001`, `bca95 · n=40`, `v0.1.0`), left-aligned wordmark
  with a short terracotta interval rule underneath — that rule is the
  whole logo motif: "a precise measurement between two tick marks."
- **What we deliberately avoided:** literal caliper drawing, rainbow
  pill tags, steel-grey engineering clipart, anything that tries too
  hard.
