# support-desk

Answers customer questions for one business from that business's own FAQ, and
hands off to a human contact when the FAQ doesn't cover the question.

Install it once per business, with that business's config:

```bash
plnt install support-desk --tenant bistro \
  --config business_name="Luigi's Bistro" \
  --config handoff_contact=hello@luigis.example \
  --config-json faq='[{"q": "When are you open?", "a": "Tue-Sun, 5pm-11pm."}]'
```

| Config | Required | Meaning |
|---|---|---|
| `business_name` | yes | Shown to customers |
| `handoff_contact` | yes | Where unanswered questions go |
| `tone` | no | `friendly` (default), `formal`, `playful` |
| `faq` | no | List of `{q, a}` pairs the agent answers from |
