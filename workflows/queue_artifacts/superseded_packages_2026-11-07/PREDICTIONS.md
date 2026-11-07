# Predictions, written before the run (2026-11-07)

- Package IDs dropped by the remove_list.txt removal (apply_rest_2026-11-07.json ledger.package_ids): 35.
- 04_IMPORTED folders whose INGEST_MANIFEST.json package_id is one of those 35: 35 (one folder each).
- Each has a sibling <folder>.IMPORT_RECEIPT.json: 35. Entries moved: 70.
- 04_IMPORTED entries: 131 before, 61 after. 08_SUPERSEDED_PRE_V3: absent before, 70 after.
- Ledger rows matching any of the 35 package IDs: 0 (so the timer's receipt republish skips them).
- Moved folders that are v3 packages (name contains 20261107, or the Ryan v3 491e70003998): 0.
- Folders ending _6e9806531b13 or _88e0ed70f72a: IMPORTED 3 + 3 before, 0 after; READY 0 before and after.
- 03_READY_FOR_TTROS listing: unchanged. Model calls: 0.
