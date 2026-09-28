import hashlib
import json
import uuid
import time
from datetime import datetime, timezone
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from . import storage as db
from .config import ROOT
from .models import NewMission
from .provider import generate, repair, live_enabled
from .routing import route
from .tools import ToolBox
from .evaluation import evaluate

ROLES = ["pd", "story", "audience", "campaign", "qa"]

def event(m, kind, detail):
    m["events"].append({"sequence":len(m["events"])+1, "time":datetime.now(timezone.utc).isoformat(), "type":kind, "detail":detail})

def package_hash(m):
    data = {"version":m["version"], "input":m["input"], "artifacts":m["artifacts"]}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def create(request: NewMission, input_data=None):
    """input_data는 평가 스크립트가 평가 미션 자료를 넣을 때만 쓴다. API는 합성 EP.12 고정"""
    if request.mode == "live" and not live_enabled():
        raise ValueError("실제 모델 호출이 비활성화되어 있습니다.")
    m = {"id":str(uuid.uuid4()), **request.model_dump(), "version":1, "status":"draft", "active_role":None,
         "input":input_data or json.loads((ROOT / "data" / "episode-12.json").read_text(encoding="utf-8")),
         "artifacts":{}, "history":[], "events":[], "calls":0, "usage":[], "approval":None, "error":None, "instructions":{},
         "route":route(request.goal,request.workflow), "traces":[]}
    event(m, "created", "합성 입력을 고정했습니다: " + m["input"]["title"])
    event(m, "routed", m["route"]["reason"] + " / " + " → ".join(m["route"]["roles"]))
    with db.lock:
        db.save(m)
    return view(m)

def view(m):
    return {**m, "package_hash":package_hash(m)}

def queue(mid):
    with db.lock:
        m = db.get(mid)
        if m["mode"] == "live" and not live_enabled():
            raise ValueError("실제 모델 호출이 비활성화되어 있습니다.")
        if m["status"] not in ["draft", "failed"]:
            raise ValueError("현재 상태에서는 실행할 수 없습니다.")
        if m["calls"] >= m["call_limit"]:
            raise ValueError("호출 한도에 도달했습니다. 새 미션을 만드세요.")
        m.update(status="queued", error=None)
        event(m,"queued","실행 대기. 완료된 역할 결과는 재사용합니다.")
        db.save(m)
        return view(m)

def revise(mid, req):
    with db.lock:
        m = db.get(mid)
        if req.version != m["version"] or m["status"] not in ["review_required","approved","exported"]:
            raise ValueError("미션이 변경되었거나 수정할 수 없는 상태입니다.")
        if m["mode"] == "live" and not live_enabled():
            raise ValueError("실제 모델 호출이 비활성화되어 있습니다.")
        if req.role not in m["route"]["roles"]:
            raise ValueError("이 미션에 배정되지 않은 역할입니다.")
        affected = [r for r in (["story","campaign","qa"] if req.role == "story" else ["campaign","qa"]) if r in m["route"]["roles"]]
        if m["calls"] + len(affected)*(2 if m["mode"]=="live" else 1) > m["call_limit"]:
            raise ValueError("재작업에 필요한 호출 한도가 부족합니다.")
        m["history"].append({"version":m["version"],"artifacts":m["artifacts"],"approval":m["approval"]})
        m["artifacts"] = {k:v for k,v in m["artifacts"].items() if k not in affected}
        m["version"] += 1
        m["instructions"][req.role] = req.instruction
        m.update(status="queued", approval=None, error=None)
        event(m,"revision",req.role + " 수정 요청: " + req.instruction)
        db.save(m)
        return view(m)

def approve(mid, req):
    with db.lock:
        m = db.get(mid)
        if m["status"] != "review_required" or req.version != m["version"] or req.package_hash != package_hash(m):
            raise ValueError("최신 검토 패키지만 승인할 수 있습니다.")
        qa = m["artifacts"].get("qa",{}).get("report",{})
        # warning은 운영자가 확인하고 승인할 수 있다. 공개하면 안 되는 blocker만 승인을 막음
        if not qa or any(f["severity"]=="blocker" for f in qa.get("findings",[])):
            raise ValueError("QA 차단 항목을 수정한 뒤 승인하세요.")
        m["approval"] = {"package_hash":req.package_hash, "version":req.version, "actor":"local-operator"}
        m["status"] = "approved"
        event(m,"approved","운영자가 현재 패키지를 승인했습니다.")
        db.save(m)
        return view(m)

def export(mid):
    with db.lock:
        m = db.get(mid)
        if m["status"] not in ["approved","exported"] or not m["approval"] or m["approval"]["package_hash"] != package_hash(m):
            raise ValueError("유효한 승인이 필요합니다.")
        result = {"mission":m["title"],"version":m["version"],"mode":m["mode"],"synthetic":True,
                  "package_hash":package_hash(m),"approval":m["approval"],"input":m["input"],"artifacts":m["artifacts"]}
        if m["status"] != "exported":
            m["status"]="exported"
            event(m,"exported","승인 패키지를 내보냈습니다. 외부 게시 없음.")
            db.save(m)
        return result

def context_for(m, role):
    sources = m["input"]["sources"]
    if role == "campaign":
        sources = [s for s in sources if not s.get("spoiler") and s["type"] != "script"]
    elif role == "audience":
        sources = [s for s in sources if s["type"] == "feedback"]
    elif role == "story":
        sources = [s for s in sources if s["type"] in ["script","bible"]]
    deps = {"pd":[], "story":["pd"],"audience":["pd"],"campaign":["story","audience"],"qa":["story","audience","campaign"]}[role]
    # Campaign sees only story's revision draft, never raw spoiler excerpts.
    artifacts = {k:m["artifacts"][k]["report"] for k in deps if k in m["artifacts"]}
    if role == "campaign" and "story" in artifacts:
        artifacts["story"] = {"draft":artifacts["story"]["draft"]}
    return {"goal":m["goal"],"route":m["route"],"sources":sources,"previous_results":artifacts,"revision_instruction":m["instructions"].get(role,"")}

def run_role(mid, role):
    with db.lock:
        m = db.get(mid)
        if role in m["artifacts"]:
            return
        if m["mode"]=="live" and not live_enabled():
            raise ValueError("Live model execution is disabled")
        m["active_role"] = role
        event(m,"started",role + " 실행")
        db.save(m)
        context = context_for(m,role)
    trace_id=str(uuid.uuid4())
    started=time.perf_counter()
    with db.lock:
        current=db.get(mid)
        current["traces"].append({"id":trace_id,"role":role,"version":m["version"],"reason":m["route"]["reason"],
                                  "status":"running","tools":[],"requests":[],"evaluation":None,"duration_ms":None})
        db.save(current)
    def record_tool(record):
        with db.lock:
            current=db.get(mid)
            next(t for t in current["traces"] if t["id"]==trace_id)["tools"].append(record)
            db.save(current)
    def reserve(reason):
        with db.lock:
            current=db.get(mid)
            if current["mode"]=="live" and not live_enabled():
                raise ValueError("Live calls disabled")
            if current["calls"]>=current["call_limit"]:
                raise ValueError("Call budget exhausted")
            current["calls"]+=1
            next(t for t in current["traces"] if t["id"]==trace_id)["requests"].append({"reason":reason,"status":"reserved"})
            db.save(current)
    def record_usage(usage):
        with db.lock:
            current=db.get(mid)
            current["usage"].append({"role":role,"trace_id":trace_id,**usage})
            next(t for t in current["traces"] if t["id"]==trace_id)["requests"][-1]["status"]="completed"
            db.save(current)
    toolbox=ToolBox(role,context["sources"],mid,m["input"]["version"],record_tool)
    try:
        report=generate(role,context,m["mode"],toolbox,reserve,record_usage)
        evaluation=evaluate(role,report,context["sources"],context["previous_results"])
        if not evaluation["passed"]:
            # 게이트에 걸리면 실패한 항목을 알려 주고 한 번만 다시 받는다. 호출 예산은 reserve가 그대로 검사
            failed=[g for g,ok in evaluation["gates"].items() if not ok]
            report=repair(role,context,m["mode"],report,failed,reserve,record_usage)
            evaluation={**evaluate(role,report,context["sources"],context["previous_results"]),"repaired_from":failed}
        with db.lock:
            current=db.get(mid)
            trace=next(t for t in current["traces"] if t["id"]==trace_id)
            trace.update(evaluation=evaluation,duration_ms=round((time.perf_counter()-started)*1000,2),status="completed" if evaluation["passed"] else "evaluation_failed")
            db.save(current)
        if not evaluation["passed"]:
            raise ValueError("Evaluation gate failed")
    except Exception:
        with db.lock:
            current=db.get(mid)
            trace=next(t for t in current["traces"] if t["id"]==trace_id)
            trace.update(status="failed",duration_ms=round((time.perf_counter()-started)*1000,2))
            for request in trace["requests"]:
                if request["status"]=="reserved":
                    request["status"]="failed_or_usage_unknown"
            db.save(current)
        raise
    with db.lock:
        current = db.get(mid)
        current["artifacts"][role]={"version":current["version"],"report":report.model_dump()}
        event(current,"completed",role + " 완료")
        db.save(current)

class State(TypedDict):
    mid: str

def node(role):
    def invoke(state):
        run_role(state["mid"],role)
        return {}
    return invoke

def next_role(state):
    m=db.get(state["mid"])
    return next((r for r in m["route"]["roles"] if r not in m["artifacts"]), END)

builder = StateGraph(State)
for role in ROLES:
    builder.add_node(role,node(role))
builder.add_conditional_edges(START,next_role)
for role in ROLES:
    builder.add_conditional_edges(role,next_role)
graph = builder.compile()

def run(mid):
    with db.lock:
        m=db.get(mid)
        if m["status"]!="queued":
            return
        m["status"]="running"
        db.save(m)
    try:
        graph.invoke({"mid":mid})
        with db.lock:
            m=db.get(mid)
            m.update(status="review_required",active_role=None)
            event(m,"review","산출물과 QA를 확인하고 승인 또는 수정 요청하세요.")
            db.save(m)
    except Exception as exc:
        # Never persist provider exception text: it may contain request data or credentials.
        with db.lock:
            m=db.get(mid)
            code=getattr(exc,"status_code",None)
            reason = {401:"모델 인증 실패",429:"모델 한도 또는 크레딧 부족"}.get(code,"역할 실행 실패: 연결·출력·근거를 확인하세요.")
            m.update(status="failed",active_role=None,error=reason)
            event(m,"failed",reason)
            db.save(m)
