from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Filter:
    id: str
    user_id: str
    limit: int

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> Filter | None:
        if not isinstance(doc, dict):
            return None

        raw_id = doc.get("_id")
        if raw_id is None:
            filter_id = ""
        elif isinstance(raw_id, dict) and "$oid" in raw_id:
            filter_id = str(raw_id["$oid"])
        else:
            filter_id = str(raw_id)

        user_id = str(doc.get("user_id") or "").strip()
        preferences = doc.get("preferences")
        if not isinstance(preferences, dict):
            return None

        limit_val = preferences.get("limit")
        if limit_val is None:
            return None

        try:
            limit = int(limit_val)
        except (TypeError, ValueError):
            return None

        if not user_id or limit < 1 or limit > 31:
            return None

        return cls(
            id=filter_id,
            user_id=user_id,
            limit=limit,
        )
