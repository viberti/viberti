"""Replay de um 2º turno de governador (uma UF): o mesmo modelo do presidencial, comparado com a mudança uniforme
por capital/interior e com a apuração parcial, em ordens de chegada reais (2022, 2026) e simuladas.
Uso: ANO=... GOV_UF=.. [variáveis do modelo] python3 -I gov_replay.py <db_gov> <saida_csv>"""
import os, sys, numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "modelo.py")).read().split("# ---------- 2. ordens de chegada ----------")[0]
dbp, saida = sys.argv[1], sys.argv[2]
sys.argv = ["modelo.py", dbp, os.path.dirname(os.path.abspath(saida))]
exec(src)

rng = np.random.default_rng(7)
orders = {}
real = {2022: "/home/claude/tse/hist/ordem_real_2022_2t.csv", 2026: "/home/claude/tse/hist/ordem_real_2026_2t.csv"}.get(ANO)
if real:
    o = pd.read_csv(real, parse_dates=["t_real"])
    tr = b[K].merge(o, on=K, how="left").t_real
    if tr.notna().mean() > 0.9: orders["real"] = tr.fillna(tr.max()).rank(method="first").values
    print("ordem real casada:", f"{tr.notna().mean():.1%}", flush=True)
for i in range(4):
    orders[f"aleatoria_{i}"] = rng.permutation(N) + 1
zonas = b.nr_zona.unique()
for i in range(6):   # noites realistas dentro da UF: atraso por zona, efeito capital, tempo de cada seção
    dz = dict(zip(zonas, rng.uniform(0, 30, len(zonas)))); dc = rng.uniform(-20, 20)
    t = b.nr_zona.map(dz) + b.capital * dc + rng.exponential(25, N)
    orders[f"realista_{i}"] = t.rank(method="first").values
noise = lambda: rng.permutation(N) / N
orders["capital_primeiro"] = ((~b.capital) * 1.0 + noise()).rank(method="first").values
orders["interior_primeiro"] = ((b.capital) * 1.0 + noise()).rank(method="first").values
CK = [0.005, 0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50]
rows = []
for name, o in orders.items():
    for f in CK:
        rep = pd.Series(o <= f * N, index=b.index)
        if rep.sum() < 20: continue
        r = project(rep)
        rows.append(dict(ano=ANO, uf=GOV_UF, ordem=name, pct_secoes=f, n_secoes=int(rep.sum()), n_mun=b[rep].mun.nunique(),
                         verdade=100 * TRUE, **{k: 100 * v for k, v in r.items() if k in ("modelo", "lo", "hi", "parcial", "swing", "swing_ufcap")}))
pd.DataFrame(rows).to_csv(saida, index=False)
print("FIM", ANO, GOV_UF, len(rows), flush=True)
