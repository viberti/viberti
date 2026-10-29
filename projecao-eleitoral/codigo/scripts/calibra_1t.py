"""1º turno: compara variantes (covariáveis municipais, ridge) em pares de eleições, só projeção pontual.
Uso: ANO=<alvo> TURNO_ALVO=1 VIZ=1 COV=1 python3 -I calibra_1t.py <duckdb> <saida.csv>"""
import os, sys, numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "modelo.py")).read().split("# ---------- 2. ordens de chegada ----------")[0]
dbp, outp = sys.argv[1], sys.argv[2]
sys.argv = ["modelo.py", dbp, "/tmp/claude-0/c1t_tmp"]
exec(src)
rng = np.random.default_rng(11); REGS = ["N", "NE", "CO", "SE", "S"]; noise = lambda: rng.permutation(N) / N
orders = {}
for i in range(2): orders[f"aleatoria_{i}"] = rng.permutation(N) + 1
for i in range(4):
    dr = {r: rng.uniform(0, 60) for r in REGS + ["EXT"]}; du = {u: rng.uniform(0, 30) for u in b.sg_uf.unique()}
    t = b.reg.map(dr) + b.sg_uf.map(du) + b.capital * rng.uniform(-20, 20) + rng.exponential(25, N)
    orders[f"realista_{i}"] = t.rank(method="first").values
for r in ("NE", "S", "SE"): orders[f"{r}_primeiro"] = ((b.reg != r) * 1.0 + noise()).rank(method="first").values
orders["capitais_primeiro"] = ((~b.capital) * 1.0 + noise()).rank(method="first").values
CK = [0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.50]
base = dict(kuf=400, kmu=60, kc=3000, wpow=0.5, ridge=1000, radapt=0, feat="v1", cov="")
confs = [dict(base), dict(base, cov="1"), dict(base, cov="1x"), dict(base, ridge=300), dict(base, ridge=300, cov="1"),
         dict(base, ridge=3000, cov="1"), dict(base, feat="reg", cov="1")]
reps = {(n, f): pd.Series(o <= f * N, index=b.index) for n, o in orders.items() for f in CK}
rows = []
for cf in confs:
    HP.update({k: float(v) for k, v in cf.items() if k not in ("feat", "cov")}); FEAT = cf["feat"]; COV = cf["cov"]
    for (n, f), rep in reps.items():
        r = project(rep, sims=0)
        rows.append(dict(cf, ordem=n, pct=f, erro=100 * (r["modelo"] - TRUE), parcial=100 * (r["parcial"] - TRUE)))
    d = pd.DataFrame(rows); d = d[(d.ridge == cf["ridge"]) & (d.feat == cf["feat"]) & (d["cov"] == cf["cov"])]
    print(cf, round(d.erro.abs().mean(), 4), flush=True)
pd.DataFrame(rows).assign(ano=ANO).to_csv(outp, index=False)
