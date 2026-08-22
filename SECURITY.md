# Security Notes

Threat model: this service is designed to run **inside a private network behind an authenticating gateway**
(such as [auth-gateway](https://github.com/hari2353/auth-gateway)). It performs no authN of its own by design.

## Controls in place

- **Input validation**: every POST body is a Pydantic model; `k`/`limit` query params are range-bounded
- **No SQL surface**: storage is CSV + JSONL; no string-interpolated queries exist to inject
- **LLM output treated as untrusted**: extractor responses are parsed as strict JSON, coerced to plain
  strings, and used *only* as lookup labels against the taxonomy — never interpolated into commands,
  templates, or storage keys. Prompt-injection payloads cannot escalate beyond "unknown skill" candidates,
  which the lifecycle engine quarantines as `provisional`
- **Security headers** (`nosniff`, `DENY`, `no-store`) on all responses
- **Secrets**: LLM keys come from env vars only (`SKILLS_LLM_API_KEY`); nothing is logged or persisted;
  no secrets are committed (CI installs public deps only)
- **Graceful degradation**: LLM failures fall back to rule-based extraction and are flagged
  (`degraded_to_rules: true`) rather than exposing stack traces

## Known gaps (documented, deliberate for the demo scope)

- No per-tenant isolation inside the taxonomy store — production deployments would shard per tenant and
  enforce object-level authorization at the gateway/service layer
- No rate limiting — front with a reverse proxy or API management layer
- Snapshot writes are local-disk only; multi-instance deployments need shared storage with file locking

## Reporting

Open an issue or contact the maintainer. Do not open PRs containing suspected exploitable payloads.
