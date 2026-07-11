"""Schema-level tests for GitHubInstallation and Repository models."""

from typing import cast

from sqlalchemy import BigInteger, Table, UniqueConstraint
from sqlalchemy.sql.schema import ScalarElementColumnDefault

from devflow_api.core.models.github_installation import GitHubInstallation
from devflow_api.core.models.repository import Repository

_INSTALLATIONS_TABLE = cast("Table", GitHubInstallation.__table__)
_REPOSITORIES_TABLE = cast("Table", Repository.__table__)


def _unique_constraints(table: Table) -> dict[str, tuple[str, ...]]:
    return {
        str(c.name): tuple(col.name for col in c.columns)
        for c in table.constraints
        if isinstance(c, UniqueConstraint) and c.name is not None
    }


def test_github_installation_table_shape() -> None:
    table = _INSTALLATIONS_TABLE
    assert table.name == "github_installations"
    assert isinstance(table.c.installation_id.type, BigInteger)
    assert table.c.installation_id.unique
    assert table.c.organization_id.foreign_keys
    assert table.c.suspended_at.nullable
    assert table.c.created_by.nullable


def test_repository_table_shape() -> None:
    table = _REPOSITORIES_TABLE
    assert table.name == "repositories"
    assert isinstance(table.c.github_repo_id.type, BigInteger)
    default = table.c.tracked.default
    assert isinstance(default, ScalarElementColumnDefault)
    assert default.arg is False
    assert not table.c.tracked.nullable
    constraints = _unique_constraints(table)
    assert constraints["uq_repositories_installation_repo"] == (
        "github_installation_id",
        "github_repo_id",
    )


def test_repository_links_to_installation_and_org() -> None:
    table = _REPOSITORIES_TABLE
    fk_targets = {
        fk.column.table.name
        for col in (table.c.github_installation_id, table.c.organization_id)
        for fk in col.foreign_keys
    }
    assert fk_targets == {"github_installations", "organizations"}
