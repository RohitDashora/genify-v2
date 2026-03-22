# Public repository checklist

Use this before making the repository **public** or widely forked. It complements [SECURITY.md](../SECURITY.md) and [docs/security-auth.md](security-auth.md).

## Secrets and environment-specific config

| Item | What to verify |
|------|----------------|
| **`deploy.config.yaml`** | Must **not** be committed. It is [gitignored](../.gitignore) (copy from [`deploy.config.example.yaml`](../deploy.config.example.yaml)). Run `./scripts/check_repo_hygiene.sh` to confirm it is not tracked. |
| **`.env`, `.databrickscfg`, `*.pem`, keys** | Also gitignored; ensure they were never committed in history (`git log --all -- .env` etc.). |
| **Warehouse / workspace IDs** | If examples in docs use placeholders, keep them clearly fake (`<warehouse-id>`). Real IDs belong only in local `deploy.config.yaml`. |

## History (optional hardening)

If `deploy.config.yaml` or secrets were ever committed, **removing the file is not enough** — rotate any exposed credentials (PATs, warehouse bindings if sensitive) and consider `git filter-repo` or a fresh repo for a clean public history.

## Cursor IDE assets (`.cursor/`)

The repo [gitignore](../.gitignore) currently ignores **all of `.cursor/`**, so **rules and skills under `.cursor/` are not part of a clone** unless you change that.

- **Leave as-is** if Cursor content is personal/local only.
- **To ship shared rules/skills**, replace the single `.cursor/` ignore with patterns that ignore local junk but allow `rules/` and `skills/` (see comments in `.gitignore`), then `git add` what you want public.

## License and notices

- [LICENSE](../LICENSE) is Apache-2.0; keep `NOTICE` if you add third-party attribution files later.
- Headers on new files: follow repo convention (Apache-2.0 is already stated at repo level).

## Automation

From the repository root:

```bash
./scripts/check_repo_hygiene.sh
```

Exit code `0` means no tracked sensitive filenames were found. Re-run after any `.gitignore` change.

## Documentation

- [README.md](../README.md) and [docs/README.md](README.md) already state **demo / reference** scope.
- Point contributors at this checklist from [CONTRIBUTING.md](../CONTRIBUTING.md) when opening the repo to external PRs.
