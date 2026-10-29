"""Avaliação da regra de suficiência deixando uma eleição de fora (2º turno).
1) A regra publicada (duas condições) é avaliada por eleição nos pontos refeitos (modelo final, sinais sem vazamento).
2) Para cada eleição E: a busca em grade (regra conjuntiva, como regra_semaforo.py) é feita nas outras quatro e a regra
   escolhida é aplicada a E. Mede-se, em E: pontos marcados, % com erro <= 0,5, erro máximo, primeiro ponto marcado.
3) Comparação com referências simples, por eleição, nos mesmos pontos.
Uso: python3 -I regra_loo.py modelo/sem2
"""
import sys, glob, os, itertools, numpy as np, pandas as pd
base = sys.argv[1]
d = pd.concat([pd.read_csv(f).assign(eleicao=os.path.basename(os.path.dirname(f))[:4])
               for f in sorted(glob.glob(os.path.join(base, "*_2t", "semaforo_pontos.csv")))], ignore_index=True)
d["abs_err"] = d.erro_pp.abs(); d["abs_vies"] = d.vies_hist_pp.abs()
d["cobre"] = (d.lo <= d.verdade) & (d.verdade <= d.hi)
ERRO_MAX = 0.5

def publicada(x):
    c1 = (x.abs_vies <= 2) & (x.largura_pp <= 1.5) & (x.n_mun >= 500)
    c2 = (x.cob_min_tipo_regiao >= 0.001) & (x.abs_vies <= 10) & (x.n_mun >= 200)
    return c1 | c2

grid = dict(cob_min_regiao=[0, 0.005, 0.01, 0.02, 0.05], cob_min_tipo_regiao=[0, 0.001, 0.002, 0.005, 0.01, 0.02],
            abs_vies=[99, 10, 5, 3, 2, 1], largura_pp=[99, 2.0, 1.5, 1.2, 1.0], n_mun=[0, 50, 200, 500, 1000])
def aplica(x, r):
    return (x.cob_min_regiao >= r["cob_min_regiao"]) & (x.cob_min_tipo_regiao >= r["cob_min_tipo_regiao"]) & \
           (x.abs_vies <= r["abs_vies"]) & (x.largura_pp <= r["largura_pp"]) & (x.n_mun >= r["n_mun"])
def busca(x):
    best = None
    for vals in itertools.product(*grid.values()):
        r = dict(zip(grid, vals)); g = aplica(x, r)
        if g.sum() < 20: continue
        e = x.abs_err[g]
        if (e <= ERRO_MAX).mean() >= 0.99 and e.max() <= 2 * ERRO_MAX and (best is None or g.sum() > best[0]):
            best = (g.sum(), r)
    return best[1] if best else None
def resumo(x, g):
    e = x.abs_err[g]
    prim = x[g].groupby("ordem").pct_secoes.min()
    return dict(pontos=int(g.sum()), de=len(x), pct_ok=round(100 * (e <= ERRO_MAX).mean(), 1) if len(e) else np.nan,
                erro_max=round(e.max(), 2) if len(e) else np.nan, cobertura_faixa=round(100 * x.cobre[g].mean(), 1) if len(e) else np.nan,
                primeiro_mediano_pct=round(100 * prim.median(), 2) if len(prim) else np.nan)

print("== 1. Regra publicada, por eleição (pontos refeitos) ==")
rows = [dict(eleicao=E, **resumo(x, publicada(x))) for E, x in d.groupby("eleicao")]
rows.append(dict(eleicao="todas", **resumo(d, publicada(d)))); print(pd.DataFrame(rows).to_string(index=False))

print("\n== 2. Deixando uma eleição de fora ==")
rows = []
for E in sorted(d.eleicao.unique()):
    tr, te = d[d.eleicao != E], d[d.eleicao == E]
    r = busca(tr)
    if r is None: rows.append(dict(fora=E, regra="nenhuma válida")); continue
    rows.append(dict(fora=E, regra=str({k: v for k, v in r.items() if v not in (0, 99)}), **resumo(te, aplica(te, r))))
print(pd.DataFrame(rows).to_string(index=False))

print("\n== 3. Erro absoluto médio por método e eleição (todos os pontos; pontos de 0,5% a 50%) ==")
m = {"Apuração parcial": "erro_parcial_pp", "Reponderação por UF": "erro_uf_pp", "Mudança uniforme nacional": "erro_swing_pp",
     "Mudança uniforme por UF × capital": "erro_swing_ufcap_pp", "Modelo": "erro_pp"}
x = d[(d.pct_secoes >= 0.005) & (d.pct_secoes <= 0.5)]
t = pd.DataFrame({k: x.groupby("eleicao")[v].apply(lambda s: s.abs().mean()) for k, v in m.items()}).T.round(2)
t["todas"] = [x[v].abs().mean().round(2) for v in m.values()]; print(t.to_string())
print("\npior erro por método e eleição:")
t2 = pd.DataFrame({k: x.groupby("eleicao")[v].apply(lambda s: s.abs().max()) for k, v in m.items()}).T.round(1); print(t2.to_string())
print("\ncobertura da faixa de 90% por fase (todos os pontos):")
d["fase"] = pd.cut(d.pct_secoes, [0, 0.005, 0.02, 0.1, 0.3, 1], labels=["≤0,5%", "0,5–2%", "2–10%", "10–30%", ">30%"])
print((100 * d.groupby(["eleicao", "fase"], observed=True).cobre.mean()).unstack().round(0).to_string())
d.to_csv(os.path.join(base, "pontos_todos.csv"), index=False)
