# Featured project audit (read-only)

The profile `README.md` is curated by hand. The `scripts/portfolio_audit.py` utility checks whether the **public projects already linked in the “Explore the work” table** still resolve to public, non-archived GitHub repositories. It also checks relative `./assets/` image references used by the profile.

The tool **does not** generate commits, publish releases, rewrite the README, change links, increase GitHub activity, scrape user profiles, inspect private repositories, or authenticate with your GitHub account. It makes only public GET requests to the official GitHub REST API when online mode is selected.

## Requirements

Python 3.9+ only; no third-party dependencies, GitHub token, `pip install`, account connector or browser automation required.

From the cloned profile repository:

```bash
# Default: check local SVGs + public repository metadata; human-readable stdout
python3 scripts/portfolio_audit.py

# Machine-readable stdout for optional local review tooling
python3 scripts/portfolio_audit.py --format json

# Fully offline (no HTTP requests): local assets and table format only
python3 scripts/portfolio_audit.py --offline

# Optional alternate local README; the profile itself remains untouched
python3 scripts/portfolio_audit.py --readme ./README.md --timeout 10
```

Online mode reads the GitHub public endpoint `https://api.github.com/repos/MeiRR17/<name>` for each featured repository in the table. It reports the repository's verified visibility, default branch and GitHub's `pushed_at` metadata field. **A recent push is not evidence of quality, deployment, stable release, code review, successful tests or legitimate activity**, and no such score is generated.

The script checks that the API's canonical `full_name` matches the linked repository. Private or archived repositories, missing repositories, response errors and rate limits are reported as issues. Links are discovered from the table instead of being duplicated in a hardcoded list.

## Output, exit codes and privacy

The default output is a Markdown table printed to **stdout**. `--format json` prints a structured report with `schema_version: 1`, a UTC generation time, individual repositories, local-image count and a list of issues. Neither mode saves a file. If you want to keep a local snapshot, explicitly redirect stdout:

```bash
python3 scripts/portfolio_audit.py --format json > portfolio-audit-local.json
```

Keep locally saved snapshots out of Git unless you intentionally want to publish their contents. A snapshot is a point-in-time observation, not a continuous GitHub monitor.

- Exit **0**: no detected issues in the selected mode.
- Exit **1**: a missing/broken local image, unexpected table content, a non-public/archived featured repository, or an incomplete online verification.
- Exit **2**: invalid CLI arguments.
- In `--offline` mode every repository is labelled **`not_checked`**, even when the local checks succeed. Never interpret a successful offline run as confirmation that a repository is public.

The public GitHub API limits anonymous requests. HTTP 403/429 or network failures yield **unverified** status and a failing exit code rather than declaring success. No token is accepted or printed. Remote image badges/counters are ignored; only relative profile images are checked.

## Design boundaries

This tool is intentionally a small **audit utility**, not a README generator or auto-committer. The profile's professional positioning, text, graphics and project selection stay under human editorial control. Only the five links currently present in the featured table are inspected; other personal/private projects, all-star counts, contributions, PR activity, branches, issues and releases are not enumerated. New featured links added manually to that table will be included the next time the tool runs.

This code has been committed on a feature branch for owner review. **No script run, tests, network query, validation or deployment was performed as part of the development pass.**
