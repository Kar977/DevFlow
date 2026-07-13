"""Sentinel distinguishing "field not provided" from "field explicitly
set to null" in partial (PATCH) updates.

Optional fields on update methods default to ``UNSET`` instead of ``None``,
so ``None`` unambiguously means "clear this field" while omission means
"leave it unchanged". Pair with ``BaseModel.model_fields_set`` at the route
layer to know which fields were actually present in the request body.
"""

from typing import Final


class _UnsetType:
    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = _UnsetType()
Unset = _UnsetType
