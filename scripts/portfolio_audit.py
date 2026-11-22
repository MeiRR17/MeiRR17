#!/usr/bin/env python3
"""Read-only audit of the public GitHub projects featured in the profile README.

No third-party dependencies, GitHub writes, account tokens or profile rewrites.
Default mode checks the canonical public GitHub API; --offline checks only the
local README and referenced local images, without claiming online verification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ACCOUNT = "MeiRR17"
ROOT = Path(__file__).resolve().parents[1]
SECTION = re.compile(r"^#{2,6}\s+Explore the work\s*$", re.IGNORECASE)
HEADING = re.compile(r"^#{1,6}\s+\S")
PROJECT_LINK = re.compile(
    r"\[[^\]]+\]\(https://github\.com/MeiRR17/([A-Za-z0-9_.-]+)/?\)",
    re.IGNORECASE,
)
IMAGE_LINK = re.compile(r"""<img\b[^>]*\bsrc=["']([^"']+)["']""", re.IGNORECASE)
SLUG = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def collect_repositories(readme: str) -> list[str]:
    """Use the public portfolio table as the sole source of featured links."""
    in_section = False
    projects: list[str] = []
    seen: set[str] = set()
    for line in readme.splitlines():
        if not in_section:
            if SECTION.fullmatch(line.strip()):
                in_section = True
            continue
        if HEADING.match(line):
            break
        if not line.lstrip().startswith("|"):
            continue
        for slug in PROJECT_LINK.findall(line):
            if not SLUG.fullmatch(slug):
                raise ValueError("Unsafe repository slug in portfolio table")
            if slug.casefold() in seen:
                raise ValueError(f"Duplicate featured repository: {slug}")
            seen.add(slug.casefold())
            projects.append(slug)
    if not in_section:
        raise ValueError('README lacks the "Explore the work" section')
    if not projects:
        raise ValueError("No public repositories linked in the featured table")
    return projects


def check_local_images(document: str, root: Path) -> tuple[int, list[str]]:
    """Validate relative image paths without following links outside root."""
    issues = []
    count = 0
    for source in IMAGE_LINK.findall(document):
        if source.startswith(("https://", "http://")):
            continue  # Remote badges and counters are not assumed reliable.
        count += 1
        if not source.startswith("./assets/"):
            issues.append(f"Unexpected relative profile image: {source}")
            continue
        candidate = (root / source).resolve()
        if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
            issues.append(f"Missing or escaping local image: {source}")
    return count, issues


def fetch_public_repo(slug: str, timeout: float) -> dict:
    """Fetch metadata from a fixed API hostname; no user-supplied URLs."""
    url = f"https://api.github.com/repos/{ACCOUNT}/{slug}"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MeiRR17-profile-public-audit",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        # Repository metadata should be small; cap unexpected payloads.
        payload = response.read(512_001)
    if len(payload) > 512_000:
        raise ValueError(f"Unexpectedly large API response for {slug}")
    result = json.loads(payload)
    if not isinstance(result, dict):
        raise ValueError(f"Invalid API metadata for {slug}")
    return result


def audit(readme_path: Path, offline: bool, timeout: float) -> dict:
    readme_path = readme_path.resolve()
    document = readme_path.read_text(encoding="utf-8")
    projects = collect_repositories(document)
    images_checked, issues = check_local_images(document, readme_path.parent)

    rows = []
    for slug in projects:
        row = {
            "repository": f"{ACCOUNT}/{slug}",
            "url": f"https://github.com/{ACCOUNT}/{slug}",
            "status": "not_checked" if offline else "unverified",
            "default_branch": None,
            "last_push_utc": None,
        }
        if not offline:
            try:
                meta = fetch_public_repo(slug, timeout)
                canonical = str(meta.get("full_name", ""))
                if canonical.casefold() != row["repository"].casefold():
                    issues.append(f"{slug}: GitHub returned a different repository")
                    row["status"] = "mismatch"
                elif meta.get("private") is not False:
                    issues.append(f"{slug}: repository is not verified public")
                    row["status"] = "not_public"
                elif meta.get("disabled") or meta.get("archived"):
                    issues.append(f"{slug}: repository is disabled or archived")
                    row["status"] = "archived_or_disabled"
                else:
                    row["status"] = "public"
                if isinstance(meta.get("default_branch"), str):
                    row["default_branch"] = meta["default_branch"]
                pushed_at = meta.get("pushed_at")
                if isinstance(pushed_at, str) and re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", pushed_at
                ):
                    row["last_push_utc"] = pushed_at
            except HTTPError as exc:
                issues.append(
                    f"{slug}: GitHub API returned HTTP {exc.code}; "
                    "check visibility, rate limits or repository availability"
                )
            except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
                issues.append(f"{slug}: unable to verify public repository ({type(exc).__name__})")
        rows.append(row)

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "offline_readme_only" if offline else "public_github_api",
        "profile_file": readme_path.name,
        "featured_repositories": rows,
        "local_images_checked": images_checked,
        "issue_count": len(issues),
        "issues": issues,
        "notice": (
            "GitHub metadata shows repository visibility and last push only; "
            "it does not verify software quality, releases, activity or deployment."
        ),
    }


def markdown(report: dict) -> str:
    lines = [
        "# Featured public repository audit",
        "",
        f"Mode: **{report['mode']}** · Generated: {report['generated_at_utc']}",
        "",
        "| Repository | Visibility check | Default branch | Last push (UTC) |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["featured_repositories"]:
        name = item["repository"].split("/", 1)[1]
        lines.append(
            f"| [{name}]({item['url']}) | {item['status']} "
            f"| {item['default_branch'] or '—'} | {item['last_push_utc'] or '—'} |"
        )
    lines.extend([
        "",
        f"Local images checked: {report['local_images_checked']}",
        f"Issues: {report['issue_count']}",
    ])
    if report["issues"]:
        lines.extend(["", "## Verification issues", ""])
        lines.extend(f"- {item}" for item in report["issues"])
    lines.extend(["", report["notice"]])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--readme", type=Path, default=ROOT / "README.md",
        help="profile README to inspect (default: this repository's README.md)",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="inspect only local links and images; do not claim repos were verified",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument(
        "--timeout", type=float, default=8.0,
        help="GitHub API timeout in seconds, between 1 and 30",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 30:
        parser.error("--timeout must be between 1 and 30 seconds")
    try:
        report = audit(args.readme, args.offline, args.timeout)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Profile audit could not start: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(markdown(report))
    return 1 if report["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
