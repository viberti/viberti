"""Decodifica os bu.dat baixados (bu2t/bu.sqlite) e grava no DuckDB:
  bu_2t_secao  : 1 linha por seção/eleição (urna, carga, horários, aptos, comparecimento)
  bu_2t_votos  : 1 linha por seção × cargo × votável (nominal, branco, nulo...)
  bu_2t_status : estado do download de cada seção (inclui agregadas e falhas)
Uso: python3 -I decode_bu.py <bu.sqlite> <duckdb>
Estrutura inferida do BER e validada contra 1º turno e correspondência esperada.
"""
import sys, os, sqlite3, duckdb, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
import ber

TIPO_VOTO = {1: "nominal", 2: "branco", 3: "nulo", 4: "legenda", 5: "cargoSemCandidato"}
CARGO = {1: "Presidente", 3: "Governador"}

def i(n): return int.from_bytes(n["val"], "big", signed=False)
def s(n): return n["val"].decode("latin1")
def ts(x):
    try: return dt.datetime.strptime(x, "%Y%m%dT%H%M%S")
    except Exception: return None

def decode(blob):
    env = ber.parse(blob)[0]["kids"]
    inner = next(k for k in env if not k["cons"] and len(k["val"]) > 100)
    b = ber.parse(inner["val"])[0]["kids"]
    urna = b[2]["kids"]
    corr = urna[2]["kids"]                       # correspondência resultado/carga
    id_sec = corr[0]["kids"]                     # [ (mun,zona), local?, secao? ]
    carga = corr[1]["kids"]
    sec = b[3]["kids"]                           # identificação da seção
    sess = b[5]["kids"]
    head = dict(
        tipo_urna=i(urna[0]), versao_sw=s(urna[1]),
        nr_urna=i(carga[0]), cd_carga=s(carga[4]), dt_carga=ts(s(carga[3])),
        cd_flashcard=s(carga[2]["kids"][2]) if carga[2]["cons"] else None,
        nr_local=i(sec[1]), nr_secao_bu=i(sec[2]),
        dt_emissao=ts(s(b[4])), dt_abertura=ts(s(sess[0])), dt_encerramento=ts(s(sess[-1])),
        qt_campo6=i(b[6]) if not b[6]["cons"] else None,
        campo7=",".join(str(i(k)) for k in b[7]["kids"]) if b[7]["cls"] == 2 else None,   # bloco biometria (ausente no exterior)
    )
    res_blk = b[8] if b[7]["cls"] == 2 else b[7]
    secs, votos = [], []
    for el in res_blk["kids"]:
        e = el["kids"]
        id_el, aptos = i(e[0]), i(e[1])
        for rv in e[4]["kids"]:
            r = rv["kids"]
            comp = i(r[1])
            for tvc in r[2]["kids"]:
                t = tvc["kids"]
                cargo = i(t[0])
                secs.append(dict(head, id_eleicao=id_el, cd_cargo=cargo, ds_cargo=CARGO.get(cargo, str(cargo)),
                                 qt_aptos=aptos, qt_comparecimento=comp))
                for vv in t[2]["kids"]:
                    v = vv["kids"]
                    tipo, qt = i(v[0]), i(v[1])
                    nr = i(v[2]["kids"][1]) if v[2]["cons"] else None
                    votos.append(dict(id_eleicao=id_el, cd_cargo=cargo, ds_cargo=CARGO.get(cargo, str(cargo)),
                                      tipo_voto=TIPO_VOTO.get(tipo, str(tipo)), nr_votavel=nr, qt_votos=qt))
    return secs, votos

src, dst = sys.argv[1], sys.argv[2]
sl = sqlite3.connect(src)
S, V, ST = [], [], []
for uf, mun, zona, secao, st, err, blob, dr, hr in sl.execute(
        "SELECT uf,mun,zona,secao,st_aux,err,bu,dr,hr FROM secao"):
    key = dict(sg_uf=uf.upper(), cd_municipio=int(mun), nr_zona=int(zona), nr_secao=int(secao))
    nsp = None
    if err and err.startswith("agregada:"):
        err, nsp = "agregada", int(err.split(":")[1])
    status = err or "ok"
    if blob:
        try:
            ss, vv = decode(blob)
            S += [dict(key, **x) for x in ss]; V += [dict(key, **x) for x in vv]
        except Exception as e:
            status = f"decode:{e}"[:120]
    ST.append(dict(key, st_aux=st, status=status, nr_secao_principal=nsp, dr=dr, hr=hr))

import pandas as pd
con = duckdb.connect(dst)
for name, rows in (("bu_2t_secao", S), ("bu_2t_votos", V), ("bu_2t_status", ST)):
    df = pd.DataFrame(rows)
    con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM df")
    print(name, len(df))
con.close()
