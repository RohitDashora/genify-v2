# Security

## Reporting a vulnerability

Please **do not** open a public GitHub issue for undisclosed security problems.

- Use **[GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories)** for this repository (private report), if enabled for the fork or upstream you use, **or**
- Contact the repository maintainers through your organization’s usual security channel.

Include steps to reproduce, affected versions or commits, and impact where possible.

## Scope

This project is a **demo / reference application** for Databricks Apps, MCP, and Lakebase. It is **not** positioned as a production-hardened product; threat modeling, patching cadence, and operational security are **out of scope** for this repo as shipped.

Security in any deployment still depends on your **workspace configuration** (service principals, UC grants, secrets, network). See [docs/security-auth.md](docs/security-auth.md).

## Open-sourcing and secrets

Before publishing or forking publicly, use **[docs/public-repo-checklist.md](docs/public-repo-checklist.md)** and run **`./scripts/check_repo_hygiene.sh`** locally to ensure environment-specific files (for example `deploy.config.yaml`) are **not** tracked by git.
