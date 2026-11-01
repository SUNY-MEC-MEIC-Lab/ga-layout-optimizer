# -*- coding: utf-8 -*-
"""
make_viewer_data.py — docs/data.js 를 만든다 (3D 비교 페이지용 데이터).

예제 도면 4종을 MCP 도구와 같은 절차로 읽고(도면 → IR → 요건 적용 → Gate 1 → 동결),
결정론적 솔버로 최적화한 뒤 현황 배치와 최적화 배치의 3D 좌표를 내보낸다.
좌표는 파서(현황)와 솔버(최적화)가 만든 그대로이며, 이 스크립트는 단위만 정리한다.

  python3 tools/make_viewer_data.py            # effort normal, seed 20260826
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, os.path.join(ROOT, "server"))

import asis as ASIS          # noqa: E402
import ga_core as G          # noqa: E402
import pipeline              # noqa: E402
import tools as T            # noqa: E402

OUT = os.path.join(ROOT, "docs", "data.js")
SEED = 20260826

CASES = [
    ("smr_aux", "원전 SMR 보조건물", "DXF 도면 · 3개 층 · 원전급 제약 (화재분리·다층 관통·중요구역 등)"),
    ("chem_plant", "석유화학 공정 플랜트", "벡터 PDF 1:500 · 화재·폭발 이격 거리"),
    ("fpso_topside", "FPSO 해상 플랜트 상부", "SVG · 2개 데크 · 위험구역 분리 · 무게중심"),
    ("hospital_or", "병원 수술부", "PNG 스캔 · 청결/오염 동선 분리 · 이미 꽉 찬 평면"),
]


def _r(v):
    return round(float(v), 3)


def _blocks(spec, geo, fh):
    base = [sum(fh[:f]) for f in range(len(fh))]
    out = []
    for i, g in sorted(geo.items(), key=lambda kv: spec.blocks[kv[0]].id):
        b = spec.blocks[i]
        cl = b.clearance
        f = int(g["f"])
        out.append(dict(
            id=b.id, name=b.name, kind=b.kind,
            group=b.fire_zone or b.zone or b.kind,
            f=f, x=_r(g["x"] + cl), y=_r(g["y"] + cl),
            w=_r(g["w"] - 2 * cl), d=_r(g["d"] - 2 * cl),
            z=_r(base[f] if f < len(base) else g.get("z", 0.0)),
            h=_r(min(b.h, sum(fh[f:]) if f < len(fh) else b.h)),
            pinned=bool(b.pinned)))
    return out


def _metrics(m, viols, tol=1e-6):
    hard = [v for v in viols if v.hard and v.amount > tol]
    return dict(width=m["width_m"], depth=m["depth_m"], footprint=m["footprint_m2"],
                volume=m["volume_m3"], hard=m["hard_violation_count"],
                violations=[dict(id=v.cid, detail=v.detail, blocks=list(v.blocks))
                            for v in hard])


def build_case(t, tmp, name, title, desc):
    r = t.ga_load_example(name=name)
    pid = r["project"]["project_id"]
    t.ga_apply_example_requirements(project_id=pid, name=name)
    if not t.ga_validate(project_id=pid)["passed"]:
        raise SystemExit(f"{name}: Gate 1 실패")
    t.ga_freeze(project_id=pid, approved_by="make_viewer_data", acknowledged_warnings=True)
    d, ir = t._load_ir(pid)
    asis = t.ws.rjson(os.path.join(d, "asis.json"))
    out = os.path.join(tmp, name)
    s = pipeline.optimize_ir(ir, out, effort="normal", seed=SEED, asis=asis)

    spec = G.spec_from_dict(ir)
    a_sol = ASIS.AsIsSolution(spec, asis)
    a_viols = a_sol.evaluate(detail=True)[4]
    fh = list(a_sol.fh)
    asis_blocks = _blocks(spec, a_sol.geo, fh)

    with open(os.path.join(out, "result.json"), encoding="utf-8") as fp:
        res = json.load(fp)
    idx = {b.id: i for i, b in enumerate(spec.blocks)}
    geo = {idx[b["id"]]: dict(x=b["x"], y=b["y"], w=b["w"], d=b["d"], f=b["f"], z=b["z"])
           for b in res["blocks"]}
    opt_blocks = _blocks(spec, geo, fh)
    o_viols = [type("V", (), dict(cid=v["id"], detail=v["detail"], amount=v["amount"],
                                  hard=True, blocks=v["blocks"]))
               for v in res["hard_violations"]]

    c = s["comparison"]
    return dict(
        key=name, title=title, desc=desc, floors=spec.n_floors, floor_heights=fh,
        asis=dict(blocks=asis_blocks, **_metrics(s["asis"], a_viols, ASIS.ASIS_TOL)),
        optimized=dict(blocks=opt_blocks, **_metrics(s["optimized"], o_viols)),
        footprint_reduction_pct=c["footprint_reduction_pct"],
        volume_reduction_pct=c["volume_reduction_pct"],
        asis_better=bool(c.get("asis_better")),
        verdict=c["verdict"],
        result_sha256=s["result_sha256"], seed=SEED,
    )


def main():
    tmp = tempfile.mkdtemp(prefix="viewer-")
    try:
        t = T.Tools(T.Workspace(os.path.join(tmp, "ws"), allow_local_paths=True,
                                allow_url_fetch=False))
        cases = []
        for name, title, desc in CASES:
            print(f"  {name} …", flush=True)
            c = build_case(t, tmp, name, title, desc)
            print(f"    현황 {c['asis']['footprint']:,.0f} m² (위반 {c['asis']['hard']}) → "
                  f"최적화 {c['optimized']['footprint']:,.0f} m² (위반 {c['optimized']['hard']}) "
                  f"· {c['footprint_reduction_pct']}%")
            cases.append(c)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fp:
        fp.write("// 자동 생성: python3 tools/make_viewer_data.py — 손으로 고치지 말 것\n")
        fp.write("window.GA_CASES = ")
        json.dump(cases, fp, ensure_ascii=False, separators=(",", ":"))
        fp.write(";\n")
    print(f"→ {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT):,} bytes)")


if __name__ == "__main__":
    main()
