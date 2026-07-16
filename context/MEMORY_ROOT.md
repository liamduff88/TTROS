# MEMORY ROOT
> Revisit: when the canonical Business Brain moves or pointer resolution changes. · Last touched: 2026-07-15.

Canonical logical root: `business_brain:README.md`

Start navigation at `business_brain:index/MEMORY_INDEX.md`. Agentic OS Live
references Business Brain by logical pointer only; do not copy Business Brain
content into this repo and do not embed a Windows or WSL vault path in prompts.

The shared resolver in `tools/business_brain.py` maps a declared logical pointer
to the live vault. It rejects absolute paths, traversal, `_backups/`, missing or
non-canonical targets, and basename lookup.

Use this memory root for ChatGPT handoffs, workbench prompts, Hermes context,
and Agentic OS project continuity.

Do not use old vaults, old runtimes, old sessions, old skills, or retired plugin
state as live memory.

Local pointer indexes in this repo:

- `memory_index/README.md`
- `memory_index/INDEX.md`

Notable Business Brain references:

- `business_brain:memory/company.md`
- `business_brain:memory/offers.md`
- `business_brain:memory/positioning.md`
- `business_brain:memory/ideal_clients.md`
- `business_brain:memory/sales_and_revenue.md`
- `business_brain:memory/marketing_voice.md`
- `business_brain:memory/delivery_model.md`
- `business_brain:memory/website_and_content.md`
- `business_brain:memory/agentic_os.md`
- `business_brain:decisions/DECISIONS.md`
- `business_brain:operating_context/current_priorities.md`
- `business_brain:operating_context/active_projects.md`
- `business_brain:operating_context/protected_paths.md`
- `business_brain:operating_context/old_vault_archive_plan.md`

Business-plan routing:

- Company: `business_brain:memory/company.md`, `business_brain:memory/positioning.md`, `business_brain:memory/ideal_clients.md`.
- Offers: `business_brain:memory/offers.md`.
- Website/content: `business_brain:memory/website_and_content.md`, `business_brain:memory/marketing_voice.md`.
- Revenue: `business_brain:memory/sales_and_revenue.md`.
- Delivery: `business_brain:memory/delivery_model.md`.
- Current work: `business_brain:operating_context/current_priorities.md`, `business_brain:operating_context/active_projects.md`.
- Protected boundaries: `business_brain:operating_context/protected_paths.md`.
