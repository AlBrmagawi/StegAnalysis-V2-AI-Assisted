# Security and privacy boundaries

The intended environment is **one trusted analyst using a local machine** to inspect potentially untrusted evidence. This is not an authenticated public service, a secure multi-tenant platform, or a replacement for a disposable analysis VM.

## Implemented controls

- Loopback native binding and loopback-only Compose published port. Host validation, exact same-origin checks, cross-site Fetch Metadata rejection, and an explicit custom header for API mutations. No permissive CORS.
- SHA-256 at ingestion, immutable objects by application contract, re-hashing before each analyzer, safe display names, random record IDs and case-scoped artifact access. Resolved-path containment and symlink checks protect evidence storage. No upload/delete/overwrite endpoint exists for originals.
- 32 MiB file/request limits, bounded extraction depth/count/bytes, pixel/page/sample budgets, bounded text/string output, timeouts and memory monitoring. Deduplication prevents repeated recursive processing of the same content hash within a job. Transformations are never recursively treated as new originals.
- Parser work in a killable child process, separate workspaces, closed stdin for external commands, argument arrays with `shell=False`, child-process cancellation and secret-stripped worker environments. No extracted content is executed.
- HTML/SVG treated as inert text or downloads. PDFs are downloaded rather than embedded in a browser frame. Original images await bounded native decoding before UI preview. React renders text; report HTML escapes untrusted fields and embeds only bounded generated PNG previews. CSP, nosniff, no-referrer and no-frame headers are applied.
- Hosted assistant calls require preview and a consent digest tied to the exact question, selected records, case and configured endpoint/model. There is no tool-execution interface available to a model.

## Remaining isolation limits

Native workers share the analyst’s OS account. A parser exploit could access that account’s files or network despite application-level path controls. Windows uses process-tree termination and sampled memory limits rather than a Windows Job Object or filesystem/network sandbox. Linux rlimits do not create a filesystem or network namespace. Memory sampling can overshoot between checks. No absolute aggregate case/disk quota is enforced across repeated analyses. A same-user local attacker can tamper with storage; this is not write-once media or a cryptographically signed evidence vault.

Compose narrows exposure: UID/GID 10001, read-only image, only a named `/data` volume writable, bounded noexec `/tmp`, all capabilities dropped, no-new-privileges, PID/memory/CPU limits, and an internal network without outbound connectivity. Parsers still share the container’s evidence volume, including other cases; this is not per-job container isolation. Docker Desktop or rootless containers and a disposable VM are sensible for hostile inputs. No broad host mounts or Docker socket are needed.

The default Compose network intentionally prevents hosted models and external Ollama connections. Native optional providers can be configured explicitly. Changing container network policy is an analyst deployment decision; do not silently enable outbound access.

## Data handling

Evidence, notes, conversation history and reports are plaintext local data. Reports may contain personal or sensitive metadata. Protect `.data` and exported files with OS permissions/encryption appropriate to your investigation. Back up the full data directory while the service is stopped, or use SQLite’s backup API and preserve all object files. Do not copy a live SQLite main file without its WAL.

Do not expose port 8000 publicly. Do not run multiple API workers or instances against one data directory. API clients must send `X-Steganalysis: local` on mutations. No auth token is advertised because the trust boundary is the local single-user machine, not an internet login.


## Container network gateway

Docker Compose includes one non-root Nginx transport gateway in front of the application. It publishes only the loopback port and preserves Host/Origin and SSE streaming. It has no evidence-volume mount. The workbench remains on an internal network with no outbound route. This avoids Docker Desktop internal-network port-publication limitations without granting parsers internet access. The gateway itself has a normal bridge interface; its sole configured upstream is the workbench. Native use needs no gateway.
