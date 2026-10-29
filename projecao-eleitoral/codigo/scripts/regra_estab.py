"""Teste do sinal de estabilidade (mudança da projeção desde o corte anterior) na regra de suficiência, deixando uma eleição de fora."""
import itertools, numpy as np, pandas as pd, sys
d = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else "modelo/sem2/pontos_todos.csv")
d["ae"] = d.erro_pp.abs(); d["av"] = d.vies_hist_pp.abs(); d["mu"] = d.mudanca_pp.fillna(99)
G = dict(cob=[0, 0.001, 0.002, 0.005, 0.01, 0.02], vies=[99, 10, 5, 3], mu=[99, 0.5, 0.3, 0.2, 0.1, 0.05], nmun=[0, 200, 500])
ap = lambda x, r: (x.cob_min_tipo_regiao >= r["cob"]) & (x.av <= r["vies"]) & (x.mu <= r["mu"]) & (x.n_mun >= r["nmun"])
def busca(x, fix=None):
    best = None
    for vals in itertools.product(*G.values()):
        r = dict(zip(G, vals))
        if fix and any(r[k] != v for k, v in fix.items()): continue
        g = ap(x, r)
        if g.sum() < 20: continue
        e = x.ae[g]
        if (e <= 0.5).mean() >= 0.99 and e.max() <= 1 and (best is None or g.sum() > best[0]): best = (g.sum(), r)
    return best[1] if best else None
def res(x, g):
    e = x.ae[g]; first = x[g].groupby("ordem").pct_secoes.min()
    return dict(pontos=int(g.sum()), ok=round(100 * (e <= 0.5).mean(), 1) if len(e) else None, emax=round(e.max(), 2) if len(e) else None,
                primeiro_med=round(100 * first.median(), 1) if len(first) else None, ordens_sem_ponto=int(x.ordem.nunique() - len(first)))
adot = dict(cob=0.01, vies=10, mu=99, nmun=0)
rows = []
for E in sorted(d.eleicao.unique()):
    tr, te = d[d.eleicao != E], d[d.eleicao == E]
    r = busca(tr); rows.append(dict(fora=E, tipo="busca com estabilidade", regra=str({k: v for k, v in r.items() if v not in (0, 99)}) if r else None, **(res(te, ap(te, r)) if r else {})))
    r2 = busca(tr, fix=dict(mu=99)); rows.append(dict(fora=E, tipo="busca sem estabilidade", regra=str({k: v for k, v in r2.items() if v not in (0, 99)}) if r2 else None, **(res(te, ap(te, r2)) if r2 else {})))
print(pd.DataFrame(rows).to_string(index=False))
print("\nregra adotada (todas):", res(d, ap(d, adot)))
for m in (0.3, 0.2, 0.1):
    r = dict(adot, mu=m); print(f"adotada + mudança ≤ {m}:", res(d, ap(d, r)))
    r = dict(cob=0.005, vies=10, mu=m, nmun=0); print(f"  cobertura 0,5% + mudança ≤ {m}:", res(d, ap(d, r)))
print("\npor eleição, adotada + mudança ≤ 0,2:")
for E, x in d.groupby("eleicao"): print(E, res(x, ap(x, dict(adot, mu=0.2))), "| adotada:", res(x, ap(x, adot)))
