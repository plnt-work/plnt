---
title: Local models
description: Run agents on Ollama, vLLM, llama.cpp or LM Studio, on your machine or your customer's.
---

Local models are first-class in plnt. The same bundle runs on a hosted API or on a GPU box in your customer's building, and you can choose per customer.

## Pick a server

| Server | `PLNT_LOCAL_URL` | Notes |
| --- | --- | --- |
| Ollama | `http://127.0.0.1:11434` (default) | Uses Ollama's native `/api/chat`, so `num_ctx` is honoured. |
| vLLM | `http://host:8000/v1` | Start with `--enable-auto-tool-choice --tool-call-parser hermes` for native tools. |
| llama.cpp server | `http://host:8080/v1` | Start with `--jinja` for native tools. |
| LM Studio | `http://127.0.0.1:1234/v1` | |

A URL whose path contains `/v1` is treated as OpenAI-compatible; anything else as Ollama. Override with `PLNT_LOCAL_PROVIDER=ollama|openai`.

```bash
export PLNT_LOCAL_URL=http://127.0.0.1:11434
export PLNT_PLANNER_MODEL=qwen2.5:7b    # used for model_hint = "small" / "auto"
export PLNT_DEEP_MODEL=qwen2.5:14b      # used for model_hint = "deep"
```

## Check it

```bash
$ plnt models doctor
qwen2.5:1.5b  ollama · http://127.0.0.1:11434 · local
  ✓ reachable       http://127.0.0.1:11434
  ✓ model present   qwen2.5:1.5b
  ✓ context window  requesting 8192 of 32768 tokens
  ✓ tool calling    native; called get_weather(city='Paris')
  ✓ JSON output     got {'answer': 42}
```

Each failed check prints the fix, for example ``fix: ollama pull qwen2.5:7b``. `plnt models list` shows what the server has.

## Which model

Agents need a model that calls tools reliably. What we have measured:

- **qwen2.5:1.5b** passes the doctor but often skips lookups. With [`require_tool`](/docs/guides/guardrails/) its answers are grounded or withheld, never invented. Fine for CI, too weak for customers.
- **7B–8B instruction-tuned models with tool support** (qwen2.5:7b, llama3.1:8b) are the practical minimum for customer-facing agents.

Run your own bundle's `plnt run` against the model you intend to ship, and watch for `guardrail` events.

## Models without native tool calling

If a model or server doesn't support native tools, plnt describes the tools in the prompt and asks for a JSON object instead, then parses it. `plnt models doctor` reports which mode is used. Force it with `PLNT_NATIVE_TOOLS=on|off`.

## How the default model is chosen

For each run, unless the tenant has its own model:

1. `PLNT_FORCE=local|cloud|offline` wins if set.
2. Otherwise, if the local server accepts TCP connections, use it.
3. Otherwise, if `PLNT_CLOUD_URL`, `PLNT_CLOUD_API_KEY` and `PLNT_CLOUD_SMALL_MODEL` are set, use the cloud model.
4. Otherwise the run fails with `NoModelConfigured` and a hint.

`PLNT_FORCE=offline` uses a deterministic stub that makes no network calls. It exists for tests and never answers real questions.

## One model per customer

A customer who wants their data to stay on their own hardware can have their own model. The rest of your customers are unaffected:

```bash
curl -X PUT $API/tenants/clinic/model -H "$AUTH" -H 'content-type: application/json' -d '{
  "provider": "ollama",
  "base_url": "http://gpu.clinic.internal:11434",
  "model": "qwen2.5:7b",
  "num_ctx": 16384
}'
curl $API/tenants/clinic/model/health -H "$AUTH"
```

Every `run_started` event records which model and endpoint served the run, so you can show a customer where their conversations went.

## Running plnt in Docker with Ollama on the host

Inside a container, `127.0.0.1` is the container. Use `http://host.docker.internal:11434` and on Linux add `--add-host=host.docker.internal:host-gateway`.
