from datetime import date, timedelta


def make_retry_leg(original_leg: str, year: int, month: int, day: int) -> str:
    parts = original_leg.split("-")
    if len(parts) >= 3:
        parts[-1] = f"{year:04d}{month:02d}{day:02d}"
        return "-".join(parts)
    return original_leg


def get_year_month_from_params(params: list[tuple[str, str]]) -> tuple[int, int] | None:
    for name, val in params:
        if name == "leg":
            parts = val.split("-")
            if len(parts) >= 3:
                date_part = parts[-1]
                if len(date_part) >= 6:
                    try:
                        year = int(date_part[:4])
                        month = int(date_part[4:6])
                        return year, month
                    except ValueError:
                        pass
    return None


def get_target_days(year: int, month: int) -> list[int]:
    next_month = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
    num_days = (next_month - timedelta(days=1)).day
    return list(range(1, num_days + 1))
