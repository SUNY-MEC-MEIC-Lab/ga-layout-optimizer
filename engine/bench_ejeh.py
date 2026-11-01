# -*- coding: utf-8 -*-
"""
bench_ejeh.py — 2단계: Ejeh, Liu, Papageorgiou (2019) 다층 공정 플랜트 배치 MILP 와의 대조.

논문  "Optimal layout of multi-floor process plants using MILP", Comput. Chem. Eng. 131, 106573.
      doi:10.1016/j.compchemeng.2019.106573 · 저자 원고(무료): discovery.ucl.ac.uk/10096679/
데이터 tests/data/ejeh2019/ejeh2019_appendixB.json — 부록 B 표 B.1–B.8 (기기 치수·연결·파라미터).
      PDF 원문과 숫자를 전수 대조했다(불일치 0). 실험 조건은 아래에 논문 본문에서 직접 옮겼다.

무엇을 푸는가
  논문 OPTL 모델과 같은 문제를 이 엔진의 표현(층별 Sequence-Pair + 회전 + 층 배정 + 관통 기기)과
  SA 탐색으로 푼다. 목적함수만 논문 식 (10) 그대로다:

    Σ [ Cc·TD + Cv·D + Ch·(R+L+A+B) ]  +  FC1·NF  +  FC2·FA·NF  +  LC·FA
    R−L = xi−xj, A−B = yi−yj (중심), U−D = FH·(ki−kj) + OP − IP, TD = R+L+A+B+U+D   (S.17–S.20)

  · 바닥 크기 X, Y 는 후보 중에서 고른다 (요소: 5–45 m 10 m 간격, 나머지 5–60 m 5 m 간격 — 4절 본문)
  · 모든 기기는 0≤x±l/2≤X, 0≤y±d/2≤Y (S.27–S.30), 90° 회전 허용 (A.1.2)
  · 같은 층 기기 사이 최소 이격 De_min (S.13–S.16): 요소 4 m, CDU 0, LNG 4 m, COGP 언급 없음 → 0
    (엔진에서는 clearance = De_min/2 로 두어 본체 간극 ≥ De_min 을 구조적으로 보장)
  · 키 큰 기기는 여러 층을 관통하고, 맨 위 층을 넘어 솟을 수 있다 (OPTL 의 특징)
  · LNG 추가 조건 (4절 본문): 기기 16(MR 압축기)이 17(냉각기) 바로 위·18(천장 크레인) 바로 아래,
    3(PMR 압축기)이 4 바로 위·5 바로 아래; 1층 면적 50%·최상층 60% 비움.
    "바로 위" 는 이 구현의 해석이다 — 한 층 위에서 시작하고, 아래 기기의 평면이 위 기기 평면 안에 든다.

최종 판정은 이 엔진의 패킹이 아니라 독립 검사(check_solution)로 한다 — 이격·경계·LNG 조건 위반이 0 이어야 실현가능.

  python3 bench_ejeh.py tests/data/ejeh2019/ejeh2019_appendixB.json --plant urea --seeds 3
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from typing import Dict, List, Optional, Tuple

import ga_core as G

SIZES = {"urea": [5.0, 15.0, 25.0, 35.0, 45.0]}
SIZES_DEFAULT = [5.0 * k for k in range(1, 13)]          # 5..60
DEMIN = {"urea": 4.0, "cdu": 0.0, "lng": 4.0, "cogp": 0.0}
DEMIN_NOTE = {"cogp": "논문에 최소 이격 언급 없음 → 0 으로 둠"}
# 논문이 보고한 값 (표 1·2·3). proven = 전역 최적 증명(CPLEX gap 0).
PUBLISHED = {
    "urea": dict(cost=117431.0, proven=True, NF=4, X=5.0, Y=15.0),
    "cdu": dict(cost=592322.2, proven=True, NF=7, X=20.0, Y=15.0),
    "lng": dict(cost=1466654.2, proven=False, gap_pct=2.2, NF=5, X=35.0, Y=30.0),
    "cogp": dict(cost=255320.4, proven=False, gap_pct=11.8, NF=7, X=20.0, Y=10.0),
}
SWEEP = {   # 표 2 (요소), 표 3 (CDU): 가용 층 수 |K| → 전역 최적
    "urea": {1: 260942.2, 2: 167298.8, 3: 149498.0, 4: 117431.0},
    "cdu": {1: 1112094.7, 2: 855465.8, 3: 697672.4, 4: 624452.8, 5: 603886.5, 6: 603886.5, 7: 592322.2},
}
LNG_STACKS = [(17, 16, 18), (4, 3, 5)]                  # 아래 → 위
LNG_FREE = (0.50, 0.60)                                   # 1층, 최상층 비움 비율
PENALTY = 1.0e5                                           # 위반 1 m (또는 1 m²) 당
GUIDE = 0.0                                               # 탐색 안내 항 배율 — 0.25·1.0 을 시험했지만 seed 편차보다 효과가 작아 끔 (2026-11-01)


def load(path: str, plant: str, K: Optional[int] = None) -> dict:
    with open(path, encoding="utf-8") as fp:
        d = json.load(fp)[plant]
    P = dict(d["params"])
    if K is not None:
        P["K"] = int(K)
    items = {it["i"]: it for it in d["items"]}
    conns = [(c["i"], c["j"], c["Cc"], c["Ch"], c["Cv"], c["OP"], c["IP"]) for c in d["connections"]]
    return dict(plant=plant, P=P, items=items, conns=conns, demin=DEMIN[plant],
                sizes=SIZES.get(plant, SIZES_DEFAULT))


def make_spec(inst: dict) -> G.Spec:
    P, cl = inst["P"], inst["demin"] / 2.0
    blocks = [dict(id=f"E{i}", name=it["name"], w=it["alpha"], d=it["beta"], h=it["gamma"] - 1e-6,
                   clearance=cl, rotatable=True, kind="equipment")
              for i, it in sorted(inst["items"].items())]
    return G.spec_from_dict(dict(project=f"ejeh2019-{inst['plant']}", blocks=blocks,
                                 n_floors=int(P["K"]), floor_heights=[float(P["FH"])] * int(P["K"])))


def _bodies(spec, sol) -> Tuple[Dict[int, dict], Dict[Tuple[int, int], tuple]]:
    """기기 번호 → 본체 (x0, y0, w, d, k0) 와, 층별 점유 (번호, 층) → 본체 사각형."""
    geo, sh = sol.decode()
    body, occ = {}, {}
    for i, g in geo.items():
        cl = spec.blocks[i].clearance
        no = int(spec.blocks[i].id[1:])
        body[no] = (g["x"] + cl, g["y"] + cl, g["w"] - 2 * cl, g["d"] - 2 * cl, g["f"])
        for f in sol.floors_of(i):
            occ[(no, f)] = body[no][:4]
    return body, occ


def evaluate(inst: dict, spec, sol) -> dict:
    P = inst["P"]
    body, occ = _bodies(spec, sol)
    x0 = min(b[0] for b in body.values()); y0 = min(b[1] for b in body.values())
    W = max(b[0] + b[2] for b in body.values()) - x0
    D = max(b[1] + b[3] for b in body.values()) - y0
    sizes = inst["sizes"]
    X = next((s for s in sizes if s >= W - 1e-9), None)
    Y = next((s for s in sizes if s >= D - 1e-9), None)
    pen = 0.0
    if X is None:
        pen += W - sizes[-1]; X = sizes[-1]
    if Y is None:
        pen += D - sizes[-1]; Y = sizes[-1]
    NF = max(b[4] for b in body.values()) + 1
    FH = P["FH"]
    pipe = 0.0
    for (i, j, Cc, Ch, Cv, OP, IP) in inst["conns"]:
        bi, bj = body[i], body[j]
        dx = abs((bi[0] + bi[2] / 2) - (bj[0] + bj[2] / 2))
        dy = abs((bi[1] + bi[3] / 2) - (bj[1] + bj[3] / 2))
        delta = (FH * bi[4] + OP) - (FH * bj[4] + IP)        # U − D  (S.19)
        U, Dn = max(0.0, delta), max(0.0, -delta)
        pipe += Cc * (dx + dy + U + Dn) + Cv * Dn + Ch * (dx + dy)
    FA = X * Y
    fixed = P["FC1"] * NF + P["FC2"] * FA * NF + P["LC"] * FA
    extra = []
    if inst["plant"] == "lng":
        for lo, mid, hi in LNG_STACKS:
            for a, b in ((lo, mid), (mid, hi)):
                A, B = body[a], body[b]
                v = abs(B[4] - (A[4] + 1)) * FH
                v += max(0.0, B[0] - A[0]) + max(0.0, (A[0] + A[2]) - (B[0] + B[2]))   # A 평면이 B 평면 안
                v += max(0.0, B[1] - A[1]) + max(0.0, (A[1] + A[3]) - (B[1] + B[3]))
                if v > 1e-9:
                    extra.append((f"E{b} 가 E{a} 바로 위가 아님", v))
                pen += v
        for f, ratio, tag in ((0, LNG_FREE[0], "1층"), (NF - 1, LNG_FREE[1], "최상층")):
            a = sum(r[2] * r[3] for (no, ff), r in occ.items() if ff == f)
            v = max(0.0, a - (1 - ratio) * FA)
            if v > 1e-9:
                extra.append((f"{tag} 공지 부족 {v:.1f} m²", v))
            pen += v
    total = pipe + fixed
    # 탐색 안내 항: 바닥 크기는 후보(5 m 단위) 중에서 고르므로 비용이 계단식이다 — 같은 후보 안에서
    # '조금 더 빽빽한' 배치가 비용에 안 보여 SA 가 다음 계단으로 내려가지 못한다. 그래서 탐색에만
    # 실제 외곽 W·D 의 면적 비용(땅값+층 면적비)을 GUIDE 배로 더한다. 보고하는 total 은 논문 식 그대로다.
    guide = GUIDE * (P["LC"] + P["FC2"] * NF) * (W * D)
    return dict(total=total, pipe=pipe, fixed=fixed, X=X, Y=Y, W=W, D=D, NF=NF, penalty=pen,
                F=total + PENALTY * pen + guide, extra=extra)


def check_solution(inst: dict, spec, sol) -> List[str]:
    """엔진과 독립된 실현가능성 검사 — 같은 층 이격, 바닥 경계, 겹침."""
    body, occ = _bodies(spec, sol)
    r = evaluate(inst, spec, sol)
    x0 = min(b[0] for b in body.values()); y0 = min(b[1] for b in body.values())
    bad = []
    for (no, f), (x, y, w, d) in occ.items():
        if x - x0 < -1e-6 or y - y0 < -1e-6 or x - x0 + w > r["X"] + 1e-6 or y - y0 + d > r["Y"] + 1e-6:
            bad.append(f"E{no} {f+1}층: 바닥 {r['X']:g}×{r['Y']:g} m 밖")
    keys = sorted(occ)
    dm = inst["demin"]
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            (i, fi), (j, fj) = keys[a], keys[b]
            if fi != fj or i == j:
                continue
            A, B = occ[keys[a]], occ[keys[b]]
            gx = max(B[0] - (A[0] + A[2]), A[0] - (B[0] + B[2]))
            gy = max(B[1] - (A[1] + A[3]), A[1] - (B[1] + B[3]))
            if max(gx, gy) < dm - 1e-6:
                bad.append(f"E{i}–E{j} {fi+1}층: 간극 {max(gx, gy):.2f} m < {dm:g} m")
    bad += [m for m, _ in r["extra"]]
    return bad


def solve(inst: dict, seed: int, iters: int, restarts: int) -> Tuple[object, dict]:
    spec = make_spec(inst)
    rng = random.Random(seed)
    best, bestF = None, float("inf")
    for _ in range(restarts):
        cur = G.Solution(spec, rng)
        cF = evaluate(inst, spec, cur)["F"]
        T0 = max(1.0, cF * 0.05)
        lb, lbF = cur.clone(), cF
        for it in range(iters):
            T = T0 * (1e-4) ** (it / max(1, iters - 1))
            cand = cur.clone()
            G._mutate(cand, rng)
            nF = evaluate(inst, spec, cand)["F"]
            if nF < cF or rng.random() < math.exp(-(nF - cF) / max(T, 1e-9)):
                cur, cF = cand, nF
                if nF < lbF:
                    lb, lbF = cand.clone(), nF
        if lbF < bestF:
            best, bestF = lb, lbF
    return best, dict(evaluate(inst, spec, best), violations=check_solution(inst, spec, best), spec=spec)


def run(path: str, plant: str, seeds: List[int], iters: int, restarts: int, K: Optional[int] = None) -> dict:
    inst = load(path, plant, K)
    pub = (SWEEP.get(plant, {}).get(int(inst["P"]["K"])) if K is not None else PUBLISHED[plant]["cost"])
    rows = []
    for s in seeds:
        t0 = time.time()
        sol, r = solve(inst, s, iters, restarts)
        ok = not r["violations"]
        rows.append(dict(seed=s, total=round(r["total"], 1), feasible=ok, NF=r["NF"], X=r["X"], Y=r["Y"],
                         gap_pct=round((r["total"] - pub) / pub * 100, 2) if pub else None,
                         violations=r["violations"][:5], wall_s=round(time.time() - t0, 1)))
    feas = [r for r in rows if r["feasible"]]
    gaps = sorted(r["gap_pct"] for r in feas if r["gap_pct"] is not None)
    return dict(plant=plant, K=int(inst["P"]["K"]), published=pub, demin=inst["demin"],
                demin_note=DEMIN_NOTE.get(plant, ""), runs=rows,
                best_gap_pct=gaps[0] if gaps else None,
                median_gap_pct=statistics.median(gaps) if gaps else None,
                feasible=len(feas), n=len(rows))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ejeh 2019 다층 플랜트 배치 — 논문 MILP 최적값과 대조")
    ap.add_argument("json")
    ap.add_argument("--plant", default="urea", choices=["urea", "cdu", "lng", "cogp"])
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--iters", type=int, default=40000)
    ap.add_argument("--restarts", type=int, default=3)
    ap.add_argument("--sweep", action="store_true", help="가용 층 수를 바꿔 가며 (요소 1–4, CDU 1–7)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    seeds = list(range(1, a.seeds + 1))
    res = []
    if a.sweep:
        for K in sorted(SWEEP[a.plant]):
            res.append(run(a.json, a.plant, seeds, a.iters, a.restarts, K))
    else:
        res.append(run(a.json, a.plant, seeds, a.iters, a.restarts))
    for r in res:
        print(f"{r['plant']:5s} |K|={r['K']} 논문 {r['published']:>12,.1f} · 실현가능 {r['feasible']}/{r['n']} · "
              f"최고 갭 {r['best_gap_pct']}% · 중앙 {r['median_gap_pct']}%")
        for x in r["runs"]:
            print(f"    seed {x['seed']}: {x['total']:>12,.1f}  NF {x['NF']}  {x['X']:g}×{x['Y']:g} m  "
                  f"{'OK' if x['feasible'] else '위반 ' + str(x['violations'][:2])}  {x['wall_s']} s")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fp:
            json.dump(res, fp, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
