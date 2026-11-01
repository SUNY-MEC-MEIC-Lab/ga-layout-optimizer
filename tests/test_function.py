# -*- coding: utf-8 -*-
"""
test_function.py — 면적을 줄여도 각 공간이 '역할' 을 하는지 확인하는 제약과 규모 계획.

  · CIRC-ACCESS : 복도에서 들어갈 수 없는 실을 잡는다 (via_rooms 개 실을 거치는 것은 허용)
  · CIRC-CONNECT: 끊긴 복도를 잡는다
  · EGRESS      : 계단까지 거리·계단 수·계단 간 이격
  · RACK-SERVE  : 배관대에서 떨어진 설비, 끊긴 배관대
  · optional    : 솔버가 복도 구간을 없앨 수 있고, 없애도 위 제약은 지켜진다
  · program     : 근거 없는 규칙 거부, 실 축소·확대, 수직 코어 묶기, 구간 나누기
"""
import copy
import random
import unittest

from _util import G, CONS, spec, ctx, B
import program as PROGRAM


def _room(bid, w, d, **kw):
    return B(bid, w=w, d=d, kind="room", rotatable=False, **kw)


def _corr(bid, w, d, **kw):
    return B(bid, w=w, d=d, kind="room", rotatable=False, circulation="corridor", **kw)


def _stair(bid, **kw):
    return B(bid, w=3.0, d=6.0, kind="room", rotatable=False, circulation="stair", **kw)


def _viols(sp, placements, cid):
    c = ctx(sp, placements)
    return [v for v in CONS.REGISTRY[cid].evaluate(c, c.params_of(cid)) if v.cid == cid]


class TestAccess(unittest.TestCase):

    def _sp(self, via=0):
        return spec([_corr("C1", 20.0, 2.0), _room("R1", 4, 4), _room("R2", 4, 4), _room("R3", 4, 4)],
                    constraints=[{"id": "CIRC-ACCESS", "params": {"door_m": 0.9, "via_rooms": via,
                                                                  "touch_tol_m": 0.2}}])[0]

    def test_room_on_corridor_ok_and_detached_room_caught(self):
        sp = self._sp()
        ok = {"C1": (0, 0, 0), "R1": (0, 2, 0), "R2": (5, 2, 0), "R3": (10, 2, 0)}
        self.assertEqual(_viols(sp, ok, "CIRC-ACCESS"), [])
        bad = dict(ok, R3=(10, 12, 0))
        v = _viols(sp, bad, "CIRC-ACCESS")
        self.assertEqual([x.blocks for x in v], [["R3"]])

    def test_via_rooms(self):
        # R3 은 R2 위에 붙어 있다 — 복도에는 직접 닿지 않는다
        pl = {"C1": (0, 0, 0), "R1": (0, 2, 0), "R2": (5, 2, 0), "R3": (5, 6, 0)}
        self.assertEqual(len(_viols(self._sp(0), pl, "CIRC-ACCESS")), 1)
        self.assertEqual(_viols(self._sp(1), pl, "CIRC-ACCESS"), [])

    def test_touch_shorter_than_door_is_not_access(self):
        sp = self._sp()
        pl = {"C1": (0, 0, 0), "R1": (0, 2, 0), "R2": (5, 2, 0), "R3": (19.5, 2, 0)}   # 0.5 m 만 겹침
        self.assertEqual([x.blocks for x in _viols(sp, pl, "CIRC-ACCESS")], [["R3"]])


class TestConnectEgress(unittest.TestCase):

    def test_broken_corridor(self):
        sp = spec([_corr("C1", 10, 2), _corr("C2", 10, 2), _stair("S1")],
                  constraints=[{"id": "CIRC-CONNECT", "params": {"min_width_m": 1.1, "touch_tol_m": 0.2}}])[0]
        ok = {"C1": (0, 0, 0), "C2": (10, 0, 0), "S1": (20, 0, 0)}
        self.assertEqual(_viols(sp, ok, "CIRC-CONNECT"), [])
        bad = {"C1": (0, 0, 0), "C2": (13, 0, 0), "S1": (23, 0, 0)}
        self.assertTrue(_viols(sp, bad, "CIRC-CONNECT"))

    def test_egress_distance_and_count(self):
        sp = spec([_stair("S1"), _stair("S2"), _room("R1", 4, 4)],
                  constraints=[{"id": "EGRESS", "params": {"max_travel_m": 30.0, "min_exits": 2,
                                                           "exit_separation_frac": 0.33}}])[0]
        self.assertEqual(_viols(sp, {"S1": (0, 0, 0), "S2": (40, 0, 0), "R1": (10, 0, 0)}, "EGRESS"), [])
        far = _viols(sp, {"S1": (0, 0, 0), "S2": (3, 0, 0), "R1": (60, 0, 0)}, "EGRESS")
        self.assertTrue(any("가장 가까운 계단" in v.detail for v in far))
        self.assertTrue(any("계단 사이 거리" in v.detail for v in far))


class TestRackServe(unittest.TestCase):

    def test_equipment_far_from_rack(self):
        sp = spec([B("P1", w=4, d=4, zone="PROCESS"),
                   B("RK1", w=12, d=6, kind="room", circulation="piperack"),
                   B("RK2", w=12, d=6, kind="room", circulation="piperack")],
                  constraints=[{"id": "RACK-SERVE", "params": {"served": "zone:PROCESS", "max_gap_m": 3.0}}])[0]
        self.assertEqual(_viols(sp, {"P1": (0, 6, 0), "RK1": (0, 0, 0), "RK2": (12, 0, 0)}, "RACK-SERVE"), [])
        v = _viols(sp, {"P1": (0, 20, 0), "RK1": (0, 0, 0), "RK2": (30, 0, 0)}, "RACK-SERVE")
        self.assertTrue(any("배관대에서" in x.detail for x in v))
        self.assertTrue(any("끊겼다" in x.detail for x in v))


class TestOptionalBlocks(unittest.TestCase):

    def test_solver_removes_spare_corridor_but_keeps_access(self):
        blocks = [_corr(f"C{k}", 8.0, 2.0, optional=True) for k in range(6)]
        blocks += [_room(f"R{k}", 4.0, 4.0) for k in range(4)]
        blocks += [_stair("S1")]
        cons = [{"id": "CIRC-ACCESS", "params": {"door_m": 0.9, "touch_tol_m": 0.2, "via_rooms": 0}},
                {"id": "CIRC-CONNECT", "params": {"min_width_m": 1.0, "touch_tol_m": 0.2}}]
        sp = spec(blocks, constraints=cons, preset="space_first",
                  weights={"constraint.CIRC-ACCESS": 5000.0, "constraint.CIRC-CONNECT": 5000.0})[0]
        best, F, _ = G.optimize(sp, iters=4000, restarts=2, seed=7, verbose=False)
        F2, t, geo, env, v, sh = best.evaluate(detail=True)
        hard = [x for x in v if x.hard and x.amount > 1e-6]
        self.assertEqual(hard, [], [x.detail for x in hard])
        self.assertGreater(len(best.off), 0, "남는 복도 구간을 하나도 없애지 않았다")
        self.assertTrue(all(sp.blocks[i].optional for i in best.off))

    def test_no_optional_keeps_move_set(self):
        sp = spec([_room("R1", 4, 4), _room("R2", 3, 3)])[0]
        a = G.Solution(sp, random.Random(1)); b = a.clone()
        G._mutate(a, random.Random(5)); G._mutate(b, random.Random(5))
        self.assertEqual((a.gp, a.gm, a.rot), (b.gp, b.gm, b.rot))
        self.assertEqual(sp._moves, G.MOVES)


class TestProgram(unittest.TestCase):

    def _ir(self):
        return {"blocks": [
            {"id": "E1", "name": "EXAM 1", "w": 5.0, "d": 4.0, "kind": "room"},
            {"id": "E2", "name": "EXAM 2", "w": 2.0, "d": 2.0, "kind": "room"},
            {"id": "O1", "name": "OPEN OFFICE", "w": 10.0, "d": 8.0, "kind": "room"},
            {"id": "C1", "name": "CORRIDOR", "w": 20.0, "d": 3.0, "kind": "room"},
            {"id": "S1", "name": "STAIR", "w": 3.0, "d": 6.0, "kind": "room"},
            {"id": "S2", "name": "STAIR", "w": 3.0, "d": 6.0, "kind": "room"},
            {"id": "PR", "name": "PIPE RACK", "w": 30.0, "d": 6.0, "kind": "obstacle", "pinned": True,
             "fixed_xy": [15.0, 23.0], "floor": 0},
        ], "links": [{"a": "S2", "b": "E1"}], "separations": [], "floor_heights": [4.0, 4.0]}

    def test_resize_stack_segment(self):
        ir = self._ir()
        asis = {"blocks": {"S1": dict(x=0, y=0, w=3, d=6, floor=0), "S2": dict(x=0.2, y=0, w=3, d=6, floor=1),
                           "PR": dict(x=0, y=20, w=30, d=6, floor=0)}}
        rep = PROGRAM.apply_program(ir, {
            "rooms": [{"type": "exam", "match": "EXAM", "target_area_m2": 11.0, "min_area_m2": 7.4,
                       "min_clear_dim_m": 2.4, "basis": "test"}],
            "corridor": {"width_m": 1.8, "basis": "test"},
            "stack_cores": True, "optional_corridors": True,
            "segment": [{"match": "^PR$", "length_m": 12.0}],
            "_asis": asis})
        b = {x["id"]: x for x in ir["blocks"]}
        self.assertAlmostEqual(b["E1"]["w"] * b["E1"]["d"], 11.0, places=2)      # 20 → 11 m²
        self.assertAlmostEqual(b["E2"]["w"] * b["E2"]["d"], 7.4, places=1)       # 4 → 7.4 m² (미달 → 키움)
        self.assertGreaterEqual(min(b["E2"]["w"], b["E2"]["d"]), 2.4 - 1e-9)
        self.assertEqual(b["O1"]["w"] * b["O1"]["d"], 80.0, "규칙 없는 실은 그대로")
        self.assertEqual(b["C1"]["d"], 1.8)
        self.assertTrue(b["C1"]["optional"])
        self.assertNotIn("S2", b, "위층 계단은 아래층 계단과 한 코어로 묶인다")
        self.assertEqual(ir["links"], [], "묶여 사라진 블록의 링크도 사라진다")
        self.assertGreater(b["S1"]["h"], 4.0)
        segs = [x for x in ir["blocks"] if x["id"].startswith("PR-S")]
        self.assertEqual(len(segs), 3)
        self.assertTrue(all(s["optional"] and s["circulation"] == "piperack" and not s.get("pinned") for s in segs))
        self.assertEqual(sorted(k for k in asis["blocks"] if k.startswith("PR")), ["PR-S1", "PR-S2", "PR-S3"])
        self.assertTrue(rep)

    def test_tools_reject_rule_without_basis(self):
        import os, sys, tempfile
        from _util import ROOT
        sys.path.insert(0, os.path.join(ROOT, "server"))
        import tools as T
        t = T.Tools(T.Workspace(tempfile.mkdtemp(prefix="smrga-"), allow_local_paths=True, allow_url_fetch=False))
        pid = t.ga_load_example(name="hospital_or")["project"]["project_id"]
        with self.assertRaises(T.ToolError):
            t.ga_update_ir(project_id=pid, reason="x", patch={"program": {"rooms": [
                {"type": "or", "match": "OR", "target_area_m2": 37.2}]}})


if __name__ == "__main__":
    unittest.main()
