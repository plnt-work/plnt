# plnt design rules

`tokens.css` here is the only place colours, radii and type sizes are defined.
The site (`site/src/styles/tokens.css`) and the console (`console/src/tokens.css`)
carry byte-identical copies; CI fails if they drift. Edit this file, then copy it.

## Colour

- **Light theme only.** There is no dark variant and no theme switch.
- **Two accents, split by contrast.**
  - `--accent` (`#ff5a1f`) is for shapes only: fills, rules, focus rings, the
    brand square, the status light. It is 2.9:1 on the page, so never set text in it.
  - `--accent-text` (`#b8401a`) is the orange for text: links, eyebrows, small labels.
  - Text on an `--accent` fill uses `--accent-ink` (ink, 6:1).
- **Every text colour passes WCAG AA (4.5:1)** on every background it is used on.
  `scripts/check_contrast.py` lists the pairs and runs in CI. Add a pair there
  when you introduce one.
- Status colours (`--ok`, `--warn`, `--danger`) always come with a text label.
  Colour is never the only signal.

## Shape

- One multiplier: `--radius` (6px). `--radius-sm` and `--radius-lg` derive from it;
  `--radius-pill` is for pills only. No other radius values.
- Flat surfaces: hairlines (`--line`), no shadows, no gradients.

## Type

- Geist for prose and headings, JetBrains Mono for labels, numbers, paths, ids.
- Nothing below `--text-label` (11px). Mono labels are 11px uppercase with 0.12em tracking (`.eyebrow`).
- Section heads on the site use numbered eyebrows: `.eyebrow.numbered` renders `01 — Label`
  with the brand square in front.

## Behaviour

- Every view has a loading, an empty and an error state. Unknown values render `—`, never `0`, `?` or `undefined`.
- Touch targets are at least 44px tall on coarse pointers.
- Every control has a visible `:focus-visible` ring (2px `--accent`).
- No content is invisible without JavaScript. Motion respects `prefers-reduced-motion`.
- A disabled control says why. Destructive actions say what will break before they run.
- No custom cursors, no scroll-jacking, no decorative animation.

## Brand assets

`site/public/mark.svg` is the one mark (sprout, orange). The favicon, the
apple-touch-icon and the OG image are generated from it by running
`node scripts/make_brand_assets.mjs` in `site/` (headless Chrome; `og.html` here is the
OG layout). The docs logo (`site/src/assets/logo.svg`) is a copy of the mark, and the
console inlines the favicon in `console/index.html`.
