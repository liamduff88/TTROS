# North Shore Honda Sales Reporting Pilot

Pilot ID: northshore_honda_sales_demo

Purpose: Telegram sales reporting demo for North Shore Honda.

Pilot group commands:
- /whoami
- /report <sales update>

Setup:
1. Add the Agentic OS Telegram bot to the North Shore Honda Sales Pilot Telegram group.
2. In the group, send /whoami.
3. Copy the returned group chat ID.
4. From Liam's private operator bot chat, send:
/pilot_add <group_chat_id> northshore_honda_sales_demo

Reports save to:
Agentic OS Live/pilots/northshore_honda_sales_demo/sales_reports.jsonl

Pilot chats cannot control Hermes. They only submit approved demo reports.
