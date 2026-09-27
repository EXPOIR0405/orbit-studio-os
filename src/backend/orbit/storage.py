import copy
import threading
from sqlalchemy import create_engine, MetaData, Table, Column, String, JSON, select, update
from .config import DATABASE_URL

# Single-process local prototype. This lock is not a distributed worker lease.
lock = threading.RLock()
engine = create_engine(DATABASE_URL, **({"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}))
meta = MetaData()
missions = Table("orbit_missions", meta, Column("id", String(36), primary_key=True), Column("body", JSON, nullable=False))

def initialize():
    meta.create_all(engine)

def all_missions():
    with engine.connect() as conn:
        return [copy.deepcopy(x[0]) for x in conn.execute(select(missions.c.body))]

def get(mid):
    with engine.connect() as conn:
        row = conn.execute(select(missions.c.body).where(missions.c.id == mid)).first()
        if not row:
            raise KeyError(mid)
        return copy.deepcopy(row[0])

def save(m):
    with engine.begin() as conn:
        result = conn.execute(update(missions).where(missions.c.id == m["id"]).values(body=copy.deepcopy(m)))
        if not result.rowcount:
            conn.execute(missions.insert().values(id=m["id"], body=copy.deepcopy(m)))
