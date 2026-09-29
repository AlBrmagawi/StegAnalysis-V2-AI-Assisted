# Evidence-scoped assistant

The default **deterministic evidence guide** is a rule-based rendering of actual findings, their benign alternatives and suggested next steps. It is labeled as such everywhere. It does not impersonate a language model. Core analysis remains available without credentials, a downloaded model or a GPU.

Select up to 12 findings in the Findings inspector, or expand one finding, then open Assistant. Without explicit selection, the guide uses up to six findings belonging to the selected artifact. Questions, provider labels and cited answers persist within the active case.

## Optional local model

Install and provision an Ollama model yourself. The workbench never downloads one. Set server environment variables before startup:

```powershell
$env:STEG_LOCAL_URL = "http://127.0.0.1:11434"
$env:STEG_LOCAL_MODEL = "your-installed-model"
& .\.venv\Scripts\steganalysis.exe serve
```

The local endpoint is restricted to loopback. The provider calls Ollama’s [chat API](https://docs.ollama.com/api/chat) with a JSON output schema, no tool definitions, a fixed token budget and a deadline. The health screen distinguishes configured availability from a live reachability check; connection errors are displayed on request.

## Optional hosted provider

Use a server-side HTTPS endpoint compatible with the Chat Completions request/response shape, accepting system/user messages and JSON-object response format:

```powershell
$env:STEG_HOSTED_URL = "https://your-provider.example/v1/chat/completions"
$env:STEG_HOSTED_MODEL = "your-model"
$env:STEG_HOSTED_KEY = "your-secret"
```

Never use `VITE_` variables for secrets. `.env.example` is a reference, not an automatically loaded config file. Environment proxy settings and HTTP redirects are not used by provider requests.

Before **every hosted request**, the UI displays the exact selected fields and question, destination, and payload size. The analyst must click **Approve & send this payload**. The server rejects stale/missing consent. Original files, raw extracted text, hashes/paths, unselected findings and conversation history are not sent. Selected finding interpretations and analyst review notes can contain evidence-derived text; the preview exposes this before transmission.

## Grounding and trust

Providers must return facts, hypotheses, and recommended actions as typed claims citing selected finding IDs. Unknown, absent and cross-case citations are rejected. Evidence is explicitly untrusted in the system prompt; it cannot supply instructions or invoke a shell. The minimal projection excludes raw strings/text and context snippets that commonly contain injected instructions. No model output is automatically executed.

**Citation validation is not semantic truth verification.** A model can misinterpret a valid citation. The UI labels model-authored content and asks analysts to verify it. Nothing here guarantees full prompt-injection resistance for an arbitrary model; tests cover context minimization, no tool surface, scoped citations, consent, and rejection of invalid output. All provider failures leave evidence and earlier conversation intact. Timeout, rate-limit, malformed-output and configuration errors offer a return to the deterministic guide.

“Use as report draft” copies a labeled narrative into the editable reporting screen. The analyst reviews and saves it before export. No conversation history from another case is retrieved or transmitted. A real local/hosted model was not provisioned during the rebuild; the provider boundary is verified with deterministic HTTP stubs.
