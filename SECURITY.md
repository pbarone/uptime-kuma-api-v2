# Security Policy

## Supported versions

Security fixes are applied to the latest released version of `uptime-kuma-api2`.
Please make sure you can reproduce an issue on the current release before
reporting.

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Report privately using GitHub's private vulnerability reporting:

1. Go to the [Security advisories page](https://github.com/pbarone/uptime-kuma-api2/security/advisories/new).
2. Click **Report a vulnerability** and describe the issue, including a
   reproduction if possible.

This keeps the report private until a fix is available. You'll get a response
as soon as the maintainer is able; please allow reasonable time before any
public disclosure.

## Scope

This library is a client wrapper for the Uptime Kuma Socket.IO API. It handles
credentials and API tokens on behalf of the caller. Relevant concerns include,
for example, accidental logging of secrets, unsafe handling of TLS verification,
or dependency vulnerabilities.

Vulnerabilities in **Uptime Kuma itself** (the server) should be reported to the
[Uptime Kuma project](https://github.com/louislam/uptime-kuma), not here.

## Handling secrets in reports

When sharing reproductions or logs, redact real tokens, passwords, and hostnames.
