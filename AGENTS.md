# Repository Guidance

## Code Review Rules

Review pull requests for actionable correctness, privacy, security, regression,
and test-coverage problems. Do not request broad refactors that are unrelated
to the changed code.

### Privacy and security

- Treat WeChat databases, chat messages, account identifiers, keys, decrypted
  caches, and exported files as private data.
- Never add telemetry or upload chat content, database files, keys, decrypted
  caches, or raw diagnostic candidates.
- Do not log raw messages, secrets, key material, memory addresses, or
  machine-specific database paths.
- Preserve the rule that the original WeChat databases are not modified.

### Runtime and packaging

- Preserve the local/offline runtime model and bundled dependency behavior.
- Keep Python `>=3.10` compatibility unless a pull request explicitly changes
  the supported floor.
- Preserve the current no-MCP architecture unless a pull request explicitly
  proposes that change.
- Keep `pyproject.toml`, `plugin.json`, and `.codex-plugin/plugin.json`
  consistent when package metadata or versions change.

### Required validation

- Changes to decryption, key handling, SQLite access, image decoding, or path
  discovery should include focused success and failure tests.
- Changes to the launcher, bootstrap, packaging, or runtime setup should
  include an install or bootstrap smoke check.
- Flag missing tests when behavior or security boundaries change, but do not
  treat unrelated coverage improvements as required.

### Review style

- Report only issues that can be acted on, with the affected file and line
  context when possible.
- Explain the impact and a concrete fix direction.
- Prefer evidence from the diff and existing tests over speculation.

## Documentation and Audience Rules

Before editing README files, release notes, or other project documentation,
read [`docs/WRITING_GUIDE.md`](docs/WRITING_GUIDE.md). Treat that file as the
reference for audience, tone, and document boundaries.

### Document roles

- `README.md` is a GitHub-facing document. Its main content is written for
  users and should preserve the author's wording, product positioning, and
  approachable style. Do not broadly rewrite user-facing copy without explicit
  authorization.
- The developer section in `README.md` is public technical documentation. Keep
  it concise, accurate, and consistent with the current CLI and source tree.
- `README.en.md` should be synchronized only after the Chinese README has been
  confirmed. Do not independently change its product positioning.
- `dist/RELEASE_NOTES_*.md` is user-facing release copy. Follow the README's
  tone and describe only changes that belong to the stated release.
- `skills/**/SKILL.md` contains instructions for AI Agents. Do not copy
  internal execution instructions, trigger wording, or diagnostic procedures
  into user-facing README or release copy.
- `AGENTS.md` contains repository-level instructions for coding and review
  Agents. Keep engineering, privacy, security, and documentation constraints
  here; do not turn it into marketing copy.

### Editing boundaries

- Direct user instructions about an existing document take priority. Preserve
  user-written text and make only the specifically authorized changes.
- When a documentation request affects multiple audiences, separate the
  sections instead of blending user copy, developer API details, and AI
  execution instructions.
- If the Chinese README or release copy is awaiting user confirmation, do not
  synchronize the English README or rebuild the release package from it.
- Keep release notes, release README drafts, and writing templates as local
  project references unless the user explicitly asks to publish or package
  them. Do not assume that a document under `docs/` or `dist/` belongs in the
  plugin ZIP or GitHub Release assets.
- Never include real WeChat messages, databases, keys, decrypted caches, or
  private configuration in examples or documentation.
