"""1º turno, variante escolhida (covariáveis municipais com interação): cobertura da faixa de 90% para várias escalas
de ruído e parcela apurada por região em cada ponto (para a regra do semáforo).
Uso: ANO=... TURNO_ALVO=1 VIZ=1 COV=1x SD_SCALES=... python3 -I calibra_1t_faixa.py <duckdb> <saida.csv>"""
import os, sys, numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "modelo.py")).read().split("# ---------- 2. ordens de chegada ----------")[0]
dbp, outp = sys.argv[1], sys.argv[2]
sys.argv = ["modelo.py", dbp, "/tmp/claude-0/c1tf_tmp"]
exec(src)
HP.update(dict(ridge=1000.0, radapt=0.0)); FEAT = "v1"
rng0 = np.random.default_rng(11); REGS = ["N", "NE", "CO", "SE", "S"]; noise = lambda: rng0.permutation(N) / N
orders = {}
for i in range(2): orders[f"aleatoria_{i}"] = rng0.permutation(N) + 1
for i in range(6):
    dr = {r: rng0.uniform(0, 60) for r in REGS + ["EXT"]}; du = {u: rng0.uniform(0, 30) for u in b.sg_uf.unique()}
    t = b.reg.map(dr) + b.sg_uf.map(du) + b.capital * rng0.uniform(-20, 20) + rng0.exponential(25, N)
    orders[f"realista_{i}"] = t.rank(method="first").values
for r in ("NE", "S", "SE"): orders[f"{r}_primeiro"] = ((b.reg != r) * 1.0 + noise()).rank(method="first").values
orders["capitais_primeiro"] = ((~b.capital) * 1.0 + noise()).rank(method="first").values
if os.environ.get("ORDEM_REAL"):
    _o = pd.read_csv(os.environ["ORDEM_REAL"]); _o["t_real"] = pd.to_datetime(_o.t_real, format="mixed")
    _tr = b[K].merge(_o, on=K, how="left").t_real
    orders = {"real": _tr.fillna(_tr.max()).rank(method="first").values, **orders}
if os.environ.get("ORDENS"): orders = {k: v for k, v in orders.items() if k in os.environ["ORDENS"].split(",")}
CK = [float(x) for x in os.environ.get("CKS", "0.005,0.01,0.02,0.05,0.10,0.20,0.50").split(",")]
vreg = b.groupby("reg").aptos2.sum()                      # denominadores conhecidos antes da eleição
b["hw"] = np.where(b.has1, (b.a22 + b.a13).fillna(0), 0.0)   # peso histórico (turno de referência)
pr1 = np.where(b.hw > 0, b.a22.fillna(0) / b.hw.replace(0, np.nan), np.nan); b["p1"] = pd.Series(pr1).fillna(np.nanmean(pr1)).values
HIST_ALL = np.average(b.p1, weights=b.hw)
rows = []
for n, o in orders.items():
    for f in CK:
        rep = pd.Series(o <= f * N, index=b.index)
        r = project(rep, sims=200, rng=np.random.default_rng(7))
        cov_reg = (b[rep].groupby("reg").aptos2.sum() / vreg).reindex(REGS).fillna(0)
        cc = b[rep].groupby(["reg", "capital"]).aptos2.sum() / b.groupby(["reg", "capital"]).aptos2.sum()
        row = dict(ano=ANO, ordem=n, pct=f, modelo=r["modelo"], verdade=TRUE, parcial=r["parcial"],
                   min_reg=float(cov_reg.min()), vies_hist_pp=float(100 * (np.average(b[rep].p1, weights=b[rep].hw) - HIST_ALL)) if b[rep].hw.sum() > 0 else 99.0, min_regcap=float(cc.reindex(pd.MultiIndex.from_product([REGS, [True, False]])).fillna(0).min()))
        for s in SD_SCALES: row[f"lo_{s}"], row[f"hi_{s}"] = r[f"lo_{s}"], r[f"hi_{s}"]
        rows.append(row)
    print(n, flush=True)
pd.DataFrame(rows).to_csv(outp, index=False); print("OK")
