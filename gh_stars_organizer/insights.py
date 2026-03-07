from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from gh_stars_organizer.models import Repository


def category_distribution(classifications: dict[str, str]) -> Counter:
    return Counter(classifications.values())


def technology_distribution(repositories: list[Repository]) -> Counter:
    counts: Counter = Counter()
    for repo in repositories:
        if repo.primary_language:
            counts[repo.primary_language] += 1
        for topic in repo.topics[:5]:
            counts[topic] += 1
    return counts


def detect_inactive(repositories: list[Repository], inactive_months: int = 18) -> list[Repository]:
    now = datetime.now(UTC)
    threshold_days = inactive_months * 30
    return [repo for repo in repositories if (now - repo.updated_at).days > threshold_days]


def detect_archived(repositories: list[Repository]) -> list[Repository]:
    return [repo for repo in repositories if repo.archived]


def detect_duplicates(repositories: list[Repository]) -> list[list[Repository]]:
    groups: dict[str, list[Repository]] = defaultdict(list)
    for repo in repositories:
        key = repo.name.lower().replace("-", "").replace("_", "")
        groups[key].append(repo)
    return [group for group in groups.values() if len(group) > 1]


def build_markdown_report(
    repositories: list[Repository],
    classifications: dict[str, str],
    report_path: Path,
    inactive_months: int = 18,
) -> Path:
    cat_counts = category_distribution(classifications)
    tech_counts = technology_distribution(repositories)
    archived = detect_archived(repositories)
    inactive = detect_inactive(repositories, inactive_months=inactive_months)
    duplicates = detect_duplicates(repositories)

    lines = [
        "# GitHub Stars Insights",
        "",
        f"Generated at: {datetime.now(UTC).isoformat()}",
        f"Total starred repositories: {len(repositories)}",
        "",
        "## Most Starred Categories",
        "",
    ]
    for category, count in cat_counts.most_common():
        lines.append(f"- {category}: {count} repos")

    lines.extend(["", "## Top Technologies", ""])
    for technology, count in tech_counts.most_common(15):
        lines.append(f"- {technology}: {count} repos")

    lines.extend(["", "## Repo Discovery Recommendations", ""])
    lines.append(f"- Archived repositories: {len(archived)}")
    lines.append(f"- Inactive repositories (>{inactive_months} months): {len(inactive)}")
    lines.append(f"- Potential duplicates: {sum(len(group) for group in duplicates)}")

    if archived:
        lines.extend(["", "### Archived candidates to unstar", ""])
        for repo in archived[:20]:
            lines.append(f"- {repo.full_name} ({repo.url})")

    if inactive:
        lines.extend(["", "### Inactive candidates to review", ""])
        for repo in inactive[:20]:
            lines.append(f"- {repo.full_name} (updated {repo.updated_at.date()})")

    if duplicates:
        lines.extend(["", "### Potential duplicate groups", ""])
        for group in duplicates[:20]:
            lines.append("- " + ", ".join(repo.full_name for repo in group))

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n")
    return report_path

