"""Inferência ecológica R×C bayesiana (PyEI, multinomial-Dirichlet, Rosen et al. 2001) em amostras de seções.
Uso: python3 -I transferencia_pyei.py <base_transferencia.parquet> <saida_dir> <regiao|Brasil> <n_secoes> [draws]
"""
import os, sys, time, numpy as np, pandas as pd
from pyei.r_by_c import RowByColumnEI
src, out, area, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
draws = int(sys.argv[5]) if len(sys.argv) > 5 else 400
os.makedirs(out, exist_ok=True)
b = pd.read_parquet(src)
if area != "Brasil": b = b[b.reg == area]
s = b.sample(n, random_state=7, weights=b.aptos2)          # amostra proporcional ao eleitorado
O = ["o_flavio", "o_lula", "o_cury", "o_renan", "o_caiado", "o_zema", "o_outros", "o_branco_nulo", "o_abstencao"]
D = ["d_22", "d_13", "d_branco_nulo", "d_abstencao"]
eps = 1e-4
gf = s[O].values.T + eps; gf = gf / gf.sum(0)
vf = s[D].values.T + eps; vf = vf / vf.sum(0)
pops = s.aptos2.values.astype(int)
t0 = time.time()
ei = RowByColumnEI(model_name="multinomial-dirichlet-modified", pareto_scale=8, pareto_shape=2)
ei.fit(gf, vf, pops, demographic_group_names=[o[2:] for o in O], candidate_names=[d[2:] for d in D],
       draws=draws, tune=draws, chains=2, target_accept=0.9, random_seed=7, progressbar=False)
post = ei.sampled_voting_prefs            # (amostras, R, C)
mean = post.mean(0); lo = np.percentile(post, 5, axis=0); hi = np.percentile(post, 95, axis=0)
rows = [dict(area=area, origem=O[i][2:], destino=D[j][2:], media=mean[i, j], p05=lo[i, j], p95=hi[i, j])
        for i in range(len(O)) for j in range(len(D))]
pd.DataFrame(rows).to_csv(os.path.join(out, f"pyei_{area}.csv"), index=False)
print(area, "seções", n, "tempo", round(time.time() - t0), "s")
print((100 * pd.DataFrame(mean, index=[o[2:] for o in O], columns=[d[2:] for d in D])).round(1).to_string())
