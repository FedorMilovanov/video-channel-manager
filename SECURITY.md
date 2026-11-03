# Security policy

This file is the repository-level security entry point. The detailed
safety model is [docs/security.md](docs/security.md), and the current
operational authority is
[docs/operations/current-state.md](docs/operations/current-state.md).
Do not infer authorization to act on YouTube, VK, Telegram, or any other
provider from this file, a CI result, or a vulnerability report.

## Reporting a vulnerability

Please **do not post credentials, tokens, personal data, or exploitable
private details** in public GitHub issues, pull requests, discussions,
or CI logs.

If GitHub's **Report a vulnerability** option is available for this
repository, use it to send the maintainer a private report. Otherwise,
contact the repository maintainer privately before publishing sensitive
details. Do not include live credentials; provide a redacted minimal
reproducer, affected component/version or commit, impact, and the
conditions required to reproduce.

Do not attempt production exploitation, provider writes, replay,
deletion, or mutation to demonstrate a finding. Read-only evidence and
local tests are the default; every provider mutation needs separate,
exact authorization under the canonical operational policy.

## Supported scope

The actively developed source of truth is `main`. Historical
branches, archived artifacts, and third-party services are not
implicitly supported release channels. No response-time or remediation
SLA is promised by this policy.

A security report is evidence for investigation, not approval to
change remote accounts or to publish findings.
