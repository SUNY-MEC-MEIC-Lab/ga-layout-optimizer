# 구조 — 파이프라인 · 제약 라이브러리 · 알고리즘

[← README](../README.md) · [결과 상세](RESULTS.md) · [벤치마크](BENCHMARKS.md) · [한계](LIMITATIONS.md) · [설치·연결](CONNECT.md)

이 문서는 엔진이 어떻게 구성되어 있는지, 무엇이 결정론적이고 무엇이 LLM 의 몫인지를 설명한다.
설계 원칙 하나로 요약하면 **LLM 은 좌표를 한 개도 생성하지 않는다**는 것이다.

## 1. 4단계 파이프라인

```
자연어 요구사항
   │
   ▼  LAYER 1 — LLM : 추출 · 되묻기 · 사전검증 제약 라이브러리에서 선택
Design Intent IR (JSON)
   │
   ▼  결정론적 규칙 검증기 (LLM 미사용)
╔══════════ GATE 1 : 사람 승인 ══════════╗
║ ERROR 0 이어야 통과. 승인 즉시 IR 동결 ║
║ 이후 전 과정은 LLM 호출 0회로 재현     ║
╚════════════════════════════════════════╝
   │
   ▼  LAYER 2 — 결정론적 솔버 (seed 고정)
Sequence-Pair 패킹 → SA 또는 NSGA-II 다목적
   │
   ▼  LAYER 3 — 결정론적 도면 생성기
SVG / DXF / JSON — 모든 치수는 IR 과 솔버에서만 온다
   │
   ▼  LAYER 4 — LLM : 읽기 전용 해설 · 트레이드오프 · 추적성 보고
```

이 구조는 우회로가 아니다. 원자력 품질보증 규정 **10 CFR 50 Appendix B Criterion III** 는 설계검증 수단으로
"설계검토, **대안적 또는 단순화된 계산방법의 수행**, 시험"을 명시하고 있으므로,
LLM 산출물을 결정론적 솔버로 재계산해 검증하는 것은 **규정이 이미 기술해 둔 경로**다.
원자력이 아닌 분야에서도 같은 원칙이 성립한다 — 생성자와 검증자를 분리하고, 검증은 결정론적 도구가 한다.

## 2. v0.3 — 도면을 넣으면, 그 공간을 더 작게

```
도면 파일 (DXF · SVG · PDF · PNG · IFC · CSV/XLSX)
   │  결정론적 파서 — LLM 이 좌표를 읽지 않는다
   ▼
현황 배치 (Takeoff) ──────────────┐  인식 미리보기를 사람이 확인 (축척·분류)
   │                               │
   ▼  도면이 모르는 것은 질문으로   │
IR 초안: 기기·실 치수, 고정 장애물, │  "현재 공간" 외곽 = 넘을 수 없는 한계
         공간 우선(space_first)     │
   ▼  요건(연결·구역·이격) 반영 → Gate 1 → 사람 승인 → 동결
결정론적 솔버 (현황 배치에서 출발 + 다중 재시작)
   ▼
같은 목적함수로 현황 vs 최적화 채점 → 판정 · 도면 · 보고서
```

| 하고 싶은 것 | 무엇이 해 주나 |
|---|---|
| 아무 형식의 도면을 넣는다 | `engine/importers/` — DXF(R12~2018, 블록·해치·MTEXT·한글), SVG(transform·path), **벡터 PDF**(OCG 레이어·한글 ToUnicode·xref stream), **PNG 래스터**(벽으로 둘러싸인 실 인식), IFC(IfcSpace·기기 압출형상·층), CSV/XLSX/JSON 기기 목록. DWG·JPEG 는 변환 방법을 안내한다 |
| 그 공간 안에서 더 작게 | 현재 외곽 → `max_w/max_d` hard 한계, `preset: space_first`, 코어·기둥·격납은 `pinned` 고정 장애물(다른 블록이 피해 간다), 배치 금지 영역 `void` |
| 개선이 진짜인지 | 현황 배치를 **같은 IR·같은 목적함수**로 채점해 비교. 현황이 더 나으면 "현황 유지" 판정. 해에 hard 위반이 있으면 "채택 불가" |
| Claude 와 GPT 에서 쓰기 | `server/mcp_server.py` — 표준 라이브러리만 쓴 **MCP 서버**. stdio(Claude Code·Desktop·Codex) + Streamable HTTP(ChatGPT 웹·Claude.ai 커넥터) |
| 사람이 직접 쓰기 | `/studio` 브라우저 화면 — 업로드 → 인식 확인 → 요건 → Gate 1 승인 → 실행 → 현황 대비 비교 |

### 기능 유지 최적화 — "줄이되 각 공간이 역할을 하게"

면적만 보고 줄이면 복도가 끊기고 실에 들어갈 수 없게 된다. 그래서 **고정은 없애고(계단 코어·배관대·크레인도 이동,
복도·배관대 구간은 삭제 가능) 대신 역할을 제약으로 지킨다** — 실 출입(`CIRC-ACCESS`), 동선 연결(`CIRC-CONNECT`),
피난(`EGRESS`), 배관대·크레인 공급(`RACK-SERVE`), 근거 있는 실 규모 계획(`program`).
요건과 근거 출처: [`examples/function/`](../examples/function/README.md).

## 3. MCP 도구 (18개)

| 도구 | 하는 일 | 쓰기 |
|---|---|---|
| `ga_supported_formats` · `ga_upload_link` | 형식·전달 방법 안내 | |
| `ga_import_drawing` | 도면 → 현황 배치 + 인식 미리보기 SVG | ✓ |
| `ga_create_project` | 현황 → IR 초안 + asis.json + **확인 질문** | ✓ |
| `ga_create_project_from_ir` | 자연어 경로 (좌표 필드 거부) | ✓ |
| `ga_list_examples` · `ga_load_example` · `ga_apply_example_requirements` | 내장 예제 | ✓ |
| `ga_get_ir` · `ga_update_ir` | IR 조회 · 비좌표 필드 패치 (근거 `reason` 필수, 편집 시 동결 해제) | ✓ |
| `ga_validate` | Gate 1 결정론적 검증 | |
| `ga_freeze` | **사람 승인** 후 IR 동결 (`approved_by` 필수) | ✓ |
| `ga_optimize` · `ga_run_status` | 동결된 IR 로만 실행 · 진행/결과 | ✓ |
| `ga_get_drawing` · `ga_explain` · `ga_floor_sweep` · `ga_constraint_catalog` | 도면·해설용 사실·층수 스윕·제약 카탈로그 | |

도구가 강제하는 규칙: 좌표(`x`·`y`·`fixed_xy`)는 대화로 넣거나 바꿀 수 없다 · 동결 안 된(또는 동결 후 바뀐) IR 로는
실행 거부 · 결과는 `{IR 해시, seed, 엔진 소스}` 로 캐시되어 같은 입력은 같은 결과 해시 · 가중치 패치는 병합되고
층고·외곽이 바뀌면 hard 가중치를 다시 산정(낮추지 않음).

## 4. 제약조건 라이브러리

LLM 은 여기서 **선택**만 하고 파라미터를 채운다. 수식을 발명하지 않는다.
전체 카탈로그(코드에서 자동 생성, `python3 engine/gen_docs.py --write`):
[`skills/ga-layout/references/constraint-library.md`](../skills/ga-layout/references/constraint-library.md)

### 기능 유지 제약 (모든 건물 유형)

| ID | 제약 | 근거 예 |
|---|---|---|
| `CIRC-ACCESS` | 실·기기가 복도에 일정 폭 이상 접해 출입 가능 | IBC §1010.1.1 문 폭, ADA §404.2.3 |
| `CIRC-CONNECT` | 층마다 복도·계단이 끊기지 않고 하나로 연결 | IBC Table 1020.3 복도 폭 |
| `EGRESS` | 층당 출구 수 · 출구 간 대각선 거리 · 보행거리 · 위층 계단이 피난층까지 연속 | IBC §1006.3, §1007.1.1, Table 1017.2 |
| `RACK-SERVE` | 설비가 배관대·크레인 작업반경 안에 있고 배관대는 끊기지 않음 | CCPS 2018 (배치 원칙) |
| `program` | 근거 있는 실만 기준 규모로 축소·확대 — 근거(`basis`) 없는 실은 손대지 않음 | FGI, ASR 등 |

### 원전 고유 제약 (10종)

이 라이브러리는 원전 보조건물 예제를 위해 먼저 만들어졌고, 그 도메인의 제약이 가장 많다.
다른 도메인에서는 쓰지 않으면 된다 — 선택하지 않은 제약은 평가되지 않는다.

| ID | 제약 | 근거 |
|---|---|---|
| `FIRE-20FT` | 화재방호 계열 분리 | 10 CFR 50 App. R III.G.2 (20 ft = 6.096 m). **이 값이 GA 의 실질 그리드 모듈이다** |
| `FIRE-HATCH` | 해치·계단에 의한 화재구역 병합 | RG 1.189 Rev.5 |
| `TURBINE-25` | 터빈 미사일 금지 부채꼴 (±25°, 방위각이 이산 결정변수) | RG 1.115 |
| `SEISMIC-GAP` | 건물 간 이격 — 고정 수치가 아니라 성능식 | SRP 3.7.2 |
| `HELB-DIST` | 고에너지배관파단 — 거리에 의한 분리가 규제상 1순위 | BTP 3-3 |
| `TALL-EQUIP` | 다층 관통 기기 (관통부 정렬) | — |
| `FREE-AREA` | 공지 제약 (작업공간 / 비상공간) | Ejeh 2019 |
| `LOAD-PATH` | 안전하중경로 — 단일 낙하가 중복 트레인을 동시 무력화 금지 | NUREG-0612 §5.1.1 |
| `VITAL-AREA` | 중요구역 집약 + 2중 방벽 | 10 CFR 73.55(e)(9) |
| `ELEC-SEP` | 전기계통 물리적 분리 — **기본값 없음. 원문 대조 강제** | GDC 17 / RG 1.75 Rev.3 |

`FIRE-HATCH` 는 선행 프로토타입이 전혀 잡지 못하던 항목이다. 반출 해치·계단이 서로 다른
화재구역에 걸치면 **양쪽이 하나의 화재구역으로 병합되어** 분리 요건이 무효가 된다.
모듈 반출로는 화재구역 설계와 **동시에** 풀어야 한다.

**2차 범위 (미구현, 후속 확장):** 다수호기 동시영향(IAEA SSR-2/1 Req.17 — 부지배치 문제라 1차 제외) ·
내부침수 분리(SRP 3.4.1/3.4.2) · 항공기 충돌 기능분리(10 CFR 50.150) · 격납 격리밸브 검사공간(GDC 57) ·
토네이도 미사일(RG 1.76) · A\*/Dijkstra 라우팅 사후검증. [한계](LIMITATIONS.md) 2·5항 참조.

### 사용금지 규제 수치 5건

[`regulatory-numbers.md`](../skills/ga-layout/references/regulatory-numbers.md) 에 문서화되어 있고,
`engine/constraints.py` 의 `scan_forbidden()` 이 코드에서도 막는다. 원문에 없는 수치가
"관행값" 으로 굳어져 IR 에 들어오는 것을 막기 위한 장치다.

1. 전기계통 이격 **"수평 3 ft / 수직 5 ft"** — RG 1.75 Rev.3 에는 수치가 없다. IEEE 384-1981 관행값.
2. 건물 간 이격 **고정 수치** — SRP 3.7.2 는 성능식이다.
3. **방사선구역 번호 체계** 하드코딩 — RG 8.8 이 구역 번호를 일절 언급하지 않는다.
4. 격리구역 폭 **"20 ft"** — §73.51(ISFSI) 조항이다. §73.55 에는 폭 수치가 없다.
5. **Safeguards Information** — 슬롯만 두고 값은 보안등급 자료에서 주입한다.

## 5. 목적함수 (9항 + 제약 라이브러리)

체적 · 연결비용 · 방사선구역 분산(RZDI) · 물리적 분리 · 외벽 접면 · 크레인 커버리지 ·
외피 형상비 · 질량 편심 · 중력구동 표고 순서(원전 고유).
→ [`objective-terms.md`](../skills/ga-layout/references/objective-terms.md)

**가중치 자동 점검**: hard 페널티가 "1 m 를 양보해 얻는 한계이득"의 10배 미만이면 경고한다.
이 함정은 실제로 발생했다 — 프로토타입에서 크레인 가중치를 올리기 전까지 최적해가
크레인 베이를 **1.9 m** 벗어나 있었고, 다른 해에서는 출입통제 구역이 외벽에서 **0.10 m**
떠 있었다. **둘 다 도면상 정상으로 보인다.**

## 6. 알고리즘

- **표현**: 층별 Sequence-Pair (Murata et al., IEEE TCAD 1996).
  겹치는 배치를 **생성할 수 없으므로** 중첩 페널티가 필요 없고 탐색공간 전체가 실현가능하다.
  유지보수 이격은 블록 치수를 `clearance` 만큼 팽창시켜 흡수한다.
- **탐색**: SA + 다중 재시작 (`--mode sa`) 또는 **NSGA-II 3목적** (`--mode nsga`).
- **계층분해** (`--mode hierarchical`): ① 구역 배정 → ② 층·표고 배정 → ③ 층내 상세배치.
  정확해 MILP 는 25기기에서 이미 무너진다(갭 11.8%). 실제 건물은 수백 개 규모다.
- **층수 민감도 스윕** (`--sweep-floors`): 층수-비용 트레이드오프 곡선.
  근거: Ejeh 2019 요소플랜트 1층 260,942 → 4층 117,431(−55.0%). **층수를 고정하면 이 개선 여지가 사라진다.**
- **현황에서 출발(warm start)**: 도면 경로에서는 현황 배치를 Sequence-Pair 로 변환해 초기해로 쓴다.
  Murata 조건 그대로 구성하므로 현황보다 커지지 않는다(테스트로 보장).

## 7. 재현성

```
동일 IR 해시 + 동일 seed  →  동일 결과 해시
```

`out/run_manifest.json` 에 `{ir_sha256, seed, engine_version, result_sha256}` 가 기록된다.
`tests/test_determinism.py` 가 이 성질을 강제한다.

## 8. 저장소 구조

```
engine/            결정론적 영역 — LLM 미개입 (Python 3.8+, 표준 라이브러리만)
  importers/         DXF · SVG · PDF · PNG · IFC · 표 파서
  takeoff.py         도면 → 현황 배치
  ga_core.py         Sequence-Pair 표현 + 목적함수 + SA
  nsga.py            NSGA-II 다목적
  constraints.py     제약 라이브러리 + 사용금지 수치 감시
  program.py         실 규모 계획 (근거 있는 실만 조정)
  validate_spec.py   Gate 1 검증기
  run.py             실행 오케스트레이터 + run_manifest.json
  bench_*.py         QAPLIB · Wrigley · Ejeh 벤치마크
server/            MCP 서버 (stdio + Streamable HTTP) + 브라우저 스튜디오
skills/ commands/  Claude Code 스킬 · 슬래시 커맨드 · 참조 문서
examples/          합성 도면 4종 · 기능 유지 요건 6종 · IR 예제 · 음성 대조군
tests/             패킹 · 제약 · 재현성 · 파서 · 벤치마크
tools/             예제·뷰어 데이터 생성 스크립트
docs/              GitHub Pages 3D 비교 페이지
```

Codex 등 다른 에이전트를 위한 공통 규약은 [`AGENTS.md`](../AGENTS.md) 에 있다.
