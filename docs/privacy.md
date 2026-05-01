# Privacy

Purpose: state the trust-zone reasoning behind [archithreat](../src/archithreat/__init__.py)'s design and the engineering claims that follow from it for each distribution surface. Verifiable, not legalese.

## Contents

- [Why this matters](#why-this-matters)
- [CLI](#cli)
- [Browser app](#browser-app)
- [Self-hosted container](#self-hosted-container)
- [What no surface can see](#what-no-surface-can-see)

## Why this matters

Architecture models for critical infrastructure — airports, utilities, finance, health — describe operational attack surfaces. Policies and contracts frequently forbid uploading them to third-party services. A public hosted converter would either be unusable for the audience that most needs it, or be a target for the most sensitive data the tool processes.

archithreat avoids both outcomes by shipping software, not a service. Every deployment runs inside a trust zone the user already controls: their laptop (CLI), their browser (browser app), or their internal infrastructure (container). The privacy properties below are structural; they hold by construction, not by promise.

## CLI

**What it sees:** the input file and the output file, both on local disk; the mapping file (if specified) on local disk; stdin/stdout/stderr.

**What it does not see:** the network. The CLI makes no outbound network calls during conversion. There is no telemetry, no version check, no remote default fetch. The bundled default mapping is loaded as a Python package resource, not from a URL.

**Verifiable:**

```bash
strace -e trace=network archithreat convert model.xml model.drawio
```

You should see no `connect`, `sendto`, or `socket` syscalls beyond what the kernel does for unrelated reasons (DNS lookups for hostname resolution if your locale config triggers them, etc.). The process itself does not open sockets.

The optional `archithreat serve` subcommand starts the local web shell; that surface's properties are documented in the next section.

## Browser app

**What it sees:** the file the user picks via the File API, in the browser's memory only; the mapping textarea contents.

**What it does not see:** the network, after the initial page load completes. The Pyodide runtime is vendored in the bundle. The core Python wheel is vendored in the bundle and installed from a same-origin path. There is no `fetch` of user content. The download is a Blob URL that never leaves the page.

**Verifiable:** open developer tools, switch to the Network tab, wait for the page to finish loading, clear the log, run a conversion. The Network tab stays empty. The file never leaves the browser. See [browser.md](browser.md#verifying-the-privacy-claim) for the step-by-step.

## Self-hosted container

**What it sees:** the upload payloads on incoming requests; the JSON or HTML responses it returns; logs containing request metadata (method, path, status, duration, client IP, request ID).

**What it does not see:**

- **The disk, for user content.** No database. No `tempfile` use. No file writes for the input, the mapping, the intermediate model, or the output. Processing happens in-memory via `BytesIO`.
- **Logs containing model contents.** Application logs record request metadata only; uploaded XML, mapping YAML, and emitted output never appear in log lines.
- **The network**, beyond the request/response cycle the client initiated. There is no upstream telemetry, no version check, no remote dependency fetch at runtime.

**Verifiable:** [tests/web/test_no_persistence.py](../tests/web/test_no_persistence.py) patches `builtins.open` (write modes), `os.write`, `tempfile.mkstemp`, `tempfile.NamedTemporaryFile`, and `pathlib.Path.write_bytes` / `write_text` to raise on any call, then exercises `POST /api/v1/convert` end-to-end. The test asserts the conversion succeeds while every disk-write path is blocked. Re-running it on your own infrastructure proves the property locally:

```bash
pytest tests/web/test_no_persistence.py -v
```

The container is also short-lived: kill the process and the request memory is gone. There is no persistent state to compromise.

## What no surface can see

- The contents of any file you do not explicitly hand to it.
- Other models you have converted previously (the CLI process exits between runs; the container holds nothing across requests; the browser holds nothing across page reloads).
- Anything that would need a third-party service to retrieve (no analytics, no error reporting, no usage metrics, no remote feature flags).

If the trust-zone story is what brought you to archithreat, that is the property you are buying. Verify it. The instructions above are written so you can.
