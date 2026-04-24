<p align="right"><b>English</b> · <a href="SECURITY.zh-CN.md">简体中文</a></p>

# Security Policy

## Reporting a vulnerability

Please **do not open a public GitHub issue** for security vulnerabilities.

Instead, use [GitHub Private Vulnerability Reporting](https://github.com/OWNER/caliper/security/advisories/new)
or email the maintainers directly (address available in the repository
`CODEOWNERS` file).

We will acknowledge receipt within **72 hours** and aim to ship a patch
within **14 days** for high-severity findings.

## Scope

This policy covers:

- Remote code execution or command injection via malformed SKILL.md / eval
  JSONL inputs
- Secrets or API keys leaked through logs, run directories, or error messages
- Bypasses of the budget governor (`caliper.governance.budget`) that could lead
  to uncapped API spend
- Prompt-injection vectors where an eval case or judge response can escape
  its role boundary

Bugs that are purely quality-of-life or accuracy issues should be reported
via the standard GitHub issue tracker.

## Supported versions

Only the `main` branch and the most recent tagged release receive security
fixes. Earlier versions will not be backported unless a high-impact RCE is
discovered.

## Disclosure policy

After a patch ships, we publish a GitHub Security Advisory with the CVE
identifier (if assigned), affected versions, fixed version, and credit to the
reporter (unless the reporter prefers anonymity).
