// bench-view.js — '벤치마크' 섹션: 정답이 알려진 문제로 탐색부를 검증한 결과.
// 데이터는 docs/bench.js (python3 tools/make_bench_data.py) 에서만 읽는다 — 숫자를 손으로 넣지 않는다.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { buildModel } from "./models.js";

const B = window.GA_BENCH;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
const fmt = (n, d = 0) => Number(n).toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d });
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

const PLANT = {
  urea: ["요소 비료 플랜트", "Urea"], cdu: ["원유 증류 플랜트", "CDU"],
  lng: ["액화천연가스 플랜트", "LNG"], cogp: ["원유·가스 처리 플랜트", "COGP"],
};
// 공정 기기 이름 → 모형 종류 (논문 영문명)
function typeOf(name) {
  const n = name || "";
  if (/crane/i.test(n)) return "crane_frame";
  if (/fired heater/i.test(n)) return "heater";
  if (/column|tower|debutan|contactor|MCHE/i.test(n)) return "column";
  if (/reactor/i.test(n)) return "column";
  if (/compressor(?! (cooler|suction))/i.test(n)) return "compressor";
  if (/drum|separator|tank|receiver|desalter|stabil|SS$/i.test(n)) return "tank";
  if (/exchanger|cooler|heater|condenser|reboiler|preheat|precool/i.test(n)) return "hx";
  if (/pump/i.test(n)) return "pump";
  return "generic";
}
const TYPE_COLOR = { column: "#5b7ea8", tank: "#6f9c7c", hx: "#c48a52", compressor: "#9a7cb3",
                     heater: "#a8665a", pump: "#63a0a6", crane_frame: "#c7b05a", generic: "#8a8d94" };

let cur = 0, view = null;

function makeView(el) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  el.prepend(renderer.domElement);
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffffff, 0xb8b4aa, 1.0));
  const sun = new THREE.DirectionalLight(0xfff4e6, 1.25); sun.position.set(60, 120, 80); scene.add(sun);
  const fill = new THREE.DirectionalLight(0xdfe7ff, 0.35); fill.position.set(-80, 50, -60); scene.add(fill);
  const root = new THREE.Group(); scene.add(root);
  const camera = new THREE.PerspectiveCamera(38, 1, 0.3, 3000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = false;
  const v = { el, renderer, scene, root, camera, controls, tip: el.querySelector(".tip"), pick: [] };
  controls.addEventListener("change", () => render(v));
  new ResizeObserver(() => size(v)).observe(el);
  hover(v);
  return v;
}
function size(v) {
  const r = v.el.getBoundingClientRect();
  v.renderer.setSize(r.width, r.height, false);
  v.camera.aspect = r.width / Math.max(1, r.height);
  v.camera.updateProjectionMatrix();
  render(v);
}
const render = v => v.renderer.render(v.scene, v.camera);

function draw(v, lay) {
  v.root.clear(); v.pick = [];
  if (!lay) return;
  const gap = 1.5;                                   // 층을 조금 띄워 보이게
  const line = new THREE.LineBasicMaterial({ color: css("--mut2") || "#9a9992" });
  for (let f = 0; f < lay.NF; f++) {
    const y = f * (lay.FH + gap);
    const slab = new THREE.Mesh(new THREE.BoxGeometry(lay.X, 0.12, lay.Y),
      new THREE.MeshStandardMaterial({ color: f ? 0xffffff : 0xf3f0e8, transparent: true, opacity: f ? 0.18 : 0.9, depthWrite: !f }));
    slab.position.set(0, y - 0.06, 0); v.root.add(slab);
    const e = new THREE.LineSegments(new THREE.EdgesGeometry(slab.geometry), line);
    e.position.copy(slab.position); v.root.add(e);
  }
  for (const it of lay.items) {
    const t = typeOf(it.name);
    const col = TYPE_COLOR[t];
    let obj;
    if (t === "crane_frame") {
      obj = new THREE.Group();
      const m = new THREE.MeshStandardMaterial({ color: col });
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
        const p = new THREE.Mesh(new THREE.BoxGeometry(0.4, it.h, 0.4), m);
        p.position.set(sx * (it.w / 2 - 0.2), it.h / 2, sz * (it.d / 2 - 0.2)); obj.add(p);
      }
      for (const sz of [-1, 1]) { const g = new THREE.Mesh(new THREE.BoxGeometry(it.w, 0.6, 0.6), m); g.position.set(0, it.h - 0.3, sz * (it.d / 2 - 0.3)); obj.add(g); }
      const br = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.6, it.d), m); br.position.set(0, it.h - 0.3, 0); obj.add(br);
    } else {
      obj = buildModel(t, it.w, it.d, it.h, col);
    }
    // 여러 층을 관통하는 기기는 층 띄움만큼 늘려 그린다
    const spanFloors = Math.max(1, Math.ceil(it.h / lay.FH - 1e-6));
    obj.scale.y = (it.h + gap * (spanFloors - 1)) / it.h;
    obj.position.set(it.x + it.w / 2 - lay.X / 2, it.f * (lay.FH + gap), it.y + it.d / 2 - lay.Y / 2);
    obj.userData = { it, t };
    v.root.add(obj); v.pick.push(obj);
  }
  const H = lay.NF * (lay.FH + gap);
  const r = Math.hypot(lay.X, lay.Y, H) / 2;
  const fit = v.camera.aspect < 1.2 ? 1.2 / Math.max(v.camera.aspect, 0.3) : 1;
  const dist = r / Math.sin(THREE.MathUtils.degToRad(19)) * 0.85 * fit;
  v.camera.position.copy(new THREE.Vector3(0.8, 0.7, 1).normalize().multiplyScalar(dist)).add(new THREE.Vector3(0, H / 2.5, 0));
  v.controls.target.set(0, H / 2.5, 0); v.controls.update();
  render(v);
}

function hover(v) {
  const ray = new THREE.Raycaster(), p = new THREE.Vector2();
  v.el.addEventListener("pointermove", ev => {
    const r = v.el.getBoundingClientRect();
    p.x = ((ev.clientX - r.left) / r.width) * 2 - 1; p.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    ray.setFromCamera(p, v.camera);
    const hit = ray.intersectObjects(v.pick, true)[0];
    let o = hit && hit.object; while (o && !o.userData.it) o = o.parent;
    if (!o) { v.tip.style.display = "none"; return; }
    const it = o.userData.it;
    v.tip.innerHTML = `<b>${esc(it.no)}. ${esc(it.name)}</b><div class="mt">${it.f + 1}층부터 · ${it.w.toFixed(2)} × ${it.d.toFixed(2)} × 높이 ${it.h.toFixed(2)} m</div>`;
    v.tip.style.display = "block";
    v.tip.style.left = Math.min(ev.clientX - r.left + 14, r.width - 240) + "px";
    v.tip.style.top = Math.min(ev.clientY - r.top + 14, r.height - 70) + "px";
  });
  v.el.addEventListener("pointerleave", () => v.tip.style.display = "none");
}

function sweepChart(plant) {
  const rows = (B.sweep || {})[plant];
  if (!rows || !rows.length) return "";
  const W = 520, H = 220, pl = 64, pr = 16, pt = 14, pb = 34;
  const ys = rows.flatMap(r => [r.published, r.best]).filter(x => x != null);
  const y0 = Math.min(...ys) * 0.92, y1 = Math.max(...ys) * 1.04;
  const X = k => pl + (k - rows[0].K) / Math.max(1, rows[rows.length - 1].K - rows[0].K) * (W - pl - pr);
  const Y = v => pt + (1 - (v - y0) / (y1 - y0)) * (H - pt - pb);
  const path = key => rows.filter(r => r[key] != null).map((r, i) => `${i ? "L" : "M"}${X(r.K).toFixed(1)},${Y(r[key]).toFixed(1)}`).join("");
  const ticks = [y0, (y0 + y1) / 2, y1].map(v => `<line x1="${pl}" x2="${W - pr}" y1="${Y(v)}" y2="${Y(v)}" class="gl"/><text x="${pl - 8}" y="${Y(v) + 4}" text-anchor="end">${fmt(v / 1000)}k</text>`).join("");
  const dots = key => rows.filter(r => r[key] != null).map(r => `<circle cx="${X(r.K)}" cy="${Y(r[key])}" r="3.5" class="${key}"><title>${r.K}층 · ${fmt(r[key], 1)} rmu${key === "best" ? ` (+${r.best_gap_pct}%)` : ""}</title></circle>`).join("");
  const xl = rows.map(r => `<text x="${X(r.K)}" y="${H - 12}" text-anchor="middle">${r.K}</text>`).join("");
  return `<figure class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="가용 층 수에 따른 총비용">
      ${ticks}${xl}<text x="${(W + pl) / 2}" y="${H}" text-anchor="middle" class="ax">가용 층 수</text>
      <path d="${path("published")}" class="published"/><path d="${path("best")}" class="best"/>${dots("published")}${dots("best")}</svg>
    <figcaption><span class="k pub"></span>논문 (MILP 전역 최적) <span class="k ours"></span>이 엔진 (seed 3개 중 최선)</figcaption></figure>`;
}

function showPlant(i) {
  cur = i;
  const r = B.ejeh[i], info = r.published_info, lay = r.layout;
  document.querySelectorAll("#b-tabs button").forEach((b, k) => b.setAttribute("aria-selected", k === i));
  const best = Math.min(...r.runs.filter(x => x.feasible).map(x => x.total));
  $("b-fig").innerHTML = `
    <div class="bn"><span class="lbl">논문 ${info.proven ? "· 증명된 최적" : `· 정답과 ${info.gap_pct}% 차이 남음`}</span><b>${fmt(r.published, 1)}</b><small>rmu · ${info.NF ?? "?"}층 · ${info.X ?? "?"}×${info.Y ?? "?"} m</small></div>
    <div class="bn"><span class="lbl">이 엔진 · seed ${r.n}개 중 최선</span><b>${fmt(best, 1)}</b><small>rmu · ${lay ? `${lay.NF}층 · ${lay.X}×${lay.Y} m` : ""}</small></div>
    <div class="bn"><span class="lbl">차이 (최선 / 중앙값)</span><b class="${r.best_gap_pct < 5 ? "good" : "warn"}">+${r.best_gap_pct}%</b><small>중앙 +${r.median_gap_pct}% · 실현가능 ${r.feasible}/${r.n}</small></div>`;
  $("b-note").textContent = r.demin_note || "";
  draw(view, lay);
  $("b-chart").innerHTML = sweepChart(r.plant);
}

function tables() {
  const ej = B.ejeh.map(r => `<tr><td>${esc(PLANT[r.plant][0])}<small>${PLANT[r.plant][1]} · 기기 ${r.layout ? r.layout.items.length : ""}개</small></td>
     <td class="n">${fmt(r.published, 1)}${r.published_info.proven ? "" : "<small>논문도 미증명</small>"}</td>
     <td class="n">${r.feasible}/${r.n}</td><td class="n"><b>+${r.best_gap_pct}%</b></td><td class="n">+${r.median_gap_pct}%</td></tr>`).join("");
  $("b-ejeh").innerHTML = `<table class="bt"><thead><tr><th>플랜트</th><th>논문 (rmu)</th><th>실현가능</th><th>최선 차이</th><th>중앙 차이</th></tr></thead><tbody>${ej}</tbody></table>`;
  const q = (B.qaplib || []).slice().sort((a, b) => a.n - b.n || a.instance.localeCompare(b.instance));
  const mx = Math.max(1, ...q.map(r => r.gap_pct));
  $("b-qap").innerHTML = `<table class="bt"><thead><tr><th>문제</th><th>크기</th><th>공개 최적</th><th>이 엔진</th><th>차이</th></tr></thead><tbody>${q.map(r =>
    `<tr><td>${esc(r.instance)}</td><td class="n">${r.n}</td><td class="n">${fmt(r.known_optimum)}</td><td class="n">${fmt(r.found)}</td>
     <td class="n"><span class="bar"><i style="width:${(r.gap_pct / mx * 100).toFixed(1)}%"></i></span>${r.gap_pct.toFixed(2)}%</td></tr>`).join("")}</tbody></table>`;
  const w = B.wrigley;
  if (w) $("b-wr").innerHTML = `<table class="bt"><thead><tr><th>격자</th><th>자리</th><th>이 엔진</th><th>기준안 ${fmt(w.baseline)} 대비</th><th>논문</th></tr></thead><tbody>${w.rows.map(r =>
    `<tr><td>${r.grid === "one_side_4F" ? "한 면 · 4층" : "한 면 · 3층"}</td><td class="n">${r.slots}</td><td class="n">${fmt(r.objective)}</td>
     <td class="n">−${((w.baseline - r.objective) / w.baseline * 100).toFixed(1)}%</td>
     <td class="n">${r.paper_optimum ? fmt(r.paper_optimum) + " " : ""}−${r.paper_reduction_pct}%</td></tr>`).join("")}</tbody></table>`;
}

if (B && B.ejeh && B.ejeh.length) {
  const order = ["urea", "cdu", "lng", "cogp"];
  B.ejeh.sort((a, b) => order.indexOf(a.plant) - order.indexOf(b.plant));
  $("b-tabs").innerHTML = B.ejeh.map((r, i) => `<button class="btab" role="tab" data-i="${i}"><span class="no">${PLANT[r.plant][1]}</span>${esc(PLANT[r.plant][0])}</button>`).join("");
  document.querySelectorAll("#b-tabs button").forEach(b => b.onclick = () => showPlant(+b.dataset.i));
  view = makeView($("b-canvas"));
  size(view);
  showPlant(0);
  tables();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => showPlant(cur));
} else {
  const s = document.getElementById("bench"); if (s) s.hidden = true;
}
