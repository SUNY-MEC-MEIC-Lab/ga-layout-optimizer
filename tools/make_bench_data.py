# -*- coding: utf-8 -*-
"""
make_bench_data.py — docs/bench.js 를 만든다 (3D 페이지의 '벤치마크' 섹션 데이터).

정답이 알려진 문제로 탐색부를 검증한 결과를 README 와 같은 설정으로 다시 계산해 내보낸다 (결정론적).
  · QAPLIB 12건 — 공개 최적해 대비 갭 (100000×5, seed 20260826)
  · Wrigley 2019 Shearon Harris — 한 면 4층/3층 자리 배정 (기본 예산)
  · Ejeh 2019 4개 플랜트 — 논문 목적함수, seed 1–5 (100000×4) + 가용 층 수 스윕 (요소·CDU, seed 1–3, 60000×3)

  python3 tools/make_bench_data.py
"""
import json
import multiprocessing as mp
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
DATA = os.path.join(ROOT, "tests", "data")
OUT = os.path.join(ROOT, "docs", "bench.js")
EJEH = os.path.join(DATA, "ejeh2019", "ejeh2019_appendixB.json")


def job(spec):
    kind = spec[0]
    if kind == "qap":
        import bench_qap as Q
        return ("qap", Q.run_dir(os.path.join(DATA, "qaplib"), iters=100000, restarts=5, seed=20260826))
    if kind == "wrigley":
        import bench_wrigley as W
        d = W.load(os.path.join(DATA, "wrigley2019", "shearon_harris.xlsx"))
        with open(os.path.join(DATA, "wrigley2019", "expected.json"), encoding="utf-8") as fp:
            exp = json.load(fp)
        rows = []
        for g in ("one_side_4F", "one_side_3F"):
            r = W.solve(d, g)
            rows.append(dict(grid=g, objective=r["objective"], slots=r["slots"],
                             paper_reduction_pct=exp["reduction_pct"].get(g), paper_optimum=exp["optimum"].get(g)))
        return ("wrigley", dict(baseline=exp["baseline_objective"], rows=rows))
    import bench_ejeh as E
    if kind == "ejeh":
        return ("ejeh", E.run(EJEH, spec[1], [1, 2, 3, 4, 5], 100000, 4, keep_layout=True))
    if kind == "sweep":
        r = E.run(EJEH, spec[1], [1, 2, 3], 60000, 3, K=spec[2])
        r.pop("layout", None)
        return ("sweep", r)


def main():
    import bench_ejeh as E
    jobs = [("qap",), ("wrigley",)] + [("ejeh", p) for p in ("urea", "cdu", "lng", "cogp")]
    jobs += [("sweep", p, K) for p in ("urea", "cdu") for K in sorted(E.SWEEP[p])]
    with mp.Pool(min(len(jobs), os.cpu_count() or 1)) as pool:
        res = pool.map(job, jobs)
    out = dict(qaplib=None, wrigley=None, ejeh=[], sweep={})
    for kind, r in res:
        if kind == "qap":
            out["qaplib"] = r
        elif kind == "wrigley":
            out["wrigley"] = r
        elif kind == "ejeh":
            r["published_info"] = E.PUBLISHED[r["plant"]]
            out["ejeh"].append(r)
        else:
            out["sweep"].setdefault(r["plant"], []).append(
                dict(K=r["K"], published=r["published"], best_gap_pct=r["best_gap_pct"],
                     best=min((x["total"] for x in r["runs"] if x["feasible"]), default=None)))
    for v in out["sweep"].values():
        v.sort(key=lambda x: x["K"])
    for r in out["ejeh"]:
        print(f"  {r['plant']:5s} 최고 갭 {r['best_gap_pct']}% · 중앙 {r['median_gap_pct']}% · 실현가능 {r['feasible']}/{r['n']}")
    with open(OUT, "w", encoding="utf-8") as fp:
        fp.write("// 자동 생성: python3 tools/make_bench_data.py — 손으로 고치지 말 것\n")
        fp.write("window.GA_BENCH = ")
        json.dump(out, fp, ensure_ascii=False, separators=(",", ":"))
        fp.write(";\n")
    print(f"→ {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT):,} bytes)")


if __name__ == "__main__":
    main()
