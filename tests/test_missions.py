from fastapi.testclient import TestClient
from orbit.api import app
from orbit import service, storage as db

def mission(client, limit=12):
    return client.post("/missions",json={"title":"test","goal":"공개 준비 패키지 검토","mode":"mock","call_limit":limit}).json()

def complete(client, m):
    assert client.post(f"/missions/{m['id']}/start").status_code==200
    service.run(m["id"])
    return client.get(f"/missions/{m['id']}").json()

def test_full_flow_and_idempotent_export():
    with TestClient(app) as c:
        m=mission(c)
        assert c.post(f"/missions/{m['id']}/export").status_code==409
        m=complete(c,m)
        assert m["status"]=="review_required"
        assert len(m["artifacts"])==5
        decision={"version":m["version"],"package_hash":m["package_hash"]}
        assert c.post(f"/missions/{m['id']}/approvals",json=decision).status_code==200
        a=c.post(f"/missions/{m['id']}/export").json()
        b=c.post(f"/missions/{m['id']}/export").json()
        assert a==b

def test_revision_preserves_independent_artifacts_and_invalidates_approval():
    with TestClient(app) as c:
        m=complete(c,mission(c))
        old={"version":m["version"],"package_hash":m["package_hash"]}
        c.post(f"/missions/{m['id']}/approvals",json=old)
        r=c.post(f"/missions/{m['id']}/revisions",json={"version":1,"role":"campaign","instruction":"더 짧고 따뜻하게 작성"}).json()
        assert set(r["artifacts"])=={"pd","story","audience"}
        assert r["approval"] is None
        assert c.post(f"/missions/{m['id']}/approvals",json=old).status_code==409
        service.run(m["id"])
        fresh=c.get(f"/missions/{m['id']}").json()
        assert fresh["calls"]==7
        assert fresh["artifacts"]["story"]==m["artifacts"]["story"]
        assert fresh["artifacts"]["campaign"]["version"]==2
        assert c.post(f"/missions/{m['id']}/export").status_code==409

def test_limit_and_duplicate_start():
    with TestClient(app) as c:
        m=mission(c,5)
        c.post(f"/missions/{m['id']}/start")
        assert c.post(f"/missions/{m['id']}/start").status_code==409
        service.run(m["id"])
        assert c.post(f"/missions/{m['id']}/revisions",json={"version":1,"role":"story","instruction":"수정해 주세요"}).status_code==409

def test_bad_origin_and_missing():
    with TestClient(app) as c:
        assert c.post("/missions",headers={"Origin":"https://evil.example"},json={}).status_code==403
        assert c.get("/missions/missing").status_code==404

def test_failure_resume_does_not_repeat_success(monkeypatch):
    actual=service.generate
    def fail(role,context,mode,tools,on_request,on_usage):
        if role=="campaign":
            on_request("simulated_failure")
            raise RuntimeError("do not leak this")
        return actual(role,context,mode,tools,on_request,on_usage)
    with TestClient(app) as c:
        m=mission(c)
        monkeypatch.setattr(service,"generate",fail)
        m=complete(c,m)
        assert m["status"]=="failed" and m["calls"]==4
        assert "do not leak" not in str(m)
        monkeypatch.setattr(service,"generate",actual)
        m=complete(c,m)
        assert m["status"]=="review_required" and m["calls"]==6

def test_qa_warning_blocks_approval():
    with TestClient(app) as c:
        m=complete(c,mission(c))
        raw=db.get(m["id"])
        raw["artifacts"]["qa"]["report"]["needs_review"]=True
        db.save(raw)
        m=c.get(f"/missions/{m['id']}").json()
        assert c.post(f"/missions/{m['id']}/approvals",json={"version":1,"package_hash":m["package_hash"]}).status_code==409

def test_restart_marks_inflight_failed():
    with TestClient(app) as c:
        m=mission(c)
        raw=db.get(m["id"]);raw["status"]="running";raw["calls"]=1;db.save(raw)
    with TestClient(app) as c:
        m=c.get(f"/missions/{m['id']}").json()
        assert m["status"]=="failed" and m["calls"]==1
