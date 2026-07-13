# Pass 10 interactive graph repair receipt
> Expires: when the Graphify preview interaction contract changes or this proof is superseded.

- Lane: operations
- Profile: Codex workbench
- Model requested: unavailable
- Model confirmed: unavailable
- Definition of done: the same self-contained Graphify preview is clickable and interactive from the Graphify iframe and the Repo Ingest Graph link without relaxing its local-only security boundary.
- Result: PASS
- Behavior: node click/keyboard selection, detail inspection, relationship highlighting, pointer pan, wheel/button zoom, and reset.
- Browser proof: `proofs/pass10-graphify/browser-evidence.json`
- Screenshots: `proofs/pass10-graphify/01-repo-ingest-itsdangerous.png`, `proofs/pass10-graphify/02-graphify-itsdangerous-graph-tree.png`
- Validation: 24 focused Graphify tests; 186 required backend regression tests; 21 frontend tests; production frontend build; dashboard cleanup test; live Playwright interaction proof.
- Security verification: `sandbox="allow-scripts"` unchanged; no-network CSP unchanged; zero remote graph requests, failed responses, or browser console errors.

```yaml
token_usage:
  input_tokens: unavailable
  output_tokens: unavailable
  total_tokens: unavailable
  source: harness did not expose session token totals
```
