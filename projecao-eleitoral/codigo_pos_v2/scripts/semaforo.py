"""Calibra o "semáforo" de confiabilidade do modelo.
Gera muitas ordens de apuração (real, aleatórias, enviesadas, atrasos por região/tipo), e em cada ponto
registra indicadores de representatividade/estabilidade + erro do modelo. Saída: semaforo_pontos.csv
Uso: ANO=... [TURNO_ALVO=1] [ORDEM_REAL=...] [variantes do modelo] python3 -I semaforo.py <duckdb> <saida_dir>
"""
import os, sys, numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "modelo.py")).read().split("# ---------- 2. ordens de chegada ----------")[0]
dbp, out = sys.argv[1], sys.argv[2]
sys.argv = ["modelo.py", dbp, out]
exec(src)   # define b, project(), TRUE, N, K, UF2REG ...

rng = np.random.default_rng(7)
REGS = ["N", "NE", "CO", "SE", "S"]
pr1 = np.where(b.has1, b.a22 / (b.a22 + b.a13).replace(0, np.nan), np.nan)
b["p1"] = pd.Series(pr1).fillna(np.nanmean(pr1)).values
# pesos conhecidos antes da eleição (sem vazamento): votos dos dois campos no turno de referência; cobertura pelo eleitorado apto
b["hw"] = np.where(b.has1, (b.a22 + b.a13).fillna(0), 0.0)
HIST_ALL = np.average(b.p1, weights=b.hw)
noise = lambda: rng.permutation(N) / N

orders = {}
if os.environ.get("ORDEM_REAL"):
    o = pd.read_csv(os.environ["ORDEM_REAL"], parse_dates=["t_real"])
    tr = b[K].merge(o, on=K, how="left").t_real
    orders["real"] = tr.fillna(tr.max()).rank(method="first").values
if b.t_rec.notna().any():
    orders["proxy_repositorio"] = b.t_rec.rank(method="first").values
for i in range(6):
    orders[f"aleatoria_{i}"] = rng.permutation(N) + 1
for r in REGS:
    orders[f"{r}_primeiro"] = ((b.reg != r) * 1.0 + noise()).rank(method="first").values
    orders[f"{r}_ultimo"] = ((b.reg == r) * 1.0 + noise()).rank(method="first").values
orders["capitais_primeiro"] = ((~b.capital) * 1.0 + noise()).rank(method="first").values
orders["interior_primeiro"] = ((b.capital) * 1.0 + noise()).rank(method="first").values
orders["pro22_primeiro"] = (-b.p1 + 0.15 * rng.standard_normal(N)).rank(method="first").values
orders["pro13_primeiro"] = (b.p1 + 0.15 * rng.standard_normal(N)).rank(method="first").values
# noites "realistas": atraso aleatório por região, por UF e por capital/interior + ruído de seção
for i in range(10):
    dr = {r: rng.uniform(0, 60) for r in REGS + ["EXT"]}
    du = {u: rng.uniform(0, 30) for u in b.sg_uf.unique()}
    dc = rng.uniform(-20, 20)
    t = b.reg.map(dr) + b.sg_uf.map(du) + b.capital * dc + rng.exponential(25, N)
    orders[f"realista_{i}"] = t.rank(method="first").values
    if i < 4: TREAL = globals().setdefault("TREAL", {}); TREAL[i] = t.values

# ordens adversariais (ADV=1): mesmo calendário de município das realistas, mas dentro de cada município
# as seções chegam na ordem da mudança verdadeira do voto (informação que nenhuma ordem real teria; teste de pior caso)
if os.environ.get("ADV"):
    d = pd.Series(np.where(b.has1, b.y - b.x1, np.nan)).fillna(0).values
    vol = np.log((b.val2 / b.comp1.where(b.comp1 > 0)).fillna(1).clip(0.05, 20)).values
    def within_mun(t, key):
        # tempos do município ordenados, atribuídos às seções do município ordenadas pela chave
        df = pd.DataFrame({"m": b.mun.values, "t": t, "k": key, "i": np.arange(N)})
        ts = df.sort_values(["m", "t"]).t.values
        idx = df.sort_values(["m", "k"]).i.values
        tt = np.empty(N); tt[idx] = ts
        return pd.Series(tt).rank(method="first").values
    zs = lambda x: (x - x.mean()) / (x.std() + 1e-12)
    for i, t in TREAL.items():
        orders[f"adv_dir_{i}"] = within_mun(t, -d)                     # seções que mais foram à direita primeiro
        orders[f"adv_esq_{i}"] = within_mun(t, d)                      # que mais foram à esquerda primeiro
        orders[f"adv_meio_{i}"] = within_mun(t, -zs(d) + rng.standard_normal(N))   # correlação parcial (~0,7)
        orders[f"adv_vol_{i}"] = within_mun(t, -vol)                   # maior comparecimento relativo primeiro

if os.environ.get("ORDENS"): orders = {k: v for k, v in orders.items() if k in os.environ["ORDENS"].split(",")}
CK = [0.001, 0.002, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30, 0.50]
rows = []
reg_tot = b.groupby("reg").aptos2.sum()
# alarme de ordem dentro do município: só com seções apuradas (mudança observada = y − x1, chegada = posição na ordem)
D_OBS = pd.Series(np.where(b.has1, b.y - b.x1, np.nan))
def corr_intra(o, rep, kmin=5):
    x = pd.DataFrame({"m": b.mun.values[rep.values], "t": o[rep.values], "d": D_OBS.values[rep.values]}).dropna()
    n = x.groupby("m").d.transform("size"); x = x[n >= kmin]
    if len(x) < 200: return np.nan, 0
    x["rt"] = x.groupby("m").t.rank(pct=True); x["rt"] -= x.groupby("m").rt.transform("mean")
    x["dd"] = x.d - x.groupby("m").d.transform("mean")
    c = np.corrcoef(x.rt, x.dd)[0, 1]
    return c, len(x)
for name, o in orders.items():
    prev = None
    for f in CK:
        rep = pd.Series(o <= f * N, index=b.index)
        R = b[rep]
        r = project(rep)
        cov_reg = (R.groupby("reg").aptos2.sum() / reg_tot).reindex(REGS).fillna(0)
        capcov = []
        for rg in REGS:
            g = b[b.reg == rg]; gr = R[R.reg == rg]
            for c in (True, False):
                tot = g[g.capital == c].aptos2.sum(); got = gr[gr.capital == c].aptos2.sum()
                capcov.append(got / tot if tot else 1)
        ci, ni = corr_intra(o, rep)
        rows.append(dict(
            ordem=name, pct_secoes=f, corr_intra=ci, n_intra=ni, n_secoes=int(rep.sum()), n_mun=R.mun.nunique(), n_uf=R.sg_uf.nunique(),
            cob_min_regiao=cov_reg.min(), cob_min_tipo_regiao=min(capcov),
            vies_hist_pp=100 * (np.average(R.p1, weights=R.hw) - HIST_ALL) if R.hw.sum() > 0 else 99.0,
            largura_pp=100 * (r["hi"] - r["lo"]),
            mudanca_pp=None if prev is None else 100 * abs(r["modelo"] - prev),
            modelo=100 * r["modelo"], lo=100 * r["lo"], hi=100 * r["hi"], verdade=100 * TRUE,
            erro_pp=100 * (r["modelo"] - TRUE),
            **{f"erro_{k}_pp": 100 * (r[k] - TRUE) for k in ("parcial", "uf", "swing", "swing_ufcap")}))
        prev = r["modelo"]
    print(name, "ok", flush=True)
pd.DataFrame(rows).to_csv(os.path.join(out, "semaforo_pontos.csv"), index=False)
print("FIM")
