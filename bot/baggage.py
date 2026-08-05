import json
from pathlib import Path

DEFAULT_RULES = {
    "by_booking_class": {},
    "by_fare_basis_prefix": {},
    "default": {"cabin": 1, "checked": 0},
}


class BaggageResolver:
    def __init__(self, rules_path: str | Path | None = None):
        self.rules = DEFAULT_RULES.copy()
        if rules_path:
            path = Path(rules_path)
            if path.exists():
                with path.open(encoding="utf-8") as f:
                    loaded = json.load(f)
                self.rules = {
                    "by_booking_class": loaded.get("by_booking_class") or {},
                    "by_fare_basis_prefix": loaded.get("by_fare_basis_prefix") or {},
                    "default": loaded.get("default") or DEFAULT_RULES["default"],
                }

    def resolve(self, booking_class: str | None, fare_basis: str | None) -> tuple[int, int]:
        bc = (booking_class or "").strip().upper()
        fb = (fare_basis or "").strip().upper()

        by_class = self.rules.get("by_booking_class") or {}
        if bc and bc in by_class:
            rule = by_class[bc]
            return int(rule.get("cabin", 1)), int(rule.get("checked", 0))

        by_prefix = self.rules.get("by_fare_basis_prefix") or {}
        if fb:
            prefix = fb[0]
            if prefix in by_prefix:
                rule = by_prefix[prefix]
                return int(rule.get("cabin", 1)), int(rule.get("checked", 0))
            for key, rule in by_prefix.items():
                if fb.startswith(str(key).upper()):
                    return int(rule.get("cabin", 1)), int(rule.get("checked", 0))

        default = self.rules.get("default") or DEFAULT_RULES["default"]
        return int(default.get("cabin", 1)), int(default.get("checked", 0))
