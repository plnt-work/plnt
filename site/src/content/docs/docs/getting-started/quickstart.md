---
title: Quickstart
description: Install plnt, point it at a model, and run an agent for two customers.
---

## 1. Install

plnt needs Python 3.11 or newer.

```bash
pip install "git+https://github.com/plnt-work/plnt"
plnt --version
```

Once v0.1.0 is on PyPI this becomes `pip install plnt`.

## 2. Pick a model

Choose **one** of these.

**Local, with Ollama.** Nothing leaves your machine.

```bash
ollama pull qwen2.5:7b
export PLNT_PLANNER_MODEL=qwen2.5:7b
```

**Hosted, with any OpenAI-compatible API.** Gemini is shown here; OpenAI, Groq and OpenRouter work the same way.

```bash
export PLNT_CLOUD_URL=https://generativelanguage.googleapis.com/v1beta/openai
export PLNT_CLOUD_API_KEY=...
export PLNT_CLOUD_SMALL_MODEL=gemini-2.5-flash
```

Then check that the model can do what an agent needs:

```bash
plnt models doctor
```

The doctor checks that the server is reachable, the model is pulled, it calls tools, and it returns JSON. For anything that fails, it prints the fix. See [Local models](/docs/guides/local-models/).

## 3. Run a bundle

`support-desk` ships with plnt. It answers questions from a business's own FAQ.

```bash
plnt run support-desk "when are you open?" \
  --config business_name="Bright Smile Dental" \
  --config handoff_contact=front@brightsmile.example \
  --config-json faq='[{"q":"When are you open?","a":"Monday to Friday, 8am to 4pm."}]'
```

You see each step as it happens: the model call, the `lookup_faq` tool call, and the answer.

## 4. Two customers, one agent

```bash
plnt tenants create dental
plnt tenants create bistro

plnt install support-desk --tenant dental --config business_name=Dental \
  --config handoff_contact=a@dental.example \
  --config-json faq='[{"q":"Hours?","a":"Mon-Fri 8-4."}]'
plnt install support-desk --tenant bistro --config business_name=Bistro \
  --config handoff_contact=b@bistro.example \
  --config-json faq='[{"q":"Hours?","a":"Tue-Sun 6pm-11pm."}]'

plnt run support-desk "what are your hours?" --tenant dental
plnt run support-desk "what are your hours?" --tenant bistro
```

Same bundle, two answers. Each tenant's sessions, usage and audit log are stored under `~/.plnt/tenants/<id>/`. Set `PLNT_HOME` to store them somewhere else.

## 5. Serve it

```bash
export PLNT_ADMIN_TOKEN=$(openssl rand -hex 24)
plnt serve --port 8787
```

```bash
API=http://127.0.0.1:8787/v1
AUTH="Authorization: Bearer $PLNT_ADMIN_TOKEN"

SID=$(curl -s -X POST $API/tenants/dental/sessions -H "$AUTH" \
  -H 'content-type: application/json' -d '{"bundle":"support-desk"}' | jq -r .session_id)
curl -s -X POST $API/tenants/dental/sessions/$SID/messages -H "$AUTH" \
  -H 'content-type: application/json' -d '{"text":"are you open on Friday?"}'
curl -N "$API/tenants/dental/sessions/$SID/stream?until_idle=1" -H "$AUTH"
```

The console is at `http://127.0.0.1:8787/console`. Sign in with the admin token, or with a tenant's own `pk_…` key to see only that tenant.

## 6. Write your own

```bash
plnt init hello-desk
plnt run ./hello-desk "when are you open?" --config business_name=Acme
```

Next: [Write a bundle](/docs/guides/bundles/).
