"""Only scoped read tools. No arbitrary URL, SQL, filesystem, shell or external writes."""
import time
from pydantic import BaseModel, Field, ConfigDict
from .memory import search_approved

class Query(BaseModel):
    model_config=ConfigDict(extra="forbid")
    query: str = Field(max_length=200)
class Source(BaseModel):
    model_config=ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1,max_length=40)

SCHEMAS={
    "search_sources": {"description":"현재 역할에 허용된 합성 자료에서 키워드 검색","schema":Query},
    "get_source": {"description":"현재 역할에 허용된 source_id의 원문 조회","schema":Source},
    "search_approved_memory": {"description":"같은 작품·입력 버전의 승인된 이전 결과 검색. 설정집의 진실을 대신하지 않음","schema":Query}
}
ALLOWLIST={
    "pd":set(SCHEMAS), "story":set(SCHEMAS), "audience":{"search_sources","get_source"},
    "campaign":set(SCHEMAS), "qa":set(SCHEMAS)
}
class ToolBox:
    def __init__(self,role,sources,mission_id,source_version,record):
        self.role=role;self.sources=sources;self.mission_id=mission_id
        self.source_version=source_version;self.record=record
    def definitions(self):
        return [{"type":"function","name":name,"description":SCHEMAS[name]["description"],
                 "strict":True,"parameters":SCHEMAS[name]["schema"].model_json_schema()}
                for name in sorted(ALLOWLIST[self.role])]
    def call(self,name,args):
        start=time.perf_counter()
        try:
            if name not in ALLOWLIST[self.role]:
                raise ValueError("도구 권한 없음")
            validated=SCHEMAS[name]["schema"].model_validate(args)
            if name=="get_source":
                result=[s for s in self.sources if s["id"]==validated.source_id]
                if not result:
                    raise ValueError("자료 접근 범위 밖의 source_id")
            elif name=="search_sources":
                words=validated.query.lower().split()
                result=[s for s in self.sources if not words or any(w in (s["text"]+" "+s["id"]).lower() for w in words)]
            else:
                result=search_approved(validated.query,self.source_version,self.mission_id,self.role)
            self.record({"tool":name,"status":"ok","result_count":len(result),
                         "source_ids":[s["id"] for s in result if "id" in s],"duration_ms":round((time.perf_counter()-start)*1000,2)})
            return result
        except Exception:
            self.record({"tool":name if name in SCHEMAS else "unregistered","status":"denied_or_invalid",
                         "result_count":0,"duration_ms":round((time.perf_counter()-start)*1000,2)})
            raise ValueError("도구 요청이 거절되었습니다.")
