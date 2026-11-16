// O render: a cena (web/scene/) em three.js, com câmera ortográfica 2:1 de pixel art, luz em degraus e contorno.
// Corre no Chromium sem tela (pipeline/render.mjs chama window.renderTile) ou aberto num navegador para conferir.
//
// Eixos do three: X = leste, Y = cima, Z = sul (−norte). A cena vem em metros (x leste, y norte, z cima).
import * as THREE from "three";

const MPP = 0.5;          // metros por pixel do desenho: uma casa estreita da Ribeira tem uns 12 px
const TILE = 512;         // px por tile
const MARGIN = 4;         // px a mais em volta de cada tile, para o contorno não ter costura
const PITCH = 30;         // graus: a inclinação 2:1 da pixel art isométrica
const YAW = 225;          // de onde a câmera olha: sudoeste, para nordeste (a Ribeira de frente, do outro lado do rio)
const SUN = { az: 165, el: 48 };   // sol a sul-sudeste: as fachadas viradas ao rio iluminadas, as do poente meia-sombra

const W3 = (x, y, z) => new THREE.Vector3(x, z, -y);   // cena -> three
const dirENU = (azDeg, elDeg) => {
  const a = THREE.MathUtils.degToRad(azDeg), e = THREE.MathUtils.degToRad(elDeg);
  return W3(Math.sin(a) * Math.cos(e), Math.cos(a) * Math.cos(e), Math.sin(e)).normalize();
};
const col = hex => new THREE.Color(hex);

// ---- materiais: um shader de luz em degraus, com variantes por tipo ----------------------------------------
const shared = { uSun: { value: dirENU(SUN.az, SUN.el) }, uSunT: { value: dirENU(SUN.az + 40, 34) }, uMode: { value: 0 },
  uWater: { value: 0.6 } };
const KIND = { flat: 0, terrain: 1, wall: 2, roof: 3, water: 4, iron: 5, soil: 6, tree: 7 };

const vert = /* glsl */`
  attribute vec4 aInfo;            // por vértice: u ao longo da parede, v (altura), altura total da parede, janelas sim/não
  #ifdef USE_VCOLOR
  attribute vec3 color;
  #endif
  varying vec3 vN, vW, vC; varying vec4 vInfo; varying vec2 vUv;
  uniform vec3 uColor;
  void main() {
    mat4 m = modelMatrix;
    #ifdef USE_INSTANCING
    m = m * instanceMatrix;
    #endif
    vec4 w = m * vec4(position, 1.0);
    vW = w.xyz; vN = normalize(mat3(m) * normal); vUv = uv; vInfo = aInfo;
    vC = uColor;
    #ifdef USE_VCOLOR
    vC = color;
    #endif
    #ifdef USE_INSTANCING_COLOR
    vC = instanceColor;
    #endif
    gl_Position = projectionMatrix * viewMatrix * w;
  }`;

const frag = /* glsl */`
  uniform vec3 uSun, uSunT; uniform int uMode; uniform float uWater; uniform sampler2D uMap;
  varying vec3 vN, vW, vC; varying vec4 vInfo; varying vec2 vUv;
  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float steps(vec3 n) { float d = dot(normalize(n), uSun); return d > 0.62 ? 1.0 : d > 0.22 ? 0.84 : 0.66; }
  void main() {
    vec3 n = normalize(vN); vec3 c = vC; float lit = steps(n);
    #if KIND == 1
      vec4 t = texture2D(uMap, vUv);
      c = t.rgb;
      if (t.a < 0.75) {                       // chão comum: a inclinação decide (muros de granito, mato)
        if (n.y < 0.62) c = vec3(0.60, 0.58, 0.54);
        else if (n.y < 0.86) c = vec3(0.47, 0.57, 0.31);
      } else if (n.y < 0.5) c = vec3(0.60, 0.58, 0.54);
      if (vW.y < uWater) c = vec3(0.24, 0.38, 0.45);
      // o relevo: luz rasante em cinco degraus, para as encostas do Douro se lerem
      lit = 0.72 + 0.34 * floor(clamp(dot(n, uSunT), 0.0, 1.0) * 5.0) / 5.0;
    #elif KIND == 2
      float u = vInfo.x, v = vInfo.y, top = vInfo.z;
      if (vInfo.w > 0.5 && v > 3.4 && v < top - 0.9) {   // janelas: um andar a cada 3,2 m, um vão a cada 2,6 m
        float fu = mod(u, 2.6), fv = mod(v - 3.4, 3.2);
        if (fu > 0.8 && fu < 1.85 && fv > 0.7 && fv < 2.3) c = mix(vec3(0.20, 0.25, 0.32), vec3(0.42, 0.52, 0.62), step(0.8, lit));
      } else if (vInfo.w > 0.5 && v > 0.6 && v < 3.0) {    // rés-do-chão: portas e montras
        float fu = mod(u, 2.6);
        if (fu > 0.7 && fu < 1.9 && v < 2.6) c *= 0.55;
      }
      if (v > top - 0.45) c *= 1.12;   // a cornija, mais clara
    #elif KIND == 3
      if (mod(floor(vW.y * 2.0), 2.0) < 0.5) c *= 0.92;   // fiadas de telha
    #elif KIND == 4
      vec2 cell = floor(vW.xz / vec2(1.5, 0.75));
      float h = hash(cell);
      c = vec3(0.25, 0.50, 0.66);
      if (h > 0.994) c = vec3(0.80, 0.90, 0.95);
      else if (h > 0.972) c = vec3(0.31, 0.57, 0.72);
      lit = 1.0;
    #elif KIND == 5
      // treliça de ferro: banzos cheios, diagonais em N, o resto vazado
      float s = mod(vInfo.x, 5.0) / 5.0, v = vInfo.y;
      if (abs(n.y) < 0.5 && v > 0.16 && v < 0.84 && abs(s - v) > 0.11 && s > 0.08) discard;
    #elif KIND == 6
      if (mod(floor(vW.y * 0.5), 3.0) < 0.5) c *= 0.88;   // estratos
      if (vW.y < uWater && vInfo.w > 0.5) c = vec3(0.18, 0.33, 0.45);
    #endif
    if (uMode == 1) { gl_FragColor = vec4(n * 0.5 + 0.5, KIND == 1 || KIND == 4 || KIND == 6 ? 0.0 : 1.0); return; }
    gl_FragColor = vec4(c * lit, 1.0);
  }`;

function toon(kind, opts = {}) {
  const defines = { KIND: KIND[kind] };
  if (opts.vcolor) defines.USE_VCOLOR = "";
  return new THREE.ShaderMaterial({
    defines, vertexShader: vert, fragmentShader: frag, side: opts.side ?? THREE.FrontSide,
    uniforms: { ...shared, uColor: { value: col(opts.color ?? "#ffffff") }, uMap: { value: opts.map ?? null } },
  });
}

// ---- construção ---------------------------------------------------------------------------------------------
class Builder {   // junta triângulos com cor e aInfo num só BufferGeometry
  constructor() { this.p = []; this.n = []; this.c = []; this.i = []; }
  tri(a, b, c, color, ia = [0, 0, 0, 0], ib = ia, ic = ia) {
    const n = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(c, a)).normalize();
    for (const [v, info] of [[a, ia], [b, ib], [c, ic]]) {
      this.p.push(v.x, v.y, v.z); this.n.push(n.x, n.y, n.z); this.c.push(color.r, color.g, color.b); this.i.push(...info);
    }
  }
  quad(a, b, c, d, color, ia, ib, ic, id) { this.tri(a, b, c, color, ia, ib, ic); this.tri(a, c, d, color, ia, ic, id); }
  mesh(material) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(this.p, 3));
    g.setAttribute("normal", new THREE.Float32BufferAttribute(this.n, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(this.c, 3));
    g.setAttribute("aInfo", new THREE.Float32BufferAttribute(this.i, 4));
    return new THREE.Mesh(g, material);
  }
}

function cap(builder, ring, holes, z, color) {   // um polígono horizontal (laje, topo de telhado)
  const v2 = r => r.map(([x, y]) => new THREE.Vector2(x, y));
  const contour = v2(ring), hs = holes.map(v2);
  const all = [...contour, ...hs.flat()];
  for (const [a, b, c] of THREE.ShapeUtils.triangulateShape(contour, hs)) {
    const A = W3(all[a].x, all[a].y, z), B = W3(all[b].x, all[b].y, z), C = W3(all[c].x, all[c].y, z);
    const up = new THREE.Vector3().subVectors(B, A).cross(new THREE.Vector3().subVectors(C, A)).y > 0;
    up ? builder.tri(A, B, C, color) : builder.tri(A, C, B, color);
  }
}

function walls(builder, ring, z0, z1, color, win) {
  // anel no sentido anti-horário (visto de cima): a normal de cada parede aponta para fora
  let u = 0;
  for (let k = 0; k < ring.length; k++) {
    const [x0, y0] = ring[k], [x1, y1] = ring[(k + 1) % ring.length];
    const len = Math.hypot(x1 - x0, y1 - y0);
    if (len < 0.05) continue;
    const h = z1 - z0, w = win && len > 1.6 ? 1 : 0;
    builder.quad(W3(x0, y0, z0), W3(x1, y1, z0), W3(x1, y1, z1), W3(x0, y0, z1), color,
      [u, 0, h, w], [u + len, 0, h, w], [u + len, h, h, w], [u, h, h, w]);
    u += len;
  }
}

const area = r => r.reduce((s, [x0, y0], k) => { const [x1, y1] = r[(k + 1) % r.length]; return s + x0 * y1 - x1 * y0; }, 0) / 2;
const ccw = r => area(r) >= 0 ? r : [...r].reverse();
const cw = r => area(r) < 0 ? r : [...r].reverse();

function buildings(scene, list) {
  const wallB = new Builder(), roofB = new Builder(), flatB = new Builder();
  for (const b of list) {
    const ring = ccw(b.o), wall = col(b.w), roof = col(b.r);
    const win = !/^#d8d0bf|^#a59d8f/.test(b.w) && b.t - b.b > 4;
    const eave = b.rs === "hipped" ? b.t - b.rh : b.t;
    walls(wallB, ring, b.b, eave, wall, win);
    for (const hole of b.i) walls(wallB, cw(hole), b.b, eave, wall, false);
    if (b.rs === "hipped" && b.rh > 0.3 && !b.i.length) {
      const cx = ring.reduce((s, p) => s + p[0], 0) / ring.length, cy = ring.reduce((s, p) => s + p[1], 0) / ring.length;
      const inner = ring.map(([x, y]) => [cx + (x - cx) * 0.38, cy + (y - cy) * 0.38]);
      for (let k = 0; k < ring.length; k++) {
        const a = ring[k], b2 = ring[(k + 1) % ring.length], c = inner[(k + 1) % ring.length], d = inner[k];
        roofB.quad(W3(a[0], a[1], eave), W3(b2[0], b2[1], eave), W3(c[0], c[1], b.t), W3(d[0], d[1], b.t), roof);
      }
      cap(roofB, inner, [], b.t, roof);
    } else {
      cap(flatB, ring, b.i, b.t, roof);
    }
  }
  scene.add(wallB.mesh(toon("wall", { vcolor: true })));
  scene.add(roofB.mesh(toon("roof", { vcolor: true })));
  scene.add(flatB.mesh(toon("flat", { vcolor: true })));
}

function terrain(scene, S, heights, groundTex) {
  const { nx, ny, step, x0, y0 } = S.terrain, [X0, Y0, X1, Y1] = S.bbox;
  // em blocos, para o three deixar de fora o que não está no tile
  const CH = 64;
  const mat = toon("terrain", { map: groundTex });
  for (let j0 = 0; j0 < ny - 1; j0 += CH) for (let i0 = 0; i0 < nx - 1; i0 += CH) {
    const i1 = Math.min(nx - 1, i0 + CH), j1 = Math.min(ny - 1, j0 + CH);
    const w = i1 - i0 + 1, h = j1 - j0 + 1;
    const pos = new Float32Array(w * h * 3), uv = new Float32Array(w * h * 2), idx = [];
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
      const x = x0 + i * step, y = y0 + j * step, k = (j - j0) * w + (i - i0);
      const v = W3(x, y, heights[j * nx + i]);
      pos.set([v.x, v.y, v.z], k * 3);
      uv.set([(x - X0) / (X1 - X0), (y - Y0) / (Y1 - Y0)], k * 2);
    }
    for (let j = 0; j < h - 1; j++) for (let i = 0; i < w - 1; i++) {
      const a = j * w + i, b = a + 1, c = a + w, d = c + 1;
      idx.push(a, b, d, a, d, c);
    }
    let g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    g.setIndex(idx);
    g = g.toNonIndexed(); g.computeVertexNormals();   // faces chapadas: a luz em degraus fica nítida
    g.setAttribute("aInfo", new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 4), 4));
    scene.add(new THREE.Mesh(g, mat));
  }
  // as paredes laterais da maquete, até 25 m abaixo do rio
  const soil = new Builder(), brown = col("#7a5b3e"), BOTTOM = -25;
  const edge = (pts) => {
    for (let k = 0; k < pts.length - 1; k++) {
      const [xa, ya, za] = pts[k], [xb, yb, zb] = pts[k + 1];
      const ta = Math.max(za, S.water), tb = Math.max(zb, S.water), wet = za < S.water || zb < S.water ? 1 : 0;
      soil.quad(W3(xa, ya, BOTTOM), W3(xb, yb, BOTTOM), W3(xb, yb, tb), W3(xa, ya, ta), brown,
        [0, 0, 0, wet], [0, 0, 0, wet], [0, 0, 0, wet], [0, 0, 0, wet]);
    }
  };
  const at = (i, j) => [x0 + i * step, y0 + j * step, heights[j * nx + i]];
  const range = (n) => [...Array(n).keys()];
  edge(range(nx).map(i => at(i, 0)));                       // sul, de oeste para leste
  edge(range(ny).map(j => at(nx - 1, j)));                  // leste, de sul para norte
  edge(range(nx).map(i => at(nx - 1 - i, ny - 1)));         // norte, de leste para oeste
  edge(range(ny).map(j => at(0, ny - 1 - j)));              // oeste, de norte para sul
  scene.add(soil.mesh(toon("soil", { vcolor: true })));
  // o Douro: um plano à cota da água, só visível onde o terreno desce abaixo dela
  const water = new THREE.Mesh(new THREE.PlaneGeometry(X1 - X0, Y1 - Y0), toon("water"));
  water.rotation.x = -Math.PI / 2; water.position.copy(W3((X0 + X1) / 2, (Y0 + Y1) / 2, S.water));
  scene.add(water);
}

function ribbon(builder, pts, width, depth, top, side, lift = 0) {   // um tabuleiro: laje com espessura
  for (let k = 0; k < pts.length - 1; k++) {
    const [xa, ya, za] = pts[k], [xb, yb, zb] = pts[k + 1];
    const L = Math.hypot(xb - xa, yb - ya); if (L < 0.1) continue;
    const px = -(yb - ya) / L * width / 2, py = (xb - xa) / L * width / 2;
    const A = [xa + px, ya + py], B = [xb + px, yb + py], C = [xb - px, yb - py], D = [xa - px, ya - py];
    const t = (p, z) => W3(p[0], p[1], z + lift);
    builder.quad(t(D, za), t(C, zb), t(B, zb), t(A, za), top);                       // em cima
    builder.quad(t(A, za - depth), t(B, zb - depth), t(C, zb - depth), t(D, za - depth), side);   // em baixo
    builder.quad(t(D, za - depth), t(C, zb - depth), t(C, zb), t(D, za), side);      // lado direito
    builder.quad(t(B, zb - depth), t(A, za - depth), t(A, za), t(B, zb), side);      // lado esquerdo
  }
}

function box(builder, cx, cy, z0, z1, sx, sy, ang, color, iron = false) {
  const c = Math.cos(ang), s = Math.sin(ang);
  const P = (dx, dy) => [cx + dx * c - dy * s, cy + dx * s + dy * c];
  const r = [P(-sx / 2, -sy / 2), P(sx / 2, -sy / 2), P(sx / 2, sy / 2), P(-sx / 2, sy / 2)];
  let u = 0;
  for (let k = 0; k < 4; k++) {
    const [x0, y0] = r[k], [x1, y1] = r[(k + 1) % 4], len = Math.hypot(x1 - x0, y1 - y0);
    // aInfo: u ao longo, v normalizado 0..1 (a treliça dos pilares de ferro)
    builder.quad(W3(x0, y0, z0), W3(x1, y1, z0), W3(x1, y1, z1), W3(x0, y0, z1), color,
      iron ? [z0 * 0.8, 0.5, 0, 0] : [u, 0, z1 - z0, 0], iron ? [z0 * 0.8 + 0.0001, 0.5, 0, 0] : [u + len, 0, z1 - z0, 0],
      iron ? [z1 * 0.8, 0.5, 0, 0] : [u + len, z1 - z0, z1 - z0, 0], iron ? [z1 * 0.8, 0.5, 0, 0] : [u, z1 - z0, z1 - z0, 0]);
    u += len;
  }
  cap(builder, r, [], z1, color);
}

function bridges(scene, S) {
  const deckB = new Builder(), ironB = new Builder();
  const asphalt = col("#5c5c61"), stone = col("#bcb19b"), rail = col("#6d645b"), concrete = col("#bdb8ae"), iron = col("#4b4744");
  for (const d of S.decks) {
    const luiz = d.name.startsWith("Ponte Luiz");
    const top = d.kind === "light_rail" ? rail : ["pedestrian", "footway", "cycleway"].includes(d.kind) ? stone : asphalt;
    ribbon(deckB, d.p, d.w, luiz ? 2.2 : 1.2, top, luiz ? iron : concrete, d.kind === "pedestrian" ? 0.12 : 0);
  }
  for (const [x, y, z0, z1, size, c] of S.piers) box(deckB, x, y, z0, z1, size, size, 0, col(c));
  // o arco da Ponte Luiz I: duas nervuras em crescente, de treliça, com montantes até aos tabuleiros
  const lower = S.decks.find(d => d.name.includes("tabuleiro inferior"));
  for (const a of S.arches) {
    const [dx, dy] = a.dir, px = -dy, py = dx, half = a.span / 2, N = 72;
    const topZ = t => a.spring + (a.crown - a.spring) * (1 - (2 * t / a.span) ** 2);
    const botZ = t => a.spring + (a.crown - 7.5 - a.spring) * (1 - (2 * t / a.span) ** 2);
    const at = (t, off) => [a.c[0] + dx * t + px * off, a.c[1] + dy * t + py * off];
    for (const off of [-a.w / 2, a.w / 2]) {
      for (let k = 0; k < N; k++) {
        const t0 = -half + a.span * k / N, t1 = -half + a.span * (k + 1) / N;
        const s0 = t0 + half, s1 = t1 + half;
        for (const side of [-1.1, 1.1]) {   // as duas faces de cada nervura, 2,2 m de largura
          const [ax, ay] = at(t0, off + side), [bx, by] = at(t1, off + side);
          const q = side > 0
            ? [W3(ax, ay, botZ(t0)), W3(bx, by, botZ(t1)), W3(bx, by, topZ(t1)), W3(ax, ay, topZ(t0))]
            : [W3(bx, by, botZ(t1)), W3(ax, ay, botZ(t0)), W3(ax, ay, topZ(t0)), W3(bx, by, topZ(t1))];
          const info = side > 0 ? [[s0, 0], [s1, 0], [s1, 1], [s0, 1]] : [[s1, 0], [s0, 0], [s0, 1], [s1, 1]];
          ironB.quad(...q, iron, ...info.map(([s, v]) => [s, v, 0, 0]));
        }
        const [ax0, ay0] = at(t0, off - 1.1), [ax1, ay1] = at(t0, off + 1.1), [bx0, by0] = at(t1, off - 1.1), [bx1, by1] = at(t1, off + 1.1);
        ironB.quad(W3(ax1, ay1, topZ(t0)), W3(bx1, by1, topZ(t1)), W3(bx0, by0, topZ(t1)), W3(ax0, ay0, topZ(t0)), iron, [0, 0.5, 0, 0]);   // banzo de cima
        ironB.quad(W3(ax0, ay0, botZ(t0)), W3(bx0, by0, botZ(t1)), W3(bx1, by1, botZ(t1)), W3(ax1, ay1, botZ(t0)), iron, [0, 0.5, 0, 0]);   // banzo de baixo
      }
      // montantes: do arco ao tabuleiro de cima perto dos apoios, e tirantes ao de baixo no meio
      for (let t = -half + 6; t < half - 3; t += 7.5) {
        const [x, y] = at(t, off);
        if (a.crown + 1.2 - topZ(t) > 1.5) box(deckB, x, y, topZ(t) - 0.3, a.crown + 0.2, 0.9, 0.9, 0, iron);
        if (lower && botZ(t) - lower.p[0][2] > 1.5) box(deckB, x, y, lower.p[0][2] - 0.5, botZ(t) + 0.3, 0.45, 0.45, 0, iron);
      }
    }
    for (let t = -half + 10; t < half - 6; t += 10) {   // contraventamento entre as nervuras
      const [x, y] = at(t, 0);
      box(deckB, x, y, topZ(t) - 0.9, topZ(t) - 0.3, 0.6, a.w, Math.atan2(dy, dx), iron);
    }
  }
  scene.add(deckB.mesh(toon("flat", { vcolor: true })));
  scene.add(ironB.mesh(toon("iron", { vcolor: true, side: THREE.DoubleSide })));
}

function trees(scene, list) {
  const crown = new THREE.IcosahedronGeometry(1, 0).toNonIndexed(); crown.computeVertexNormals();
  crown.setAttribute("aInfo", new THREE.Float32BufferAttribute(new Float32Array(crown.attributes.position.count * 4), 4));
  const trunk = new THREE.BoxGeometry(0.5, 1, 0.5).toNonIndexed();
  trunk.setAttribute("aInfo", new THREE.Float32BufferAttribute(new Float32Array(trunk.attributes.position.count * 4), 4));
  const greens = ["#5f8c3b", "#4f7d35", "#6f9a45", "#58803a", "#7aa14c"].map(col);
  const cm = new THREE.InstancedMesh(crown, toon("tree"), list.length);
  const tm = new THREE.InstancedMesh(trunk, toon("flat", { color: "#6b4a30" }), list.length);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
  list.forEach(([x, y, z, r], k) => {
    e.set(0, (k * 2.399) % 6.283, 0); q.setFromEuler(e);
    m.compose(W3(x, y, z + r * 1.25), q, new THREE.Vector3(r, r * 0.9, r)); cm.setMatrixAt(k, m);
    cm.setColorAt(k, greens[k % greens.length]);
    m.compose(W3(x, y, z + r * 0.4), q, new THREE.Vector3(1, r * 0.9, 1)); tm.setMatrixAt(k, m);
  });
  scene.add(cm, tm);
}

function boats(scene, list) {
  // barco rabelo: casco escuro e comprido, pipas no convés, vela quadrada
  const hull = new Builder(), wood = col("#5a3a24"), dark = col("#3d2717"), sail = col("#eee5cf"), cask = col("#7b4f2c");
  const one = new Builder();
  for (const [x, y, z, ang] of list) {
    const c = Math.cos(ang), s = Math.sin(ang), P = (dx, dy) => [x + dx * c - dy * s, y + dx * s + dy * c];
    const L = 8, B = 2.1, z0 = z - 0.3, z1 = z + 1.1;
    const ring = [P(-L, 0), P(-L + 2.5, -B), P(L - 3, -B), P(L, 0), P(L - 3, B), P(-L + 2.5, B)];
    for (let k = 0; k < ring.length; k++) {
      const [ax, ay] = ring[k], [bx, by] = ring[(k + 1) % ring.length];
      hull.quad(W3(ax, ay, z0), W3(bx, by, z0), W3(bx, by, z1), W3(ax, ay, z1), wood);
    }
    cap(hull, ring, [], z1, dark);
    for (const k of [-4, -2.2, -0.4, 1.4, 3.2]) { const [cx, cy] = P(k, 0); box(one, cx, cy, z1, z1 + 1.1, 1.3, 1.3, ang, cask); }
    const [mx, my] = P(-1.5, 0); box(one, mx, my, z1, z1 + 9, 0.3, 0.3, ang, dark);
    const [sx0, sy0] = P(-1.2, -3.2), [sx1, sy1] = P(-1.2, 3.2);   // a vela, de través
    one.quad(W3(sx0, sy0, z1 + 2.5), W3(sx1, sy1, z1 + 2.5), W3(sx1, sy1, z1 + 8.6), W3(sx0, sy0, z1 + 8.6), sail);
    one.quad(W3(sx1, sy1, z1 + 2.5), W3(sx0, sy0, z1 + 2.5), W3(sx0, sy0, z1 + 8.6), W3(sx1, sy1, z1 + 8.6), sail);
  }
  scene.add(hull.mesh(toon("flat", { vcolor: true })), one.mesh(toon("flat", { vcolor: true })));
}

// ---- contorno: um passe sobre a cor, as normais e a profundidade --------------------------------------------
const post = new THREE.ShaderMaterial({
  uniforms: { tColor: { value: null }, tNormal: { value: null }, tDepth: { value: null }, uPx: { value: new THREE.Vector2() },
    uRange: { value: 1 } },
  vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
  fragmentShader: /* glsl */`
    uniform sampler2D tColor, tNormal, tDepth; uniform vec2 uPx; uniform float uRange; varying vec2 vUv;
    void main() {
      float d = texture2D(tDepth, vUv).r;
      vec4 nn = texture2D(tNormal, vUv);
      vec3 c = texture2D(tColor, vUv).rgb;
      if (d >= 1.0) { gl_FragColor = vec4(0.0); return; }
      float sil = 0.0, crease = 0.0;
      vec2 o[4]; o[0] = vec2(1, 0); o[1] = vec2(-1, 0); o[2] = vec2(0, 1); o[3] = vec2(0, -1);
      for (int k = 0; k < 4; k++) {
        vec2 q = vUv + o[k] * uPx;
        float dq = texture2D(tDepth, q).r;
        vec4 nq = texture2D(tNormal, q);
        float gap = (dq - d) * uRange;   // metros a mais de profundidade no vizinho
        float thr = (nn.a < 0.5 && nq.a < 0.5) ? 9.0 : 2.2;   // chão com chão: só as arribas
        if (dq >= 1.0 || gap > thr) sil = 1.0;
        else if (nn.a > 0.5 && nq.a > 0.5 && abs(gap) < thr && dot(nn.rgb * 2.0 - 1.0, nq.rgb * 2.0 - 1.0) < 0.6 && gap > -0.05) crease = 1.0;
      }
      if (sil > 0.0) c *= 0.42; else if (crease > 0.0) c *= 0.78;
      gl_FragColor = vec4(c, 1.0);
    }`,
  depthTest: false, depthWrite: false,
});

// ---- montagem -----------------------------------------------------------------------------------------------
export async function setup(base = "scene/") {
  const S = await (await fetch(base + "scene.json")).json();
  const heights = new Float32Array(await (await fetch(base + S.terrain.file)).arrayBuffer());
  const groundTex = await new THREE.TextureLoader().loadAsync(base + S.ground.file);
  groundTex.magFilter = groundTex.minFilter = THREE.NearestFilter; groundTex.generateMipmaps = false;
  groundTex.colorSpace = THREE.NoColorSpace;
  shared.uWater.value = S.water;

  const scene = new THREE.Scene();
  terrain(scene, S, heights, groundTex);
  buildings(scene, S.buildings);
  bridges(scene, S);
  trees(scene, S.trees);
  boats(scene, S.boats);

  const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true, preserveDrawingBuffer: true });
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;   // cores tal como escritas: nada de correção gama
  renderer.setPixelRatio(1);
  const size = TILE + 2 * MARGIN;
  renderer.setSize(size, size, false);
  renderer.setClearColor(0x000000, 0);

  const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 1, 8000);
  const toCam = dirENU(YAW, PITCH);   // do alvo para a câmera
  const target = W3(0, 0, 40);
  cam.position.copy(target).addScaledVector(toCam, 4000);
  cam.up.set(0, 1, 0); cam.lookAt(target); cam.updateMatrixWorld();
  const range = cam.far - cam.near;

  const opts = { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter };
  const rtColor = new THREE.WebGLRenderTarget(size, size, { ...opts, depthTexture: new THREE.DepthTexture(size, size) });
  const rtNormal = new THREE.WebGLRenderTarget(size, size, opts);
  rtColor.depthTexture.type = THREE.FloatType;
  post.uniforms.tColor.value = rtColor.texture; post.uniforms.tNormal.value = rtNormal.texture;
  post.uniforms.tDepth.value = rtColor.depthTexture; post.uniforms.uPx.value.set(1 / size, 1 / size);
  post.uniforms.uRange.value = range;
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), post), postScene = new THREE.Scene(), postCam = new THREE.Camera();
  postScene.add(quad);

  // o recorte da cena em pixels do desenho: os cantos do bloco, do fundo da maquete ao topo da torre mais alta
  const [X0, Y0, X1, Y1] = S.bbox, inv = cam.matrixWorldInverse;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const x of [X0, X1]) for (const y of [Y0, Y1]) for (const z of [-25, 200]) {
    const v = W3(x, y, z).applyMatrix4(inv);
    minX = Math.min(minX, v.x / MPP); maxX = Math.max(maxX, v.x / MPP);
    minY = Math.min(minY, -v.y / MPP); maxY = Math.max(maxY, -v.y / MPP);   // y do ecrã para baixo
  }
  const grid = { c0: Math.floor(minX / TILE), c1: Math.floor(maxX / TILE), r0: Math.floor(minY / TILE), r1: Math.floor(maxY / TILE) };

  const out = document.createElement("canvas"); out.width = out.height = TILE;
  const octx = out.getContext("2d", { willReadFrequently: true });
  function renderTile(cx, cy) {
    const l = (cx * TILE - MARGIN) * MPP, r = ((cx + 1) * TILE + MARGIN) * MPP;
    const t = -(cy * TILE - MARGIN) * MPP, b = -((cy + 1) * TILE + MARGIN) * MPP;
    cam.left = l; cam.right = r; cam.top = t; cam.bottom = b; cam.updateProjectionMatrix();
    shared.uMode.value = 0; renderer.setRenderTarget(rtColor); renderer.clear(); renderer.render(scene, cam);
    shared.uMode.value = 1; renderer.setRenderTarget(rtNormal); renderer.setClearColor(0x000000, 0); renderer.clear(); renderer.render(scene, cam);
    renderer.setRenderTarget(null); renderer.clear(); renderer.render(postScene, postCam);
    octx.clearRect(0, 0, TILE, TILE);
    octx.drawImage(renderer.domElement, MARGIN, MARGIN, TILE, TILE, 0, 0, TILE, TILE);
    const px = octx.getImageData(0, 0, TILE, TILE).data;
    let any = false; for (let k = 3; k < px.length; k += 64) if (px[k]) { any = true; break; }
    return any ? out.toDataURL("image/png") : null;
  }
  // um ponto da cena (metros) em pixels do desenho, para o visualizador pôr nomes no mapa
  function project(x, y, z) { const v = W3(x, y, z).applyMatrix4(inv); return [v.x / MPP, -v.y / MPP]; }
  const labels = S.labels.map(l => ({ ...l, px: project(l.x, l.y, l.z) }));
  return { grid, renderTile, project, labels, tile: TILE, mpp: MPP, credits: S.credits };
}
