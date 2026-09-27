# registry

The public index of plnt agent bundles. It was imported from
`github.com/plnt-work/microagents` with full history.

> **Status: early.** `bundles/` holds the four shipped developer bundles
> (`code-reviewer`, `test-writer`, `repo-explainer`, `changelog-writer`);
> `plnt install <slug>` finds them here and the wheel ships a copy. This
> directory also holds one `workflows/` recipe from the pre-consolidation
> scaffold, in a retired YAML format that the runtime does not use. The real
> registry is roadmap Phase 5 (see `../ROADMAP.md`).

## Target shape (Phase 5)

```
registry/
  bundles/<slug>/            skill.toml, prompt.md, config_schema.json, tools/, evals/
  index.json                 generated in CI: slug, version, sha256, tools, config schema
```

`plnt install <slug> --tenant <id>` will fetch a bundle from this index, verify
its sha256, validate the tenant's config against `config_schema.json`, and
install it for that tenant only.

The booking example's bundles (`booking-desk`, `support-desk`) live in
`../examples/booking/bundles/`; point `PLNT_BUNDLE_PATH` there to install them.
