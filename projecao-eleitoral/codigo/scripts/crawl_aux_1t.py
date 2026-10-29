"""Hora de recebimento de cada seção no 1º turno 2026 (pleito 3220), lida do arquivo auxiliar do site de resultados.
Usa a lista de seções do 2º turno (bu2t/bu.sqlite). Retomável. Uso: python3 -I crawl_aux_1t.py <saida.sqlite> [workers]"""
import sys, json, sqlite3, time, threading, requests
from concurrent.futures import ThreadPoolExecutor
out = sys.argv[1]; W = int(sys.argv[2]) if len(sys.argv) > 2 else 16
B = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados"
src = sqlite3.connect("/home/claude/tse/bu2t/bu.sqlite").execute("SELECT uf,mun,zona,secao FROM secao").fetchall()
db = sqlite3.connect(out, check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS aux(uf,mun,zona,secao,st,dr,hr,n_hash,err, PRIMARY KEY(uf,mun,zona,secao))"); db.commit()
feito = set(db.execute("SELECT uf,mun,zona,secao FROM aux WHERE err IS NULL OR err='404'").fetchall())
todo = [t for t in src if t not in feito]; print(len(src), "seções;", len(todo), "a baixar", flush=True)
lock = threading.Lock(); tls = threading.local(); n = [0]; t0 = time.time()
def sess():
    if not hasattr(tls, "s"): tls.s = requests.Session(); tls.s.headers["User-Agent"] = "Mozilla/5.0 (pesquisa academica; dados publicos TSE)"
    return tls.s
def job(t):
    uf, mun, zona, sec = t; url = f"{B}/{uf}/{mun}/{zona}/{sec}/p003220-{uf}-m{mun}-z{zona}-s{sec}-aux.json"; row = None
    for k in range(10):
        try:
            r = sess().get(url, timeout=60)
            if r.status_code == 200:
                a = r.json(); hs = [h for h in a.get("hashes", []) if h.get("st") == "Totalizado"] or a.get("hashes", [])
                h = sorted(hs, key=lambda h: (h["dr"][6:] + h["dr"][3:5] + h["dr"][:2], h["hr"]))[0] if hs else None
                row = (uf, mun, zona, sec, a.get("st"), h and h["dr"], h and h["hr"], len(a.get("hashes", [])), None); break
            if r.status_code == 404: row = (uf, mun, zona, sec, None, None, None, 0, "404"); break
            if r.status_code == 429: time.sleep(min(120, 5 * 2 ** k)); continue
        except Exception: pass
        time.sleep(2 * (k + 1))
    if row is None: row = (uf, mun, zona, sec, None, None, None, 0, "falhou")
    with lock:
        db.execute("INSERT OR REPLACE INTO aux VALUES (?,?,?,?,?,?,?,?,?)", row); n[0] += 1
        if n[0] % 20000 == 0: db.commit(); print(f"{n[0]}/{len(todo)} {time.time()-t0:.0f}s", flush=True)
with ThreadPoolExecutor(W) as ex: list(ex.map(job, todo))
db.commit(); print("AUX1T_OK", flush=True)
