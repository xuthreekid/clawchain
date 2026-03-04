# Security Policy

## Supported versions

This project is under active development. Security fixes are applied on the latest mainline version.

## Reporting a vulnerability

If you discover a security issue:

1. Do not open a public issue with exploit details.
2. Contact maintainers privately with:
   - impact summary
   - reproduction steps
   - affected files/versions
3. Allow reasonable time for triage and patching before public disclosure.

## Scope

Typical security-sensitive areas:

- secret/config handling (`backend/data/config.json`, `.env`)
- runtime logs/sessions under `backend/data/agents/`
- tool execution and path validation
