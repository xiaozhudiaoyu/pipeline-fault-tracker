"""Timezone fix probe: run the real app code with the process timezone forced to UTC
(the backend container default) and print what the validator / clock factory return.

Read-only: no database, no HTTP, no writes. Mounted into a throwaway container.
"""
import time
from datetime import datetime, timedelta, timezone

print("process tzname      :", time.tzname)
print("process naive now   :", datetime.now().isoformat(timespec="seconds"))

try:  # pre-fix image has no timeutil module; fall back to the same +08 reference clock
    from app import timeutil

    def _biz_now() -> datetime:
        return timeutil.business_now()
except ImportError:  # pragma: no cover - baseline branch on purpose
    def _biz_now() -> datetime:
        return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)

from app.config import settings  # noqa: E402
from app.models import _local_now  # noqa: E402
from app.schemas import FaultCreate  # noqa: E402

print("business offset (h) :", getattr(settings, "business_utc_offset_hours", "n/a (pre-fix code)"))
print("business_now()      :", _biz_now().isoformat(timespec="seconds"))
print("_local_now()        :", _local_now().isoformat(timespec="seconds"))

beijing_wall = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None, microsecond=0)
print("beijing wall clock  :", beijing_wall.isoformat())

body = {
    "pipeline_id": 1,
    "location": "P1",
    "occurred_at": beijing_wall.isoformat(),
    "symptom": "probe symptom text",
}
try:
    fc = FaultCreate(**body)
    print("RESULT              : ACCEPTED, stored wall clock =", fc.occurred_at.isoformat())
    print("wall clock preserved:", fc.occurred_at == beijing_wall)
except ValueError as exc:
    print("RESULT              : REJECTED ->", exc.errors()[0]["msg"].encode("unicode_escape").decode())

# future beyond tolerance must still be rejected (no regression on the guard itself)
future = (_biz_now() + timedelta(hours=1)).isoformat()
try:
    FaultCreate(**{**body, "occurred_at": future})
    print("FUTURE CHECK        : BROKEN (future accepted)")
except ValueError:
    print("FUTURE CHECK        : still rejects +1h")

# Z-suffixed input normalises to the business wall clock, not the process one
z_input = FaultCreate(**{**body, "occurred_at": "2026-11-01T05:00:00Z"})
print("Z input normalised  :", z_input.occurred_at.isoformat(), "(expect 13:00 business clock)")
