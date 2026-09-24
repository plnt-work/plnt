// Tailwind config — the `theme.extend.colors` block is generated from
// web/src/styles/tokens.css by `node scripts/sync-tokens.mjs`. Run that
// script after touching the upstream tokens; don't hand-edit colors here.
const tokens = require("./src/styles/tokens.js");

module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        paper: tokens.colors.paper,
        ink: tokens.colors.ink,
        coal: tokens.colors.coal,
        sage: tokens.colors.sage,
        amber: tokens.colors.amber,
        rust: tokens.colors.rust,
        sky: tokens.colors.sky,
        iri: tokens.colors.iri,
        map: tokens.colors.map,
      },
      borderRadius: tokens.radius,
      spacing: tokens.space,
      fontFamily: {
        sans: ["Geist", "System", "sans-serif"],
        mono: ["JetBrainsMono", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
