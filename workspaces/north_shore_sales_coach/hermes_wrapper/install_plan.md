# Future installation plan

1. Create a new isolated Hermes workspace from this package; do not import or
   reuse old `.hermes`, Ubuntu, vault/runtime, sessions, skills, ZPC, MCP, or
   OpenRouter state.
2. Validate the manifest and wrapper config, resolve package-relative paths,
   and confirm host tool/session inheritance is disabled.
3. Bind only the four declared North Shore entrypoints. Keep the package's
   command allowlist and role checks as the authorization boundary.
4. Inject secrets at deployment time through the named environment variables.
   Never copy secrets into this package or wrapper config.
5. Keep Telegram polling, Sheets reads/writes, LLM use, and Composio execution
   disabled during installation. Enable any future integration only through a
   separate, reviewed deployment change.
6. If Sheets is later enabled, select exactly one provider: Hermes native,
   direct Google API, or optional Composio. Do not add a core dependency on
   Composio or Agentic OS backend routes.
7. Run package tests and wrapper readiness tests before starting any transport.

Installation must not modify protected Agentic OS Telegram or startup files.
Runtime-generated files belong in the new workspace's deployment-managed
runtime area and are intentionally absent from this readiness scaffold.
