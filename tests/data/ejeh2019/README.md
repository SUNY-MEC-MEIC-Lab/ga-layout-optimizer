# Ejeh 2019 — 다층 공정 플랜트 배치 (부록 B)

- 논문: J. O. Ejeh, S. Liu, L. G. Papageorgiou (2019), *Optimal layout of multi-floor process plants using MILP*,
  Computers & Chemical Engineering 131, 106573. doi:10.1016/j.compchemeng.2019.106573
- 저자 원고(무료): https://discovery.ucl.ac.uk/10096679/1/CACE_JOE_SL_LGP_accepted.pdf
- `ejeh2019_appendixB.json` — 부록 B 표 B.1–B.8 (요소 8 · CDU 17 · LNG 22 · COGP 25 기기의 치수, 연결 비용·펌핑 비용·
  배관 높이, 층 수 K·층고 FH·FC1·FC2·LC). 동료가 옮긴 파일이고, **PDF 원문 표와 숫자를 전수 대조해 불일치 0** 을 확인했다
  (2026-11-01). 기기 이름은 PDF 합자(fl/fi)가 빠져 있다 — 숫자에는 영향 없음.
- 표에 없는 실험 조건(최소 이격·후보 바닥 크기·LNG 적층/공지)은 `engine/bench_ejeh.py` 에 논문 4절 본문을 근거로 넣었다.
- 실행: `python3 engine/bench_ejeh.py tests/data/ejeh2019/ejeh2019_appendixB.json --plant urea --seeds 5`
