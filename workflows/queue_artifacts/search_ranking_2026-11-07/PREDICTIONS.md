# Predictions (written 2026-11-07 before the before/after measurement runs)

Before (current bm25-only order):
- Q1 "how to get my first paying customers": top 1 is an intake record (Chris 098e5a08). Top 3 contains 2 records.
- Q2 "how often should I post on LinkedIn": top 2 are intake records; no v3 topic note in top 3.
- Q3 "lead magnet ideas to collect emails": top 3 already all v3 (Lara three-value-bridge first).
- David query "who did I talk to about scheduler beta testing": #1 Ryan scheduler-beta-testing, #2 Ryan record (491e7000).

After (records bottom tier, v3 notes/indexes x2):
- Q1, Q2, Q3: top 3 are all v3 topic notes or source indexes; zero intake records in top 3.
- Q1 top 3 includes Chris free-to-paid-conversion. Q2 top 3 will NOT include Lara four-three-two-one
  (it lacks the words "often/should/how"; it ranks ~#7 among v3 notes). Q3 top 1 unchanged.
- David query: #1 unchanged; record leaves the top 3.
- Graph node/edge counts and graph.json hash: identical (Graphify not touched).
- Entity counts for person:ryan-spencer and person:chris-donnelly: identical.
- analyze_vault: PASS before and after, same canonical note count, 0 broken, 0 unreachable.
- Only differences in the snapshot diff: search orderings and the 4 v3 record titles.
