"""Compara v1, v2b e uma candidata (pasta com <ano>_<nome>/semaforo_pontos.csv) nas mesmas noites e ordens.
Uso: python3 -I compara_v3.py <pasta> <rótulo>"""
import os, sys, glob, numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
ns = {}; exec(open(os.path.join(here, "semaforo_v2.py")).read().split("if __name__")[0], ns)
pasta, rot = sys.argv[1], sys.argv[2]

def v1_path(n):
    a, o = n.split("_", 1)
    if a == "2018": return {"todas": "modelo/sem_2018/2018_2t", "real2026_2t": "modelo/sem_2018/real_2026_2t", "real2022_2t": "modelo/sem_2018/real_2022_2t"}[o]
    if o == "real2022_2t": return f"modelo/sem_v1/{a}_real2022_2t"
    if o == "real2026_2t": return f"modelo/sem_v1/{a}_real2026_2t"
    return f"modelo/sem_bv/{a}_2t"

def carrega(p, n, ver, ordens):
    f = os.path.join(p, "semaforo_pontos.csv")
    if not os.path.exists(f): return None
    x = pd.read_csv(f)
    if n == "2018_todas" and ver == "v1" and "real" in ordens:   # no v1, a ordem real transplantada de 2022 está noutra pasta
        r = pd.read_csv("modelo/sem_2018/real_2022_2t/semaforo_pontos.csv"); x = pd.concat([x[x.ordem != "real"], r])
    x = x[x.ordem.isin(ordens)].copy(); x["noite"] = n; x["ver"] = ver; x["fonte"] = n
    return x

rows = []
for f in sorted(glob.glob(os.path.join(pasta, "*", "semaforo_pontos.csv"))):
    n = os.path.basename(os.path.dirname(f)); ordens = pd.read_csv(f).ordem.unique()
    for ver, p in (("v1", v1_path(n)), ("v2b", f"modelo/sem_v2b/{n}" if os.path.exists(f"modelo/sem_v2b/{n}") else f"modelo/sem_v2b/{n[:4]}_todas"), (rot, os.path.dirname(f))):
        x = carrega(p, n, ver, ordens)
        if x is not None: rows.append(x)
a = pd.concat(rows, ignore_index=True)
# só pontos presentes nas três versões
k = ["noite", "ordem", "pct_secoes"]
comum = a.groupby(k).ver.nunique(); comum = comum[comum == 3].index
a = a.set_index(k).loc[comum].reset_index()
a["ano"] = a.noite.str[:4]; a["ae"] = (a.modelo - a.verdade).abs(); a["cob"] = (a.lo <= a.verdade) & (a.verdade <= a.hi)
a["tipo"] = np.where(a.ordem != "real", "simulada", np.where(a.ano.isin(["2022", "2026"]), "real", "transplantada"))
m = a[(a.pct_secoes >= 0.005) & (a.pct_secoes <= 0.5)]
pd.set_option("display.width", 200)
print("== erro absoluto médio (0,5% a 50%) por ano"); print(m.pivot_table(index="ano", columns="ver", values="ae").round(3))
print("== idem, só ordens reais e transplantadas"); print(m[m.tipo != "simulada"].pivot_table(index="noite", columns="ver", values="ae").round(3))
fase = pd.cut(a.pct_secoes, [0, 0.005, 0.02, 0.1, 0.3, 1])
print("== cobertura da faixa por fase (%)"); print((100 * a.groupby([fase, "ver"], observed=True).cob.mean().unstack()).round(1))
print("== cobertura por ano (%)"); print((100 * m.pivot_table(index="ano", columns="ver", values="cob")).round(0))
print("== largura mediana por fase"); print(a.groupby([fase, "ver"], observed=True).largura_pp.median().unstack().round(2))
for vm in (0.0, 0.15):
    ns["VERDE_MIN_SECOES"] = vm
    print(f"== semáforo com verde a partir de {vm:.0%}")
    for ver, g in a.groupby("ver"):
        l = ns["luzes"](g.assign(fonte=g.noite)); l["ae"] = (l.modelo - l.verdade).abs()
        v = l[l.luz == "verde"]; an = l[l.luz.isin(["verde", "amarelo"])]
        err = (np.sign(an.modelo - 50) != np.sign(an.verdade - 50)).sum()
        pior = v.nlargest(3, "ae")[["noite", "ordem", "pct_secoes", "erro_pp"]].round(2).values.tolist()
        print(f"  {ver:6} verdes {len(v):4} | >0,5: {(v.ae > 0.5).sum():3} | máx {v.ae.max():.2f} | anúncios {len(an)} errados {err} | piores {pior}")
