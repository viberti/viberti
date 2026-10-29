"""Calibração da faixa de 90%: cobertura observada para várias escalas do ruído da simulação.
Uso: ANO=... SD_SCALES=0.5,0.6,... python3 -I calibra_faixa.py <duckdb> <saida.csv>"""
import os, sys, numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "modelo.py")).read().split("# ---------- 2. ordens de chegada ----------")[0]
dbp, outp = sys.argv[1], sys.argv[2]
sys.argv = ["modelo.py", dbp, "/tmp/claude-0/faixa_tmp"]
exec(src)
HP.update(dict(ridge=1000.0, radapt=0.0)); FEAT = "v1"
rng0 = np.random.default_rng(11); REGS = ["N", "NE", "CO", "SE", "S"]
orders = {}
if os.environ.get("ORDEM_REAL"):
    o = pd.read_csv(os.environ["ORDEM_REAL"], parse_dates=["t_real"]); tr = b[K].merge(o, on=K, how="left").t_real
    orders["real"] = tr.fillna(tr.max()).rank(method="first").values
if b.t_rec.notna().any(): orders["proxy"] = b.t_rec.rank(method="first").values
for i in range(2): orders[f"aleatoria_{i}"] = rng0.permutation(N) + 1
for i in range(4):
    dr = {r: rng0.uniform(0, 60) for r in REGS + ["EXT"]}; du = {u: rng0.uniform(0, 30) for u in b.sg_uf.unique()}
    t = b.reg.map(dr) + b.sg_uf.map(du) + b.capital * rng0.uniform(-20, 20) + rng0.exponential(25, N)
    orders[f"realista_{i}"] = t.rank(method="first").values
CK = [0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.50]
rows = []
for n, o in orders.items():
    for f in CK:
        rep = pd.Series(o <= f * N, index=b.index)
        r = project(rep, sims=200, rng=np.random.default_rng(7))
        row = dict(ano=ANO, ordem=n, pct=f, modelo=r["modelo"], verdade=TRUE)
        for s in SD_SCALES: row[f"lo_{s}"], row[f"hi_{s}"] = r[f"lo_{s}"], r[f"hi_{s}"]
        rows.append(row)
    print(n, flush=True)
d = pd.DataFrame(rows); d.to_csv(outp, index=False)
for s in SD_SCALES:
    cov = ((d[f"lo_{s}"] <= d.verdade) & (d.verdade <= d[f"hi_{s}"])).mean()
    print("escala", s, "cobertura", round(cov, 3), "largura media pp", round(100 * (d[f"hi_{s}"] - d[f"lo_{s}"]).mean(), 3), flush=True)
