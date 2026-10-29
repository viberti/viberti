"""Para cada seção já presente em bu2t/bu.sqlite (com hash), baixa:
  - rdv.dat  (guardado inteiro, ~4 KB)
  - log.jez  (processado em memória; guarda só os eventos de voto do dia, descarta o resto)
Grava em bu2t/logrdv.sqlite. Retomável; repete enquanto o crawl do BU ainda estiver a correr.
Uso: python3 -I crawl_log_rdv.py <bu2t_dir> [workers]
Eventos guardados por eleitor (string compacta, zlib):  DDHHMMSS_identificacao,DDHHMMSS_habilitacao,DDHHMMSS_computado,tipo_hab
  tipo_hab: b = biométrica, o = outra/manual, ? = sem registo
"""
import sys, os, io, json, sqlite3, time, zlib, zipfile, threading, re
from concurrent.futures import ThreadPoolExecutor
import requests

BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados"
d = sys.argv[1]; workers = int(sys.argv[2]) if len(sys.argv) > 2 else 24
src = sqlite3.connect(os.path.join(d, "bu.sqlite"), check_same_thread=False, timeout=300)
db = sqlite3.connect(os.path.join(d, "logrdv.sqlite"), check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS sec(uf TEXT, mun TEXT, zona TEXT, secao TEXT, hash TEXT,
  rdv BLOB, ev BLOB, n_comp INT, log_urna TEXT, t_first TEXT, t_last TEXT, err TEXT,
  PRIMARY KEY(uf,mun,zona,secao))""")
db.commit()
lock = threading.Lock(); tls = threading.local()

def sess():
    if not hasattr(tls, "s"):
        tls.s = requests.Session(); tls.s.headers["User-Agent"] = "Mozilla/5.0 (pesquisa; dados publicos TSE)"
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
    raise RuntimeError("falhou " + url)

def parse_log(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    name = next(n for n in z.namelist() if n.startswith("logd"))
    voters, urna, first, last = [], None, None, None
    t_id = t_hab = None; tipo = "?"
    for line in z.read(name).decode("latin1").splitlines():
        p = line.split("\t")
        if len(p) < 5 or not p[0].startswith(("24/10/2026", "25/10/2026", "26/10/2026")):
            continue
        ts, msg = p[0], p[4]
        hms = ts[0:2] + ts[11:13] + ts[14:16] + ts[17:19]          # DDHHMMSS
        if msg == "Identificador do eleitor digitado pelo mesário":
            t_id = hms; tipo = "?"
        elif msg.startswith("Tipo de habilitação do eleitor"):
            tipo = "b" if "biom" in msg else "o"
        elif msg == "Eleitor foi habilitado":
            t_hab = hms; urna = p[2]
        elif msg == "O voto do eleitor foi computado":
            voters.append(f"{t_id or ''},{t_hab or ''},{hms},{tipo}")
            first = first or hms; last = hms; t_id = t_hab = None; tipo = "?"
    return voters, urna, first, last

def job(uf, mun, zona, sec, h, aux):
    base = f"{BASE}/{uf}/{mun}/{zona}/{sec}/{h}"
    arq = {x["tp"]: x["nm"] for hh in json.loads(aux)["hashes"] if hh["hash"] == h for x in hh["arq"]}
    rdv = ev = n = lu = f = l = err = None
    try:
        if "rdv" in arq: rdv = get(f"{base}/{arq['rdv']}")
        if "log" in arq:
            raw = get(f"{base}/{arq['log']}")
            if raw:
                v, lu, f, l = parse_log(raw); n = len(v)
                ev = zlib.compress(";".join(v).encode(), 9)
        if rdv is None: err = "semrdv"
        if ev is None: err = (err + "+" if err else "") + "semlog"
    except Exception as e:
        err = str(e)[:200]
    with lock:
        db.execute("INSERT OR REPLACE INTO sec VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   (uf, mun, zona, sec, h, rdv, ev, n, lu, f, l, err))

def bu_running():
    return os.system("pgrep -f crawl_bu.py > /dev/null") == 0

t0 = time.time(); passes_after = 0
while passes_after < 3:
    done = set(db.execute("SELECT uf,mun,zona,secao FROM sec WHERE err IS NULL").fetchall())
    todo = [r for r in src.execute("SELECT uf,mun,zona,secao,hash,aux FROM secao WHERE hash IS NOT NULL").fetchall()
            if tuple(r[:4]) not in done]
    running = bu_running()
    print(f"{time.strftime('%H:%M:%S')} a fazer {len(todo)} (crawl BU a correr: {running})", flush=True)
    if not todo and not running: break
    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(lambda r: job(*r), todo), 1):
            if i % 2000 == 0:
                with lock: db.commit()
                print(f"  {i}/{len(todo)} {time.time()-t0:.0f}s", flush=True)
    with lock: db.commit()
    if not running: passes_after += 1     # depois do BU acabar: no máx. 3 voltas p/ refazer falhas
    elif not todo: time.sleep(60)
print("FIM", time.time() - t0, flush=True)
