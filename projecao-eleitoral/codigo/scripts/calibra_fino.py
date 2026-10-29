"""Ajuste fino: ridge adaptativo e transferência por região.\nBusca de hiperparâmetros (só projeção pontual). Carrega a eleição uma vez e varia HP.
Uso: ANO=... python3 -I calibra_hp.py <duckdb> <saida.csv>
Ordens: real (se ORDEM_REAL), 4 aleatórias, 6 realistas, capitais primeiro, NE/S primeiro."""
import os, sys, itertools, numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "modelo.py")).read().split("# ---------- 2. ordens de chegada ----------")[0]
dbp, outp = sys.argv[1], sys.argv[2]
sys.argv = ["modelo.py", dbp, "/tmp/claude-0/hp_tmp"]
exec(src)
rng = np.random.default_rng(11); REGS = ["N", "NE", "CO", "SE", "S"]; noise = lambda: rng.permutation(N) / N
orders = {}
if os.environ.get("ORDEM_REAL"):
    o = pd.read_csv(os.environ["ORDEM_REAL"], parse_dates=["t_real"]); tr = b[K].merge(o, on=K, how="left").t_real
    orders["real"] = tr.fillna(tr.max()).rank(method="first").values
if b.t_rec.notna().any(): orders["proxy"] = b.t_rec.rank(method="first").values
for i in range(4): orders[f"aleatoria_{i}"] = rng.permutation(N) + 1
for i in range(6):
    dr = {r: rng.uniform(0, 60) for r in REGS + ["EXT"]}; du = {u: rng.uniform(0, 30) for u in b.sg_uf.unique()}
    t = b.reg.map(dr) + b.sg_uf.map(du) + b.capital * rng.uniform(-20, 20) + rng.exponential(25, N)
    orders[f"realista_{i}"] = t.rank(method="first").values
orders["capitais_primeiro"] = ((~b.capital) * 1.0 + noise()).rank(method="first").values
orders["NE_primeiro"] = ((b.reg != "NE") * 1.0 + noise()).rank(method="first").values
orders["S_primeiro"] = ((b.reg != "S") * 1.0 + noise()).rank(method="first").values
CK = [0.002, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.50]
grid = None
base = dict(kuf=400, kmu=60, kc=3000, wpow=0.5, ridge=1000, radapt=0, feat="v1")
confs = [dict(base, ridge=0), dict(base), dict(base, radapt=5000), dict(base, radapt=20000), dict(base, ridge=3000, radapt=5000),
         dict(base, feat="reg"), dict(base, feat="reg", radapt=5000), dict(base, feat="reg", ridge=3000, radapt=5000)]
reps = {(n, f): pd.Series(o <= f * N, index=b.index) for n, o in orders.items() for f in CK}
rows = []
for cf in confs:
    HP.update({k: float(v) for k, v in cf.items() if k != "feat"}); FEAT = cf["feat"]
    for (n, f), rep in reps.items():
        r = project(rep, sims=0)
        rows.append(dict(cf, ordem=n, pct=f, erro=100 * (r["modelo"] - TRUE)))
    print(cf, round(pd.DataFrame(rows).query(" & ".join(f"{k}=={v!r}" for k, v in cf.items())).erro.abs().mean(), 4), flush=True)
pd.DataFrame(rows).assign(ano=ANO).to_csv(outp, index=False)
