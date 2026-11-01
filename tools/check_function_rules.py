# -*- coding: utf-8 -*-
"""
check_function_rules.py — 어떤 data.js 의 배치(현황·최적화)를 '기능 유지 요건'(examples/function/*.json)
의 동선 제약으로 다시 채점한다. 면적만 보고 줄였던 이전 결과가 기능을 얼마나 깼는지 재는 데 썼다.

  git show b315488:docs/data.js > /tmp/old.js
  python3 tools/check_function_rules.py /tmp/old.js

docs/data.js 의 previous_area_only.new_rule_violations 는 이 스크립트로 잰 값이다
(최적화 배치 기준; asis_rule_violations 는 같은 방법으로 잰 현황. 동선 요소는 이름으로 판별하고 계단 중복 제거·코어 묶기·복도 분할은 하지 않는 근사 — 엔진의 현황 평가와 수치가 다르다).
"""
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))

import constraints as CONS   # noqa: E402
import ga_core as G          # noqa: E402
import program as P          # noqa: E402

REQ = {"smr_aux": "smr_aux", "hospital_or": "hospital_or", "clinic_real": "clinic_us",
       "chem_plant": "chem_plant", "fpso_topside": "fpso_topside", "institute_real": "office_de"}
RULES = ("CIRC-ACCESS", "CIRC-CONNECT", "EGRESS", "RACK-SERVE")


def check(case: dict, which: str) -> collections.Counter:
    with open(os.path.join(ROOT, "examples", "function", REQ[case["key"]] + ".json"), encoding="utf-8") as fp:
        req = json.load(fp)
    cons = [x for x in req["set"]["constraints"] if x["id"] in RULES]
    bl = case[which]["blocks"]
    blocks = []
    for b in bl:
        k = "room" if b["kind"] in ("room", "obstacle", "opening") else b["kind"]
        circ = b.get("circ") or P.circulation_of(b["name"], k)
        if re.match(r"^CORE-", b["id"]):
            circ = "stair"
        if re.match(r"^PR-\d", b["id"]):
            circ = "piperack"
        if re.match(r"^CRANE", b["id"]):
            circ = "crane"
        kind = "room" if b["kind"] in ("obstacle", "opening") and circ else b["kind"]
        zone = b["group"] if b["group"] not in ("room", "equipment", "obstacle") else None
        blocks.append(dict(id=b["id"], name=b["name"], w=max(b["w"], 0.05), d=max(b["d"], 0.05),
                           kind=kind, circulation=circ, zone=zone, h=b["h"]))
    sp = G.spec_from_dict(dict(project="check", blocks=blocks, constraints=cons,
                               n_floors=case["floors"], floor_heights=case["floor_heights"]))
    geo = {i: dict(x=b["x"], y=b["y"], w=max(b["w"], 0.05), d=max(b["d"], 0.05), f=b["f"], z=b["z"],
                   cx=b["x"] + b["w"] / 2, cy=b["y"] + b["d"] / 2) for i, b in enumerate(bl)}
    ctx = CONS.EvalContext(sp, geo, (case[which]["width"], case[which]["depth"], 10.0), {})
    ctx.turbine_azimuth, ctx.tall_span = {}, {}
    v, _ = CONS.evaluate_all(ctx)
    return collections.Counter(x.cid for x in v)


def main(path):
    with open(path, encoding="utf-8") as fp:
        s = fp.read()
    for c in json.loads(s[s.index("=") + 1:].strip().rstrip(";")):
        if c["key"] not in REQ or not c["asis"]["blocks"]:
            continue
        for which in ("asis", "optimized"):
            n = check(c, which)
            print(f"{c['key']:15s} {which:9s} 위반 {sum(n.values()):3d} {dict(n)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "data.js"))
