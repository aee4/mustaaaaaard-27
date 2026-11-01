from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ACCRA = ZoneInfo("Africa/Accra")


class Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def activity_date(value: datetime) -> date:
    return value.astimezone(ACCRA).date()


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = datetime.combine(week_start(activity_date(now)), time.min, ACCRA)
    return start.astimezone(UTC), (start + timedelta(days=7)).astimezone(UTC)
