import asyncio
import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from . import storage as db, service
from .models import NewMission, Decision, Revision

@asynccontextmanager
async def lifespan(app):
    db.initialize()
    with db.lock:
        for m in db.all_missions():
            if m["status"]=="running":
                m.update(status="failed",active_role=None,error="이전 실행이 중단되었습니다. 완료 결과를 유지한 채 재개할 수 있습니다.")
                service.event(m,"interrupted",m["error"])
                db.save(m)
    async def worker():
        while True:
            for m in db.all_missions():
                if m["status"]=="queued":
                    await asyncio.to_thread(service.run,m["id"])
            await asyncio.sleep(.5)
    task=asyncio.create_task(worker()) if os.getenv("ORBIT_DISABLE_WORKER")!="1" else None
    yield
    if task:
        task.cancel()

app=FastAPI(title="ORBIT local prototype",lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost","127.0.0.1","testserver","api"])

@app.middleware("http")
async def local_origin(request: Request, call_next):
    origin=request.headers.get("origin")
    if origin and origin not in ["http://localhost:3000","http://127.0.0.1:3000","http://localhost:8000","http://127.0.0.1:8000"]:
        return JSONResponse({"detail":"Origin not allowed"},status_code=403)
    return await call_next(request)

@app.exception_handler(KeyError)
async def missing(request, exc):
    return JSONResponse({"detail":"미션을 찾을 수 없습니다."},status_code=404)

@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({"detail":str(exc)},status_code=409)

@app.get("/health")
def health():
    return {"status":"ok","live_configured":bool(os.getenv("OPENAI_API_KEY")) and os.getenv("ORBIT_ENABLE_LIVE", "false").lower()=="true","live_enabled":os.getenv("ORBIT_ENABLE_LIVE", "false").lower()=="true","storage":db.engine.dialect.name,"local_only":True}

@app.get("/missions")
def listing():
    return [service.view(m) for m in reversed(db.all_missions())]

@app.post("/missions",status_code=201)
def create(req:NewMission):
    if req.mode=="live" and os.getenv("ORBIT_ENABLE_LIVE", "false").lower()!="true":
        raise HTTPException(403,"실제 모델 호출은 비활성화되어 있습니다.")
    if req.mode=="live" and not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(409,"서버에 모델 키가 설정되지 않았습니다.")
    return service.create(req)

@app.get("/missions/{mid}")
def get(mid:str):
    return service.view(db.get(mid))

@app.post("/missions/{mid}/start")
def start(mid:str):
    return service.queue(mid)

@app.post("/missions/{mid}/revisions")
def revise(mid:str,req:Revision):
    return service.revise(mid,req)

@app.post("/missions/{mid}/approvals")
def approve(mid:str,req:Decision):
    return service.approve(mid,req)

@app.post("/missions/{mid}/export")
def export(mid:str):
    return JSONResponse(service.export(mid),headers={"Content-Disposition":'attachment; filename="orbit-package.json"'})

@app.get("/missions/{mid}/events")
async def events(mid:str,request:Request):
    db.get(mid)
    try:
        cursor=int(request.headers.get("last-event-id","0"))
    except ValueError:
        raise HTTPException(400,"Invalid event cursor")
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            for e in db.get(mid)["events"]:
                if e["sequence"]>cursor:
                    cursor=e["sequence"]
                    yield f"id: {cursor}\ndata: {json.dumps(e,ensure_ascii=False)}\n\n"
            yield ": keepalive\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache"})
