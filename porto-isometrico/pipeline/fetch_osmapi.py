"""Alternativa ao Overpass: a API oficial do OpenStreetMap (/api/0.6/map), em quadros pequenos.

Monta data/osm.json no mesmo formato de `out geom` do Overpass (ways com "geometry"),
para o resto do pipeline não saber de onde veio. Relações multipolígono viram ways
com a geometria do anel externo de cada membro.
"""
import json, pathlib, sys, time, urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch import BBOX, DATA, UA, dem

API = "https://api.openstreetmap.org/api/0.6/map?bbox={w},{s},{e},{n}"
SPLIT = 3   # 3x3 quadros: cada um bem abaixo do limite de 50 000 nós da API


def get(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as ex:
            if k == tries - 1:
                raise
            print(f"  {ex}; nova tentativa", file=sys.stderr)
            time.sleep(3 * (k + 1))


def main():
    s, w, n, e = BBOX
    nodes, ways, rels = {}, {}, {}
    for i in range(SPLIT):
        for j in range(SPLIT):
            qs, qn = s + (n - s) * i / SPLIT, s + (n - s) * (i + 1) / SPLIT
            qw, qe = w + (e - w) * j / SPLIT, w + (e - w) * (j + 1) / SPLIT
            root = ET.fromstring(get(API.format(s=qs, w=qw, n=qn, e=qe)))
            for el in root:
                tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
                if el.tag == "node":
                    nodes[el.get("id")] = (float(el.get("lat")), float(el.get("lon")), tags)
                elif el.tag == "way":
                    ways[el.get("id")] = ([nd.get("ref") for nd in el.findall("nd")], tags)
                elif el.tag == "relation":
                    rels[el.get("id")] = ([(m.get("type"), m.get("ref"), m.get("role")) for m in el.findall("member")], tags)
            print(f"quadro {i},{j}: {len(nodes)} nós, {len(ways)} ways, {len(rels)} relações no total")
            time.sleep(1)   # cortesia com a API

    def geom(refs):
        pts = [nodes[r] for r in refs if r in nodes]
        return [{"lat": p[0], "lon": p[1]} for p in pts]

    out = []
    for wid, (refs, tags) in ways.items():
        if tags:
            out.append({"type": "way", "id": int(wid), "tags": tags, "geometry": geom(refs)})
    for rid, (members, tags) in rels.items():
        if tags.get("type") in ("multipolygon", "building") and tags:
            mem = [{"type": "way", "ref": int(ref), "role": role, "geometry": geom(ways[ref][0])}
                   for typ, ref, role in members if typ == "way" and ref in ways]
            out.append({"type": "relation", "id": int(rid), "tags": tags, "members": mem})
    for nid, (lat, lon, tags) in nodes.items():
        if tags.get("natural") == "tree":
            out.append({"type": "node", "id": int(nid), "lat": lat, "lon": lon, "tags": tags})
    (DATA / "osm.json").write_text(json.dumps({"source": "api.openstreetmap.org", "elements": out}))
    print(f"osm: {len(out)} elementos com etiquetas")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    main()
    dem()
