# -*- coding: utf-8 -*-
"""
test_benchmarks.py — 3단계 검증 계획.

  1단계 (즉시)  QAPLIB + 2DPackLib — 최적성 갭을 정량 보고할 수 있는 유일한 단계.
                여기서 못 맞추면 원전 문제로 갈 이유가 없다.
  2단계 (핵심)  Wrigley 2019 Shearon Harris 데이터셋 (CC BY 4.0) 재현,
                Ejeh 2019 부록 B 요소플랜트 8기기 MILP 정식화 대조.
  3단계        ABWR DCD Ch.1 표고별 실 폴리곤, AP1000 §12.3 방사선구역도.

  + 음성 대조군: 실현 불가능한 요구사항 집합에 '불가능' 이라고 답하는지.

★ 외부 데이터는 폐쇄망 특성상 수동으로 넣는다. 없으면 SKIP 하고 안내를 출력한다.
  값을 지어내서 '통과' 시키지 않는다 — 그것이 이 분야에서 가장 흔한 실패다.
"""
import glob
import json
import os
import subprocess
import sys
import unittest

from _util import DATA, ENGINE, EXAMPLES, G
import bench_qap
import validate_spec

QAPLIB = os.path.join(DATA, "qaplib")
PACK2D = os.path.join(DATA, "2dpacklib")
WRIGLEY = os.path.join(DATA, "wrigley2019")
EJEH = os.path.join(DATA, "ejeh2019")


def _has(d, pat="*"):
    return os.path.isdir(d) and bool(glob.glob(os.path.join(d, pat)))


# ---------------------------------------------------------------------------
# 1단계
# ---------------------------------------------------------------------------

class TestStage1Optimality(unittest.TestCase):

    def test_selftest_gap_is_zero_on_brute_forced_instances(self):
        """
        외부 데이터 없이도 최적성 갭을 보고할 수 있는 경로.
        n<=8 전수탐색이 '진짜 최적' 을 주므로 탐색부의 갭이 정확히 측정된다.
        """
        rows = bench_qap.selftest(seed=20260826, iters=20000, restarts=3)
        self.assertEqual(len(rows), 3)
        for r in rows:
            self.assertLessEqual(r["gap_pct"], 0.0 + 1e-9,
                                 f"{r['instance']}: 갭 {r['gap_pct']}% — "
                                 f"탐색부가 소규모 인스턴스조차 못 맞춘다")

    def test_fixed_facility_matches_brute_force(self):
        """fixed={시설: 위치} — 고정 시설은 움직이지 않고, 나머지는 조건부 최적에 도달한다."""
        import itertools
        A, B = bench_qap.random_instance(7, seed=3)
        perm, c = bench_qap.solve_qap(A, B, iters=20000, restarts=3, fixed={2: 5})
        self.assertEqual(perm[2], 5)
        best = min(bench_qap.qap_cost(p, A, B)
                   for p in itertools.permutations(range(7)) if p[2] == 5)
        self.assertAlmostEqual(c, best)

    def test_qaplib_instances(self):
        if not _has(QAPLIB, "*.dat"):
            self.skipTest(
                f"QAPLIB 데이터 없음. {QAPLIB} 에 .dat/.sln 을 넣을 것.\n"
                f"  출처: coral.ise.lehigh.edu/data-sets/qaplib/\n"
                f"  ※ 최적값은 .sln 파일에서 읽는다. 코드에 하드코딩하지 않는다.")
        # 예산은 CLI 기본값(100000×5)과 같게 둔다. 50000×3 에서는 chr25a 갭이 23.9% 로
        # 15% 를 넘었다 — 예산이 작으면 n≥25 에서 탐색이 덜 수렴한다 (2026-11-01 확인).
        rows = bench_qap.run_dir(QAPLIB, iters=100000, restarts=5, seed=20260826)
        self.assertTrue(rows, "「.dat 은 있는데 짝이 되는 .sln 이 없다」")
        worst = max(r["gap_pct"] for r in rows)
        print(f"\n  QAPLIB {len(rows)}건 · 최대 갭 {worst:.2f}%")
        # 회귀 감시용 상한. 넉넉히 잡되, 갭은 반드시 '보고' 된다.
        self.assertLess(worst, 15.0,
                        "QAPLIB 갭이 15% 를 넘는다 — 탐색부 회귀를 의심할 것")

    def test_2dpacklib_instances(self):
        if not _has(PACK2D):
            self.skipTest(
                f"2DPackLib 데이터 없음. {PACK2D} 에 인스턴스를 넣을 것.\n"
                f"  출처: site.unibo.it/operations-research/en/research/2dpacklib")
        self.fail("2DPackLib 로더 미구현 — 데이터를 넣었다면 로더를 먼저 붙일 것")


# ---------------------------------------------------------------------------
# 2단계
# ---------------------------------------------------------------------------

class TestStage2Reproduction(unittest.TestCase):

    def test_wrigley2019_shearon_harris(self):
        """
        Shearon Harris 데이터셋(CC BY 4.0)으로 층 배정까지 포함한 자리 배정을 푼다.
        RCP 는 원자력섬에 고정, 나머지 20개 모듈의 층·자리를 모두 결정변수로 둔다.
        검사하는 것: 데이터를 빠짐없이 읽는가 · seed 를 바꿔도 같은 최적값에 도달하는가 ·
        4층 격자가 3층 격자보다 나쁘지 않은가(논문도 4층이 더 좋다고 보고).
        """
        xlsx = os.path.join(WRIGLEY, "shearon_harris.xlsx")
        if not os.path.exists(xlsx):
            self.skipTest(
                f"Wrigley 2019 데이터 없음. {xlsx} 에 넣을 것 (CC BY 4.0).\n"
                f"  출처: data.mendeley.com/datasets/w39zbzj6bk/1")
        import bench_wrigley as BW
        data = BW.load(xlsx)
        self.assertEqual(len(data["ids"]), 21)
        self.assertEqual(sum(1 for r in data["W"] for v in r if v), 65,
                         "DSM 의 모든 칸(비대칭)을 읽어야 한다")
        self.assertEqual({g: len(v) for g, v in data["grids"].items()},
                         {"one_side_4F": 20, "one_side_3F": 21,
                          "two_sides_3F": 12, "two_sides_4F": 16})
        res = {}
        for g in ("one_side_4F", "one_side_3F"):
            objs = {BW.solve(data, g, seed=s)["objective"]   # 기본 예산 200000×6
                    for s in (20260826, 1)}
            print(f"\n  Wrigley 2019 {g}: 목적함수 {sorted(objs)}")
            self.assertEqual(len(objs), 1, f"{g}: seed 에 따라 해가 다르다 — 수렴 부족")
            res[g] = objs.pop()
        self.assertLessEqual(res["one_side_4F"], res["one_side_3F"])
        with self.assertRaises(ValueError):
            BW.instance(data, "two_sides_3F")   # 자리 12 < 모듈 20 — 지어내지 않고 멈춘다

    def test_wrigley2019_paper_reproduction(self):
        """
        논문(−33.9~46.1%) 대조. 기준안 좌표·기준 목적함수·모듈 재묶음은 논문에만 있고
        데이터셋에 없다. 원논문에서 옮겨 적은 expected.json 이 있을 때만 돈다.
        """
        exp_path = os.path.join(WRIGLEY, "expected.json")
        if not os.path.exists(exp_path):
            self.skipTest(
                "Wrigley 2019 논문 대조값 없음. 원논문(doi:10.1016/j.nucengdes.2018.10.023)"
                "에서 격자별 최적 목적함수를 옮겨 적을 것:\n"
                f"  {exp_path} = {{\"optimum\": {{\"one_side_4F\": …, \"one_side_3F\": …}}, "
                "\"source\": \"표·쪽 번호\"}}\n"
                "  ※ 기준 목적함수 14,914 는 출처를 확인하지 못한 값이다. 쓰지 말 것.")
        import bench_wrigley as BW
        with open(exp_path, encoding="utf-8") as fp:
            exp = json.load(fp)
        data = BW.load(os.path.join(WRIGLEY, "shearon_harris.xlsx"))
        for g, target in exp["optimum"].items():
            got = BW.solve(data, g)["objective"]
            print(f"\n  {g}: 우리 {got:,.0f} · 논문 {target:,.0f}")
            self.assertLessEqual(got, target * 1.05,
                                 f"{g}: 논문 최적값보다 5% 넘게 나쁘다")

    def test_ejeh2019_appendix_b(self):
        """
        Ejeh 2019 부록 B 의 요소플랜트 8기기 전체 입력데이터가 공개되어 있다.
        MILP 정식화 검증에 쓴다. 기대값: 4층 117,431 rmu.
        """
        if not _has(EJEH):
            self.skipTest(
                f"Ejeh 2019 부록 B 데이터 없음. {EJEH} 에 넣을 것.\n"
                f"  기대값: 1층 260,942 / 2층 167,299 / 3층 149,498 / 4층 117,431 rmu\n"
                f"  ※ 이 엔진은 MILP 가 아니라 메타휴리스틱이므로 값이 아니라 "
                f"'층수-비용 곡선의 형상' 을 대조한다.")
        spec_path = os.path.join(EJEH, "spec.json")
        sp = G.load_spec(spec_path)
        import decompose
        rows = decompose.floor_sweep(sp, [1, 2, 3, 4], iters=40000, restarts=3,
                                     seed=20260826, verbose=True)
        best = min(rows, key=lambda r: r["F"])
        print(f"\n  Ejeh 2019 층수 스윕 최적 = {best['n_floors']}층")
        self.assertLess(rows[-1]["F"], rows[0]["F"],
                        "다층이 단층보다 나빠졌다 — 수직 비용 모형을 의심할 것")


# ---------------------------------------------------------------------------
# 음성 대조군
# ---------------------------------------------------------------------------

class TestNegativeControl(unittest.TestCase):
    """
    LLM 파이프라인은 유창하게 실패한다. 실현 불가능한 요구사항 집합을 넣어
    '불가능' 이라고 답하는지 정례적으로 확인한다.
    """

    def setUp(self):
        self.path = os.path.join(EXAMPLES, "spec_infeasible.json")
        with open(self.path, encoding="utf-8") as fp:
            self.ir = json.load(fp)
        self.rep = validate_spec.check_ir(self.ir, probe=False)
        self.msgs = "\n".join(self.rep.ERR)

    def test_every_planted_defect_is_detected(self):
        expect = {
            "면적 초과": "실현 불가",
            "표고 모순": "표고 제약 모순",
            "치수 누락": "치수 'w' 누락",
            "전기이격 3ft": "ELEC-3FT-5FT",
            "SGI 값": "금지:SGI",
        }
        for label, needle in expect.items():
            self.assertIn(needle, self.msgs, f"음성 대조군의 '{label}' 이 안 잡혔다")

    def test_zone_numbering_is_warned(self):
        self.assertTrue(any("ZONE-NUMBERING" in m for m in self.rep.WARN))

    def test_pipeline_refuses_to_produce_a_drawing(self):
        out = os.path.join(os.path.dirname(__file__), "_tmp_neg")
        r = subprocess.run([sys.executable, os.path.join(ENGINE, "run.py"),
                            self.path, "--iters", "50", "--out", out],
                           capture_output=True, text=True, cwd=ENGINE)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(out))

    def test_impossible_geometry_is_not_silently_shrunk(self):
        """단일 블록이 외피보다 크면 '알아서 줄이지' 않고 ERROR 로 멈춘다."""
        self.assertTrue(any("단일 블록이 외피 한계보다 큼" in m
                            for m in self.rep.ERR))


if __name__ == "__main__":
    unittest.main(verbosity=2)
