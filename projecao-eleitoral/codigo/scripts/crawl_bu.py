"""Baixa os boletins de urna (bu.dat) de todas as seções do 2º turno 2026 (pleito 3221)
do site de resultados do TSE. Retomável: guarda tudo em SQLite.
Uso: python3 -I crawl_bu.py <out_dir> [workers] [UFs separadas por vírgula]
"""
import sys, os, json, sqlite3, time, threading, queue
from concurrent.futures import ThreadPoolExecutor
import requests

BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221"
P = "p003221"
UFS = "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to zz".split()

out = sys.argv[1]
workers = int(sys.argv[2]) if len(sys.argv) > 2 else 24
ufs = sys.argv[3].split(",") if len(sys.argv) > 3 else UFS
os.makedirs(os.path.join(out, "config"), exist_ok=True)

db = sqlite3.connect(os.path.join(out, "bu.sqlite"), check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS secao(uf TEXT, mun TEXT, zona TEXT, secao TEXT,
  st_aux TEXT, hash TEXT, st_hash TEXT, dr TEXT, hr TEXT, aux TEXT, bu BLOB, err TEXT,
  PRIMARY KEY(uf,mun,zona,secao))""")
db.commit()
lock = threading.Lock()
tls = threading.local()

def sess():
    if not hasattr(tls, "s"):
        tls.s = requests.Session()
        tls.s.headers["User-Agent"] = "Mozilla/5.0 (pesquisa academica; dados publicos TSE)"
    return tls.s

def get(url, tries=8):
    for k in range(tries):
        try:
            r = sess().get(url, timeout=60)
            if r.status_code == 200: return r.content
            if r.status_code == 404: return None
            if r.status_code == 429:          # limite do servidor: espera progressiva
                time.sleep(min(120, 10 * 2 ** k)); continue
        except Exception: pass
        time.sleep(2 * (k + 1))
    raise RuntimeError(f"falhou {url}")

def job(uf, mun, zona, sec):
    base = f"{BASE}/dados/{uf}/{mun}/{zona}/{sec}"
    try:
        raw = get(f"{base}/{P}-{uf}-m{mun}-z{zona}-s{sec}-aux.json")
        if raw is None:
            row = (uf, mun, zona, sec, None, None, None, None, None, None, None, "aux404")
        else:
            a = json.loads(raw)
            hs = [h for h in a.get("hashes", []) if h.get("st") == "Totalizado"] or a.get("hashes", [])
            h = sorted(hs, key=lambda h: (h["dr"][6:] + h["dr"][3:5] + h["dr"][:2], h["hr"]))[-1] if hs else None
            bu = err = None
            if h:
                nm = next((x["nm"] for x in h["arq"] if x["tp"] == "bu"), None)
                bu = get(f"{base}/{h['hash']}/{nm}") if nm else None
                if bu is None: err = "bu404"
            else:
                err = "semhash"
            row = (uf, mun, zona, sec, a.get("st"), h and h["hash"], h and h["st"], h and h["dr"], h and h["hr"],
                   raw.decode(), bu, err)
    except Exception as e:
        row = (uf, mun, zona, sec, None, None, None, None, None, None, None, str(e)[:200])
    with lock:
        db.execute("INSERT OR REPLACE INTO secao VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", row)

done_keys = set(db.execute("SELECT uf,mun,zona,secao FROM secao WHERE bu IS NOT NULL OR err IN ('aux404','semhash')").fetchall())
t0 = time.time()
for uf in ufs:
    cfg = get(f"{BASE}/config/{uf}/{uf}-{P}-cs.json")
    open(os.path.join(out, "config", f"{uf}.json"), "wb").write(cfg)
    c = json.loads(cfg)
    tasks = []
    with lock:
        for ab in c["abr"]:
            for m in ab["mu"]:
                for z in m["zon"]:
                    for s in z["sec"]:
                        if "nsp" in s:   # seção agregada: votou na seção principal, sem BU próprio
                            db.execute("INSERT OR REPLACE INTO secao(uf,mun,zona,secao,err) VALUES (?,?,?,?,?)",
                                       (uf, m["cd"], z["cd"], s["ns"], "agregada:" + s["nsp"]))
                        else:
                            tasks.append((uf, m["cd"], z["cd"], s["ns"]))
        db.commit()
    todo = [t for t in tasks if t not in done_keys]
    print(f"{uf}: {len(tasks)} seções, {len(todo)} a baixar", flush=True)
    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(lambda t: job(*t), todo), 1):
            if i % 2000 == 0:
                with lock: db.commit()
                print(f"  {uf} {i}/{len(todo)}  {time.time()-t0:.0f}s", flush=True)
    with lock: db.commit()
print("FIM", time.time() - t0, flush=True)
