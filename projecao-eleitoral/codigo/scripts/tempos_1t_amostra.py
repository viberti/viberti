"""Votos computados após as 17h (Brasília) no 1º turno 2026, numa amostra aleatória de seções,
lendo o log de cada urna no site de resultados (pleito 3220). Compara com o 2º turno nas mesmas seções.
Uso: python3 -I votos_tardios_amostra.py <cfg1t_dir> <tse_2026.duckdb> <saida.csv> [n]
"""
import sys, os, io, json, glob, random, time, zipfile, requests, pandas as pd, duckdb
import concurrent.futures as cf
cfgd, dbp, outp = sys.argv[1], sys.argv[2], sys.argv[3]; n = int(sys.argv[4]) if len(sys.argv) > 4 else 10000
B = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados"
secs = []
for f in glob.glob(os.path.join(cfgd, "*.json")):
    uf = os.path.basename(f)[:2]; d = json.load(open(f))
    for ab in d["abr"]:
        for m in ab["mu"]:
            for z in m["zon"]:
                for s in z["sec"]:
                    if "nsp" not in s and uf != "zz": secs.append((uf, m["cd"], z["cd"], s["ns"]))
random.seed(11); amostra = random.sample(secs, n)
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (pesquisa; dados publicos TSE)"
def get(url):
    for k in range(6):
        try:
            r = S.get(url, timeout=60)
            if r.status_code == 200: return r.content
            if r.status_code == 404: return None
            if r.status_code == 429: time.sleep(min(120, 10 * 2 ** k)); continue
        except Exception: pass
        time.sleep(2 * (k + 1))
    return None
def job(t):
    uf, mu, zo, se = t
    base = f"{B}/{uf}/{mu}/{zo}/{se}"
    raw = get(f"{base}/p003220-{uf}-m{mu}-z{zo}-s{se}-aux.json")
    if not raw: return None
    h = [x for x in json.loads(raw)["hashes"] if x["st"] == "Totalizado"] or json.loads(raw)["hashes"]
    h = h[-1]; nm = next((x["nm"] for x in h["arq"] if x["tp"] == "log"), None)
    if not nm: return None
    lj = get(f"{base}/{h['hash']}/{nm}")
    if not lj: return None
    z = zipfile.ZipFile(io.BytesIO(lj)); name = next(x for x in z.namelist() if x.startswith("logd"))
    ts = []; t_id = t_hab = None; tipo = "?"
    for line in z.read(name).decode("latin1").splitlines():
        p = line.split("\t")
        if len(p) < 5 or not p[0].startswith(("03/10/2026", "04/10/2026", "05/10/2026")): continue
        msg = p[4]; hms = p[0][11:19]
        if msg == "Identificador do eleitor digitado pelo mesário": t_id = hms; tipo = "?"
        elif msg.startswith("Tipo de habilitação do eleitor"): tipo = "b" if "biom" in msg else "o"
        elif msg == "Eleitor foi habilitado": t_hab = hms
        elif msg == "O voto do eleitor foi computado":
            ts.append(f"{t_id or ''},{t_hab or ''},{hms},{tipo}"); t_id = t_hab = None; tipo = "?"
    return dict(sg_uf=uf.upper(), cd_municipio=int(mu), nr_zona=int(zo), nr_secao=int(se), votos=len(ts),
                ts=";".join(ts))
rows = []
with cf.ThreadPoolExecutor(8) as ex:
    for i, r in enumerate(ex.map(job, amostra), 1):
        if r: rows.append(r)
        if i % 1000 == 0: print(i, "seções", flush=True)
d = pd.DataFrame(rows)
d.to_parquet(outp.replace(".csv", "_bruto.parquet"), index=False)   # grava antes de processar
print("bruto gravado", len(d), flush=True)
if os.environ.get("SO_BRUTO"): sys.exit(0)
# fuso por município (mesmo do 2T) e hora de Brasília
con = duckdb.connect(dbp, read_only=True)
fz = con.execute("SELECT sg_uf, cd_municipio, desloc_h FROM fuso_municipio_2t").df()
d = d.merge(fz, on=["sg_uf", "cd_municipio"], how="left").fillna({"desloc_h": 0})
ex = d.assign(t=d.ts.str.split(";")).explode("t")
ex = ex[ex.t.notna() & (ex.t != "")]
ex["t"] = pd.to_datetime(ex.t, format="%d/%m/%Y %H:%M:%S") - pd.to_timedelta(ex.desloc_h, unit="h")
ex.drop(columns="ts").to_parquet(outp.replace(".csv", "_votos.parquet"), index=False)
d.drop(columns="ts").to_csv(outp, index=False)
print("seções lidas", len(d), "votos", int(d.votos.sum()))
