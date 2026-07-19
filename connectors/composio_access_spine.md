# Composio Access Spine v0
> Revisit: when the Composio CLI or Gmail action catalog changes. · Last touched: 2026-07-17.

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

The `run` command accepts registered toolkits and validated Composio action slugs. It previews with Composio `--dry-run` by default. Generic Gmail routing is fail-closed to read-only `FETCH`/`GET`/`LIST`/`SEARCH` actions:

```bash
python3 connectors/composio_access_adapter.py run gmail GMAIL_LIST_DRAFTS --data '{"user_id":"me"}'
```

Non-Gmail external mutations retain both generic gates:

```bash
python3 connectors/composio_access_adapter.py run github GITHUB_CREATE_AN_ISSUE --data '{"owner":"example","repo":"example","title":"Approved"}' --execute --operator-command
```

The adapter accepts an inline JSON object in `--data`. Before execution, obtain the exact action slug with `prepare`, then inspect required inputs directly:

```bash
/home/liam/.composio/composio execute GITHUB_CREATE_AN_ISSUE --get-schema
```

Gmail sends, replies, forwards, schedule-send effects, draft update/delete, and
label/message mutations are unconditionally rejected from the generic runner.

## Gmail draft-only adapter

The sole Gmail outbound-preparation authority is the live action
`GMAIL_CREATE_EMAIL_DRAFT`, through the dedicated adapter:

```bash
python3 connectors/gmail_draft_adapter.py create --input -
```

It requires a work-item ID and prospect/message identity, validates recipient,
subject, body, optional cc/bcc, passes content to Composio over stdin, creates
one idempotent draft effect, and emits safe metadata only. Recovery packages
live only in ignored, search-excluded `queue/draft_runtime/`. The adapter has no
send or fallback-send path.

## Connection-state fallback

The verified current set is Google Sheets, Instagram, Google Maps, YouTube, Google Docs, Agent Mail, Reddit, LinkedIn, GitHub, Google Drive, Google Calendar, and Gmail. Expired Facebook (2), WhatsApp, Apollo, and duplicate Google Maps, YouTube, and Google Drive connections remain recorded as expired. Do not reconnect, create, update, or delete connections from this adapter.

Action discovery is independent of connection-state verification. A failed `search` leaves discovery pending and does not make a verified active connection stale.
