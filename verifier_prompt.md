# queue/templates/verifier.prompt.md
> Template only — does not launch agents or change queue state.

## Purpose
Fresh-context verifier subagents outperform self-critique. This template
gives a worker's output to a separate subagent with no memory of building
it, to check against the original work order — never the same context that
did the work.

---

**Verification — {item_id}**

You did not do this work. Check it cold against the spec below. Do not
assume good faith; look for evidence.

### Original definition of done
{definition_of_done}

### Original stop conditions
{stop_conditions}

### Artifact(s) to check
{artifact_paths}

### Checklist
1. Does the artifact satisfy every clause of the definition of done —
   specifically, not generally?
2. Was any stop condition crossed (external action, client blending,
   scope creep)?
3. Is every factual claim in the artifact traceable to a source pointer
   in the original work order? Flag anything that looks invented.
4. Are acceptance tests (if any) evidenced — logs, screenshots, paths —
   not asserted?

### Output — exactly one of
- `PASS` — with the one-line evidence for each checklist item.
- `NEEDS ATTENTION` — with the specific clause that failed and why.

Never split the difference. Never fill a gap in the evidence with your own
inference — if you can't verify a claim, say so as a failure, not a pass.
