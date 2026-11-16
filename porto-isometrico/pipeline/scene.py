"""OSM + relevo -> uma cena 3D simples em metros locais, pronta para o render (web/render.html).

Uso: python3 pipeline/scene.py
Lê data/osm.json, data/dem.npy, data/dem.json (pipeline/fetch_osmapi.py)
Escreve web/scene/scene.json, web/scene/terrain.bin (float32) e web/scene/ground.png

Eixos: x para leste, y para norte, z para cima, em metros, com origem no centro do recorte.
"""
import hashlib, json, math, pathlib, re, sys
import numpy as np
from PIL import Image, ImageDraw
import shapely
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import linemerge, unary_union

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch import BBOX, DATA

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "scene"
S, W, N, E = BBOX
LAT0, LON0 = (S + N) / 2, (W + E) / 2
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110574
STEP = 3.0          # m entre os vértices do terreno
TEX_M = 0.5         # m por pixel da textura do chão: o mesmo de um pixel do desenho
WATER_Z = 0.6       # a superfície do Douro
RIVERBED = -3.0     # o fundo, para o cais ter parede
QUAY_MIN = 5.0      # a terra junto ao rio nunca abaixo disto: os cais de granito


def xy(lat, lon):
    return ((lon - LON0) * KX, (lat - LAT0) * KY)


XMIN, YMIN = xy(S, W)
XMAX, YMAX = xy(N, E)
FRAME = box(XMIN, YMIN, XMAX, YMAX)


def hsh(*parts):   # determinístico: o mesmo prédio tem sempre a mesma cor
    return int(hashlib.md5(":".join(map(str, parts)).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


# ---- relevo ---------------------------------------------------------------------------------------------------
dem = np.load(DATA / "dem.npy").astype(np.float64)
meta = json.loads((DATA / "dem.json").read_text())


def elev(x, y):
    """Altitude (m) em pontos locais, bilinear no raster Terrarium (Web Mercator)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    lat, lon = LAT0 + y / KY, LON0 + x / KX
    n = 2 ** meta["zoom"]
    px = ((lon + 180) / 360 * n - meta["x0"]) * 256 - 0.5
    py = ((1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n - meta["y0"]) * 256 - 0.5
    x0 = np.clip(np.floor(px).astype(int), 0, dem.shape[1] - 2)
    y0 = np.clip(np.floor(py).astype(int), 0, dem.shape[0] - 2)
    fx, fy = np.clip(px - x0, 0, 1), np.clip(py - y0, 0, 1)
    a, b = dem[y0, x0], dem[y0, x0 + 1]
    c, d = dem[y0 + 1, x0], dem[y0 + 1, x0 + 1]
    return a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy


# ---- OSM -> geometrias ----------------------------------------------------------------------------------------
osm = json.loads((DATA / "osm.json").read_text())["elements"]


def line_of(geom):
    return [xy(p["lat"], p["lon"]) for p in geom if p]


def rings_from(members):
    """Junta os ways de um multipolígono em anéis fechados (por pontas em comum)."""
    lines = [LineString(line_of(m["geometry"])) for m in members if len(m.get("geometry", [])) >= 2]
    if not lines:
        return []
    merged = linemerge(lines)
    parts = merged.geoms if hasattr(merged, "geoms") else [merged]
    return [list(p.coords) for p in parts]


def polygon_of(el):
    if el["type"] == "way":
        pts = line_of(el.get("geometry", []))
        if len(pts) < 4 or pts[0] != pts[-1]:
            return None
        g = Polygon(pts)
    elif el["type"] == "relation":
        outer = [r for r in rings_from([m for m in el.get("members", []) if m.get("role") != "inner"]) if len(r) >= 4 and r[0] == r[-1]]
        inner = [r for r in rings_from([m for m in el.get("members", []) if m.get("role") == "inner"]) if len(r) >= 4 and r[0] == r[-1]]
        if not outer:
            return None
        g = unary_union([Polygon(r) for r in outer]).difference(unary_union([Polygon(r) for r in inner]) if inner else Polygon())
    else:
        return None
    g = shapely.make_valid(g)
    return g if g.area > 0 else None


def polys(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return list(g.geoms)
    return [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]


# o Douro: as duas margens longas, fechadas longe do recorte
river = None
for el in osm:
    t = el.get("tags", {})
    if el["type"] == "relation" and t.get("water") == "river":
        banks = [line_of(m["geometry"]) for m in el["members"] if m.get("role") == "outer"]
        if len(banks) == 2:
            a, b = banks
            # a ponta oeste de uma liga à ponta oeste da outra
            if math.dist(a[-1], b[-1]) < math.dist(a[-1], b[0]):
                b = b[::-1]
            river = shapely.make_valid(Polygon(a + b))
        else:
            river = polygon_of(el)
river = (river or Polygon()).intersection(FRAME.buffer(200))
print(f"rio: {river.intersection(FRAME).area / 1e4:.1f} ha no recorte")

# ---- terreno --------------------------------------------------------------------------------------------------
nx, ny = int((XMAX - XMIN) / STEP) + 1, int((YMAX - YMIN) / STEP) + 1
gx = XMIN + np.arange(nx) * STEP
gy = YMIN + np.arange(ny) * STEP
GX, GY = np.meshgrid(gx, gy)
H = elev(GX, GY)
wet = shapely.contains_xy(river, GX, GY)
near = shapely.contains_xy(river.buffer(60), GX, GY) & ~wet
H = np.where(near, np.maximum(H, QUAY_MIN), H)
H = np.where(wet, RIVERBED, H)
land = np.where(wet, np.nan, H)
print(f"terreno: {nx}x{ny} vértices, {np.nanmin(land):.0f} a {np.nanmax(land):.0f} m")


def ground(x, y):
    """Altitude do terreno já tratado (cais, leito), bilinear na grade."""
    fx = np.clip((np.asarray(x) - XMIN) / STEP, 0, nx - 1.001)
    fy = np.clip((np.asarray(y) - YMIN) / STEP, 0, ny - 1.001)
    i, j = fx.astype(int), fy.astype(int)
    tx, ty = fx - i, fy - j
    return (H[j, i] * (1 - tx) * (1 - ty) + H[j, i + 1] * tx * (1 - ty)
            + H[j + 1, i] * (1 - tx) * ty + H[j + 1, i + 1] * tx * ty)


# ---- textura do chão ------------------------------------------------------------------------------------------
TW, TH = int((XMAX - XMIN) / TEX_M), int((YMAX - YMIN) / TEX_M)
tex = Image.new("RGBA", (TW, TH), (206, 198, 180, 128))   # alfa 128: chão "comum", o shader decide pela inclinação
draw = ImageDraw.Draw(tex)


def tp(pts):
    return [((x - XMIN) / TEX_M, (YMAX - y) / TEX_M) for x, y in pts]


def fill(g, rgb):
    for p in polys(g.intersection(FRAME.buffer(5)) if g is not None else None):
        if p.exterior.coords and len(p.exterior.coords) >= 3:
            draw.polygon(tp(p.exterior.coords), fill=rgb + (255,))
            for hole in p.interiors:
                draw.polygon(tp(hole.coords), fill=(206, 198, 180, 128))


AREA_COLOURS = [
    (lambda t: t.get("landuse") in ("grass", "village_green", "recreation_ground", "meadow") or t.get("natural") == "grassland", (134, 172, 92)),
    (lambda t: t.get("leisure") in ("park", "garden"), (122, 164, 86)),
    (lambda t: t.get("landuse") == "cemetery", (150, 162, 128)),
    (lambda t: t.get("landuse") == "forest" or t.get("natural") in ("wood", "scrub"), (88, 128, 66)),
    (lambda t: t.get("leisure") == "pitch", (96, 156, 86)),
]
for rule, rgb in AREA_COLOURS:
    for el in osm:
        t = el.get("tags", {})
        if el["type"] in ("way", "relation") and rule(t):
            fill(polygon_of(el), rgb)
# praças e ruas pedonais desenhadas como área: granito claro
for el in osm:
    t = el.get("tags", {})
    if (t.get("area") == "yes" and t.get("highway") in ("pedestrian", "footway")) or t.get("place") == "square" or t.get("area:highway"):
        fill(polygon_of(el), (214, 204, 182))
fill(river, (63, 127, 168))
for el in osm:
    t = el.get("tags", {})
    if t.get("natural") == "water" and t.get("water") != "river":
        fill(polygon_of(el), (78, 142, 180))

ROAD_W = {"motorway": 16, "trunk": 14, "primary": 11, "secondary": 9, "tertiary": 8, "residential": 6.5,
          "unclassified": 6, "living_street": 5, "service": 4, "pedestrian": 6, "footway": 2.4, "path": 2,
          "steps": 2.4, "cycleway": 2.4, "track": 3}
STONE = {"pedestrian", "footway", "steps", "path", "living_street"}


def stroke(pts, width_m, rgb):
    if len(pts) >= 2:
        draw.line(tp(pts), fill=rgb + (255,), width=max(1, round(width_m / TEX_M)), joint="curve")


roads = []
for el in osm:
    t = el.get("tags", {})
    if el["type"] == "way" and t.get("highway") in ROAD_W and t.get("area") != "yes":
        if t.get("bridge") in ("yes", "viaduct") or t.get("tunnel") in ("yes", "building_passage") or t.get("covered") == "yes":
            continue
        roads.append((t["highway"], line_of(el["geometry"])))
for kind, pts in roads:          # passeios primeiro, debaixo do asfalto
    if kind not in STONE:
        stroke(pts, ROAD_W[kind] + 3, (196, 188, 170))
for kind, pts in roads:
    stroke(pts, ROAD_W[kind], (204, 194, 172) if kind in STONE else (104, 104, 110))
for kind, pts in roads:          # escadas: degraus como riscas
    if kind == "steps":
        stroke(pts, 1.2, (170, 160, 142))
for el in osm:
    t = el.get("tags", {})
    if el["type"] == "way" and t.get("railway") in ("rail", "light_rail", "tram") and t.get("bridge") is None and t.get("tunnel") is None:
        stroke(line_of(el["geometry"]), 3.2, (112, 96, 84))
        stroke(line_of(el["geometry"]), 1.0, (150, 150, 155))
OUT.mkdir(parents=True, exist_ok=True)
tex.save(OUT / "ground.png", optimize=True)
print(f"chão: {TW}x{TH} px")

# ---- prédios --------------------------------------------------------------------------------------------------
WALLS = ["#ead9b4", "#e2b867", "#c95f3f", "#f1e6cb", "#9fb7c8", "#e4b6a3", "#cdd5b2", "#efcf72",
         "#f7f3ea", "#b8c6d4", "#d88a5c", "#e7c79d", "#86a7c4", "#f0b9a0"]
ROOFS = ["#b4532f", "#a64a2a", "#bf633a", "#9b4426", "#b75a36", "#c06c44"]
NAMED = {"white": "#f4f1ea", "red": "#b4532f", "grey": "#a9a59d", "gray": "#a9a59d", "brown": "#8c5a3c",
         "black": "#3a3a3a", "yellow": "#efcf72", "blue": "#86a7c4", "green": "#8aa86a", "orange": "#d88a5c",
         "beige": "#e7d7b4", "darkgrey": "#7c7a75", "lightgrey": "#c7c3bb", "pink": "#e8b4b0", "maroon": "#8a3b2c"}


def colour(v):
    if not v:
        return None
    v = v.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", v):
        return v
    if re.fullmatch(r"#[0-9a-f]{3}", v):
        return "#" + "".join(c * 2 for c in v[1:])
    return NAMED.get(v.replace(" ", "").replace("_", ""))


def num(v):
    try:
        return float(re.match(r"[-\d.]+", str(v).replace(",", ".")).group())
    except Exception:
        return None


def heights(t, eid, area):
    kind = t.get("building") or t.get("building:part")
    lv, minlv = num(t.get("building:levels")), num(t.get("building:min_level"))
    h = num(t.get("height"))
    if h is None and lv is not None:
        h = lv * 3.2 + (1.5 if t.get("roof:shape") not in (None, "flat") else 0.6)
    if h is None:
        h = {"house": 8, "apartments": 15, "residential": 12, "church": 16, "cathedral": 24, "chapel": 9,
             "commercial": 11, "retail": 8, "office": 15, "garage": 3, "garages": 3, "shed": 3, "hut": 3,
             "roof": 4, "ruins": 4, "kiosk": 3, "train_station": 12, "public": 14, "monastery": 15,
             "hotel": 16, "industrial": 9, "warehouse": 9}.get(kind)
    if h is None:   # o centro histórico: três a cinco andares
        h = 9.6 + 3.2 * int(hsh(eid, "lv") * 3)
    mh = num(t.get("min_height"))
    if mh is None and minlv is not None:
        mh = minlv * 3.2
    if kind == "roof":                       # alpendres e coberturas: só a laje
        mh = max(mh or 0, h - 0.6)
    rs = t.get("roof:shape")
    if rs is None:
        rs = "hipped" if area < 450 and kind not in ("roof", "ruins") else "flat"
    rh = num(t.get("roof:height"))
    if rs != "flat" and rh is None:
        rh = min(3.5, 0.28 * math.sqrt(area))
    return mh or 0.0, h, rs if rs == "flat" else "hipped", (rh or 0.0)


feats = [el for el in osm if ("building" in el.get("tags", {}) or "building:part" in el.get("tags", {}))
         and el["type"] in ("way", "relation") and el["tags"].get("building") not in ("no",)]
parts = []
for el in feats:
    if "building:part" in el["tags"] and el["tags"]["building:part"] != "no":
        for p in polys(polygon_of(el)):
            parts.append(p.representative_point())
part_tree = shapely.STRtree(parts) if parts else None

buildings, footprints = [], []
for el in feats:
    t = el["tags"]
    is_part = "building:part" in t and t["building:part"] != "no"
    for k, p in enumerate(polys(polygon_of(el))):
        c = p.representative_point()
        if not FRAME.contains(c):
            continue
        if not is_part and part_tree is not None and len(part_tree.query(p, predicate="contains")):
            continue   # as partes desenham este prédio (Simple 3D Buildings)
        p = p.simplify(0.25)
        if p.is_empty or p.area < 6 or not isinstance(p, Polygon):
            continue
        p = shapely.geometry.polygon.orient(p, 1.0)
        eid = f"{el['type']}{el['id']}.{k}"
        mh, h, rs, rh = heights(t, eid, p.area)
        ring = np.array(p.exterior.coords[:-1])
        zs = ground(ring[:, 0], ring[:, 1])
        base = float(np.min(zs)) - 0.8
        top = float(np.mean(zs)) + h
        if t.get("building") in ("church", "cathedral", "chapel", "monastery") or t.get("amenity") == "place_of_worship":
            wall = "#d8d0bf"
        elif t.get("building") == "ruins":
            wall = "#a59d8f"
        else:
            r = hsh(eid, "w")
            wall = WALLS[int(r * len(WALLS))]
        wall = colour(t.get("building:colour")) or wall
        roof = colour(t.get("roof:colour")) or (ROOFS[int(hsh(eid, "r") * len(ROOFS))] if rs == "hipped" else "#a8a39a")
        buildings.append({
            "o": [[round(x, 2), round(y, 2)] for x, y in ring],
            "i": [[[round(x, 2), round(y, 2)] for x, y in hole.coords[:-1]] for hole in p.interiors],
            "b": round(base + mh, 2) if mh else round(base, 2), "t": round(top, 2),
            "rs": rs, "rh": round(rh, 2), "w": wall, "r": roof,
        })
        if not is_part:
            footprints.append(p)
print(f"prédios: {len(buildings)} ({sum(b['rs'] == 'hipped' for b in buildings)} com telhado de quatro águas)")

# ---- pontes ---------------------------------------------------------------------------------------------------
DECK_W = {"light_rail": 7.5, "rail": 7.5, "pedestrian": 3.0, "footway": 2.5, "primary": 12, "secondary": 9,
          "tertiary": 8, "residential": 7, "service": 5, "unclassified": 6, "cycleway": 2.5}
chains = {}
for el in osm:
    t = el.get("tags", {})
    kind = t.get("highway") or t.get("railway")
    if el["type"] == "way" and t.get("bridge") in ("yes", "viaduct") and kind in DECK_W:
        key = (t.get("name", f"#{el['id']}"), t.get("layer", "1"), kind)
        chains.setdefault(key, []).append(LineString(line_of(el["geometry"])))
decks = []
for (name, layer, kind), lines in chains.items():
    merged = linemerge(lines)
    for ln in (merged.geoms if hasattr(merged, "geoms") else [merged]):
        clipped = ln.intersection(FRAME)
        if clipped.is_empty or clipped.length < 4:
            continue
        a, b = ln.coords[0], ln.coords[-1]
        za, zb = float(ground(a[0], a[1])), float(ground(b[0], b[1]))
        if ln.length > 120:   # as pontes grandes do Porto são planas; o relevo grosso erra uma das pontas
            za = zb = max(za, zb)
        za, zb = max(za, WATER_Z + 1.2), max(zb, WATER_Z + 1.2)   # passadiços dos cais: nunca dentro de água
        for seg in (clipped.geoms if hasattr(clipped, "geoms") else [clipped]):
            pts = []
            for x, y in seg.coords:
                f = ln.project(Point(x, y)) / ln.length
                pts.append([round(x, 2), round(y, 2), round(za + (zb - za) * f + 0.5, 2)])
            decks.append({"name": name, "kind": kind, "w": DECK_W[kind], "p": pts, "layer": layer})
for d in decks:
    print(f"  ponte {d['name']} ({d['kind']}, camada {d['layer']}): {d['p'][0][2]:.0f} a {d['p'][-1][2]:.0f} m")


def deck_of(prefix, kind=None):
    for d in decks:
        if d["name"].startswith(prefix) and (kind is None or d["kind"] == kind):
            return d
    return None


arches, piers = [], []


def arch_over(d, span, rise_from, style, width):
    """Um arco sob o tabuleiro d, centrado onde o tabuleiro cruza o rio."""
    ln = LineString([p[:2] for p in d["p"]])
    wet_part = ln.intersection(river)
    if wet_part.is_empty:
        return None
    cpt = wet_part.interpolate(0.5, normalized=True) if not hasattr(wet_part, "geoms") else unary_union(wet_part).centroid
    (x0, y0), (x1, y1) = d["p"][0][:2], d["p"][-1][:2]
    L = math.hypot(x1 - x0, y1 - y0)
    crown = min(p[2] for p in d["p"]) - 1.2
    a = {"c": [round(cpt.x, 2), round(cpt.y, 2)], "dir": [(x1 - x0) / L, (y1 - y0) / L], "span": span,
         "spring": round(rise_from, 2), "crown": round(crown, 2), "style": style, "w": width}
    arches.append(a)
    return a


luiz_up = deck_of("Ponte Luiz I", "light_rail")
luiz_low = deck_of("Ponte Luiz I (tabuleiro inferior)")
if luiz_low:   # o tabuleiro de baixo passa rente ao cais, sobre o rio
    zl = max(QUAY_MIN + 4, min(p[2] for p in luiz_low["p"]))
    for p in luiz_low["p"]:
        p[2] = round(zl, 2)
luiz = arch_over(luiz_up, 172, 1.0, "iron", 8.5) if luiz_up else None
# a Ponte Infante Dom Henrique fica quase toda a leste do recorte: aqui só a ponta norte do tabuleiro

# pilares: a cada ~30 m onde o tabuleiro vai alto sobre terra firme, fora do vão dos arcos
for d in decks:
    ln = LineString([p[:2] for p in d["p"]])
    zs = [p[2] for p in d["p"]]
    n = int(ln.length // 30)
    for k in range(1, n + 1):
        s = k * ln.length / (n + 1)
        pt = ln.interpolate(s)
        f = s / ln.length
        # o tabuleiro é uma reta entre as pontas da cadeia; aqui basta interpolar entre os pontos
        dz = np.interp(s, [ln.project(Point(p[:2])) for p in d["p"]], zs)
        g = float(ground(pt.x, pt.y))
        if river.contains(pt) or dz - g < 4:
            continue
        inside = any(abs((pt.x - a["c"][0]) * a["dir"][0] + (pt.y - a["c"][1]) * a["dir"][1]) < a["span"] / 2 + 6 for a in arches)
        if inside:
            continue
        size = 4.0 if d["name"].startswith("Ponte Luiz") else 3.0
        piers.append([round(pt.x, 2), round(pt.y, 2), round(g - 1, 2), round(dz - 0.4, 2), size,
                      "#4a4743" if d["name"].startswith("Ponte Luiz") else "#bdb8ae"])
print(f"arcos: {len(arches)}, pilares: {len(piers)}")

# ---- árvores e barcos -----------------------------------------------------------------------------------------
foot_union = unary_union(footprints).buffer(1.5)
trees = []
for el in osm:
    t = el.get("tags", {})
    if el["type"] == "node" and t.get("natural") == "tree":
        x, y = xy(el["lat"], el["lon"])
        if FRAME.contains(Point(x, y)):
            trees.append([round(x, 1), round(y, 1), round(float(ground(x, y)), 1), round(2.4 + 1.6 * hsh(el["id"]), 1)])
green = []
for el in osm:
    t = el.get("tags", {})
    if el["type"] in ("way", "relation") and (t.get("leisure") in ("park", "garden") or t.get("landuse") == "forest"
                                              or t.get("natural") in ("wood", "scrub")):
        g = polygon_of(el)
        if g is not None:
            green.append((g.intersection(FRAME), 0.85 if t.get("leisure") is None else 0.45, el["id"]))
for g, keep, gid in green:
    if g.is_empty:
        continue
    x0, y0, x1, y1 = g.bounds
    for gx_ in np.arange(x0, x1, 8.5):
        for gy_ in np.arange(y0, y1, 8.5):
            r = hsh(gid, round(gx_), round(gy_))
            px_, py_ = gx_ + (hsh(gid, gx_, "x") - 0.5) * 6, gy_ + (hsh(gid, gy_, "y") - 0.5) * 6
            if r < keep and g.contains(Point(px_, py_)) and not foot_union.contains(Point(px_, py_)):
                trees.append([round(px_, 1), round(py_, 1), round(float(ground(px_, py_)), 1), round(2.6 + 1.8 * r, 1)])
print(f"árvores: {len(trees)}")

# barcos rabelos atracados no cais de Gaia (margem sul), a oeste da Ponte Luiz I
boats = []
for k, lon in enumerate(np.linspace(-8.6138, -8.6100, 9)):
    x, _ = xy(LAT0, lon)
    cut = river.intersection(LineString([(x, YMIN), (x, YMAX)]))
    if cut.is_empty:
        continue
    ysouth = cut.bounds[1]
    boats.append([round(x, 1), round(ysouth + 9 + 3 * hsh(k, "b"), 1), WATER_Z, round((hsh(k, "a") - 0.5) * 0.25, 3)])
print(f"barcos: {len(boats)}")

# ---- nomes no mapa ---------------------------------------------------------------------------------------------
LABELS = [   # nome, onde procurar no OSM, e onde pôr se não achar (lat, lon)
    ("Ponte Luiz I", "Ponte Luiz I (tabuleiro superior)", (41.14010, -8.60940), "ponte"),
    ("Ribeira", "Praça da Ribeira", (41.14060, -8.61310), "bairro"),
    ("Sé do Porto", "Sé do Porto", (41.14280, -8.61130), "marco"),
    ("Torre dos Clérigos", "Torre dos Clérigos", (41.14570, -8.61460), "marco"),
    ("Estação de São Bento", "Estação de São Bento", (41.14560, -8.61050), "marco"),
    ("Palácio da Bolsa", "Palácio da Bolsa", (41.14150, -8.61580), "marco"),
    ("Mosteiro da Serra do Pilar", "Mosteiro da Serra do Pilar", (41.13810, -8.60770), "marco"),
    ("Cais de Gaia", None, (41.13760, -8.61250), "bairro"),
    ("Rio Douro", None, (41.13960, -8.61850), "agua"),
    ("Fontaínhas", None, (41.14240, -8.60330), "bairro"),
    ("Miragaia", None, (41.14320, -8.62020), "bairro"),
]
labels = []
for name, osm_name, (lat, lon), kind in LABELS:
    x, y = xy(lat, lon)
    top = None
    if osm_name:
        for el in osm:
            if el.get("tags", {}).get("name") == osm_name and el["type"] in ("way", "relation"):
                g = polygon_of(el) if el["type"] == "relation" or el.get("geometry", [{}])[0] == el.get("geometry", [{}])[-1] else None
                pts = list(g.exterior.coords) if isinstance(g, Polygon) else line_of(el.get("geometry", []))
                if pts:
                    c = (Polygon(pts).representative_point() if len(pts) >= 4 and isinstance(g, Polygon) else LineString(pts).interpolate(0.5, normalized=True))
                    x, y = c.x, c.y
                    break
    z = float(ground(x, y))
    for b in buildings:   # em cima do prédio, se o nome é de um prédio
        if Polygon(b["o"]).contains(Point(x, y)):
            top = max(top or 0, b["t"])
    if kind == "ponte":
        z = max(p[2] for d in decks if d["name"].startswith("Ponte Luiz") for p in d["p"])
    labels.append({"name": name, "kind": kind, "x": round(x, 1), "y": round(y, 1), "z": round(max(z, top or z, WATER_Z), 1)})
print("nomes:", ", ".join(f"{l['name']} ({l['z']:.0f} m)" for l in labels))

# ---- saída ----------------------------------------------------------------------------------------------------
H.astype(np.float32).tofile(OUT / "terrain.bin")
scene = {
    "origin": {"lat": LAT0, "lon": LON0}, "bbox": [XMIN, YMIN, XMAX, YMAX],
    "terrain": {"nx": nx, "ny": ny, "step": STEP, "x0": XMIN, "y0": YMIN, "file": "terrain.bin"},
    "ground": {"file": "ground.png", "w": TW, "h": TH, "m": TEX_M},
    "water": WATER_Z, "buildings": buildings, "decks": decks, "arches": arches, "piers": piers,
    "trees": trees, "boats": boats, "labels": labels,
    "credits": "Dados © contribuidores do OpenStreetMap (ODbL); relevo: Terrain Tiles (Mapzen/AWS, inclui dados SRTM e EU-DEM)",
}
(OUT / "scene.json").write_text(json.dumps(scene, separators=(",", ":")))
print(f"cena: {(OUT / 'scene.json').stat().st_size / 1e6:.1f} MB")
