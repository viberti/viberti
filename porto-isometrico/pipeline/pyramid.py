"""Os tiles do render -> a pirâmide de zoom do visualizador (web/tiles/<z>/<x>_<y>.png) e web/tiles/map.json.

Uso: python3 pipeline/pyramid.py
O nível mais fino (NATIVE) é o render em si; cada nível acima junta 2x2 tiles e reduz para metade.
"""
import json, math, pathlib, shutil
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
TILES = ROOT / "web" / "tiles"
T = 512

info = json.loads((TILES / "grid.json").read_text())
g = info["grid"]
cols, rows = g["c1"] - g["c0"] + 1, g["r1"] - g["r0"] + 1
native = math.ceil(math.log2(max(cols, rows)))
full = Image.new("RGBA", (cols * T, rows * T))
for c, r in info["rendered"]:
    full.paste(Image.open(TILES / "raw" / f"{c}_{r}.png"), ((c - g["c0"]) * T, (r - g["r0"]) * T))

count = 0
for z in range(native, -1, -1):
    d = TILES / str(z)
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    f = 2 ** (native - z)
    level = full if f == 1 else full.resize((math.ceil(full.width / f), math.ceil(full.height / f)), Image.BOX)
    for ty in range(math.ceil(level.height / T)):
        for tx in range(math.ceil(level.width / T)):
            tile = level.crop((tx * T, ty * T, tx * T + T, ty * T + T))
            if tile.getbbox() is None:   # vazio: o visualizador mostra o fundo
                continue
            tile.save(d / f"{tx}_{ty}.png", optimize=True)
            count += 1

# os nomes em pixels do mapa (origem no canto do tile c0, r0)
labels = [{"name": l["name"], "kind": l["kind"], "x": round(l["px"][0] - g["c0"] * T), "y": round(l["px"][1] - g["r0"] * T)}
          for l in info["labels"]]
(TILES / "map.json").write_text(json.dumps({"native": native, "tile": T, "width": full.width, "height": full.height,
                                            "mpp": info["mpp"], "labels": labels, "credits": info["credits"]}, ensure_ascii=False))
size = sum(p.stat().st_size for p in TILES.glob("[0-9]*/*.png"))
print(f"pirâmide: níveis 0..{native}, {count} tiles, {size / 1e6:.1f} MB")
