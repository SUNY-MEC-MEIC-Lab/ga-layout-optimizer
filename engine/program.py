# -*- coding: utf-8 -*-
"""
program.py — 실 '규모 계획'(space programming)을 IR 에 결정론적으로 적용한다.

면적을 줄일 때 실을 무작정 작게 만들면 기능을 잃는다. 그래서 실마다
'이 기능에 필요한 면적·최소 치수' 를 인용 가능한 기준에서 가져와(규칙 = LLM 이 조사해 근거와 함께
제안하고 사람이 승인한 값) 엔진이 치수를 계산한다. LLM 은 치수를 쓰지 않는다 — 규칙의 면적·폭만 쓴다.

규칙 형식 (ga_update_ir patch 의 "program" 키):
{
  "rooms": [ {"type": "exam", "match": "EXAM|TRMT", "target_area_m2": 11.1, "min_area_m2": 7.4,
              "min_clear_dim_m": 2.44, "basis": "FGI 2018 Outpatient 2.2-3.2.1.1 …"} , … ],
  "corridor": {"width_m": 1.83, "basis": "…"},          # 복도 폭을 이 값으로 (넓으면 줄이고, 좁으면 넓힌다)
  "optional_corridors": true,                            # 복도 구간을 솔버가 없앨 수 있게 (동선 제약이 기능을 지킨다)
  "stack_cores": true,                                   # 층마다 겹친 계단·엘리베이터를 하나의 수직 코어로
  "unpin": ["CORE-*", "PR-*"],                           # 고정 해제 (fnmatch)
  "exterior": [{"match": "Buero|Labor", "basis": "…"}]     # 외벽에 면해야 하는 실 (채광·구조대 진입창)
}

원칙
  · target 보다 큰 실은 target 까지 줄인다 (가로세로 비율 유지, 최소 치수 보장).
  · min 보다 작은 실은 min 까지 키운다 — 기능 미달을 숨기지 않는다.
  · 일치하는 규칙이 없는 실은 그대로 둔다 (인원·장비를 모르면 줄이지 않는다).
  · grow_only 규칙은 최소 미달일 때 키우기만 한다 (최소 면적만 알려진 실 — 그보다 크면 그대로).
  · 모든 변경은 블록의 _program 에 근거와 함께 남고, 보고서로 돌려준다.
"""
from __future__ import annotations

import fnmatch
import math
import re
from typing import Dict, List, Optional, Tuple

CIRC_RX = [
    ("stair", re.compile(r"^\s*(STAIR|STAIRS|STAIRWELL)\b|^Stair:|Treppe|계단", re.I)),
    ("elevator", re.compile(r"^\s*(ELEVATOR|LIFT)\s*$|Aufzug|승강기|엘리베이터", re.I)),
    ("corridor", re.compile(r"CORRIDOR|\bCORR\b|^\s*HALL\b|^\s*VEST\b|Flur|Gang\b|복도", re.I)),
    ("lobby", re.compile(r"LOBBY|Foyer|Eingang|WAITING|^\s*WAIT\b|RECEPT|로비|현관|대기실", re.I)),
]

CORRIDOR_FIRST = re.compile(r"Flur|CORRIDOR|복도", re.I)


def circulation_of(name: str, kind: str) -> Optional[str]:
    """실 이름 → 동선 종류. 모르면 None (추정하지 않는다)."""
    if kind not in ("room", "opening", "obstacle"):
        return None
    # "Flur Keller Treppe"(계단 앞 복도) 처럼 복도 이름에 계단이 붙은 공간은 복도다 —
    # 계단 자체는 그 안의 계단 객체(IfcStair)다. 계단으로 치면 실 문이 계단실로 나는 배치가 허용된다.
    if CORRIDOR_FIRST.search(name or ""):
        return "corridor"
    for t, rx in CIRC_RX:
        if rx.search(name or ""):
            return t
    return None


def _drop(ir: dict, gone) -> None:
    """블록을 빼고, 그 블록을 가리키는 링크·이격·표고 규칙도 함께 뺀다."""
    gone = set(gone)
    if not gone:
        return
    ir["blocks"] = [b for b in ir["blocks"] if b["id"] not in gone]
    for key in ("links", "separations"):
        ir[key] = [x for x in ir.get(key, []) or [] if x.get("a") not in gone and x.get("b") not in gone]
    ir["elevations"] = [x for x in ir.get("elevations", []) or []
                        if x.get("above") not in gone and x.get("below") not in gone]


def _resize(w: float, d: float, area: float, mcd: Optional[float]) -> Tuple[float, float]:
    """면적 area, 가로세로 비율 유지, 짧은 변 ≥ mcd."""
    k = math.sqrt(area / max(w * d, 1e-9))
    w2, d2 = w * k, d * k
    if mcd:
        if min(w2, d2) < mcd:
            if w2 <= d2:
                w2 = mcd
                d2 = max(mcd, area / mcd)
            else:
                d2 = mcd
                w2 = max(mcd, area / mcd)
    return round(w2, 4), round(d2, 4)


def apply_program(ir: dict, prog: dict, tol: float = 0.05) -> List[str]:
    """IR 을 제자리에서 바꾸고 변경 기록(문장 목록)을 돌려준다."""
    rep: List[str] = []
    blocks = ir["blocks"]
    by_id = {b["id"]: b for b in blocks}

    # ---- 고정 해제 -----------------------------------------------------------
    for pat in prog.get("unpin") or []:
        hit = [b for b in blocks if b.get("pinned") and fnmatch.fnmatch(b["id"], pat)]
        for b in hit:
            b.pop("pinned", None)
            b.pop("fixed_xy", None)
            b["rotatable"] = True
            if b.get("kind") == "obstacle":
                b["kind"] = "room"
        if hit:
            rep.append(f"고정 해제 {len(hit)}개 ({pat}) — 위치도 최적화 대상")

    # ---- 긴 요소를 구간으로 (배관대 등) — 구간마다 없앨 수 있게 -------------------------
    asis_all = prog.get("_asis")
    for sg in prog.get("segment") or []:
        rx = re.compile(sg["match"], re.I)
        L = float(sg["length_m"])
        new_blocks, n_src, n_seg = [], 0, 0
        for b in blocks:
            if not rx.search(b["id"]):
                new_blocks.append(b)
                continue
            n_src += 1
            a = (asis_all or {}).get("blocks", {}).get(b["id"])
            if b.get("pinned") and a is None:
                cx, cy = b["fixed_xy"]
                a = dict(x=cx - b["w"] / 2, y=cy - b["d"] / 2, w=b["w"], d=b["d"], floor=b.get("floor", 0))
            long_x = b["w"] >= b["d"]
            total = b["w"] if long_x else b["d"]
            k = max(1, int(math.ceil(total / L - 1e-9)))
            seg = total / k
            for j in range(k):
                nb = {kk: vv for kk, vv in b.items() if kk not in ("pinned", "fixed_xy")}
                nb["id"] = f"{b['id']}-S{j+1}"
                nb["name"] = f"{b.get('name', b['id'])} (구간 {j+1}/{k})"
                nb["w"], nb["d"] = (round(seg, 4), b["d"]) if long_x else (b["w"], round(seg, 4))
                nb["kind"] = "room"
                nb["rotatable"] = True
                nb["circulation"] = sg.get("type", "piperack")
                nb["optional"] = bool(sg.get("optional", True))
                if a is not None:
                    nb["floor"] = a["floor"]
                    asis_all["blocks"][nb["id"]] = dict(
                        x=a["x"] + (j * seg if long_x else 0.0), y=a["y"] + (0.0 if long_x else j * seg),
                        w=nb["w"], d=nb["d"], floor=a["floor"])
                new_blocks.append(nb)
                n_seg += 1
            if a is not None:
                asis_all["blocks"].pop(b["id"], None)
        gone = {b["id"] for b in blocks} - {b["id"] for b in new_blocks}
        ir["blocks"] = new_blocks
        _drop(ir, gone)
        blocks = ir["blocks"]
        if n_src:
            rep.append(f"{sg['match']}: {n_src}개를 {L:g} m 구간 {n_seg}개로 나눔 (고정 해제, 없앨 수 있음, "
                       f"{sg.get('type', 'piperack')}) — {sg.get('basis', '')}")

    # ---- 동선 종류 표시 --------------------------------------------------------
    for b in blocks:
        if b.get("circulation") is None:
            c = circulation_of(b.get("name", ""), b.get("kind", "equipment"))
            if c:
                b["circulation"] = c
                if b.get("kind") == "opening":
                    b["kind"] = "room"
                    b.pop("opening", None)
    for spec in prog.get("circulation") or []:
        rx = re.compile(spec["match"], re.I)
        for b in blocks:
            if rx.search(b.get("name", "") + " " + b["id"]):
                b["circulation"] = spec["type"]
                if spec.get("unpin") and b.get("pinned"):
                    b.pop("pinned", None); b.pop("fixed_xy", None); b["rotatable"] = True
                    b["kind"] = "room"
                if spec.get("optional"):
                    b["optional"] = True

    # ---- 계단 중복 제거 (IfcStair 객체가 계단실 IfcSpace 안에 또 있다) ----------------
    asis_b = (prog.get("_asis") or {}).get("blocks", {})
    if asis_b:
        rep += _cut_stairs_from_halls(blocks, asis_b)
        stairs = [b for b in blocks if b.get("circulation") == "stair" and b["id"] in asis_b]
        drop = set()
        for b in stairs:
            a = asis_b[b["id"]]
            for c in stairs:
                if c is b or c["id"] in drop or b["id"] in drop:
                    continue
                ac = asis_b[c["id"]]
                if ac["floor"] != a["floor"] or a["w"] * a["d"] > ac["w"] * ac["d"]:
                    continue
                ox = min(a["x"] + a["w"], ac["x"] + ac["w"]) - max(a["x"], ac["x"])
                oy = min(a["y"] + a["d"], ac["y"] + ac["d"]) - max(a["y"], ac["y"])
                if ox > 0 and oy > 0 and ox * oy >= 0.8 * a["w"] * a["d"]:
                    drop.add(b["id"])          # 작은 쪽(계단 객체)이 큰 쪽(계단실) 안에 있다
        if drop:
            _drop(ir, drop)
            blocks = ir["blocks"]
            rep.append(f"계단실 안에 겹쳐 있는 계단 객체 {len(drop)}개를 뺐다 (같은 계단을 두 번 세지 않게)")

    # ---- 수직 코어 묶기 -----------------------------------------------------------
    if prog.get("stack_cores"):
        rep += _stack_cores(ir, prog.get("_asis"))
        blocks = ir["blocks"]

    # ---- 복도 폭 ---------------------------------------------------------------
    cor = prog.get("corridor") or {}
    if cor.get("width_m"):
        wm, n = float(cor["width_m"]), 0
        for b in blocks:
            if b.get("circulation") != "corridor" or b.get("pinned"):
                continue
            w, d = b["w"], b["d"]
            if max(w, d) < 1.5 * min(w, d):
                continue        # 정사각형에 가까운 복도 조각(교차부)은 어느 쪽이 폭인지 모른다 — 두고 본다
            if w <= d and abs(w - wm) > 0.01:
                b["_program"] = f"복도 폭 {w:.2f} → {wm:g} m ({cor.get('basis', '')})"; b["w"] = wm; n += 1
            elif d < w and abs(d - wm) > 0.01:
                b["_program"] = f"복도 폭 {d:.2f} → {wm:g} m ({cor.get('basis', '')})"; b["d"] = wm; n += 1
        if n:
            rep.append(f"복도 구간 {n}개의 폭을 {wm:g} m 로 ({cor.get('basis', '')})")
    if prog.get("optional_corridors"):
        n = 0
        for b in blocks:
            if b.get("circulation") == "corridor" and not b.get("pinned"):
                b["optional"] = True; n += 1
        if n:
            rep.append(f"복도 구간 {n}개를 '없앨 수 있음' 으로 — 실 출입·동선 연결·피난 제약이 필요한 만큼만 남긴다")

    # ---- 외벽에 면해야 하는 실 (채광·구조대 진입창·급배기) -------------------------
    for ex in prog.get("exterior") or []:
        rx = re.compile(ex["match"], re.I)
        fl = ex.get("floors")          # 층 제한 (예: 지하는 채광 창이 없다 → [1, 2, 3])
        hit = [b for b in blocks if not b.get("circulation") and rx.search(f"{b.get('name', '')} {b['id']}")
               and (fl is None or b.get("floor") in fl)]
        for b in hit:
            b["need_exterior"] = True
        if hit:
            rep.append(f"외벽 접면 {len(hit)}개 ({ex['match']}) — {ex.get('basis', '')}")

    # ---- 실 규모 ---------------------------------------------------------------
    rules = [(r, re.compile(r["match"], re.I)) for r in prog.get("rooms") or []]
    shrunk = grown = 0
    d_area = 0.0
    for b in blocks:
        if b.get("pinned") or b.get("circulation") or b.get("kind") not in ("room", "equipment"):
            continue
        for r, rx in rules:
            if not rx.search(b.get("name", "")):
                continue
            a0 = b["w"] * b["d"]
            tgt = r.get("target_area_m2") or r.get("min_area_m2")
            mn = r.get("min_area_m2")
            mcd = r.get("min_clear_dim_m")
            new = None
            if tgt and a0 > tgt * (1 + tol) and not r.get("grow_only"):
                new = tgt; shrunk += 1
            elif mn and a0 < mn * (1 - tol):
                new = mn; grown += 1
            if new:
                w2, d2 = _resize(b["w"], b["d"], new, mcd)
                b["_program"] = (f"{r['type']}: {a0:.1f} → {w2 * d2:.1f} m² "
                                 f"({'축소' if w2 * d2 < a0 else '확대'}; {r.get('basis', '')})")
                d_area += w2 * d2 - a0
                b["w"], b["d"] = w2, d2
            elif mcd and min(b["w"], b["d"]) < mcd - 0.01:
                rep.append(f"[{b['id']}] {b.get('name')}: 짧은 변 {min(b['w'], b['d']):.2f} m < 최소 {mcd:g} m (현황 미달 — 그대로 둠)")
            break
    if rules:
        rep.append(f"실 규모 조정: 축소 {shrunk}개 · 확대 {grown}개 · 순변화 {d_area:+.1f} m² "
                   f"(규칙 없는 실은 그대로 — 인원·장비를 모르면 줄이지 않는다)")
    ir.setdefault("_program_report", []).extend(rep)
    return rep


def _cut_stairs_from_halls(blocks, asis_b) -> List[str]:
    """
    계단 객체가 복도·로비 공간 안에 놓여 있으면(계단 앞 복도 안의 계단), 그 공간에서 계단이 차지한
    끝부분을 잘라 낸다 — 계단은 계단 블록, 나머지는 복도 블록으로 겹치지 않게.
    계단이 공간의 한쪽 끝을 폭 전체로 차지할 때만 자른다(직사각형이 유지되는 경우).
    """
    rep = []
    stairs = [b for b in blocks if b.get("circulation") == "stair" and b["id"] in asis_b]
    halls = [b for b in blocks if b.get("circulation") in ("corridor", "lobby") and b["id"] in asis_b]
    eps = 0.05
    for s in stairs:
        a = asis_b[s["id"]]
        for h in halls:
            c = asis_b[h["id"]]
            if c["floor"] != a["floor"]:
                continue
            inside = (a["x"] >= c["x"] - eps and a["y"] >= c["y"] - eps and
                      a["x"] + a["w"] <= c["x"] + c["w"] + eps and a["y"] + a["d"] <= c["y"] + c["d"] + eps)
            if not inside:
                continue
            cut = None
            if abs(a["w"] - c["w"]) <= eps:                     # 폭 전체 — 아래/위 끝
                if abs(a["y"] - c["y"]) <= eps:
                    cut = dict(y=a["y"] + a["d"], d=c["d"] - a["d"])
                elif abs(a["y"] + a["d"] - c["y"] - c["d"]) <= eps:
                    cut = dict(d=c["d"] - a["d"])
            elif abs(a["d"] - c["d"]) <= eps:                   # 깊이 전체 — 왼/오른 끝
                if abs(a["x"] - c["x"]) <= eps:
                    cut = dict(x=a["x"] + a["w"], w=c["w"] - a["w"])
                elif abs(a["x"] + a["w"] - c["x"] - c["w"]) <= eps:
                    cut = dict(w=c["w"] - a["w"])
            if cut is None or min(cut.get("w", c["w"]), cut.get("d", c["d"])) < 0.5:
                continue
            c.update({k: round(v, 4) for k, v in cut.items()})
            h["w"], h["d"] = c["w"], c["d"]
            h["_program"] = f"계단({s['id']}) 이 차지한 부분을 잘라 낸 계단 앞 복도"
            rep.append(f"{h['id']} {h.get('name', '')}: 안의 계단 {s['id']} 부분을 잘라 복도 {c['w']:.1f}×{c['d']:.1f} m 로")
            break
    return rep


def _stack_cores(ir: dict, asis: Optional[dict]) -> List[str]:
    """
    층마다 따로 있는 계단·엘리베이터 중 평면이 겹치는 것을 하나의 다층 블록으로 묶는다.
    엔진은 다층 블록을 '구조적으로' 같은 평면 위치에 둔다 — 계단이 층마다 어긋나지 않는다.
    """
    fh = ir.get("floor_heights") or []
    if not fh:
        return ["수직 코어 묶기 생략 — floor_heights 가 없다"]
    asis_b = (asis or {}).get("blocks", {})
    cores = [b for b in ir["blocks"] if b.get("circulation") in ("stair", "elevator")
             and not b.get("pinned") and b["id"] in asis_b]
    used, groups = set(), []
    for b in sorted(cores, key=lambda b: (asis_b[b["id"]]["floor"], b["id"])):
        if b["id"] in used:
            continue
        grp = [b]
        used.add(b["id"])
        cur = b
        while True:
            a = asis_b[cur["id"]]
            nxt = None
            for c in cores:
                if c["id"] in used or c["circulation"] != b["circulation"]:
                    continue
                ac = asis_b[c["id"]]
                if ac["floor"] != a["floor"] + 1:
                    continue
                ox = min(a["x"] + a["w"], ac["x"] + ac["w"]) - max(a["x"], ac["x"])
                oy = min(a["y"] + a["d"], ac["y"] + ac["d"]) - max(a["y"], ac["y"])
                # 경계값(정확히 절반 겹침)도 같은 코어로 본다 — 엄격 부등호였을 때 SMR 1층 계단이
                # 위층 계단과 묶이지 않아 엉뚱한 곳에 놓였다 (독립 검증에서 발견).
                if ox >= 0.5 * min(a["w"], ac["w"]) - 1e-6 and oy >= 0.5 * min(a["d"], ac["d"]) - 1e-6:
                    nxt = c
                    break
            if nxt is None:
                break
            grp.append(nxt); used.add(nxt["id"]); cur = nxt
        if len(grp) > 1:
            groups.append(grp)
    gone = set()
    for grp in groups:
        base = grp[0]
        f0 = asis_b[base["id"]]["floor"]
        f1 = asis_b[grp[-1]["id"]]["floor"]
        base["w"] = max(g["w"] for g in grp)
        base["d"] = max(g["d"] for g in grp)
        base["h"] = round(sum(fh[f0:f1 + 1]) - 0.01, 4)     # 위층 수 = span — 한 층 더 넘지 않게
        base["floor"] = f0
        base["rotatable"] = False
        base["_program"] = f"수직 코어: {', '.join(g['id'] for g in grp)} 를 {f0+1}–{f1+1}층 한 블록으로"
        gone |= {g["id"] for g in grp[1:]}
    _drop(ir, gone)
    alone = [b["id"] for b in cores if b["id"] not in used or
             (b["id"] not in gone and not any(b is g[0] for g in groups))]
    warn = [f"⚠ 다른 층과 묶이지 않은 계단·승강기 {len(alone)}개: {', '.join(alone[:8])} — "
            f"EGRESS 가 계단 연속성을 검사한다"] if alone else []
    return warn + [f"수직 코어 {len(groups)}개 (계단·엘리베이터 {len(gone) + len(groups)}개를 층 관통 블록으로 묶음)"] if groups else []
