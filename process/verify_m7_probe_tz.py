# M7-1 probe: what does an AWARE occurred_at datetime actually get stored as?
# Runs against an in-memory SQLite (same dialect path as dev db). ASCII only.
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DB_ECHO"] = "false"

from datetime import datetime  # noqa: E402

from app import crud, database, schemas  # noqa: E402
from app.models import Base, FaultRole, User  # noqa: E402

database.init_models()
db = database.SessionLocal()

u = User(username="probe", password_hash="x", display_name="probe",
         role=FaultRole.admin, is_active=True, token_version=0)
db.add(u)
db.commit()

p = crud.create_pipeline(db, schemas.PipelineCreate(code="TZP", name="tz probe"))

CASES = [
    ("naive local 13:00", "2026-11-01T13:00:00"),
    ("aware +08:00 13:00", "2026-11-01T13:00:00+08:00"),
    ("aware UTC Z 05:00", "2026-11-01T05:00:00+00:00"),
]

print("=== validator output (schemas.FaultCreate) ===")
for label, iso in CASES:
    body = schemas.FaultCreate(
        pipeline_id=p.id, location="probe",
        occurred_at=datetime.fromisoformat(iso),
        symptom="probe symptom text",
    )
    v = body.occurred_at
    print(f"{label:22s} in={iso:30s} out={v!r} tzinfo={v.tzinfo}")

print("=== what lands in the DB (raw SQL) ===")
from sqlalchemy import text  # noqa: E402

for label, iso in CASES:
    body = schemas.FaultCreate(
        pipeline_id=p.id, location="probe",
        occurred_at=datetime.fromisoformat(iso),
        symptom="probe symptom text",
    )
    f = crud.create_fault(db, body, creator=u)
    raw = db.scalar(text(
        "select occurred_at from pipeline_faults where id=:i"), {"i": f.id})
    print(f"{label:22s} raw={raw!r} ORM_read={f.occurred_at!r} hour={f.occurred_at.hour}")
