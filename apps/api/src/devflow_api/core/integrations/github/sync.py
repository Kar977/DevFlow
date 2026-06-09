"""Mapping helpers that turn GitHub issues/PRs into Task fields."""

from typing import Any, TypedDict


class TaskFields(TypedDict):
    title: str
    description: str | None
    github_pr_url: str


def issue_to_task_fields(issue: dict[str, Any]) -> TaskFields:
    """Map a GitHub issue/PR JSON object to task creation fields."""
    return TaskFields(
        title=str(issue.get("title", "Untitled")),
        description=issue.get("body"),
        github_pr_url=str(issue["html_url"]),
    )
