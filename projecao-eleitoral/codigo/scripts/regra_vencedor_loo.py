"""Regra para anunciar o vencedor (luz amarela), escolhida deixando uma eleição de fora (2º turno).
Anuncia quando: cobertura mínima das dez células >= c, |projeção - 50| >= L, municípios >= m, |viés| <= v.
Treino: nenhum anúncio errado nas eleições de treino; entre as válidas, a que anuncia mais pontos.
Uso: python3 -I regra_vencedor_loo.py modelo/sem2/pontos_todos.csv"""
import sys, itertools, numpy as np, pandas as pd
d = pd.read_csv(sys.argv[1]); d["eleicao"] = d.eleicao.astype(str)
d["ok"] = np.sign(d.modelo - 50) == np.sign(d.verdade - 50); d["margem"] = (d.modelo - 50).abs()
grid = dict(c=[0, 0.0005, 0.001, 0.002, 0.005], L=[0.25, 0.5, 1.0, 1.5, 2.0], m=[0, 200, 500], v=[99, 10, 5])
ap = lambda x, r: (x.cob_min_tipo_regiao >= r["c"]) & (x.margem >= r["L"]) & (x.n_mun >= r["m"]) & (x.abs_vies <= r["v"])
def busca(x):
    best = None
    for vals in itertools.product(*grid.values()):
        r = dict(zip(grid, vals)); g = ap(x, r)
        if (g & ~x.ok).sum() == 0 and (best is None or g.sum() > best[0] or (g.sum() == best[0] and r["c"] + r["L"] / 100 > best[1]["c"] + best[1]["L"] / 100)):
            best = (g.sum(), r)
    return best[1]
def res(x, r):
    g = ap(x, r); first = x[g].groupby("ordem").pct_secoes.min()
    reais = {o: (round(100 * first[o], 1) if o in first else None) for o in ("real", "proxy_repositorio") if o in set(x.ordem)}
    return dict(anuncios=int(g.sum()), errados=int((g & ~x.ok).sum()), noites_com_anuncio=f"{len(first)}/{x.ordem.nunique()}",
                primeiro_mediano=round(100 * first.median(), 1) if len(first) else None, ordem_real=reais)
rows = []
for E in sorted(d.eleicao.unique()):
    r = busca(d[d.eleicao != E]); rows.append(dict(fora=E, regra=r, **res(d[d.eleicao == E], r)))
print(pd.DataFrame(rows).to_string(index=False))
r = busca(d); print("\nregra com todas:", r)
for E, x in d.groupby("eleicao"): print(E, res(x, r))
fixa = dict(c=0.001, L=1.0, m=0, v=99); print("\nregra proposta", fixa)
for E, x in d.groupby("eleicao"): print(E, res(x, fixa))
