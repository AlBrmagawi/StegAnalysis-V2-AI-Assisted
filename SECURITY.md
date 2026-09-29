# Security policy

## Supported scope

Security fixes target the current V2 code on `main`. The historical project and its unverified executables are not maintained by this workbench. There is no promised response-time SLA.

The application is intended for one trusted analyst on a local machine. It has no multi-user authentication and must not be exposed as a public service. Parser processes have resource limits; native execution is not an OS sandbox. Read the [security and privacy boundaries](docs/security.md) before handling hostile inputs.

## Report a vulnerability

Use GitHub's private **[Report a vulnerability](https://github.com/AlBrmagawi/StegAnalysis-V2-AI-Assisted/security/advisories/new)** flow. Do not post exploit details, evidence files or credentials in a public issue.

Include the affected revision, platform, launch method, reproduction steps, expected security boundary, and a minimal benign reproducer where possible. Describe impact and any mitigation you have verified. Share only data you are authorized to disclose.

If private reporting is unavailable, contact the repository owner through their GitHub profile to arrange a private channel before sending sensitive details.

## Handling case data

Keep evidence, extracted artifacts, notes, reports, provider keys and model weights out of commits and issue attachments. `.data/`, `.env` and generated outputs are ignored. Use a disposable analysis environment for hostile evidence and back up case storage while the service is stopped. Dependency and application updates do not establish forensic accuracy; validate conclusions independently.
