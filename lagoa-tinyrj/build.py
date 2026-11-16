"""Monta a vista da Lagoa Rodrigo de Freitas a partir dos tiles públicos do tinyrj.com.

Uso:  python build.py [--nivel 256|512|1024] [--margem 500] [--qualidade 82] [--saida saida]
Precisa de Python 3.9+ e Pillow (pip install pillow). Baixa ~110 tiles da vista 0 do tinyrj.

Escreve em <saida>/:
  pedacos/<coluna>_<linha>.webp   a imagem em pedaços de 1024 px
  manifest.json                   a grade, a escala, a fórmula lat/lon -> pixel, pontos de controle
                                  e o contorno da água em pixels da imagem composta

As imagens são de terceiros (ver ORIGEM.md): não entram no git, só este script.
"""
import argparse, io, json, math, pathlib, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

AQUI = pathlib.Path(__file__).resolve().parent
BASE = "https://tinyrj.com/2/data/h0/"          # vista 0: o norte a 20,8° à direita do alto; Corcovado para cima
NIVEIS = {256: "thumbs/", 512: "mid/", 1024: ""}   # px por tile do tinyrj -> pasta
UA = {"User-Agent": "Mozilla/5.0"}

# A projeção do tinyrj (turn.js: AXES0 e MU), em unidades de canvas (1 unidade = 1 px no nível 1024):
#   x = (E*RX + N*RY) / MU + TX        y = -(E*UX + N*UY) / MU + TY
# E, N: metros a leste e a norte de (LAT0, LON0). Câmera ortográfica inclinada 45°, virada 15° do norte.
# TX, TY foram ajustados aqui casando o contorno da Lagoa no OpenStreetMap com a água do desenho
# (95% de sobreposição; erro típico de poucos metros). Valem para pontos ao nível da água.
LAT0, LON0 = -22.9670, -43.1790
MU = 0.29296875
RX, RY = 0.965925826, 0.258819045
UX, UY = -0.183012702, 0.683012702
TX, TY = -667.64, -549.76
M_LON = 111320 * math.cos(math.radians(LAT0))
M_LAT = 110574


def canvas(lon, lat):
    e, n = (lon - LON0) * M_LON, (lat - LAT0) * M_LAT
    return (e * RX + n * RY) / MU + TX, -(e * UX + n * UY) / MU + TY


def lonlat(x, y):
    p, q = (x - TX) * MU, -(y - TY) * MU          # p = E*RX + N*RY ; q = E*UX + N*UY
    det = RX * UY - RY * UX
    e, n = (p * UY - RY * q) / det, (RX * q - p * UX) / det
    return LON0 + e / M_LON, LAT0 + n / M_LAT


def baixar(url, tentativas=4):
    for k in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception as e:
            if k == tentativas - 1:
                raise
            time.sleep(2 * (k + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nivel", type=int, default=512, choices=sorted(NIVEIS))
    ap.add_argument("--margem", type=float, default=500, help="metros de terra em volta da água")
    ap.add_argument("--qualidade", type=int, default=82)
    ap.add_argument("--saida", default="saida")
    a = ap.parse_args()
    s = a.nivel / 1024                              # px da imagem final por unidade de canvas
    out = AQUI / a.saida
    (out / "pedacos").mkdir(parents=True, exist_ok=True)
    cache = AQUI / ".cache" / str(a.nivel)
    cache.mkdir(parents=True, exist_ok=True)

    agua = json.loads((AQUI / "agua-osm.json").read_text(encoding="utf-8"))
    aneis = [[canvas(lon, lat) for lon, lat in r] for r in agua["margem"] + agua["ilhas"]]
    xs = [p[0] for r in aneis for p in r]
    ys = [p[1] for r in aneis for p in r]
    # a margem em px: na horizontal 1 m = 1/MU; na vertical o chão encolhe (45°) e os prédios sobem,
    # por isso em cima sobra mais do que em baixo
    mx, my = a.margem / MU, a.margem * 0.7071 / MU
    x0, x1 = min(xs) - mx, max(xs) + mx
    y0, y1 = min(ys) - my - 500, max(ys) + my
    # o recorte alinhado a múltiplos de 4 unidades, para os três níveis caírem em px inteiros
    x0, y0 = math.floor(x0 / 4) * 4, math.floor(y0 / 4) * 4
    x1, y1 = math.ceil(x1 / 4) * 4, math.ceil(y1 / 4) * 4

    man = json.loads(baixar(BASE + "manifest.json"))["tiles"]
    fil = json.loads(baixar(BASE + "filtered.json"))["tiles"]
    # o tile k cobre o canvas [(k-1)*1024, k*1024) em cada eixo
    tx0, tx1 = math.floor(x0 / 1024) + 1, math.floor((x1 - 1) / 1024) + 1
    ty0, ty1 = math.floor(y0 / 1024) + 1, math.floor((y1 - 1) / 1024) + 1
    nomes = [f"{x}_{y}" for y in range(ty0, ty1 + 1) for x in range(tx0, tx1 + 1)]

    def tile(nome):
        f = cache / f"{nome}.webp"
        if not f.exists():
            if nome not in man:
                return nome, None
            v, look = man[nome]["v"], fil.get(nome)
            if look and look[0] == v:   # a cópia com o acabamento final, a que o site mostra
                url = f"{BASE}{NIVEIS[a.nivel]}filtered/{nome}.webp?v={v}-{urllib.parse.quote(look[1])}"
            else:
                url = f"{BASE}{NIVEIS[a.nivel]}tiles/{nome}.webp?v={v}"
            f.write_bytes(baixar(url))
        return nome, f

    W, H = round((x1 - x0) * s), round((y1 - y0) * s)
    img = Image.new("RGB", (W, H), (27, 36, 84))
    falta = []
    with ThreadPoolExecutor(3) as ex:   # poucos de cada vez: o site é de uma pessoa só
        for nome, f in ex.map(tile, nomes):
            if f is None:
                falta.append(nome)
                continue
            tx, ty = map(int, nome.split("_"))
            t = Image.open(f).convert("RGB")
            if t.size != (a.nivel, a.nivel):
                t = t.resize((a.nivel, a.nivel), Image.LANCZOS)
            img.paste(t, (round(((tx - 1) * 1024 - x0) * s), round(((ty - 1) * 1024 - y0) * s)))
    if falta:
        print("tiles que o tinyrj não tem:", falta, file=sys.stderr)

    P = 1024
    cols, rows = math.ceil(W / P), math.ceil(H / P)
    pedacos, total = [], 0
    for r in range(rows):
        for c in range(cols):
            nome = f"{c}_{r}.webp"
            buf = io.BytesIO()
            img.crop((c * P, r * P, min(W, (c + 1) * P), min(H, (r + 1) * P))).save(buf, "WEBP", quality=a.qualidade, method=6)
            (out / "pedacos" / nome).write_bytes(buf.getvalue())
            total += buf.tell()
            pedacos.append({"col": c, "lin": r, "arquivo": f"pedacos/{nome}", "x": c * P, "y": r * P,
                            "w": min(P, W - c * P), "h": min(P, H - r * P)})

    px = lambda lon, lat: [round((canvas(lon, lat)[0] - x0) * s, 1), round((canvas(lon, lat)[1] - y0) * s, 1)]
    k = s / MU                                       # px por metro ao longo do eixo x da imagem
    controle = []
    for nome, (cx, cy) in {"canto superior esquerdo": (0, 0), "canto superior direito": (W, 0),
                           "canto inferior esquerdo": (0, H), "canto inferior direito": (W, H),
                           "centro": (W / 2, H / 2)}.items():
        lon, lat = lonlat(cx / s + x0, cy / s + y0)
        controle.append({"nome": nome, "px": [cx, cy], "lat": round(lat, 6), "lon": round(lon, 6)})
    manifest = {
        "largura": W, "altura": H, "pedaco_px": P, "colunas": cols, "linhas": rows, "pedacos": pedacos,
        "bytes": total,
        "vista": "tinyrj, vista 0: câmera ortográfica a 45°; o norte aponta 20,8° à direita do alto da imagem",
        "escala": {
            "metros_por_px_eixo_x": round(1 / k, 4),
            "metros_de_chao_por_px_eixo_y": round(1 / (k * 0.70710678), 4),
            "nota": "no eixo y o chão aparece encolhido por cos 45°; a altura dos prédios sobe na imagem",
        },
        "projecao": {
            "formula": "E=(lon-lon0)*m_lon; N=(lat-lat0)*m_lat; x=a*E+b*N+tx; y=c*E+d*N+ty (px da imagem composta, pontos ao nível da água)",
            "lat0": LAT0, "lon0": LON0, "m_lon": round(M_LON, 3), "m_lat": M_LAT,
            "a": RX * k, "b": RY * k, "c": -UX * k, "d": -UY * k,
            "tx": (TX - x0) * s, "ty": (TY - y0) * s,
        },
        "pontos_de_controle": controle,
        "agua": {
            "fonte": agua["fonte"], "formato": "[x, y] em px da imagem composta",
            "margem": [[px(lon, lat) for lon, lat in r] for r in agua["margem"]],
            "ilhas": [[px(lon, lat) for lon, lat in r] for r in agua["ilhas"]],
        },
        "origem": "tinyrj.com, de @xthomasms; ver ORIGEM.md",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{W}x{H} px, {cols}x{rows} pedaços, {total / 1e6:.1f} MB, {1 / k:.2f} m/px -> {out}")


if __name__ == "__main__":
    main()
