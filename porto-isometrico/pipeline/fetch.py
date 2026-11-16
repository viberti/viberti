"""Baixa os dados abertos da zona da Ribeira: OpenStreetMap (Overpass) e relevo (Terrarium/AWS).

Uso: python3 pipeline/fetch.py
Saída: data/osm.json, data/dem.npy, data/dem.json
"""
import io, json, math, pathlib, sys, time, urllib.parse, urllib.request
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# sul, oeste, norte, leste: da Serra do Pilar e do cais de Gaia até aos Clérigos e São Bento
BBOX = (41.1335, -8.6230, 41.1490, -8.6020)
UA = "isometric-map-prototype/0.1"
ZOOM = 14
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]   # relevo: ~7 m por pixel nesta latitude (a fonte por baixo é mais grossa)


def get(url, data=None, tries=4):
    for n in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as e:   # rede: espera e tenta de novo
            if n == tries - 1:
                raise
            print(f"  {e}; nova tentativa", file=sys.stderr)
            time.sleep(2 ** (n + 1))


def osm():
    s, w, n, e = BBOX
    box = f"{s},{w},{n},{e}"
    q = f"""[out:json][timeout:120];
(
  way["building"]({box}); relation["building"]({box});
  way["building:part"]({box}); relation["building:part"]({box});
  way["highway"]({box});
  way["railway"]({box});
  way["natural"="water"]({box}); relation["natural"="water"]({box});
  way["waterway"]({box});
  way["leisure"~"park|garden|pitch"]({box}); relation["leisure"~"park|garden"]({box});
  way["landuse"~"grass|forest|meadow|cemetery|recreation_ground|village_green"]({box});
  way["natural"~"wood|scrub|grassland|tree_row"]({box});
  way["man_made"~"bridge|pier|tower"]({box});
  way["barrier"~"city_wall|retaining_wall"]({box}); way["historic"="citywalls"]({box});
  node["natural"="tree"]({box});
);
out geom;"""
    body = urllib.parse.urlencode({"data": q}).encode()
    raw = None
    for url in OVERPASS:   # o servidor principal às vezes recusa; o espelho tem os mesmos dados
        try:
            raw = get(url, body, tries=2)
            break
        except Exception as e:
            print(f"  {url}: {e}", file=sys.stderr)
    if raw is None:
        raise SystemExit("nenhum servidor Overpass respondeu")
    d = json.loads(raw)
    (DATA / "osm.json").write_bytes(raw)
    print(f"osm: {len(d['elements'])} elementos, {len(raw) / 1e6:.1f} MB")


def tile_xy(lat, lon, z):
    n = 2 ** z
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def dem():
    s, w, n, e = BBOX
    x0, y0 = (int(v) for v in tile_xy(n, w, ZOOM))
    x1, y1 = (int(v) for v in tile_xy(s, e, ZOOM))
    rows = []
    for y in range(y0, y1 + 1):
        row = []
        for x in range(x0, x1 + 1):
            png = get(f"https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{ZOOM}/{x}/{y}.png")
            a = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.float64)
            row.append(a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768)
        rows.append(np.hstack(row))
    h = np.vstack(rows).astype(np.float32)
    np.save(DATA / "dem.npy", h)
    (DATA / "dem.json").write_text(json.dumps({"zoom": ZOOM, "x0": x0, "y0": y0, "w": h.shape[1], "h": h.shape[0]}))
    print(f"relevo: {h.shape}, {h.min():.0f} a {h.max():.0f} m")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    osm()
    dem()
