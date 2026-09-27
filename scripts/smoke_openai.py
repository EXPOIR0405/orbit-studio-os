import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"/"backend"))
from orbit.config import MODEL
import os
if os.getenv("ORBIT_ENABLE_LIVE", "false").lower() != "true":
    print({"ok":False,"reason":"Live calls disabled; explicit authorization required."})
    sys.exit(2)
from openai import OpenAI
from pydantic import BaseModel
class Check(BaseModel):
    ready: bool
try:
    r=OpenAI(timeout=30,max_retries=0).responses.parse(model=MODEL,store=False,max_output_tokens=40,input="Return ready true.",text_format=Check)
    print({"ok":bool(r.output_parsed and r.output_parsed.ready),"model":MODEL,"tokens":r.usage.total_tokens})
except Exception as e:
    print({"ok":False,"error_type":type(e).__name__,"status":getattr(e,"status_code",None)})
    sys.exit(1)
