# Composio Access Spine v0

Composio is the first route for connector work. Hermes / Agentic OS should use the single stdlib adapter, not app-specific APIs.

```bash
python3 connectors/composio_access_adapter.py status
python3 connectors/composio_access_adapter.py whoami
python3 connectors/composio_access_adapter.py connected_accounts
python3 connectors/composio_access_adapter.py registry
python3 connectors/composio_access_adapter.py prepare gmail find unread invoices
```

`prepare` performs read-only action discovery for the requested toolkit and intent. The registry reflects the verified live `connections list` JSON: 12 toolkits have active accounts, while expired accounts and duplicates remain separate and unchanged. If an immediate probe has a transport failure, the adapter returns the last verified live state with the probe error instead of incorrectly reverting to stale-only state.

## Generic action runner

The `run` command accepts any registered toolkit and validated Composio action slug. It previews with Composio `--dry-run` by default:

```bash
python3 connectors/composio_access_adapter.py run gmail GMAIL_SEND_EMAIL --data '{"recipient_email":"person@example.com","subject":"Draft","body":"Review me"}'
```

Actual execution requires both gates. Use them only when Liam explicitly commands that specific action:

```bash
python3 connectors/composio_access_adapter.py run gmail GMAIL_SEND_EMAIL --data '{"recipient_email":"person@example.com","subject":"Approved","body":"Send this"}' --execute --operator-command
```

The adapter accepts an inline JSON object in `--data`. Before execution, obtain the exact action slug with `prepare`, then inspect required inputs directly:

```bash
/home/liam/.composio/composio execute GMAIL_SEND_EMAIL --get-schema
```

Read/search/status/draft/prepare may run when requested. Send/write/book/push/publish/delete/mutate are enabled only by Liam's explicit command naming the specific action. This is an action gate, not a blanket write prohibition.

## Connection-state fallback

The verified current set is Google Sheets, Instagram, Google Maps, YouTube, Google Docs, Agent Mail, Reddit, LinkedIn, GitHub, Google Drive, Google Calendar, and Gmail. Expired Facebook (2), WhatsApp, Apollo, and duplicate Google Maps, YouTube, and Google Drive connections remain recorded as expired. Do not reconnect, create, update, or delete connections from this adapter.

Action discovery is independent of connection-state verification. A failed `search` leaves discovery pending and does not make a verified active connection stale.
