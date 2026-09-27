"""Approved, versioned memory from the application database; no unreviewed writes."""
from . import storage as db

def search_approved(query, source_version, exclude_id, role="qa", limit=3):
    words=set(query.lower().split())
    matches=[]
    for m in db.all_missions():
        if m["id"]==exclude_id or m.get("status") not in ["approved","exported"]:
            continue
        if m["input"]["version"]!=source_version or m["input"]["title"]!="별빛식당 · EP.12":
            continue
        if not m.get("approval"):
            continue
        allowed={"campaign","audience"} if role=="campaign" else set(m["artifacts"])
        text=" ".join(a["report"]["summary"] for r,a in m["artifacts"].items() if r in allowed)
        score=sum(1 for w in words if w in (text+" "+m["goal"]).lower())
        if words and score==0:
            continue
        matches.append({"mission_id":m["id"],"version":m["version"],"package_hash":m["approval"]["package_hash"],
                        "summary":text[:600],"score":score,"kind":"approved_result_not_canon"})
    return sorted(matches,key=lambda x:(-x["score"],x["mission_id"]))[:limit]
