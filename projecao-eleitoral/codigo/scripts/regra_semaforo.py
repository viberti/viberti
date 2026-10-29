"""Procura a regra mais simples para o sinal verde a partir de semaforo_pontos.csv (um ou mais).
Verde = todos os critérios cumpridos. Exigência: entre os pontos verdes, |erro| <= ERRO_MAX em >= 99%
e erro máximo <= 2×ERRO_MAX. Entre as regras válidas, escolhe a que dá verde mais cedo (mais pontos verdes).
Uso: python3 -I regra_semaforo.py <csv> [<csv> ...]
"""
import sys, itertools, numpy as np, pandas as pd
ERRO_MAX = 0.5
d = pd.concat([pd.read_csv(f).assign(teste=f.split("/")[-2]) for f in sys.argv[1:]], ignore_index=True)
d["abs_err"] = d.erro_pp.abs(); d["abs_vies"] = d.vies_hist_pp.abs()
grid = dict(cob_min_regiao=[0, 0.005, 0.01, 0.02, 0.05],
            cob_min_tipo_regiao=[0, 0.002, 0.005, 0.01, 0.02],
            abs_vies=[99, 10, 5, 3, 2, 1],
            largura_pp=[99, 2.0, 1.5, 1.2, 1.0],
            n_mun=[0, 50, 200, 500, 1000])
best = None
for vals in itertools.product(*grid.values()):
    r = dict(zip(grid, vals))
    g = (d.cob_min_regiao >= r["cob_min_regiao"]) & (d.cob_min_tipo_regiao >= r["cob_min_tipo_regiao"]) & \
        (d.abs_vies <= r["abs_vies"]) & (d.largura_pp <= r["largura_pp"]) & (d.n_mun >= r["n_mun"])
    if g.sum() < 20: continue
    e = d.abs_err[g]
    if (e <= ERRO_MAX).mean() >= 0.99 and e.max() <= 2 * ERRO_MAX:
        score = g.sum()
        if best is None or score > best[0]:
            best = (score, r, g.copy())
if best is None:
    print("nenhuma regra cumpre a exigência"); sys.exit()
score, r, g = best
print("REGRA VERDE:", r)
print(f"pontos verdes {g.sum()} de {len(d)} | erro máx verde {d.abs_err[g].max():.2f} pp | "
      f"erro máx fora do verde {d.abs_err[~g].max():.2f} pp")
d["verde"] = g
first = d[d.verde].groupby(["teste", "ordem"]).pct_secoes.min()
print("\nprimeiro ponto verde por noite simulada (% de seções):")
print(first.unstack(0).round(3).to_string())
print("\nerro por estado do sinal:")
print(d.groupby("verde").abs_err.describe(percentiles=[.5, .9, .99]).round(3).to_string())
d.to_csv("/tmp/claude-0/semaforo_classificado.csv", index=False)
