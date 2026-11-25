"""In-memory reproduction + fix candidate check. Dev DB is NOT touched.

Sequence mirrors app/crud.py assign_fault / reassign_fault, with the same
session settings as app/database.py (expire_on_commit=False, autoflush=False).

Case 1  assign_fault()          -> response assignee is None            (current bug)
Case 2  reassign_fault()        -> response assignee is the OLD handler (current bug)
Case 3  raw SQL row after case2 -> assignee_id is the NEW handler       (DB is fine)
Case 4  set relationship instead of raw FK -> response assignee correct  (fix candidate)

Run from backend/:  $env:PYTHONPATH="$PWD"; .venv\\Scripts\\python.exe ..\\process\\probe_assign_stale.py
"""

from datetime import datetime

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker, selectinload

from app import crud, schemas
from app.auth import hash_password
from app.models import Base, FaultRole, Pipeline, PipelineFault, User
from app.database import ensure_sqlite_dir

URL = "sqlite://"
ensure_sqlite_dir(URL)
engine = create_engine(URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

db = Session()

pipeline = Pipeline(code="L1", name="Line 1")
db.add(pipeline)
db.commit()


def mk_user(name: str, role: FaultRole) -> User:
    u = User(username=name, password_hash=hash_password("x"), display_name=name,
             role=role, is_active=True, token_version=0)
    db.add(u)
    db.commit()
    return u


admin = mk_user("admin", FaultRole.admin)
h1 = mk_user("handler1", FaultRole.handler)
h2 = mk_user("handler2", FaultRole.handler)

fault = PipelineFault(
    pipeline_id=pipeline.id,
    location="station-1",
    occurred_at=datetime.now(),
    symptom="symptom text long enough",
    created_by=admin,
)
db.add(fault)
db.commit()
fid = fault.id


def brief(u):
    return None if u is None else u.username


print("== Case 1: assign_fault (sets raw FK assignee_id) ==")
returned = crud.assign_fault(db, fid, h1.id, actor=admin)
out = schemas.FaultOut.model_validate(returned)
print("   db assignee_id =", db.scalar(select(PipelineFault.assignee_id).where(PipelineFault.id == fid)))
print("   response assignee =", brief(out.assignee), "  <-- expected handler1")

print("== Case 2: reassign_fault h1 -> h2 ==")
returned = crud.reassign_fault(db, fid, h2.id, "change reason", actor=admin)
out = schemas.FaultOut.model_validate(returned)
print("   db assignee_id =", db.scalar(select(PipelineFault.assignee_id).where(PipelineFault.id == fid)))
print("   response assignee =", brief(out.assignee), "  <-- expected handler2")

print("== Case 3: fresh session read (what GET /api/faults/{id} returns) ==")
db2 = Session()
out2 = schemas.FaultOut.model_validate(crud.get_fault(db2, fid))
print("   response assignee =", brief(out2.assignee), "  <-- correct after refresh")
db2.close()

print("== Case 4: fix candidate - assign the relationship, not the FK ==")
db3 = Session()
f = crud.get_fault(db3, fid)
f.assignee = None                      # un-assign to simulate pending/unassigned
db3.commit()
target = db3.get(User, h1.id)          # _load_handler equivalent
f.assignee = target                    # <-- relationship assignment
db3.commit()
again = crud.get_fault(db3, fid)       # same identity-mapped instance
out3 = schemas.FaultOut.model_validate(again)
print("   db assignee_id =", db3.scalar(select(PipelineFault.assignee_id).where(PipelineFault.id == fid)))
print("   response assignee =", brief(out3.assignee))
db3.close()

print("== Case 5: fix candidate - keep FK assignment + populate_existing on reload ==")
db4 = Session()
f = db4.scalar(select(PipelineFault).where(PipelineFault.id == fid))
f.assignee_id = h2.id
db4.commit()
reloaded = db4.scalar(
    select(PipelineFault)
    .options(selectinload(PipelineFault.pipeline),
             selectinload(PipelineFault.created_by),
             selectinload(PipelineFault.assignee))
    .where(PipelineFault.id == fid)
    .execution_options(populate_existing=True)
)
out4 = schemas.FaultOut.model_validate(reloaded)
print("   response assignee =", brief(out4.assignee), "  <-- expected handler2")
raw = db4.execute(text("select assignee_id from pipeline_faults where id=:i"), {"i": fid}).scalar()
print("   raw column assignee_id =", raw)
db4.close()
