---
title: Write a bundle
description: A bundle is one agent as a folder. Build it once, install it for every customer.
---

```bash
plnt init order-desk
```

```
order-desk/
├── skill.toml           what the agent is and what it may do
├── prompt.md            system prompt; {{config.x}} is filled per customer
├── config_schema.json   the settings each customer provides (JSON Schema)
└── tools/
    └── hours.py         Python tools the model can call
```

## skill.toml

```toml
[meta]
name = "order-desk"
version = "0.1.0"
description = "Answers order-status questions for one online shop."
tags = ["support", "ecommerce"]

[runtime]
model_hint = "small"            # small | deep | auto
tools = ["lookup_order"]        # names of @tool functions in tools/
require_tool = "lookup_order"   # optional: no answer before this is called
max_steps = 4

[budget]
tokens = 8000                   # per message
wall_seconds = 60

[secrets]
required = ["SHOP_API_KEY"]     # each tenant must set these before it can run
```

Every field is described in the [skill.toml reference](/docs/reference/skill-toml/).

## prompt.md

Plain text or Markdown. `{{config.<key>}}` is replaced with the tenant's install config. Strings are inserted as they are; lists and objects are inserted as JSON.

```markdown
You answer order questions for **{{config.shop_name}}**.

- Always call `lookup_order` before saying anything about an order.
- If you can't help, tell the customer to email {{config.support_email}}.
- Tone: {{config.tone}}.
```

## config_schema.json

A JSON Schema (draft 2020-12) for the per-customer settings. Installs are validated against it, defaults are filled in, and the console builds its settings form from it. Set `"additionalProperties": false` so a typo fails the install and isn't silently ignored.

```json
{
  "type": "object",
  "properties": {
    "shop_name": {"type": "string", "title": "Shop name", "minLength": 1},
    "support_email": {"type": "string", "title": "Support email"},
    "tone": {"type": "string", "enum": ["friendly", "formal"], "default": "friendly"}
  },
  "required": ["shop_name", "support_email"],
  "additionalProperties": false
}
```

## Tools

See [Tools and ToolContext](/docs/guides/tools/).

## Try it

```bash
plnt run ./order-desk "where is order 1042?" \
  --config shop_name=Acme --config support_email=help@acme.example \
  --secret SHOP_API_KEY=test-key
```

`plnt run` installs the bundle for a tenant (`local` unless you pass `--tenant`), sends one message, and prints each event. It exits non-zero if the run did not finish with an answer, so you can use it in CI.

## Versions and upgrades

An install is a frozen copy of the bundle at the time you installed it, with a sha256 digest. Editing the bundle folder does not change what existing tenants run. To roll out a change, bump `meta.version` and install again. If a tenant has several versions installed, the highest enabled version is used.

## Where the server finds bundles

`plnt install <slug>` and the HTTP API look up slugs in the catalog, in this order:

1. directories on `PLNT_BUNDLE_PATH` (`:`-separated)
2. the bundles that ship with plnt (`support-desk`, `booking-desk`)

Over the HTTP API, tenants can only install catalog slugs, never arbitrary paths, so a tenant key cannot load new code onto the server.
