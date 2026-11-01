// models.js — 블록을 '그게 무엇인지' 알아볼 수 있는 단순한 3D 모형으로 바꾼다.
// 모형은 반드시 블록의 실제 점유 범위(w × d × h) 안에 들어간다 — 위치·크기는 솔버 결과 그대로다.
// (크레인 붐·플레어처럼 원래 높이 솟는 것만 예외로 위로 조금 더 올린다.)
import * as THREE from "three";

// ---------------------------------------------------------------------------
// 종류 판별 — 이름/ID 키워드
// ---------------------------------------------------------------------------
const RULES = [
  [b => /^CORE-/.test(b.id), "core"],
  [b => /^PR-\d/.test(b.id) || b.circ === "piperack", "piperack"],
  [b => /^CRANE/.test(b.id) || b.circ === "crane", "crane"],
  [b => /^FLARE-/.test(b.id), "flare"],
  [b => /^TURRET/.test(b.id), "turret"],
  [b => /^stair|계단/i.test(b.name), "stair"],
  [b => /^ELEVATOR$|승강기/i.test(b.name), "elevator"],
  [b => b.kind === "opening" || /해치/.test(b.name), "hatch"],
  [b => b.kind === "void", "void"],
  [b => b.kind === "room" && /복도|CORR/.test(b.name), "corridor"],
  [b => /CORRIDOR|^VEST\b|^HALL/i.test(b.name), "corridor"],
  [b => /TOILET|^JAN\b|화장실/i.test(b.name), "toilet"],
  [b => /X-RAY|RADIOGRAPH|FUNDUS|DEVELOPING|FILM VIEW|MDIS|영상/i.test(b.name), "imaging"],
  [b => /DENT|DTR\b|DIPC|PROSTH|CERAMIC|치과/i.test(b.name), "dental"],
  [b => /WAIT|RECEPT|APPMTS|대기실|접수/i.test(b.name), "waiting"],
  [b => /LOUNGE|BREAK|KITCHEN/i.test(b.name), "lounge"],
  [b => /CONF\b|CONF\.|LIBRARY|CLASSROOM|GROUP|TEAM INTER|회의/i.test(b.name), "conference"],
  [b => /SOIL|TRASH|DECON|DIRTY|오염/i.test(b.name), "soil"],
  [b => /MECH\. YARD/i.test(b.name), "utility"],
  [b => /MECH|ELEV\. EQUIP/i.test(b.name), "ahu"],
  [b => /ELEC/i.test(b.name), "switchgear"],
  [b => /COMM\. ROOM|ADP|COMPUTER/i.test(b.name), "server"],
  [b => /GAS STOR/i.test(b.name), "tank"],
  [b => /LAB\b|LAB$|SPECIMEN|PHARM/i.test(b.name), "lab"],
  [b => /EXAM|TRMT|INTERACTION|BLOOD|IMMUNIZ|ECG|AUDIO|VISUAL|EYE|COUNSEL|CONSULT|ISOLATION|PSYCH|HIST|WTS|FITTING|진료/i.test(b.name), "exam"],
  [b => /STOR|STO\.|CLEAN|SUP\.|ISSUE|PARTS|ARCHIVE|LIN\.|CL\.|DRESS|BENCHSTOCK|RECEIVING|600mm/i.test(b.name), "shelves"],
  [b => /OFFICE|ADMIN|CMDR|SGT|MGR|DIR\b|DIR\.|ANALYST|SUPER|NCOIC|CREDENTIAL|RECORDS|COPY|CUBICLE|WORK|SEC\.|CHIEF|RMO|QA|HK|TECH|SQUAD|사무/i.test(b.name), "office"],
  [b => /수술실/.test(b.name), "or"],
  [b => /스크럽/.test(b.name), "scrub"],
  [b => /회복실|대기/.test(b.name), "beds"],
  [b => /휴게/.test(b.name), "lounge"],
  [b => /탈의/.test(b.name), "locker"],
  [b => /오염/.test(b.name), "soil"],
  [b => /마취/.test(b.name), "anes"],
  [b => /창고|멸균|중앙공급/.test(b.name), "shelves"],
  [b => /^M0\d/.test(b.id), "module"],
  [b => /펌프/.test(b.name), "pump"],
  [b => /공랭식/.test(b.name), "aircooler"],
  [b => /열교환기/.test(b.name), "hx"],
  [b => /증류탑|반응기/.test(b.name), "column"],
  [b => /사용후연료/.test(b.name), "pool"],
  [b => /탱크|드럼/.test(b.name), "tank"],
  [b => /디젤발전기|가스터빈/.test(b.name), "genset"],
  [b => /압축공기|유틸리티/.test(b.name), "utility"],
  [b => /압축기/.test(b.name), "compressor"],
  [b => /냉각탑/.test(b.name), "coolingtower"],
  [b => /가열로/.test(b.name), "heater"],
  [b => /전산/.test(b.name), "server"],
  [b => /제어실|정지반/.test(b.name), "control"],
  [b => /축전지/.test(b.name), "battery"],
  [b => /스위치기어|변전|전기실/.test(b.name), "switchgear"],
  [b => /공조/.test(b.name), "ahu"],
  [b => /분석실/.test(b.name), "lab"],
  [b => /제염/.test(b.name), "decon"],
  [b => /폐기물/.test(b.name), "waste"],
  [b => /출입통제/.test(b.name), "access"],
  [b => /적치장/.test(b.name), "laydown"],
  [b => /거주구역/.test(b.name), "quarters"],
  [b => /구명정/.test(b.name), "lifeboat"],
  [b => /방폭벽/.test(b.name), "blastwall"],
];
export function classify(b) {
  for (const [f, t] of RULES) if (f(b)) return t;
  return "generic";
}

// 일반인용 설명 — 이름과 한 줄 설명
export const TYPES = {
  pump:        ["펌프", "물·냉각수·약품을 관으로 밀어 보내는 기계. 모터가 회전날개를 돌린다."],
  hx:          ["열교환기", "뜨거운 물과 차가운 물을 섞지 않고 열만 옮기는 긴 원통."],
  aircooler:   ["공랭식 냉각기", "큰 선풍기로 바람을 불어 관 속 유체를 식히는 장치."],
  tank:        ["탱크·드럼", "물·연료·약품을 담아 두는 통."],
  column:      ["증류탑·반응기", "높이 솟은 원통. 안에서 물질을 분리하거나 반응시킨다."],
  pool:        ["사용후연료 저장조", "쓰고 난 핵연료를 물속에 담가 식히고 보관하는 깊은 수조."],
  genset:      ["발전기", "엔진(또는 터빈)으로 전기를 만든다. 정전 때 안전설비에 전기를 준다."],
  compressor:  ["압축기", "기체를 눌러 압력을 높이는 큰 기계."],
  utility:     ["유틸리티 설비", "압축공기·질소처럼 다른 설비가 쓰는 공용 기체를 만든다."],
  coolingtower:["냉각탑", "물을 떨어뜨리며 바람으로 식혀 다시 쓰게 하는 탑."],
  heater:      ["가열로", "불꽃으로 원료를 데우는 화로와 굴뚝. 불이 있어 멀리 떨어져야 한다."],
  control:     ["제어실", "운전원이 화면을 보며 설비 전체를 조작하는 방."],
  server:      ["전산실", "제어용 컴퓨터 서버 랙이 줄지어 있는 방."],
  battery:     ["축전지실", "정전 때 쓸 배터리를 선반에 줄지어 둔 방."],
  switchgear:  ["전기실·스위치기어", "전기를 나누고 끊는 큰 전기 캐비닛이 늘어선 방."],
  ahu:         ["공조 설비", "건물에 공기를 걸러 보내는 대형 송풍기와 덕트."],
  lab:         ["분석실", "시료를 분석하는 실험대와 후드가 있는 방."],
  decon:       ["제염실", "작업자·공구에 묻은 방사성 오염을 씻어내는 방."],
  waste:       ["폐기물 처리·저장", "폐기물을 처리하거나 드럼에 담아 보관하는 곳."],
  access:      ["출입 통제", "관리구역에 드나드는 사람을 확인하는 게이트."],
  hatch:       ["장비 반출입 해치", "층을 관통해 큰 장비를 위아래로 옮기는 구멍."],
  core:        ["계단·승강기 코어", "층을 관통하는 계단실. 옮길 수 있지만 모든 층에서 같은 자리여야 하고 복도에 이어져야 한다."],
  piperack:    ["배관 받침대", "여러 배관을 공중에 받쳐 주는 철골 구조. 공정 설비가 옆에 붙어 있어야 하고 끊기면 안 된다."],
  crane:       ["크레인", "갑판에서 짐을 들어 올리는 크레인. 적치장·구명정이 작업반경 안에 있어야 한다."],
  flare:       ["플레어", "남는 가스를 안전하게 태우는 탑. 갑판 가장자리에, 거주구역에서 멀리."],
  turret:      ["터렛", "배를 해저에 묶어 두는 회전 장치. 선체의 일부라 상부 배치로는 옮길 수 없다."],
  laydown:     ["적치장", "정비 때 장비·자재를 내려놓는 빈 공간."],
  quarters:    ["거주구역", "작업자가 먹고 자는 숙소 건물. 위험구역에서 멀어야 한다."],
  lifeboat:    ["구명정", "비상시 탈출용 구명정과 내리는 장치."],
  blastwall:   ["방폭벽", "폭발 압력을 막아 주는 두꺼운 벽."],
  module:      ["공정 모듈", "배관·용기·펌프를 철골 틀에 묶어 통째로 옮겨 설치하는 단위."],
  or:          ["수술실", "수술대와 무영등이 있는 가장 깨끗해야 하는 방."],
  scrub:       ["스크럽실", "수술 전에 손을 씻는 세면대가 있는 공간."],
  beds:        ["회복실·대기실", "수술 전후 환자가 침대에 누워 있는 방."],
  lounge:      ["직원 휴게실", "의료진이 쉬는 방."],
  locker:      ["탈의실", "옷을 갈아입는 사물함이 있는 방."],
  shelves:     ["창고·멸균물품", "멸균된 기구와 물품을 선반에 보관하는 방."],
  soil:        ["오염 처리실", "쓰고 난 기구·폐기물을 모으는 방. 청결 구역과 떨어져야 한다."],
  anes:        ["마취 준비실", "마취 약품과 장비를 준비하는 방."],
  corridor:    ["복도", "사람과 장비가 지나다니는 길."],
  stair:       ["계단", "층을 오르내리는 계단."],
  elevator:    ["엘리베이터", "환자·장비를 층간으로 옮기는 승강기."],
  void:        ["뚫린 공간", "아래층이 내려다보이는 빈 공간. 바닥이 없어 배치하지 않는다."],
  toilet:      ["화장실", "변기와 세면대가 있는 공간."],
  imaging:     ["영상 촬영실", "X선 촬영 장비가 있는 방. 방사선 차폐가 필요하다."],
  dental:      ["치과 진료실", "치과 의자와 진료 장비가 있는 방."],
  waiting:     ["대기실·접수", "환자가 기다리는 의자 줄과 접수대."],
  conference:  ["회의실", "큰 테이블과 의자가 있는 방."],
  exam:        ["진료실·검사실", "진료 침대와 책상이 있는 방."],
  office:      ["사무실", "책상과 의자가 있는 업무 공간."],
  generic:     ["기타 설비", "기타 설비."],
};

// ---------------------------------------------------------------------------
// 재질 · 기본 도형
// ---------------------------------------------------------------------------
const C = {
  steel: 0x9aa3ad, dark: 0x3b4048, concrete: 0xb9b6ad, white: 0xf2f2ef, floor: 0xe6e3dc,
  water: 0x3d8fd6, screen: 0x1d2a44, glow: 0x6fd3ff, yellow: 0xf2c230, orange: 0xf08a24,
  pipe: 0xc98b3a, green: 0x5aa469, flame: 0xff7a1a,
};
function mat(color, o = {}) {
  return new THREE.MeshStandardMaterial({
    color, roughness: o.r ?? 0.7, metalness: o.m ?? 0.1,
    transparent: o.t !== undefined, opacity: o.t ?? 1,
    emissive: o.e ?? 0x000000, emissiveIntensity: o.ei ?? 1,
  });
}
function box(g, m, w, h, d, x = 0, y = 0, z = 0) {
  const o = new THREE.Mesh(new THREE.BoxGeometry(Math.max(w, .02), Math.max(h, .02), Math.max(d, .02)), m);
  o.position.set(x, y + h / 2, z); g.add(o); return o;
}
// axis: "y" 세움, "x" 길이방향으로 눕힘, "z" 폭방향으로 눕힘. y 는 바닥(세움) 또는 중심(눕힘).
function cyl(g, m, r, len, x = 0, y = 0, z = 0, axis = "y", seg = 22, r2) {
  const o = new THREE.Mesh(new THREE.CylinderGeometry(r2 ?? r, r, Math.max(len, .02), seg), m);
  if (axis === "x") o.rotation.z = Math.PI / 2;
  if (axis === "z") o.rotation.x = Math.PI / 2;
  o.position.set(x, axis === "y" ? y + len / 2 : y, z); g.add(o); return o;
}
function dome(g, m, r, x, y, z) {
  const o = new THREE.Mesh(new THREE.SphereGeometry(r, 22, 10, 0, Math.PI * 2, 0, Math.PI / 2), m);
  o.position.set(x, y, z); o.scale.y = 0.45; g.add(o); return o;
}
const fill = (n, f) => Array.from({ length: Math.max(0, n) }, (_, i) => f(i));
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

// 벽이 낮은 방 (안이 들여다보이게 자른 모형)
function room(g, L, S, H, accent, wallH) {
  const wh = Math.min(H, wallH ?? 1.4), t = Math.min(0.25, S * 0.05);
  const wm = mat(accent, { r: 0.9 });
  box(g, mat(C.floor, { r: 1 }), L, 0.08, S);
  box(g, wm, L, wh, t, 0, 0, -S / 2 + t / 2);
  box(g, wm, L, wh, t, 0, 0, S / 2 - t / 2);
  box(g, wm, t, wh, S, -L / 2 + t / 2, 0, 0);
  box(g, wm, t, wh, S * 0.55, L / 2 - t / 2, 0, -S * 0.225);   // 문 자리
}
// 줄지어 놓기: 방 안에 (n행 × m열) 가구
function rows(L, S, itemL, itemS, gapL, gapS) {
  const nL = Math.max(1, Math.floor((L - 1) / (itemL + gapL)));
  const nS = Math.max(1, Math.floor((S - 1) / (itemS + gapS)));
  const out = [];
  for (let i = 0; i < nL; i++) for (let j = 0; j < nS; j++)
    out.push([(i - (nL - 1) / 2) * (itemL + gapL), (j - (nS - 1) / 2) * (itemS + gapS)]);
  return out;
}

// ---------------------------------------------------------------------------
// 종류별 모형 — 길이방향(L)을 x 로 두고 만든 뒤, 필요하면 90° 돌린다.
// ---------------------------------------------------------------------------
const B = {
  pump(g, L, S, H, a) {
    box(g, mat(C.dark), L * .92, H * .08, S * .7);
    const r = clamp(Math.min(S, H) * .26, .3, 1.2);
    cyl(g, mat(a), r, L * .42, -L * .2, H * .08 + r, 0, "x");               // 모터
    for (let k = -2; k <= 2; k++) box(g, mat(a), .04, r * 2.15, r * 2.15, -L * .2 + k * L * .07, H * .08, 0); // 냉각핀
    cyl(g, mat(C.steel, { m: .5 }), r * 1.25, r * 1.1, L * .2, H * .08 + r * 1.25, 0, "z");  // 볼류트
    cyl(g, mat(C.pipe, { m: .4 }), r * .35, H * .9 - (H * .08 + r * 2.4), L * .2, H * .08 + r * 2.4, 0);
    cyl(g, mat(C.pipe, { m: .4 }), r * .35, L * .25, L * .36, H * .08 + r * 1.25, 0, "x");
  },
  hx(g, L, S, H, a) {
    const r = clamp(Math.min(S, H) * .38, .3, 2);
    for (const x of [-L * .3, L * .3]) box(g, mat(C.dark), .5, H * .25, S * .6, x, 0, 0);
    cyl(g, mat(a, { m: .3 }), r, L * .84, 0, H * .25 + r * .8, 0, "x");
    for (const s of [-1, 1]) { const o = new THREE.Mesh(new THREE.SphereGeometry(r, 18, 12), mat(a, { m: .3 }));
      o.scale.x = .35; o.position.set(s * L * .42, H * .25 + r * .8, 0); g.add(o); }
    for (const x of [-L * .25, L * .25]) cyl(g, mat(C.pipe, { m: .4 }), r * .22, H - (H * .25 + r * 1.7), x, H * .25 + r * 1.7, 0);
  },
  aircooler(g, L, S, H, a) {
    const top = H * .7;
    fill(4, i => box(g, mat(C.steel), .4, top, .4, (i % 2 ? 1 : -1) * L * .45, 0, (i < 2 ? 1 : -1) * S * .42));
    box(g, mat(a), L * .95, H * .12, S * .9, 0, top, 0);
    const n = Math.max(2, Math.round(L / S * 1.2));
    fill(n, i => { const x = (i - (n - 1) / 2) * L / n;
      cyl(g, mat(C.dark), Math.min(L / n, S) * .38, H * .1, x, top + H * .12, 0);
      box(g, mat(C.steel), Math.min(L / n, S) * .7, .05, .25, x, top + H * .22 + .02, 0); });
  },
  tank(g, L, S, H, a) {
    const r = Math.min(L, S) * .46;
    if (H > r * 2.2) {                                    // 세운 용기 (드럼·붕산탱크)
      fill(3, i => { const t = i * 2 * Math.PI / 3; box(g, mat(C.dark), .3, H * .12, .3, Math.cos(t) * r * .7, 0, Math.sin(t) * r * .7); });
      cyl(g, mat(a, { m: .25 }), r, H * .78, 0, H * .12, 0);
      dome(g, mat(a, { m: .25 }), r, 0, H * .9, 0);
    } else {                                               // 넓적한 저장탱크
      cyl(g, mat(a, { m: .2 }), r, H * .82, 0, 0, 0, "y", 32);
      cyl(g, mat(C.steel, { m: .3 }), r * .15, H * .16, 0, H * .82, 0, "y", 32, r);  // 원뿔 지붕
      fill(Math.max(2, Math.round(H / 2.5)), i => {        // 둘레 보강 띠
        const o = new THREE.Mesh(new THREE.TorusGeometry(r * 1.005, .08, 6, 40), mat(C.steel));
        o.rotation.x = Math.PI / 2; o.position.y = (i + 1) * H * .82 / (Math.round(H / 2.5) + 1); g.add(o); });
      const st = mat(C.yellow);                            // 나선 계단 흉내
      fill(8, i => { const t = i * .32; box(g, st, .9, .1, .5, Math.cos(t) * (r + .35), H * .82 * i / 8, Math.sin(t) * (r + .35)); });
    }
  },
  column(g, L, S, H, a) {
    const r = Math.min(L, S) * .36;
    box(g, mat(C.concrete), r * 2.6, H * .04, r * 2.6);
    cyl(g, mat(a, { m: .3 }), r, H * .88, 0, H * .04, 0);
    dome(g, mat(a, { m: .3 }), r, 0, H * .92, 0);
    const n = Math.max(3, Math.round(H / 7));
    fill(n, i => { const o = new THREE.Mesh(new THREE.TorusGeometry(r * 1.25, .12, 6, 30), mat(C.yellow));
      o.rotation.x = Math.PI / 2; o.position.y = H * .04 + (i + 1) * H * .86 / (n + 1); g.add(o); });
    cyl(g, mat(C.pipe, { m: .4 }), r * .18, H * .9, r * 1.5, 0, 0);
  },
  pool(g, L, S, H, a) {
    const t = Math.min(1.2, S * .1), c = mat(C.concrete, { r: .95 });
    box(g, c, L, H * .97, t, 0, 0, -S / 2 + t / 2); box(g, c, L, H * .97, t, 0, 0, S / 2 - t / 2);
    box(g, c, t, H * .97, S, -L / 2 + t / 2, 0, 0); box(g, c, t, H * .97, S, L / 2 - t / 2, 0, 0);
    box(g, c, L, .3, S);
    for (const [x, z] of rows(L - 2 * t, S - 2 * t, 1.3, 1.3, .25, .25)) box(g, mat(C.steel, { m: .6 }), 1.3, H * .32, 1.3, x, .3, z);
    box(g, mat(C.water, { t: .55, r: .1, m: .1 }), L - 2 * t, .06, S - 2 * t, 0, H * .85, 0);
    box(g, mat(C.yellow), L * .9, .25, .8, 0, H * .97, -S / 2 + t + .5);    // 연료 이송 브리지
  },
  genset(g, L, S, H, a) {
    box(g, mat(C.dark), L * .96, H * .06, S * .8);
    box(g, mat(a), L * .48, H * .5, S * .62, -L * .2, H * .06, 0);              // 엔진
    fill(6, i => box(g, mat(C.dark), .12, H * .08, S * .64, -L * .4 + i * L * .08, H * .56, 0));
    cyl(g, mat(C.steel, { m: .4 }), Math.min(S, H) * .27, L * .3, L * .2, H * .06 + Math.min(S, H) * .27, 0, "x");  // 발전기
    box(g, mat(C.steel), L * .1, H * .55, S * .7, L * .42, H * .06, 0);         // 방열기
    cyl(g, mat(C.steel, { m: .4 }), Math.min(S, L) * .07, H * .95 - H * .56, -L * .38, H * .56, -S * .2);  // 배기관
  },
  compressor(g, L, S, H, a) {
    box(g, mat(C.dark), L * .95, H * .08, S * .8);
    const r = Math.min(S, H) * .25;
    cyl(g, mat(a, { m: .3 }), r, L * .45, -L * .15, H * .08 + r, 0, "x");
    cyl(g, mat(C.steel), r * .8, L * .3, L * .27, H * .08 + r, 0, "x");
    for (const z of [-S * .25, S * .25]) cyl(g, mat(a, { m: .3 }), r * .5, H * .75, -L * .15, H * .08, z);
  },
  utility(g, L, S, H, a) {
    box(g, mat(C.dark), L * .95, H * .06, S * .85);
    box(g, mat(a), L * .4, H * .5, S * .6, -L * .22, H * .06, 0);
    fill(3, i => cyl(g, mat(C.steel, { m: .4 }), Math.min(S, L) * .1, H * .82, L * (.08 + i * .14), H * .06, -S * .15));
    cyl(g, mat(C.pipe, { m: .4 }), .12, L * .7, 0, H * .7, S * .25, "x");
  },
  coolingtower(g, L, S, H, a) {
    box(g, mat(a, { r: .9 }), L, H * .8, S);
    fill(6, i => box(g, mat(C.dark, { t: .6 }), L * 1.002, H * .03, S * 1.002, 0, H * (.12 + i * .1), 0));
    const n = Math.max(2, Math.round(L / S * 2));
    fill(n, i => cyl(g, mat(C.steel, { m: .3 }), Math.min(L / n, S) * .38, H * .2, (i - (n - 1) / 2) * L / n, H * .8, 0, "y", 24, Math.min(L / n, S) * .3));
  },
  heater(g, L, S, H, a) {
    box(g, mat(a), L, H * .42, S);
    fill(4, i => box(g, mat(C.flame, { e: 0x7a2a00 }), .5, .5, .1, -L * .3 + i * L * .2, H * .12, S / 2 + .01));
    box(g, mat(C.steel), L * .55, H * .2, S * .6, 0, H * .42, 0);
    cyl(g, mat(C.dark, { m: .3 }), Math.min(L, S) * .12, H * .38, 0, H * .62, 0);
  },
  control(g, L, S, H, a) {
    room(g, L, S, H, a);
    const scr = mat(C.screen, { e: C.glow, ei: .35 });
    box(g, mat(C.dark), L * .7, 2.2, .3, 0, 0, -S / 2 + .5);                          // 대형 상황판
    box(g, scr, L * .66, 1.8, .05, 0, .3, -S / 2 + .68);
    const n = Math.max(2, Math.floor(L / 3.2));
    fill(n, i => { const x = (i - (n - 1) / 2) * 3.0, z = -S * .05 + Math.abs(i - (n - 1) / 2) * .5;
      box(g, mat(C.white), 2.4, .75, 1.1, x, 0, z);                                   // 콘솔
      for (const dx of [-.6, .6]) box(g, scr, .9, .6, .05, x + dx, .75, z - .35); });
    box(g, mat(C.white), 3.2, .75, 1.4, 0, 0, S * .32);                               // 감독석
  },
  server(g, L, S, H, a) {
    room(g, L, S, H, a);
    for (const [x, z] of rows(L * .8, S * .7, 0.65, 1.1, .05, 1.4)) {
      box(g, mat(C.dark, { m: .3 }), .6, 2.1, 1.0, x, 0, z);
      box(g, mat(C.glow, { e: C.glow, ei: .8 }), .04, .04, .04, x, 1.8, z + .51);
    }
  },
  battery(g, L, S, H, a) {
    room(g, L, S, H, a);
    for (const [x, z] of rows(L * .8, S * .75, 2.4, .8, .3, 1.0)) {
      box(g, mat(C.steel), 2.4, .05, .8, x, .5, z); box(g, mat(C.steel), 2.4, .05, .8, x, 1.1, z);
      for (const y of [.55, 1.15]) fill(6, i => box(g, mat(a), .32, .38, .6, x - 1 + i * .4, y, z));
    }
  },
  switchgear(g, L, S, H, a) {
    room(g, L, S, H, a);
    for (const [x, z] of rows(L * .85, S * .7, L * .8, .9, 0, 1.6)) {
      const n = Math.floor(L * .8 / .9);
      fill(n, i => { box(g, mat(C.steel, { m: .3 }), .85, 2.2, .9, x - (n - 1) * .45 + i * .9, 0, z);
                     box(g, mat(a), .5, .25, .02, x - (n - 1) * .45 + i * .9, 1.6, z + .46); });
    }
  },
  ahu(g, L, S, H, a) {
    box(g, mat(a), L * .8, H * .5, S * .6, -L * .05, 0, 0);
    fill(3, i => box(g, mat(C.dark), .08, H * .5, S * .62, -L * .3 + i * L * .25, 0, 0));
    cyl(g, mat(C.dark), Math.min(S, H) * .2, .2, L * .36, H * .25, 0, "x");
    box(g, mat(C.steel, { m: .4 }), L * .25, H * .4, S * .3, L * .2, H * .5, 0);       // 덕트
  },
  lab(g, L, S, H, a) {
    room(g, L, S, H, a);
    for (const [x, z] of rows(L * .7, S * .6, L * .6, .9, 0, 1.8)) box(g, mat(C.white), L * .6, .9, .9, x, 0, z);
    box(g, mat(C.steel), 1.6, 2.3, .9, L * .38, 0, -S / 2 + .7);
  },
  decon(g, L, S, H, a) {
    room(g, L, S, H, a);
    fill(Math.max(2, Math.floor(L / 2.2)), i => box(g, mat(0xbfe3ff, { t: .55 }), 1.6, 2.2, 1.6, -L / 2 + 1.4 + i * 2.2, 0, -S * .2));
    box(g, mat(C.steel), L * .5, .9, .7, 0, 0, S * .3);
  },
  waste(g, L, S, H, a) {
    room(g, L, S, H, a);
    for (const [x, z] of rows(L * .55, S * .75, .6, .6, .15, .15)) cyl(g, mat(C.yellow, { m: .2 }), .3, .9, x - L * .18, 0, z);
    const r = Math.min(S * .3, H * .3);
    cyl(g, mat(a, { m: .3 }), r, H * .8, L * .3, 0, 0);
  },
  access(g, L, S, H, a) {
    room(g, L, S, H, a);
    fill(4, i => { box(g, mat(C.steel, { m: .5 }), .2, 1.0, 1.0, -1.5 + i * 1.0, 0, 0); });
    box(g, mat(C.white), 2.4, .9, .8, L * .25, 0, S * .25);
  },
  hatch(g, L, S, H, a) {
    const t = .4;
    fill(4, i => { const y = 0;
      const horiz = i < 2, s = i % 2 ? 1 : -1;
      box(g, mat(i % 2 ? C.yellow : C.dark), horiz ? L : t, .25, horiz ? t : S, horiz ? 0 : s * (L / 2 - t / 2), y, horiz ? s * (S / 2 - t / 2) : 0); });
    box(g, mat(C.yellow, { t: .12 }), L * .96, H, S * .96);
  },
  core(g, L, S, H, a) {
    box(g, mat(C.concrete, { r: .95 }), L, H, S);
    fill(6, i => box(g, mat(C.dark), L * .7 / 6, .08, S * .5, -L * .35 + (i + .5) * L * .7 / 6, H + i * .05, 0));
    box(g, mat(C.dark), 1.0, 2.1, .05, 0, 0, S / 2 + .01);
  },
  piperack(g, L, S, H, a) {
    const n = Math.max(2, Math.round(L / 8));
    fill(n + 1, i => { const x = -L / 2 + i * L / n;
      for (const z of [-S * .42, S * .42]) box(g, mat(C.steel, { m: .4 }), .35, H, .35, x, 0, z);
      box(g, mat(C.steel, { m: .4 }), .3, .3, S * .9, x, H * .55, 0); box(g, mat(C.steel, { m: .4 }), .3, .3, S * .9, x, H - .3, 0); });
    const cols = [C.pipe, 0x6d8fb3, C.green, 0xb35d5d];
    fill(4, k => cyl(g, mat(cols[k], { m: .3 }), .22, L, 0, H * .55 + .3 + .22, -S * .3 + k * S * .2, "x", 10));
    fill(3, k => cyl(g, mat(cols[(k + 1) % 4], { m: .3 }), .18, L, 0, H + .18, -S * .25 + k * S * .25, "x", 10));
  },
  crane(g, L, S, H, a) {
    const r = Math.min(L, S) * .3;
    cyl(g, mat(C.yellow), r, H * 1.6, 0, 0, 0);
    box(g, mat(C.yellow), r * 2.2, r * 1.6, r * 2.2, 0, H * 1.6, 0);
    const len = Math.max(L, S) * 3, boom = new THREE.Mesh(new THREE.BoxGeometry(len, .5, .5), mat(C.orange));
    boom.position.set(len * .35, H * 1.6 + r + len * .35, 0); boom.rotation.z = Math.PI / 4; g.add(boom);
  },
  flare(g, L, S, H, a) {
    const top = H * 4;
    fill(4, i => { const leg = new THREE.Mesh(new THREE.CylinderGeometry(.12, .2, top, 6), mat(C.steel, { m: .5 }));
      const sx = i % 2 ? 1 : -1, sz = i < 2 ? 1 : -1; leg.position.set(sx * L * .2, top / 2, sz * S * .2);
      leg.rotation.set(sz * .06, 0, -sx * .06); g.add(leg); });
    cyl(g, mat(C.dark), .4, 1.2, 0, top, 0);
    const fl = new THREE.Mesh(new THREE.ConeGeometry(.9, 3, 12), mat(C.flame, { e: C.flame, ei: .9 }));
    fl.position.set(0, top + 2.6, 0); g.add(fl);
  },
  turret(g, L, S, H, a) {
    const r = Math.min(L, S) * .45;
    cyl(g, mat(C.dark, { m: .4 }), r, H * .8, 0, 0, 0, "y", 32);
    cyl(g, mat(C.yellow), r * .8, H * .2, 0, H * .8, 0, "y", 32);
  },
  laydown(g, L, S, H, a) {
    box(g, mat(0xd9d4c4, { r: 1 }), L, .06, S);
    fill(4, i => box(g, mat(C.yellow), i < 2 ? L : .2, .07, i < 2 ? .2 : S, i < 2 ? 0 : (i % 2 ? 1 : -1) * (L / 2 - .1), 0, i < 2 ? (i % 2 ? 1 : -1) * (S / 2 - .1) : 0));
    const cr = [[-.25, -.2, 2.4], [.1, .15, 1.6], [.3, -.25, 2]];
    for (const [fx, fz, s] of cr) box(g, mat(0xa77b4f), s, s * .7, s, fx * L, .06, fz * S);
  },
  quarters(g, L, S, H, a) {
    box(g, mat(C.white), L, H * .88, S);
    const fl = Math.max(2, Math.round(H * .88 / 3.2));
    fill(fl, i => { const y = (i + .45) * H * .88 / fl;
      box(g, mat(C.screen, { e: C.glow, ei: .15 }), L * .9, .7, S + .02, 0, y, 0);
      box(g, mat(C.screen, { e: C.glow, ei: .15 }), L + .02, .7, S * .9, 0, y, 0); });
    cyl(g, mat(C.green), Math.min(L, S) * .45, .3, 0, H * .88, 0, "y", 32);           // 헬리데크
    box(g, mat(C.white), Math.min(L, S) * .3, .32, .4, 0, H * .88 + .01, 0);
  },
  lifeboat(g, L, S, H, a) {
    fill(2, i => { const x = (i ? 1 : -1) * L * .25;
      box(g, mat(C.steel), .3, H * .9, .3, x, 0, -S * .35);
      const boat = new THREE.Mesh(new THREE.CapsuleGeometry(Math.min(S, H) * .2, L * .3, 6, 14), mat(C.orange));
      boat.rotation.z = Math.PI / 2; boat.position.set(x, H * .5, 0); g.add(boat); });
  },
  blastwall(g, L, S, H, a) {
    box(g, mat(C.steel, { m: .5 }), L, H, S * .5);
    fill(Math.round(L / 1.5), i => box(g, mat(C.dark, { m: .5 }), .15, H, S * .8, -L / 2 + (i + .5) * 1.5, 0, 0));
  },
  module(g, L, S, H, a) {
    const st = mat(C.steel, { m: .5 });
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) box(g, st, .5, H, .5, sx * (L / 2 - .25), 0, sz * (S / 2 - .25));
    for (const y of [0, H * .5, H - .4]) { for (const sz of [-1, 1]) box(g, st, L, .4, .4, 0, y, sz * (S / 2 - .2));
      for (const sx of [-1, 1]) box(g, st, .4, .4, S, sx * (L / 2 - .2), y, 0); }
    box(g, mat(0x8d8f93, { t: .85 }), L * .98, .15, S * .98, 0, H * .5, 0);
    const r = Math.min(S, H * .5) * .28;
    cyl(g, mat(a, { m: .3 }), r, L * .6, -L * .05, r + .2, -S * .15, "x");
    cyl(g, mat(a, { m: .3 }), r * .8, L * .45, 0, H * .5 + r + .2, S * .15, "x");
    cyl(g, mat(a, { m: .3 }), r * .6, H * .45, L * .3, 0, S * .25);
    cyl(g, mat(C.pipe, { m: .4 }), .2, L * .9, 0, H * .5 - .4, S * .35, "x", 10);
  },
  or(g, L, S, H, a) {
    room(g, L, S, H, a);
    box(g, mat(C.steel, { m: .5 }), .5, .8, .5);
    box(g, mat(0x7fb6a8), 2.1, .12, .7, 0, .8, 0);                                    // 수술대
    box(g, mat(C.white), .1, H * .9 - 1.4, .1, -1.6, 0, -1.6);                          // 무영등 기둥
    cyl(g, mat(C.white, { e: 0xfff6c9, ei: .6 }), .55, .18, -.6, 2.2, -.6);              // 무영등
    box(g, mat(C.dark), .6, 1.4, .5, 1.8, 0, -1.4);
    box(g, mat(C.screen, { e: C.glow, ei: .4 }), .55, .4, .05, 1.8, 1.4, -1.15);
  },
  scrub(g, L, S, H, a) {
    room(g, L, S, H, a);
    fill(Math.max(2, Math.floor(L / 1.6)), i => box(g, mat(C.white), 1.1, .9, .6, -L / 2 + 1 + i * 1.6, 0, -S / 2 + .55));
  },
  beds(g, L, S, H, a) {
    room(g, L, S, H, a);
    for (const [x, z] of rows(L * .85, S * .8, 1.1, 2.2, 1.0, 1.4)) {
      box(g, mat(C.steel), 1.0, .55, 2.1, x, 0, z); box(g, mat(C.white), .95, .15, 2.0, x, .55, z);
      box(g, mat(0xcfe4f5), .7, .12, .4, x, .7, z - .75);
    }
  },
  lounge(g, L, S, H, a) {
    room(g, L, S, H, a);
    box(g, mat(0x7a8cb8), 2.6, .8, .9, 0, 0, -S * .25); box(g, mat(0xc9a77a), 1.4, .45, .8, 0, 0, S * .05);
    box(g, mat(C.white), 1.2, .75, 1.2, L * .28, 0, S * .25);
  },
  locker(g, L, S, H, a) {
    room(g, L, S, H, a);
    for (const z of [-S * .3, S * .3]) fill(Math.floor(L * .8 / .5), i => box(g, mat(0x8aa1b6, { m: .4 }), .45, 1.9, .5, -L * .4 + i * .5 + .25, 0, z));
  },
  shelves(g, L, S, H, a) {
    room(g, L, S, H, a);
    for (const [x, z] of rows(L * .85, S * .8, Math.min(3, L * .3), .6, .9, 1.4))
      for (const y of [0, .7, 1.4]) box(g, mat(C.steel, { m: .4 }), Math.min(3, L * .3), .06, .6, x, y + .3, z);
  },
  soil(g, L, S, H, a) {
    room(g, L, S, H, a);
    box(g, mat(C.steel, { m: .5 }), L * .5, .9, .7, 0, 0, -S / 2 + .6);
    fill(3, i => cyl(g, mat(0xd2484a), .3, .8, -L * .25 + i * .8, 0, S * .2));
  },
  anes(g, L, S, H, a) {
    room(g, L, S, H, a);
    fill(3, i => { box(g, mat(0x88a9c9), .6, 1.0, .5, -1.4 + i * 1.4, 0, -S * .2); });
    box(g, mat(C.white), 2, .9, .7, 0, 0, S * .25);
  },
  stair(g, L, S, H, a) {
    const n = Math.max(6, Math.round(L / .3)), tread = L / n, rise = Math.min(H, 4.5) / n;
    fill(n, i => box(g, mat(C.concrete, { r: .95 }), tread, rise * (i + 1), S * .9, -L / 2 + (i + .5) * tread, 0, 0));
  },
  elevator(g, L, S, H, a) {
    box(g, mat(C.steel, { m: .5 }), L, Math.min(H, 4), S);
    box(g, mat(C.dark), L * .5, 2.1, .05, 0, 0, S / 2 + .01);
    box(g, mat(C.glow, { e: C.glow, ei: .6 }), .15, .15, .03, L * .32, 1.2, S / 2 + .03);
  },
  void(g, L, S, H, a) {
    box(g, mat(0x9fb8d6, { t: .25 }), L, .05, S);
  },
  toilet(g, L, S, H, a) {
    room(g, L, S, H, a);
    const n = Math.max(1, Math.floor(L / 1.2));
    fill(n, i => { const x = -L / 2 + .6 + i * 1.2;
      box(g, mat(C.white), .45, .45, .65, x, 0, -S / 2 + .5); box(g, mat(C.white), .45, .5, .2, x, .45, -S / 2 + .25); });
    box(g, mat(C.white), Math.min(L * .6, 2.4), .85, .5, 0, 0, S / 2 - .4);
  },
  imaging(g, L, S, H, a) {
    room(g, L, S, H, a, 2.2);
    box(g, mat(C.white), 2.2, .75, .8);
    box(g, mat(C.steel, { m: .4 }), .25, 2.4, .25, -1.4, 0, -.9);
    box(g, mat(C.white), .9, .5, .6, -.6, 1.8, -.9);
    box(g, mat(C.yellow), .35, .35, .02, L / 2 - .3, 1.6, 0);          // 방사선 경고 표지
  },
  dental(g, L, S, H, a) {
    room(g, L, S, H, a);
    for (const [x, z] of rows(L * .85, S * .8, 2.4, 2.4, .6, .6)) {
      const ch = new THREE.Group();
      box(ch, mat(C.steel, { m: .5 }), .4, .5, .4);
      const seat = new THREE.Mesh(new THREE.BoxGeometry(1.8, .15, .6), mat(0x5aa7c9)); seat.position.set(0, .7, 0); seat.rotation.z = .25; ch.add(seat);
      box(ch, mat(C.white), .1, 1.6, .1, -.7, 0, .5); cyl(ch, mat(C.white, { e: 0xfff6c9, ei: .5 }), .2, .1, -.4, 1.6, .5);
      ch.position.set(x, 0, z); g.add(ch);
    }
  },
  waiting(g, L, S, H, a) {
    room(g, L, S, H, a);
    for (const [x, z] of rows(L * .8, S * .6, .55, .55, .05, 1.3)) {
      box(g, mat(0x6d8fb3), .5, .45, .5, x, 0, z); box(g, mat(0x6d8fb3), .5, .4, .08, x, .45, z - .21);
    }
    box(g, mat(C.white), Math.min(L * .4, 3), 1.05, .6, 0, 0, S / 2 - .5);
  },
  conference(g, L, S, H, a) {
    room(g, L, S, H, a);
    const tl = Math.max(1.6, L * .55), ts = Math.max(1, S * .35);
    box(g, mat(0xb08a5a), tl, .75, ts);
    const n = Math.max(2, Math.floor(tl / .8));
    fill(n, i => { const x = -tl / 2 + .4 + i * tl / n;
      for (const z of [-(ts / 2 + .4), ts / 2 + .4]) box(g, mat(C.dark), .45, .45, .45, x, 0, z); });
  },
  exam(g, L, S, H, a) {
    room(g, L, S, H, a);
    box(g, mat(C.steel), .7, .65, 1.9, -L * .2, 0, 0); box(g, mat(0x9ad0c2), .7, .1, 1.9, -L * .2, .65, 0);
    box(g, mat(C.white), 1.2, .75, .6, L * .25, 0, -S / 2 + .5);
    box(g, mat(C.dark), .45, .45, .45, L * .25, 0, -S / 2 + 1.2);
  },
  office(g, L, S, H, a) {
    room(g, L, S, H, a);
    for (const [x, z] of rows(L * .8, S * .7, 1.4, .7, 1.0, 1.2)) {
      box(g, mat(C.white), 1.4, .75, .7, x, 0, z);
      box(g, mat(C.screen, { e: C.glow, ei: .3 }), .55, .35, .04, x, .75, z - .2);
      box(g, mat(C.dark), .45, .45, .45, x, 0, z + .65);
    }
  },
  corridor(g, L, S, H, a) {
    box(g, mat(a, { t: .55 }), L, Math.min(H, .6), S);
  },
  generic(g, L, S, H, a) {
    box(g, mat(a), L, H, S);
  },
};

// 모형 만들기. 그룹 원점 = 블록 바닥 중심. 결과는 반드시 w × d 안.
export function buildModel(type, w, d, h, accent) {
  const g = new THREE.Group();
  const long = w >= d, L = long ? w : d, S = long ? d : w;
  const inner = new THREE.Group();
  (B[type] || B.generic)(inner, L, S, h, new THREE.Color(accent).getHex());
  if (!long) inner.rotation.y = Math.PI / 2;
  g.add(inner);
  return g;
}
