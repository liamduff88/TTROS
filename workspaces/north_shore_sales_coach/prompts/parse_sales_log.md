# Parse sales log (optional fallback)

Use only after the local router has classified a natural-language salesperson update as `log_sales_activity`, only when LLM use is explicitly enabled. Convert the activity statement into the sales-log schema and return JSON only. Never invent a missing field; list it in `missing_fields`. Do not classify general requests or execute commands, tools, or external actions.
