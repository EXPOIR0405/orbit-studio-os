"""평가 미션 실행·채점.

    ORBIT_ENABLE_LIVE=true python scripts/eval_missions.py --split dev --runs 3

- 실제 모델만 지원한다. mock 응답은 EP.12 고정이라 평가 미션에서는 의미가 없다.
- final은 홀드아웃이다. 프롬프트·규칙을 고치는 중에는 돌리지 않는다(--split final에 --holdout 필요).
- 결과 원본은 work/eval/(gitignore)에 저장하고, 표만 출력한다.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "eval"
OUT.mkdir(parents=True, exist_ok=True)
# 운영자 DB와 섞이지 않게 평가 전용 DB를 쓴다. 이미 설정된 DATABASE_URL(compose의 Postgres 등)도 덮어씀
# 다른 평가 DB가 필요하면 ORBIT_EVAL_DATABASE_URL로 지정. orbit import 전에 정해야 함
os.environ["DATABASE_URL"] = os.getenv("ORBIT_EVAL_DATABASE_URL") or "sqlite:///" + str(OUT / "eval.db")
sys.path.insert(0, str(ROOT / "src" / "backend"))

from orbit import storage as db, service  # noqa: E402
from orbit.config import MODEL  # noqa: E402
from orbit.models import NewMission  # noqa: E402
from orbit.provider import live_enabled  # noqa: E402
from orbit.scoring import score, summarize  # noqa: E402

def run_one(mission, attempt):
    data = {"version": 1, "title": mission["title"], "synthetic": True, "sources": mission["sources"]}
    request = NewMission(title=f"eval {mission['id']} #{attempt}", goal=mission["goal"], mode="live", call_limit=20, workflow="full")
    m = service.create(request, input_data=data)
    service.queue(m["id"])
    started = time.perf_counter()
    service.run(m["id"])
    m = db.get(m["id"])
    return {**score(mission, m), "attempt": attempt, "mission_id": m["id"], "seconds": round(time.perf_counter() - started, 1)}

def pct(pair):
    n, d = pair
    return f"{n}/{d}" + (f" ({n / d:.0%})" if d else "")

def table(rows):
    lines = ["| 유형 | 완료 | 충돌 재현율 | 오탐 | 근거 없는 단정 | 스포일러 노출 | 요약 스포일러 | 금지 문구 | 표본 수 정확 | QA 과잉 차단 | QA 경고만 | QA 놓침 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    groups = [(t, [r for r in rows if r["type"] == t]) for t in dict.fromkeys(r["type"] for r in rows)] + [("전체", rows)]
    for name, group in groups:
        s = summarize(group)
        lines.append(f"| {name} | {pct(s['completed'])} | {pct(s['conflict_recall'])} | {s['false_positives']} | {s['unsupported_asserted']} "
                     f"| {pct(s['spoiler_leak'])} | {pct(s['audience_spoiler'])} | {pct(s['forbidden_used'])} | {pct(s['sample_size_correct'])} "
                     f"| {pct(s['qa_false_block'])} | {pct(s['qa_warned_only'])} | {pct(s['qa_missed'])} |")
    return "\n".join(lines)

def rescore(path):
    saved = json.loads(path.read_text(encoding="utf-8"))
    missions = {x["id"]: x for x in json.loads((ROOT / "data" / "eval" / f"{saved['split']}.json").read_text(encoding="utf-8"))["missions"]}
    rows = [{**r, **score(missions[r["mission"]], db.get(r["mission_id"]))} for r in saved["rows"]]
    path.write_text(json.dumps({**saved, "rows": rows, "summary": summarize(rows)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(table(rows))
    print("\nQA 지표 분모는 QA까지 완료된 실행. 문안 문제가 있었던 실행 수: " + str(summarize(rows)["campaign_problems"]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "final"], default="dev")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--only", help="쉼표로 구분한 미션 id만 실행")
    parser.add_argument("--holdout", action="store_true", help="final 세트 실행 확인")
    parser.add_argument("--rescore", help="저장된 결과 파일을 모델 호출 없이 현재 채점 규칙으로 다시 채점")
    args = parser.parse_args()
    if args.rescore:
        return rescore(Path(args.rescore))
    if not live_enabled():
        sys.exit("ORBIT_ENABLE_LIVE=true가 필요합니다. 실제 모델을 호출하므로 비용이 듭니다.")
    if args.split == "final" and not args.holdout:
        sys.exit("final은 홀드아웃입니다. 구성 비교 때만 --holdout과 함께 실행하세요.")

    missions = json.loads((ROOT / "data" / "eval" / f"{args.split}.json").read_text(encoding="utf-8"))["missions"]
    if args.only:
        keep = set(args.only.split(","))
        missions = [x for x in missions if x["id"] in keep]
    db.initialize()
    jobs = [(x, i + 1) for x in missions for i in range(args.runs)]
    print(f"{args.split} · 미션 {len(missions)}개 × {args.runs}회 = {len(jobs)}회 · 모델 {MODEL}", file=sys.stderr)

    started = time.perf_counter()
    with ThreadPoolExecutor(args.workers) as pool:
        rows = list(pool.map(lambda job: run_one(*job), jobs))
    elapsed = time.perf_counter() - started

    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = OUT / f"{args.split}-{stamp}.json"
    path.write_text(json.dumps({"split": args.split, "model": MODEL, "runs": args.runs, "rows": rows,
                                "summary": summarize(rows)}, ensure_ascii=False, indent=1), encoding="utf-8")
    s = summarize(rows)
    print(table(rows))
    print("\nQA 지표 분모는 QA까지 완료된 실행. 문안 문제가 있었던 실행 수: " + str(s["campaign_problems"]))
    print(f"\n호출 {s['calls']}회 · 토큰 {s['tokens']:,} · {elapsed:.0f}초 · 원본 {path.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
