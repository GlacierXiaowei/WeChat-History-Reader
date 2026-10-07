# Weixin 4.1.13 compatibility

This scanner note applies to the WeChat History Reader 2.1.1 local CLI.
It describes Weixin database compatibility, not a separate plugin version
or MCP interface.

The Windows key scanner now supports two recovery paths:

1. The modern path reads committed process memory without injection, locates
   candidate values associated with the loaded Weixin module, derives the
   per-database SQLCipher key, and authenticates it against page 1.
2. The legacy path scans the historical hexadecimal key representation and
   applies the same page-1 authentication before accepting a key.

The modern path is intended for the Weixin 4.1.13 layout supplied with this
change. The fallback keeps older Weixin installations compatible. A modern
failure does not prevent the legacy path from running.

Only authenticated per-database keys are written to the private runtime cache.
Diagnostics contain a scanner build identifier, fixed stage names, counts, PIDs,
and system error codes; raw candidates, passwords, salts, and memory addresses
are not written to the diagnostic file.

Initialization uses a temporary key file and a temporary decrypted database for
validation. If validation fails, the existing account configuration and key
cache remain intact, while the attempted path is retained as pending diagnostic
state.

Use the bundled launcher from the plugin root:

```text
scripts/plugin_bootstrap.cmd doctor
scripts/plugin_bootstrap.cmd configure-history --db-dir "D:\path\to\db_storage"
```

Plain `doctor` reads the configured path, process state, and existing keys;
it does not scan process memory or refresh keys. Account initialization/key
recovery belongs to explicitly authorized `configure-history`, with WeChat
signed in. `doctor --repair` repairs only Python dependencies and the install
marker; it cannot fix a database format or key mismatch.

The supported modern layout is the tested Weixin 4.1.13 layout, not a promise
of compatibility with every later Weixin version.
