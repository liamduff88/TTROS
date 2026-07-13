// Revisit: when the backend GitHub URL contract changes. · Last touched: 2026-07-13.
const componentPattern = /^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?$/

export function validateGitHubRepositoryUrl(value) {
  const raw = String(value || '')
  if (!raw || raw !== raw.trim() || /[^\x00-\x7f]/.test(raw) || /[\x00-\x1f\\]/.test(raw)) return { valid: false, error: 'Enter an ASCII URL with no spaces or backslashes.' }
  let parsed
  try { parsed = new URL(raw) } catch { return { valid: false, error: 'Enter a complete GitHub repository URL.' } }
  if (raw.slice('https://'.length).split('/')[0] !== 'github.com') return { valid: false, error: 'The authority must be exactly github.com with no credentials or port.' }
  if (parsed.protocol !== 'https:' || parsed.host !== 'github.com' || parsed.hostname !== 'github.com') return { valid: false, error: 'Only https://github.com/owner/repository is accepted.' }
  if (parsed.username || parsed.password || parsed.port || parsed.search || parsed.hash) return { valid: false, error: 'Credentials, ports, query strings, and fragments are prohibited.' }
  if (parsed.pathname.includes('%')) return { valid: false, error: 'Encoded path components are prohibited.' }
  const parts = parsed.pathname.split('/')
  if (parts.length !== 3 || !parts[1] || !parts[2]) return { valid: false, error: 'Use exactly one owner and one repository path component.' }
  const owner = parts[1]
  const repository = parts[2].endsWith('.git') ? parts[2].slice(0, -4) : parts[2]
  if (!componentPattern.test(owner) || !componentPattern.test(repository) || owner === '.' || owner === '..' || repository === '.' || repository === '..') return { valid: false, error: 'Owner or repository contains unsupported characters.' }
  return { valid: true, owner, repository, normalized: `https://github.com/${owner}/${repository}`, id: `${owner}/${repository}` }
}
