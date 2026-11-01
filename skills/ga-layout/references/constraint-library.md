<!-- 자동 생성 파일 — 손으로 고치지 말 것.
     engine/constraints.py 의 REGISTRY 를 고친 뒤 `python3 engine/gen_docs.py --write` -->

# 제약조건 라이브러리 (사전 검증)

LLM 은 이 목록에서 제약을 **선택하고 파라미터만 채운다.** 수식을 발명하지 않는다.
FlairGPT / LLM-FuncMapper 가 채택한 "사전 정의 비용함수 라이브러리에 매핑" 구조이며,
원자력 적용에서 가장 이식 가치가 큰 설계 결정이다.

- `*` 가 붙은 파라미터는 **필수**다. 값이 `null` 이면 Gate 1 에서 ERROR 로 막힌다.
- 기본값이 없는 파라미터는 "규제 원문 대조 없이 값을 넣지 말라"는 뜻이다.
  → [regulatory-numbers.md](regulatory-numbers.md) 의 사용금지 항목을 먼저 읽을 것.
- 위반량의 **단위가 섞여 있다** (m / m² / 건). 가중치를 같은 크기로 주면 안 된다.
  `validate_spec.py` 의 한계이득 점검이 단위별 하한을 알려준다.

IR 에는 이렇게 적는다.

```json
"constraints": [
  {"id": "FIRE-20FT",
   "params": {"groups": [["success_path:SP-A"], ["success_path:SP-B"]],
              "combustible_free": true,
              "detection_and_suppression": true}}
]
```

선택자(selector)는 다음을 쓴다.

| 형태 | 뜻 |
|---|---|
| `"SIP-1"` | 블록 id |
| `"SIP"` | `count` 로 전개된 인스턴스 전부 (SIP-1, SIP-2 …) |
| `"zone:R3"` | 방사선/계통 구역 |
| `"train:TrainA"` | 다중성 계열 |
| `"fire_zone:FZ-A"` | 화재구역 |
| `"structure:AUX"` | 내진 이격 단위(건물) |
| `"vital_area:VA-1"` | 보안 중요구역 |
| `"success_path:SP-A"` | App. R 고온정지 성공경로 계열 |

---


## 요약

| ID | 이름 | 유형 | 근거 | 파라미터 |
|---|---|---|---|---|
| `ADJACENT` | 인접 — 붙어 있어야 하는 실 / 붙으면 안 되는 실 | hard | 기능상 직접 이어져야 하는 실(수술실↔멸균 코어, 검체 화장실↔검사실, 엘리베이터↔복도)과 직접 이어지면 안 되는 실(오염실↔청결 구역). 규칙마다 근거를 why 에 적는다. | `rules`*, `touch_tol_m` |
| `CIRC-ACCESS` | 실 출입 — 모든 실은 복도에서 들어갈 수 있어야 한다 | hard | 실은 복도(또는 via_rooms 개 이하의 다른 실)를 거쳐 문으로 드나든다. 문 폭은 인용 값으로 넣는다 (예: ADA 2010 §404.2.3 문 순폭 32 in = 0.815 m, IBC 2021 §1010.1.1). | `door_m`*, `via_rooms`, `touch_tol_m`, `applies_to`, `circulation_types`, `exterior_access`, `direct`, `through_ok`, `corridor_for`, `no_through`, `no_entry_types`, `entry_ok` |
| `CIRC-CONNECT` | 동선 연결 — 층마다 복도·계단·엘리베이터가 하나로 이어져야 한다 | hard | 복도는 실과 계단을 잇는 하나의 망이어야 피난·이동이 된다. 최소 폭은 인용 값 (예: IBC 2021 Table 1020.3 복도 44 in = 1.118 m, ASR A1.8 표 2). | `min_width_m`*, `touch_tol_m`, `circulation_types`, `must_include` |
| `DEAD-END` | 막다른 복도 길이 | hard | IBC 2021 §1020.5 — 막다른 복도 20 ft(6.1 m), B·E·F·I-1·M·R-1·R-2·S·U 용도 스프링클러 시 50 ft(15.24 m). 복도 구간을 없애면 막다른 복도가 길어질 수 있다. | `max_m`*, `min_width_m`*, `touch_tol_m`, `exit_types` |
| `EGRESS` | 피난 — 계단까지 거리·계단 수·계단 간 이격 | hard | IBC 2021 §1017.2 출구까지 보행거리, §1006.3 층당 출구 수, §1007.1.1 출구 간 이격(스프링클러 시 대각선의 1/3); 독일 MBO §35 / ASR A2.3 (계단까지 35 m). 값은 관할·용도에 맞게 인용해 넣는다. | `max_travel_m`*, `exit_types`, `min_exits`, `exit_separation_frac`, `applies_to`, `exempt`, `ground_floor` |
| `ELEC-SEP` | 전기계통 물리적 분리 | hard | GDC 17 + RG 1.75 Rev.3. ★ 현행 RG 1.75 Rev.3 본문에는 수치 이격거리가 전혀 없다. IEEE Std 384-1992 채택 시 원문이 1981년판 대비 "특정 형상에 대해 이격거리 기준이 축소되었다"고 명시했다. | `groups`*, `min_horizontal_m`*, `citation`*, `barrier_pairs` |
| `FIRE-20FT` | 화재방호 계열 분리 (App. R III.G.2) | hard | 10 CFR 50 Appendix R III.G.2 — 고온정지 1계열 무손상: ①3시간 내화방벽 ②수평 20 ft(6.096 m) 초과 + 개재 가연물 0 + 감지·자동소화 ③1시간 방벽 + 감지·자동소화 중 하나. | `groups`*, `min_horizontal_m`, `gap_metric`, `combustible_free`*, `detection_and_suppression`*, `barrier_pairs` |
| `FIRE-HATCH` | ★ 해치·계단에 의한 화재구역 병합 | hard | RG 1.189 Rev.5 — 벽·바닥에 해치·계단 같은 대형 미방호 개구부가 있으면 양쪽을 하나의 화재구역으로 간주한다. 예외는 성공경로 간 누적 수평거리 6.1 m + 개재 가연물 0 + 양쪽 층 감지·소화를 모두 만족할 때뿐. | `openings`*, `separation_m`, `combustible_free`*, `both_levels_protected`*, `merge_tolerance_m`, `required_distinct`, `penalty_m_per_conflict` |
| `FREE-AREA` | 공지(free area) 제약 | hard | Ejeh 2019 LNG 플랜트 예제: 1층 면적의 50%를 작업공간, 최상층 60%를 비상공간으로 비워둔다. 원전의 레이다운 구역·비상대응 공간에 대응. 이 제약이 없으면 최적화기가 층을 가득 채운다. | `ground_floor_free_ratio`*, `top_floor_free_ratio`*, `include_clearance` |
| `HELB-DIST` | 고에너지배관파단 — 거리에 의한 분리 | hard | NUREG-0800 BTP 3-3 원문: "방호의 선호되는 방법은 플랜트 배치에 의한 분리와 격리에 기반한다" — 거리에 의한 분리가 1순위, 구획벽 2순위, 중복성 의존이 최후수단. 명문 하드 제약: 주증기·주급수 배관을 주제어실 주변에 배선하지 말 것. 제트 확산 반각 ≤ 10°. | `sources`*, `targets`*, `min_dist_m`*, `jet_half_angle_deg`, `gap_metric` |
| `LOAD-PATH` | 안전하중경로 (중량물 취급) | hard | NUREG-0612 §5.1.1 — 안전하중경로를 절차서와 기기배치도면에 명기하고, "단일 낙하가 안전정지에 필요한 계통의 중복 트레인을 동시에 무력화해서는 안 된다". SRP 9.1.5 심사 1항은 취급기기와 주요 형상의 설계 배치도를 명시적으로 요구한다. | `paths`*, `redundant_groups`*, `min_clearance_m` |
| `RACK-SERVE` | 배관대 기능 — 공정 설비가 배관대에 붙어 있고 배관대가 끊기지 않아야 한다 | hard | CCPS Guidelines for Siting and Layout of Facilities (2018): 공정 설비는 주 배관대 양옆에 배치한다. 배관대 구간은 없앨 수 있지만(optional), 남은 배관대는 이어져 있어야 하고 설비는 max_gap 안에 있어야 한다. | `served`*, `max_gap_m`*, `rack_type`, `touch_tol_m`, `connected` |
| `SEISMIC-GAP` | 구조물 간 내진 이격 (성능식) | hard | NUREG-0800 SRP 3.7.2 — 건물 간 이격은 고정 수치가 아니라 성능식이다. 구조물 전 높이에 대해 gap_ij ≥ δ_max,i + δ_max,j + 시공오차. ITAAC 에 as-built 대 as-designed gap 확인이 포함된다. | `structures`*, `construction_tolerance_m`* |
| `TALL-EQUIP` | 다층 관통 기기 | hard | 층고보다 높은 기기(재장전수탱크·사용후연료저장조·해치)는 연속된 층을 점유한다. 관통부는 전 층에서 같은 평면 좌표를 가져야 하며 상부 층의 다른 기기와 겹칠 수 없다. | `align_tolerance_m` |
| `TURBINE-25` | 터빈 미사일 금지 부채꼴 | hard | RG 1.115 — 저궤도 터빈 미사일은 터빈 휠 평면에서 ±25°로 벌어지는 부채꼴에 집중된다. 안전목표 P4 < 1e-7/년/호기. 부지 내 현재 및 장래의 모든 호기 strike zone 을 중첩해 검토해야 한다. | `turbine_block`*, `protected`*, `half_angle_deg`, `azimuth_deg`, `allowed_azimuths_deg`, `range_m`, `other_units` |
| `VITAL-AREA` | 중요구역(vital area) 집약 및 2중 방벽 | hard | 10 CFR 73.55(e)(9) — "중요기기는 vital area 안에만 위치해야 하며, 접근에 최소 2중의 물리적 방벽 통과를 요구해야 한다". (f) target set 분석이 VA 경계를 역으로 결정한다. | `vital_blocks`*, `max_areas`*, `barrier_standoff_m`, `penalty_m_per_extra_area` |

`*` 표시는 필수 파라미터 — 값이 null 이면 Gate 1 에서 ERROR.

---

## `ADJACENT` — 인접 — 붙어 있어야 하는 실 / 붙으면 안 되는 실

**유형** hard · **기본 가중치** 2000

**근거**

> 기능상 직접 이어져야 하는 실(수술실↔멸균 코어, 검체 화장실↔검사실, 엘리베이터↔복도)과 직접 이어지면 안 되는 실(오염실↔청결 구역). 규칙마다 근거를 why 에 적는다.

**수식**

```
mode=must: ∀ a: ∃ b 같은 층, 맞닿은 길이 ≥ min_touch ; mode=must_not: ∀ a,b: 맞닿은 길이 = 0
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `rules` | list | ★ | — | [{a: 실 정규식, b: 실 정규식, mode: must/must_not, min_touch_m, max_gap_m, why}] — max_gap_m 을 주면 맞닿음 대신 간극 ≤ max_gap 이면 된다. — 정규식은 이름+id 에 맞춘다. 'circ:corridor/lobby' 처럼 동선 종류로도 지정. |
| `touch_tol_m` | m |  | `0.35` | 벽 두께. |

---

## `CIRC-ACCESS` — 실 출입 — 모든 실은 복도에서 들어갈 수 있어야 한다

**유형** hard · **기본 가중치** 2000

**근거**

> 실은 복도(또는 via_rooms 개 이하의 다른 실)를 거쳐 문으로 드나든다. 문 폭은 인용 값으로 넣는다 (예: ADA 2010 §404.2.3 문 순폭 32 in = 0.815 m, IBC 2021 §1010.1.1).

**수식**

```
∀ 실 r: 동선 집합에서 '문 폭 이상 맞닿음' 간선으로 depth ≤ via_rooms+1 안에 도달
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `door_m` | m | ★ | — | 맞닿은 벽 길이 하한 = 문 순폭. 인용 필수. |
| `via_rooms` | count |  | `1` | 다른 실을 거쳐 들어가도 되는 수 (진료실 안 화장실처럼). 0 이면 모든 실이 복도에 직접 접해야 함. |
| `touch_tol_m` | m |  | `0.35` | 벽 두께 — 이 간극 이하면 맞닿은 것으로 본다. |
| `applies_to` | kinds |  | `['room']` | 출입을 확인할 블록 종류. |
| `circulation_types` | types |  | `['corridor', 'stair', 'elevator', 'lobby']` | 동선으로 보는 circulation 값. |
| `exterior_access` | regex |  | — | 바깥 문으로 드나드는 실 이름 (예: YARD/TRASH/RECEIV) — 층 외곽에 닿으면 출입 가능. |
| `direct` | regex |  | — | 복도에 '직접' 접해야 하는 실 이름 (예: 수술실 — 침대가 다른 실을 거치면 안 됨). |
| `through_ok` | regex |  | — | 다른 실이 '거쳐 지나가도' 되는 실 이름. 정하면 그 외의 실(멸균 코어 등)은 통로로 못 쓴다. |
| `corridor_for` | pairs |  | — | [[실 이름 정규식, 복도 이름 정규식], …] — 그 실은 그 복도로만 드나든다 (청결/오염 동선 분리). |
| `no_through` | regex |  | — | 다른 실이 '거쳐 지나가면 안 되는' 실 이름 (예: 화장실·창고·기계실·전기실 — IBC 2021 §1016.2). |
| `no_entry_types` | types |  | `[]` | 실 문을 낼 수 없는 동선 종류 (예: ['stair','elevator'] — 피난계단실 개구부 제한, IBC 2021 §1023.4). 동선 연결·피난에는 그대로 쓴다. |
| `entry_ok` | regex |  | — | no_entry_types 로도 문을 낼 수 있는 실 이름 (예: 평상시 재실하는 사무실). |

---

## `CIRC-CONNECT` — 동선 연결 — 층마다 복도·계단·엘리베이터가 하나로 이어져야 한다

**유형** hard · **기본 가중치** 2000

**근거**

> 복도는 실과 계단을 잇는 하나의 망이어야 피난·이동이 된다. 최소 폭은 인용 값 (예: IBC 2021 Table 1020.3 복도 44 in = 1.118 m, ASR A1.8 표 2).

**수식**

```
층마다 동선 블록 그래프(맞닿은 길이 ≥ min_width)가 연결요소 1개이고, must_include 종류를 포함
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `min_width_m` | m | ★ | — | 이어진 것으로 보는 맞닿은 길이 하한 = 복도 최소 폭. 인용 필수. |
| `touch_tol_m` | m |  | `0.35` | 벽 두께. |
| `circulation_types` | types |  | `['corridor', 'stair', 'elevator', 'lobby']` | 한 망으로 이어져야 하는 circulation 값. |
| `must_include` | types |  | `['stair']` | 층마다 주 동선에 포함돼야 하는 종류. |

---

## `DEAD-END` — 막다른 복도 길이

**유형** hard · **기본 가중치** 2000

**근거**

> IBC 2021 §1020.5 — 막다른 복도 20 ft(6.1 m), B·E·F·I-1·M·R-1·R-2·S·U 용도 스프링클러 시 50 ft(15.24 m). 복도 구간을 없애면 막다른 복도가 길어질 수 있다.

**수식**

```
한쪽 끝만 동선망에 이어진 복도 사슬의 길이(블록 긴 변의 합) ≤ max_m — 출구에 닿는 사슬은 제외
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `max_m` | m | ★ | — | 인용 필수. |
| `min_width_m` | m | ★ | — | 이어진 것으로 보는 맞닿은 길이 = 복도 최소 폭. |
| `touch_tol_m` | m |  | `0.35` | 벽 두께. |
| `exit_types` | types |  | `['stair']` | 닿으면 막다른 곳이 아닌 동선 종류. |

---

## `EGRESS` — 피난 — 계단까지 거리·계단 수·계단 간 이격

**유형** hard · **기본 가중치** 2000

**근거**

> IBC 2021 §1017.2 출구까지 보행거리, §1006.3 층당 출구 수, §1007.1.1 출구 간 이격(스프링클러 시 대각선의 1/3); 독일 MBO §35 / ASR A2.3 (계단까지 35 m). 값은 관할·용도에 맞게 인용해 넣는다.

**수식**

```
∀ 실: 직교거리(실 중심→가장 가까운 계단) ≤ max_travel ; 층당 계단 ≥ min_exits ; 최대 계단 간 거리 ≥ frac·대각선
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `max_travel_m` | m | ★ | — | 인용 필수. 직교거리는 실제 보행거리의 하한이므로 보수적이지 않다 — 여유를 둘 것. |
| `exit_types` | types |  | `['stair']` | 출구로 보는 circulation 값. |
| `min_exits` | count |  | `2` | 층당 출구(계단) 수. |
| `exit_separation_frac` | ratio |  | — | 계단 간 최소 거리 / 층 대각선 (IBC 1007.1.1: 1/3 스프링클러, 1/2 비스프링클러). |
| `applies_to` | kinds |  | `['room', 'equipment']` |  |
| `exempt` | regex |  | — | 상주 인원이 없는 실(옥탑 기계실 등) — 피난 거리·출구 수 검사에서 뺀다. |
| `ground_floor` | index |  | `0` | 피난층(0 부터). 위층·지하층 계단은 이 층까지 끊김 없이 이어져야 한다. |

---

## `ELEC-SEP` — 전기계통 물리적 분리

**유형** hard · **기본 가중치** 800

**근거**

> GDC 17 + RG 1.75 Rev.3. ★ 현행 RG 1.75 Rev.3 본문에는 수치 이격거리가 전혀 없다. IEEE Std 384-1992 채택 시 원문이 1981년판 대비 "특정 형상에 대해 이격거리 기준이 축소되었다"고 명시했다.

**수식**

```
Σ max(0, d_min − gap)  [d_min 은 IEEE 384 최신판 §5 원본 대조 후 입력]
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `groups` | list[list[selector]] | ★ | — | 분리 대상 계열 그룹. |
| `min_horizontal_m` | m | ★ | — | ★★ 기본값 없음. '수평 3 ft / 수직 5 ft'(0.914/1.524 m)는 IEEE 384-1981 관행값이므로 그대로 넣으면 안 된다. IEEE 384 최신판 §5 원본 대조 후 입력할 것. 잠정 대용: APR1400 실적 주변압기–UAT–SAT 15 m 또는 3시간 내화방벽. |
| `citation` | str | ★ | — | 위 수치의 출처. IEEE 384 판·절 번호 또는 실적 근거를 적어야 한다. |
| `barrier_pairs` | list[[id,id]] |  | `[]` | 내화방벽으로 면제되는 쌍. |

**비고** APR1400 실적 참고: 레이스웨이 표식 간격 ≤ 4.6 m, 4계열 색상구분, 중복 축전지는 별도 안전등급 구조물, 트레이 적층 상→하 13.8 kV → 4.16 kV → 480 V/DC → 제어 → 계장.


---

## `FIRE-20FT` — 화재방호 계열 분리 (App. R III.G.2)

**유형** hard · **기본 가중치** 800

**근거**

> 10 CFR 50 Appendix R III.G.2 — 고온정지 1계열 무손상: ①3시간 내화방벽 ②수평 20 ft(6.096 m) 초과 + 개재 가연물 0 + 감지·자동소화 ③1시간 방벽 + 감지·자동소화 중 하나.

**수식**

```
Σ_{(i,j)∈성공경로 계열쌍} max(0, d_min − gap_ij)  [i,j 동일 화재구역·동일 층]
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `groups` | list[list[selector]] | ★ | — | 성공경로 계열 그룹. 서로 다른 그룹 간에 분리를 요구한다. |
| `min_horizontal_m` | m |  | `6.096` | App. R 의 20 ft. ★ 이 값이 GA 의 실질 그리드 모듈이며 격자 해상도 기본값이다. |
| `gap_metric` | enum |  | `euclid` | euclid / chebyshev / manhattan |
| `combustible_free` | bool | ★ | — | 개재 가연물 0 이 확인되었는가. 선언하지 않으면 거리 예외 불성립. |
| `detection_and_suppression` | bool | ★ | — | 화재감지 + 자동소화 설치 여부. |
| `barrier_pairs` | list[[id,id]] |  | `[]` | 3시간 내화방벽으로 분리되어 거리 요건이 면제되는 쌍. |

**비고** RG 1.189 §6.1.9: 중복 펌프 트레인실 상호 최소 3시간 방벽 + 받침대·연석·바닥배수. EDG 일일탱크는 4,164 L 이하만 EDG실 내 허용.


---

## `FIRE-HATCH` — ★ 해치·계단에 의한 화재구역 병합

**유형** hard · **기본 가중치** 800

**근거**

> RG 1.189 Rev.5 — 벽·바닥에 해치·계단 같은 대형 미방호 개구부가 있으면 양쪽을 하나의 화재구역으로 간주한다. 예외는 성공경로 간 누적 수평거리 6.1 m + 개재 가연물 0 + 양쪽 층 감지·소화를 모두 만족할 때뿐.

**수식**

```
zones' = union-find(zones, 개구부 인접관계);  Σ_{(i,j)∈분리요구} penalty · 1[find(z_i)=find(z_j)]
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `openings` | list[selector] | ★ | — | 대형 미방호 개구부 블록(기기반출 해치·계단실 등). |
| `separation_m` | m |  | `6.096` | RG 1.189 예외의 누적 수평거리. |
| `combustible_free` | bool | ★ | — | 개구부 주변 개재 가연물 0 여부. |
| `both_levels_protected` | bool | ★ | — | 양쪽 층 감지·자동소화 설치 여부. |
| `merge_tolerance_m` | m |  | `0.0` | 개구부와 이 거리 이내면 접한 것으로 본다. |
| `required_distinct` | list[[selector,selector]] |  | `[]` | FIRE-20FT groups 외에 추가로 서로 다른 화재구역이어야 하는 쌍. |
| `penalty_m_per_conflict` | m/건 |  | `25.0` | 무효화된 분리 요구 1건당 등가 위반량. 물리량이 아니라 스칼라화 계수이므로 감사 시 명시할 것. |

**비고** SMR 모듈 반출로는 화재구역 설계와 '동시에' 풀어야 한다. 해치를 독립 블록으로 두고 나중에 배치하는 방식으로는 이 충돌이 잡히지 않는다.


---

## `FREE-AREA` — 공지(free area) 제약

**유형** hard · **기본 가중치** 20

**근거**

> Ejeh 2019 LNG 플랜트 예제: 1층 면적의 50%를 작업공간, 최상층 60%를 비상공간으로 비워둔다. 원전의 레이다운 구역·비상대응 공간에 대응. 이 제약이 없으면 최적화기가 층을 가득 채운다.

**수식**

```
occupied(f) ≤ (1 − ratio_f) · W · D   for f ∈ {1층, 최상층}
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `ground_floor_free_ratio` | ratio | ★ | — | ★ 문헌 예제값 0.50 은 참고용이다. 프로젝트 레이다운/작업공간 계획에서 값을 정할 것. |
| `top_floor_free_ratio` | ratio | ★ | — | ★ 문헌 예제값 0.60 은 참고용이다. |
| `include_clearance` | bool |  | `True` | 점유면적에 유지보수 이격을 포함할지. |

**비고** 단위가 m² 이므로 가중치를 m 단위 제약과 같은 크기로 주면 안 된다.


---

## `HELB-DIST` — 고에너지배관파단 — 거리에 의한 분리

**유형** hard · **기본 가중치** 800

**근거**

> NUREG-0800 BTP 3-3 원문: "방호의 선호되는 방법은 플랜트 배치에 의한 분리와 격리에 기반한다" — 거리에 의한 분리가 1순위, 구획벽 2순위, 중복성 의존이 최후수단. 명문 하드 제약: 주증기·주급수 배관을 주제어실 주변에 배선하지 말 것. 제트 확산 반각 ≤ 10°.

**수식**

```
Σ max(0, d_min − gap) + Σ jet_cone_intrusion(target, source, ±10°)
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `sources` | list[selector|{block,jet_azimuth_deg}] | ★ | — | 고에너지 배관/기기(주증기·주급수 등). |
| `targets` | list[selector] | ★ | — | 주제어실 등 보호 대상. |
| `min_dist_m` | m | ★ | — | ★ 규제 고정 수치가 아니다. 플랜트별 HELB 해석 결과에서 주입할 것. |
| `jet_half_angle_deg` | deg |  | `10.0` | BTP 3-3 제트 확산 반각 상한. |
| `gap_metric` | enum |  | `euclid` | euclid / chebyshev / manhattan |

**비고** 거리 기반 목적함수가 규제 논리와 정합한다는 근거가 여기 있다.


---

## `LOAD-PATH` — 안전하중경로 (중량물 취급)

**유형** hard · **기본 가중치** 20

**근거**

> NUREG-0612 §5.1.1 — 안전하중경로를 절차서와 기기배치도면에 명기하고, "단일 낙하가 안전정지에 필요한 계통의 중복 트레인을 동시에 무력화해서는 안 된다". SRP 9.1.5 심사 1항은 취급기기와 주요 형상의 설계 배치도를 명시적으로 요구한다.

**수식**

```
corridor(from→to, width) 와 교차하는 train 이 동일 중복군에서 2개 이상이면 2번째 이후 교차면적을 위반량으로 계상
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `paths` | list[{id,from,to,width_m,floor}] | ★ | — | 중량물 이동 경로. |
| `redundant_groups` | list[list[train]] | ★ | — | 동시 무력화가 금지되는 계열 그룹. 예: [["TrainA","TrainB"]] |
| `min_clearance_m` | m |  | — | 경로 양측 추가 이격. APR1400 실적은 특정 기기 4.5 m 이내 통과 금지였다 — 실적값이며 규제 수치가 아니다. |

**비고** 경로는 직교(bridge+trolley) 2구간 L자 두 가지 중 위반이 작은 쪽을 취한다.


---

## `RACK-SERVE` — 배관대 기능 — 공정 설비가 배관대에 붙어 있고 배관대가 끊기지 않아야 한다

**유형** hard · **기본 가중치** 2000

**근거**

> CCPS Guidelines for Siting and Layout of Facilities (2018): 공정 설비는 주 배관대 양옆에 배치한다. 배관대 구간은 없앨 수 있지만(optional), 남은 배관대는 이어져 있어야 하고 설비는 max_gap 안에 있어야 한다.

**수식**

```
∀ 설비 s ∈ served: gap(s, 배관대) ≤ max_gap ; 배관대 구간 그래프 연결
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `served` | selector | ★ | — | 배관대에서 배관을 받는 설비 선택자. |
| `max_gap_m` | m | ★ | — | 설비–배관대 최대 간극 (배관 지선 길이). 인용 또는 가정 명시. |
| `rack_type` | type |  | `piperack` | 공급 요소의 circulation 값 (piperack, crane …). |
| `touch_tol_m` | m |  | `0.5` |  |
| `connected` | bool |  | `True` | 공급 요소끼리 이어져 있어야 하는가 (배관대 true, 크레인 false). |

---

## `SEISMIC-GAP` — 구조물 간 내진 이격 (성능식)

**유형** hard · **기본 가중치** 800

**근거**

> NUREG-0800 SRP 3.7.2 — 건물 간 이격은 고정 수치가 아니라 성능식이다. 구조물 전 높이에 대해 gap_ij ≥ δ_max,i + δ_max,j + 시공오차. ITAAC 에 as-built 대 as-designed gap 확인이 포함된다.

**수식**

```
Σ_{(i,j)} max(0, (δ_i + δ_j + tol) − gap_ij)
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `structures` | list[{id,blocks,delta_max_m}] | ★ | — | 구조물 단위와 각 구조물의 최대 지진 변위 δ_max. δ 는 구조해석 결과에서 온다 — 기본값 없음. |
| `construction_tolerance_m` | m | ★ | — | 시공오차. 프로젝트 값. |

**비고** ★ '50 mm' 류의 고정 수치는 NRC 규제문서에 존재하지 않는다. 평면 bbox 간극으로 근사하며, 전 높이 검토는 구조해석에서 별도로 확인할 것.


---

## `TALL-EQUIP` — 다층 관통 기기

**유형** hard · **기본 가중치** 800

**근거**

> 층고보다 높은 기기(재장전수탱크·사용후연료저장조·해치)는 연속된 층을 점유한다. 관통부는 전 층에서 같은 평면 좌표를 가져야 하며 상부 층의 다른 기기와 겹칠 수 없다.

**수식**

```
span_i = ceil(h_i / 층고);  Σ_{f∈span} (|Δx| + |Δy|)  [그림자 정렬오차]
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `align_tolerance_m` | m |  | `0.0` | 관통부 정렬 허용오차. |

**비고** 상위 층 중첩은 표현 단계에서 배제된다 — 관통 기기를 상위 층 Sequence-Pair 에 '그림자'로 함께 넣기 때문이다. 남는 것은 정렬오차뿐이고 이 값이 0 이어야 실제로 실현 가능한 관통부다.


---

## `TURBINE-25` — 터빈 미사일 금지 부채꼴

**유형** hard · **기본 가중치** 800

**근거**

> RG 1.115 — 저궤도 터빈 미사일은 터빈 휠 평면에서 ±25°로 벌어지는 부채꼴에 집중된다. 안전목표 P4 < 1e-7/년/호기. 부지 내 현재 및 장래의 모든 호기 strike zone 을 중첩해 검토해야 한다.

**수식**

```
Σ_{j∈보호대상} Σ_{터빈} arc_deficit(j, origin, axis, ±25°)  [방위각은 이산 결정변수]
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `turbine_block` | selector | ★ | — | 터빈 블록. |
| `protected` | list[selector] | ★ | — | 부채꼴에서 배제해야 하는 안전 관련 블록/구역. |
| `half_angle_deg` | deg |  | `25.0` | RG 1.115 저궤도 미사일. |
| `azimuth_deg` | deg |  | — | 고정 방위각. null 이면 allowed_azimuths_deg 중에서 최적화한다. |
| `allowed_azimuths_deg` | list[deg] |  | — | 이산 결정변수의 후보값. null 이면 15° 간격 0~165°. |
| `range_m` | m |  | — | strike zone 유효 반경. null 이면 무제한. |
| `other_units` | list[{id,x,y,azimuth_deg}] |  | `[]` | 장래 호기 포함 부지 좌표계상의 다른 터빈. |

**비고** 터빈 방위각은 GA 최상위 이산 결정변수다. ga_core.Solution.turbine_azimuth 에 유전자로 들어가 있으며 SA/NSGA 의 'turbine_rotate' 이동으로 탐색된다.


---

## `VITAL-AREA` — 중요구역(vital area) 집약 및 2중 방벽

**유형** hard · **기본 가중치** 200

**근거**

> 10 CFR 73.55(e)(9) — "중요기기는 vital area 안에만 위치해야 하며, 접근에 최소 2중의 물리적 방벽 통과를 요구해야 한다". (f) target set 분석이 VA 경계를 역으로 결정한다.

**수식**

```
penalty · max(0, |areas| − max_areas) + Σ max(0, standoff − d(i, ∂Ω))
```

**파라미터**

| 이름 | 단위 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `vital_blocks` | list[selector] | ★ | — | 중요기기. |
| `max_areas` | count | ★ | — | 허용 중요구역 수 상한. |
| `barrier_standoff_m` | m |  | — | ★ 외벽으로부터의 최소 이격. 차량폭탄 stand-off distance 는 Safeguards Information 이므로 그 값을 여기에 넣지 말 것. 파라미터 슬롯만 제공한다. |
| `penalty_m_per_extra_area` | m/개 |  | `30.0` | 스칼라화 계수. |

---


<sub>engine 0.3.0 · engine/constraints.py 에서 자동 생성됨</sub>
