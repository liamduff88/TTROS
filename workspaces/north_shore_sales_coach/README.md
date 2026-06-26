# North Shore Sales Coach

Phase 1 exportable, isolated workspace shell for a direct Telegram
sales-coaching sub-bot. It is independent from the Agentic OS Telegram bridge
and can later be hosted or wrapped inside Hermes without becoming a general
Hermes operator or a second Hermes system.

## Current scope

- Natural-language-first sales updates and manager questions
- Whitelisted, zero-token command routing
- File-based role authorization
- Package-local invite-code onboarding
- Local JSONL sales-log storage
- Deterministic parsing of structured sales-log input
- Daily report generation from local records
- Disabled-by-default LLM and Google Sheets adapter boundaries

The package has a direct Telegram Bot API runner. It has no LLM call, Google
Sheets connection, or customer data in this phase.

It owns its Telegram token/config, role map, local data, and Sheets connector
configuration. A future Hermes wrapper must preserve the command whitelist and
must not expose general Hermes, agent, filesystem, shell, or OS commands.

## Sheets boundary

`src.sheets_sync_adapter` constructs deterministic rows and
`src.sheets_adapter` converts them into provider-neutral read/write request
contracts. Local validation and dry-run require no provider SDK:

```bash
python3 -m src.sheets_adapter --dry-run
```

The North Shore demo is route-locked to the package-local direct Google Sheets
provider. Direct Google preflight can proceed only when
`NORTH_SHORE_SHEETS_PROVIDER=google_sheets_api`,
`NORTH_SHORE_GOOGLE_SHEET_ID` is present, and credentials are supplied through
`NORTH_SHORE_GOOGLE_CREDENTIALS_JSON` or a package-local
`NORTH_SHORE_GOOGLE_CREDENTIALS_PATH` under the gitignored `.runtime/`
directory. `NORTH_SHORE_GOOGLE_EXECUTION_ENABLED`,
`NORTH_SHORE_GOOGLE_READS_ENABLED`, and
`NORTH_SHORE_GOOGLE_WRITES_ENABLED` are separate explicit gates.

An optional faster demo bridge is scaffolded as
`NORTH_SHORE_SHEETS_PROVIDER=apps_script_webapp`. It requires
`NORTH_SHORE_SHEETS_WEBAPP_URL` and `NORTH_SHORE_SHEETS_EXECUTION_ENABLED=true`
for status checks. Append actions also require
`NORTH_SHORE_SHEETS_WRITES_ENABLED=true`, plus an explicitly supplied HTTP
client. Reads are not required for append actions. Do not commit the real
`/exec` URL or Sheet ID.

For the North Shore demo, authenticate using a separate demo Google account and
share only the target Sheet with that account. Do not use Liam's existing
Agentic OS Google Drive connector, Composio provider route, Hermes-native Google
route, or Agentic OS backend connector routes for this package.

## Interaction model

Natural language is the primary user experience. Salespeople describe activity normally, and managers ask ordinary questions such as “How did the team do today?” Deterministic local patterns route recognized intents without token use.

Slash commands are fallback/menu and admin shortcuts. The command whitelist is an internal safety and intent boundary; users are not required to speak in commands. Unknown messages stay inside a safe local help intent and never route to Hermes, Agentic OS, general-purpose agents, arbitrary tools, or operating-system controls.

The admin group is limited to North Shore intents: today, team, followups,
missing, coaching, report, dashboard, and roster/registration shortcuts.
Announcements are disabled and draft-only unless a separate scoped safe workflow
is implemented. General Hermes commands (including `/work`), Codex, Claude,
arbitrary connector/tool execution, web/browser/research, file edits, agent runs,
and OS/dashboard control are rejected locally before approved intent matching.

LLM use is disabled by default and may occur only through `src.llm_adapter` for
an explicitly scoped future step such as parsing a recognized messy sales log
or wording a validated report. Command and natural-language intent routing,
roles, roster checks, local reports, and dashboard-link responses never invoke
an LLM. No message is forwarded to Hermes or Agentic OS.

## Invite onboarding

Admins can create manager or salesperson invites:

```text
/invite manager Ryan McVeigh
/invite salesperson Sarah Jones
/create_invite salesperson Sarah Jones
```

Managers can create salesperson invites only. Natural language such as
`create invite for Sarah Jones` creates a salesperson invite unless the message
explicitly says manager. Pending invites are listed with `/invites`, revoked
with `/revoke_invite CODE`, and users can check their local role with
`/my_status`.

Invite codes are stored in `data/local_state.json`, expire after 14 days, and
work once. The invited person redeems in a direct message with the bot:

```text
/start NS-ABCD-1234
```

Redemption updates local state only. Salesperson redemption creates or updates
the local Salespeople roster and links that Telegram account to the salesperson
role. Manager redemption creates or updates a local manager user and does not
add the manager to the Salespeople roster. The existing `/sync_sheets` command
can later export the Users and Salespeople state through the configured Sheets
provider.

## Local validation

From this directory:

```bash
python3 -m compileall -q src tests
python3 -m unittest discover -s tests -v
```

Copy example configuration files outside source control before adapting them.
Keep credentials in environment variables or under the package-local gitignored
`.runtime/` directory only.

## Local bot launcher

From PowerShell, configure the package-local secret once and then start the bot:

```powershell
.\scripts\setup_local_secret.ps1
.\scripts\Start-North-Shore-Sales-Coach-Bot.ps1
```

The setup helper prompts without echoing and writes only to the gitignored
`.runtime/north_shore_bot.env` file. It can store the one North Shore Telegram
token plus Apps Script Sheets values:
`NORTH_SHORE_SHEETS_PROVIDER=apps_script_webapp`,
`NORTH_SHORE_SHEETS_WEBAPP_URL`, `NORTH_SHORE_SHEETS_WEBAPP_SECRET`,
`NORTH_SHORE_SHEETS_EXECUTION_ENABLED=true`,
`NORTH_SHORE_SHEETS_WRITES_ENABLED=true`, and
`NORTH_SHORE_SHEETS_READS_ENABLED=false`.

After setup, use the normal North Shore launcher. Do not manually paste the
Web App URL or shared secret for each run, and do not run a second North Shore
runner. The launcher starts `AgenticOSClean` as `liam`, switches to this package,
and runs exactly one `python3 -m src.north_shore_bot_runner`. It refuses to start
when another package runner is already active and prints only safe readiness
metadata such as URL length and secret length. It does not use the Agentic OS
Telegram bridge. Supplying `NORTH_SHORE_TELEGRAM_BOT_TOKEN` manually remains
supported.

`/sync_sheets` uses the same live North Shore runner and configured Apps Script
provider. Demo sync is append-only unless duplicate protection is explicitly
implemented, so re-running may duplicate rows.

## Windows startup operator notes

Install the separate North Shore Windows login startup entry from PowerShell:

```powershell
.\scripts\Install-North-Shore-Startup.ps1
```

Remove it with:

```powershell
.\scripts\Remove-North-Shore-Startup.ps1
```

Check whether the package runner is active:

```powershell
.\scripts\Get-North-Shore-Bot-Status.ps1
```

Manually start the same package-local runner:

```powershell
.\scripts\Start-North-Shore-Sales-Coach-Bot.ps1
```

The startup shortcut is named `North Shore Sales Coach Bot.lnk` and launches a
package-local hidden wrapper with `wscript.exe`, so Windows login keeps the bot
connected without leaving a PowerShell or console window open. The hidden wrapper
calls the same visible PowerShell launcher, which starts only this package
through WSL distro `AgenticOSClean`. The launcher changes to this package, runs
`scripts/start_north_shore_bot.sh`, relies on the package-local
`.runtime/north_shore_bot.env` secret file, and appends output to
`logs/north_shore_bot.log`.

Use `.\scripts\Start-North-Shore-Sales-Coach-Bot.ps1` only when you want a
visible manual runner for debugging. Closing that manual runner window can stop
the bot process it started.

Keep exactly one North Shore runner live per bot token. The bash launcher
refuses to start a second `python3 -m src.north_shore_bot_runner` process when
one is already detectable.
