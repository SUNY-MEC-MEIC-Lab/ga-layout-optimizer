# 벤치마크 데이터 (수동 배치)

폐쇄망 설치를 전제하므로 **자동 다운로드하지 않는다.** 아래 데이터를 손으로 넣으면
`tests/test_benchmarks.py` 가 SKIP 을 멈추고 실제 갭을 보고한다.
**데이터가 없으면 테스트는 SKIP 된다. 값을 지어내서 통과시키지 않는다.**

## 1단계 — 최적성 갭

### `qaplib/` — **동봉됨** (12건)
- 출처: QAPLIB, R.E. Burkard, S.E. Karisch, F. Rendl, *J. Global Optim.* 10:391–403 (1997)
  · `coral.ise.lehigh.edu/data-sets/qaplib/` (공개 배포, 사용 제한 표기 없음)
- 동봉: chr12a chr25a els19 esc16a had12 kra30a nug12 nug20 nug30 rou12 ste36a tai20a (.dat + .sln)
- **최적값은 `.sln` 에서 읽는다. 코드에 하드코딩하지 않는다.**
- 다른 인스턴스는 같은 폴더에 `.dat` 과 짝이 되는 `.sln` 을 넣으면 자동으로 포함된다.
  `.sln` 이 없는 `.dat` 은 갭을 보고할 수 없으므로 건너뛴다.

외부 데이터가 없어도 `bench_qap.py --selftest` 가 n≤8 전수탐색으로
**진짜 최적** 을 만들어 갭을 보고한다.

### `2dpacklib/`
- 출처: `site.unibo.it/operations-research/en/research/2dpacklib`
- 로더 미구현. 데이터를 넣으려면 로더를 먼저 붙일 것 (테스트가 그렇게 실패한다).

## 2단계 — 재현

### `wrigley2019/` — **동봉됨**
- `shearon_harris.xlsx` — Paul Wrigley, "Shearon Harris layout data", University of Derby (2018),
  **CC BY 4.0**, `data.mendeley.com/datasets/w39zbzj6bk/1` (원본 그대로, 수정 없음)
- 논문: Wrigley et al. (2019) *Nucl. Eng. Des.* 341:100–111, doi:10.1016/j.nucengdes.2018.10.023
- 읽기·풀기: `engine/bench_wrigley.py` (표준 라이브러리만). RCP 고정, 20개 모듈의 **층과 자리를 모두** 배정.
- 논문 대조용 `expected.json` 은 **비어 있다** — 기준안 좌표·기준 목적함수·두 면 배치의 모듈 묶음이
  데이터셋에 없고 논문에만 있다. 원논문에서 옮겨 적으면 `test_wrigley2019_paper_reproduction` 이 돈다:
  ```json
  {"optimum": {"one_side_4F": 0, "one_side_3F": 0}, "source": "Table N, p. N"}
  ```
- ※ 통용되던 "기준 목적함수 14,914" 는 출처를 확인하지 못한 값이다. 쓰지 말 것.

### `ejeh2019/`
- Ejeh 2019 부록 B 의 요소플랜트 8기기 전체 입력데이터가 공개되어 있다.
- 넣을 것: 변환된 `spec.json`
- 기대값(참고): 1층 260,942 / 2층 167,299 / 3층 149,498 / **4층 117,431 rmu**
  (수치는 보고서와 일치 확인됨. 단위 표기 "rmu" 는 보고서에 없으므로 원논문에서 확인할 것.)
- ※ 본 엔진은 MILP 가 아니라 메타휴리스틱이므로 값이 아니라
  **층수-비용 곡선의 형상**을 대조한다.

## 3단계 (미구현)

- ABWR DCD Ch.1 (벡터 PDF) — 표고별 실 폴리곤 추출
- AP1000 §12.3 방사선구역도 31장 — 선량 제약 인코딩
