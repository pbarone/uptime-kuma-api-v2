# Product

`uptime-kuma-api2` is a Python wrapper for the [Uptime Kuma](https://github.com/louislam/uptime-kuma)
Socket.IO API. It is a maintained **continuation** of the dormant
[`lucasheld/uptime-kuma-api`](https://github.com/lucasheld/uptime-kuma-api),
carried forward under the original MIT license with the original author's
copyright retained. It is not a hostile fork; credit the original author and
incorporated PR authors.

## Naming (easy to get wrong)

- **PyPI distribution:** `uptime-kuma-api2` (`pip install uptime-kuma-api2`)
- **Import package:** `uptime_kuma_api` (unchanged from upstream, so existing
  user code works as-is — never rename this)
- **GitHub repo:** `pbarone/uptime-kuma-api2` (standalone; renamed from
  `uptime-kuma-api-v2`, old URL redirects)
- The PyPI names `uptime-kuma-api` (original) and `uptime-kuma-api-v2`
  (an unrelated maintainer) are **not** this project.

## The one non-negotiable principle

**Backward compatibility with Uptime Kuma v1.x is sacred.** The library
supports Uptime Kuma 1.17+ through 2.x from a single codebase. Any
server-version-specific behavior must be gated behind
`parse_version(self.version)` checks so v1.x connections keep working. A change
that breaks v1.x is a regression, not a feature. See the backward-compatibility
policy in coding-standards steering before altering any public behavior.

## Audience

Users automate Uptime Kuma configuration (often via the companion Ansible
collection). They depend on stable public method signatures and return shapes.
Treat the public API as a contract.
