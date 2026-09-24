# Mobile assets

Placeholder. Before `eas build --profile preview` or any user-facing
distribution, drop the following PNGs here and restore the `icon`,
`splash`, and `adaptiveIcon` blocks in `app.json`:

- `icon.png` — 1024×1024, opaque
- `splash.png` — 1284×2778 or similar tall format, on `#FBF7EE`
- `adaptive-icon.png` — 1024×1024 foreground for Android adaptive icon

Until then, Expo falls back to its default icon during dev — that's
intentional, not a bug.
