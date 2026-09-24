# registry

The public index of plnt agent bundles. It was imported from
`github.com/plnt-work/microagents` with full history.

> **Status: early.** `bundles/support-desk` is a working example bundle; `plnt install support-desk` finds it here. This directory also holds one `workflows/` recipe
> from the pre-consolidation scaffold, in a retired YAML format that the
> runtime does not use. The real registry
> is roadmap Phase 5 (see `../ROADMAP.md`).

## Target shape (Phase 5)

```
registry/
  bundles/<slug>/            skill.toml, prompt.md, config_schema.json, tools/, evals/
  index.json                 generated in CI: slug, version, sha256, tools, config schema
```

`plnt install <slug> --tenant <id>` will fetch a bundle from this index, verify
its sha256, validate the tenant's config against `config_schema.json`, and
install it for that tenant only.

Until then, working bundles live in `../skills/` (runtime built-ins) and
`../examples/booking/microagents/skills/` (reference app).
