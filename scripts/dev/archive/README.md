# Archived scripts

Old / superseded tools kept for reference. **Not used by the pack** — the active
tools live one level up in `scripts/dev/`.

| Archived script | Replaced by | Why archived |
|---|---|---|
| `resolve_manifest_urls.ps1` | `scripts/dev/generate_mod_downloads.py` | One-off with hardcoded absolute paths (zip location, a personal scratch dir, the instance path). The generator does the same job pack-agnostically and merges non-destructively. |
| `extract_emc_data.py` | `scripts/dev/emc_audit.py` | Hardcoded exact jar filename (`ProjectE_Integration-1.20.1-7.2.5.jar`), required the non-stdlib `toml` package, and duplicated the EMC audit. Its unique jar-scan was folded into `emc_audit.py` (which finds the jar by glob, any version). |

Safe to delete this folder entirely if you don't need the history.
