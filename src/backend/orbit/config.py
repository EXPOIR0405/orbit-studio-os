import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///" + str(ROOT / "work" / "studio.db")
MODEL = os.getenv("ORBIT_MODEL_ID") or "gpt-5.4-mini"
(ROOT / "work").mkdir(exist_ok=True)
