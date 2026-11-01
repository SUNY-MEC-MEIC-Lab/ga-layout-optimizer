# -*- coding: utf-8 -*-
"""
bench_wrigley.py — 2단계: Wrigley et al. 2019 Shearon Harris 데이터셋으로
'층 배정까지 포함한' 모듈 배치를 푼다.

원자료  Paul Wrigley, "Shearon Harris layout data", University of Derby, 2018
        CC BY 4.0 · https://data.mendeley.com/datasets/w39zbzj6bk/1
논문    Wrigley, Wood, Stewart, Hall, Robertson (2019), Nucl. Eng. Des. 341:100-111
        doi:10.1016/j.nucengdes.2018.10.023

데이터셋이 주는 것 (엑셀 4개 시트, 표준 라이브러리 zipfile 로 읽는다)
  · Design Structure Matrix — 21개 계통 모듈(층 번호 포함)과 모듈 간 연결강도.
    행렬은 대칭이 아니다. 각 칸이 한 방향의 연결이므로 **모든 칸을 더한다**.
    (v0.2 변환기 make_shearon.py 는 상삼각만 읽어 연결의 상당 부분을 버렸다.)
  · Location data — 표준화 격자 자리 4종: 한 면 4층(20자리)·한 면 3층(21자리)·
    두 면 3층(12자리)·두 면 4층(16자리). x/y/z [m].

이 모듈이 푸는 문제
  RCP(원자로냉각재 계통)는 원자력섬 안에 고정하고, 나머지 20개 모듈을 격자
  자리에 하나씩 배정한다. **어느 층에 둘지도 결정변수다** (원자료의 층 번호는
  쓰지 않는다). 목적함수 = Σ 연결강도 × 직교거리(|dx|+|dy|+|dz|).
  이산 배정이므로 QAP 이고, bench_qap 의 같은 SA 탐색부로 푼다.

★ 논문 수치(−33.9~46.1%)와 직접 비교할 수 없는 이유 — 지어내지 않기 위해 적는다.
  1. 기준안(원 현장조립 배치)의 좌표가 데이터셋에 없다. 기준 목적함수는 논문에만 있다.
  2. 두 면 격자는 자리가 12·16개뿐이라 20개 모듈이 들어가지 않는다. 논문은
     모듈 묶음(1단계)을 다시 했을 것인데, 그 묶음이 데이터셋에 없다.
  3. RCP 의 위치(원자력섬 중심 좌표)와 거리 정의(중심 간/면 간)가 데이터셋에 없다.
  그래서 여기서는 '자리 배정 최적해가 얼마인가' 와 '탐색이 안정적인가' 만 보고한다.
  논문 대조는 tests/data/wrigley2019/expected.json 을 원논문에서 옮겨 적었을 때만 한다.

  python3 bench_wrigley.py tests/data/wrigley2019/shearon_harris.xlsx
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

import bench_qap as Q

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

# Location data 시트에서 각 격자의 x 행 번호 (y, z 는 그 다음 두 행)
GRIDS = {
    "one_side_4F": 5,
    "one_side_3F": 10,
    "two_sides_3F": 15,
    "two_sides_4F": 20,
}
# 원자력섬 안 RCP 위치 가정 — 데이터셋에 없다. 격자 원점(섬 중심), 1층 표고.
RCP_POS = (0.0, 0.0, 3.0)


def _col(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def read_xlsx(path: str) -> Dict[str, Dict[str, str]]:
    """{시트명: {셀주소: 값}} — 계산된 값(<v>)만 읽는다."""
    z = zipfile.ZipFile(path)
    ss: List[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        ss = ["".join(t.text or "" for t in si.iter(_M + "t"))
              for si in root.findall(_M + "si")]
    rels = {r.get("Id"): r.get("Target")
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    out = {}
    for s in ET.fromstring(z.read("xl/workbook.xml")).find(_M + "sheets"):
        target = rels[s.get(_R)].lstrip("/")
        target = target if target.startswith("xl/") else "xl/" + target
        cells = {}
        for c in ET.fromstring(z.read(target)).iter(_M + "c"):
            v = c.find(_M + "v")
            if v is None or v.text is None:
                continue
            cells[c.get("r")] = ss[int(v.text)] if c.get("t") == "s" else v.text
        out[s.get("name")] = cells
    return out


def load(path: str) -> dict:
    wb = read_xlsx(path)
    dsm, loc = wb["Design Structure Matrix"], wb["Location data"]
    names, floors = [], []
    j = 4
    while _col(j) + "5" in dsm:
        names.append(dsm[_col(j) + "5"].strip())
        floors.append(int(float(dsm[_col(j) + "4"])))
        j += 1
    n = len(names)
    W = [[float(dsm.get(_col(4 + jj) + str(7 + ii), 0) or 0) for jj in range(n)]
         for ii in range(n)]
    seen: Dict[str, int] = {}
    ids = []
    for nm in names:
        seen[nm] = seen.get(nm, 0) + 1
        ids.append(nm if seen[nm] == 1 else f"{nm}-{seen[nm]}")
    grids = {}
    for g, row in GRIDS.items():
        pts, k = [], 2
        while _col(k) + str(row) in loc:
            pts.append(tuple(float(loc[_col(k) + str(row + d)]) for d in range(3)))
            k += 1
        grids[g] = pts
    return dict(ids=ids, names=names, source_floors=floors, W=W, grids=grids)


def instance(data: dict, grid: str, rcp=RCP_POS) -> Tuple[list, list, dict, list]:
    """QAP 행렬. 위치 0 = RCP 자리, 1.. = 격자 자리. 남는 자리는 더미 시설."""
    ids, W = data["ids"], data["W"]
    slots = data["grids"][grid]
    nf = len(ids)
    rcp_i = ids.index("RCP")
    if len(slots) < nf - 1:
        raise ValueError(f"{grid}: 자리 {len(slots)}개 < 모듈 {nf - 1}개 — "
                         f"논문의 모듈 재묶음 정보 없이 풀 수 없다")
    locs = [tuple(rcp)] + list(slots)
    n = len(locs)
    D = [[sum(abs(a - b) for a, b in zip(p, q)) for q in locs] for p in locs]
    A = [[0.0] * n for _ in range(n)]
    for i in range(nf):
        for j in range(nf):
            if i != j:
                A[i][j] = W[i][j]        # 방향별 칸을 그대로 — 합하면 모든 칸
    return A, D, {rcp_i: 0}, locs


def solve(data: dict, grid: str, iters: int = 200000, restarts: int = 6,
          seed: int = 20260826) -> dict:
    A, D, fixed, locs = instance(data, grid)
    perm, cost = Q.solve_qap(A, D, iters=iters, restarts=restarts, seed=seed,
                             fixed=fixed)
    ids = data["ids"]
    place = {ids[i]: dict(x=locs[perm[i]][0], y=locs[perm[i]][1],
                          z=locs[perm[i]][2]) for i in range(len(ids))}
    zs = sorted({p[2] for p in locs[1:]})
    moved = sum(1 for i, nm in enumerate(ids) if nm != "RCP"
                and zs.index(place[nm]["z"]) + 1 != data["source_floors"][i])
    return dict(grid=grid, slots=len(locs) - 1, modules=len(ids), objective=cost,
                floors_changed=moved, placement=place, seed=seed,
                iters=iters, restarts=restarts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Wrigley 2019 Shearon Harris 자리 배정")
    ap.add_argument("xlsx")
    ap.add_argument("--iters", type=int, default=200000)
    ap.add_argument("--restarts", type=int, default=6)
    ap.add_argument("--seed", type=int, default=20260826)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    data = load(a.xlsx)
    print(f"모듈 {len(data['ids'])}개 · 연결 칸 "
          f"{sum(1 for r in data['W'] for v in r if v)}개 · "
          f"연결강도 합 {sum(map(sum, data['W'])):,.0f}")
    rows = []
    for g in GRIDS:
        try:
            r = solve(data, g, a.iters, a.restarts, a.seed)
        except ValueError as e:
            print(f"  {g:<14s} SKIP — {e}")
            continue
        rows.append(r)
        print(f"  {g:<14s} 자리 {r['slots']:>2d} · 목적함수 {r['objective']:>9,.0f} · "
              f"원자료와 다른 층에 놓인 모듈 {r['floors_changed']}개")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fp:
            json.dump(rows, fp, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
