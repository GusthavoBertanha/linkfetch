# Security Policy

## Reporting a vulnerability

Do not publish working exploits or secrets in a public issue. Contact the
maintainer privately through the security reporting option on the repository.

Include the affected version, reproduction steps, expected impact, and any
suggested mitigation. Reports involving unsafe file paths, command execution,
credential exposure, or untrusted redirects are especially helpful.

## Scope

LinkFetch processes untrusted URLs and response metadata. Host adapters must
validate domains, sanitize file names, avoid shell execution, and reject page
content that is not a downloadable file.
