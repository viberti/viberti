"""Desvio entre UFs da mudança do voto 1T→2T (logit), por eleição — escala do hiperprior de τ_UF.
Uso: ANO=... python3 -I sd_uf_hist.py <duckdb>   → imprime ANO e o desvio (ponderado por votos, sem o exterior)"""
import os, sys, numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "modelo.py")).read().split("# ---------- 2. ordens de chegada ----------")[0]
dbp = sys.argv[1]; sys.argv = ["modelo.py", dbp, "/tmp"]
exec(src)
d = b[b.has1 & (b.sg_uf != "ZZ")]
lg_ = lambda p: np.log(p / (1 - p))
g = d.groupby("sg_uf").agg(v22=("v22", "sum"), val2=("val2", "sum"), a22=("a22", "sum"), a13=("a13", "sum"))
ch = lg_(g.v22 / g.val2) - lg_(g.a22 / (g.a22 + g.a13))
w = g.val2
m = np.average(ch, weights=w)
print("SDUF", ANO, round(float(np.sqrt(np.average((ch - m) ** 2, weights=w))), 4), round(float(ch.std()), 4))
