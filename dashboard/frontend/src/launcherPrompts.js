export const SCOPED_PERMISSION_HEADER = `PERMISSION MODE — SCOPED LOCAL TASK APPROVED
Do not ask for permission during this scoped local task. Assume approval for local reads, local edits, file creation, dependency installation, validation commands, local dev-server startup, browser preview, and screenshot capture inside the stated scope.
Do not ask before editing files inside the stated folder. Make the changes, validate, and return the compact closeout.
Stop only for real external/destructive actions.`

export const CODEX_LINUX_LAUNCH = `cd "/home/liam/agentic-os-live"
/home/liam/.local/bin/aos-codex '<TASK>'`

export const CLAUDE_LINUX_LAUNCH = `cd "${'${AOS_ROOT:-/home/liam/agentic-os-live}'}"
export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$HOME/.composio:$PATH"
command -v claude
claude --version
claude --permission-mode acceptEdits`

export const launcherPrompt = target => `${SCOPED_PERMISSION_HEADER}\n\n${target === 'codex' ? CODEX_LINUX_LAUNCH : CLAUDE_LINUX_LAUNCH}`
