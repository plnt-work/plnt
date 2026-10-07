## Summary

One or two sentences on what this PR changes and why.

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (docs + contract test updated)
- [ ] Docs only
- [ ] Chore (deps, CI, refactor)

## Linked issues

Fixes #

## Testing

- [ ] `pytest -q` green locally
- [ ] `ruff check .` reports no new errors
- [ ] Manual smoke: describe what you ran

## Contract impact

- [ ] No wire-format change
- [ ] Wire format changed — [`tests/test_site_contract.py`](../tests/test_site_contract.py) updated
- [ ] Wire format changed — [`docs/api-contract.md`](../docs/api-contract.md) updated
- [ ] Wire format changed — plnt-site consumer flagged / co-PR opened

## Docs impact

- [ ] No docs change needed
- [ ] Runbook updated ([`deploy/RUNBOOK-do-k8s.md`](../deploy/RUNBOOK-do-k8s.md))
- [ ] ERD updated ([`docs/ERD.md`](../docs/ERD.md))
- [ ] Roadmap flipped ([`ROADMAP.md`](../ROADMAP.md))
- [ ] Changelog entry added ([`CHANGELOG.md`](../CHANGELOG.md))

## Screenshots / recordings

For UI or CLI changes.

## UI checklist (site, playground, console)

Skip if the PR touches no UI. Rules: [`design/README.md`](../design/README.md).

- [ ] Screenshots at 1280px and 375px wide, no horizontal scroll at 375
- [ ] Loading, empty and error states shown; unknown values render `—`
- [ ] `python scripts/check_contrast.py` passes; no orange text in `--accent` (use `--accent-text`)
- [ ] Nothing under 11px; touch targets 44px on a coarse pointer
- [ ] Keyboard path works with a visible focus ring
- [ ] Works without JS, or says why it can't
- [ ] No new colours, radii or sizes outside `design/tokens.css`

## Anything reviewers should look at closely

Call out tricky bits, deliberate trade-offs, and the parts you're least
sure about.
