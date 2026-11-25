# M7-2 / M7-3 probe: what do PATCH symptom='     ' and PATCH priority=null
# actually return today? Uses a temp file sqlite so the app engine and the
# TestClient portal thread share one database. ASCII only.
import os
import tempfile

_DB = os.path.join(tempfile.gettempdir(), "m7_probe.sqlite")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["DB_ECHO"] = "false"

from datetime import datetime, timedelta  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app import database  # noqa: E402
from app.auth import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, FaultRole, Pipeline, User  # noqa: E402

Base.metadata.create_all(database.engine)
db = database.SessionLocal()

admin = User(username="probe_admin", password_hash="x", display_name="a",
             role=FaultRole.admin, is_active=True, token_version=0)
db.add(admin)
db.add(Pipeline(code="PRB", name="probe"))
db.commit()

app.dependency_overrides[database.get_db] = lambda: db
app.dependency_overrides[get_current_user] = lambda: admin

client = TestClient(app)
body = {
    "pipeline_id": 1,
    "location": "probe place",
    "occurred_at": (datetime.now() - timedelta(minutes=10)).isoformat(),
    "symptom": "probe symptom text",
}
r = client.post("/api/faults", json=body)
print("POST create ->", r.status_code)
fid = r.json()["id"]

CASES = {
    "priority null": {"priority": None},
    "symptom spaces": {"symptom": "     "},
    "symptom padded": {"symptom": "  chong dian ti  "},
    "handling_note null": {"handling_note": None},
    "POST create symptom spaces": None,
    "location null": {"location": None},
    "symptom null": {"symptom": None},
    "location trailing spaces": {"location": "probe place  "},
}
for label, payload in CASES.items():
    if payload is None:
        resp = client.post("/api/faults", json={**body, "symptom": "     "})
    else:
        resp = client.patch(f"/api/faults/{fid}", json=payload)
    print(f"{label:32s} -> {resp.status_code} {str(resp.text)[:150]}")

print("GET detail ->", client.get(f"/api/faults/{fid}").json().get("symptom"))
