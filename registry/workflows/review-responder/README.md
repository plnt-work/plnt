# review-responder

Draft an on-brand reply to a Google Business review.

## Steps

1. `classify_intent` — sentiment + topics
2. `retrieve_brand_voice` — RAG from tenant brand-voice index
3. `draft_reply` — LLM generation
4. `safety_check` — policy moderation

## Requirements

- 2× nvidia.com/h100
- 40 GiB memory
- Access to a `brand-voice/<tenant>` RAG index (see `tools.rag`)

## Invoke

```json
{
  "tenant_id": "acme-cafe-nyc",
  "review": {
    "rating": 2,
    "text": "Waited 40 minutes even with a reservation..."
  }
}
```

Returns:

```json
{
  "reply_text": "Thanks for the honest feedback...",
  "sentiment": "negative",
  "safe": true
}
```

## Pull

```bash
microagents pull review-responder@1.2.0
```

## Deploy on plnt

```yaml
apiVersion: plnt.work/v1
kind: WorkflowRun
metadata:
  name: review-responder
spec:
  workflow: { ref: review-responder@1.2.0, registry: s3://microagents }
  backend:  { cluster: gpu-cluster-01, gpuClass: nvidia.com/h100, gpuCount: 2 }
```
