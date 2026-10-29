"""Replay da apuração de 2022 (Knesset 25) usando 2021 (Knesset 24) como histórico, com várias ordens de chegada."""
import sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "/home/claude/israel")
from modelo_il import *

ref, rp = load_kalpi("/home/claude/israel/k24_expb_utf8.csv")
cur, cp = load_kalpi("/home/claude/israel/k25_expb.csv")
MAP_REF = {"מחל": {"מחל": 1}, "פה": {"פה": 1}, "ט": {"ט": 1, "ב": 0.5}, "כן": {"כן": 1, "ת": 1}, "שס": {"שס": 1},
           "ג": {"ג": 1}, "ל": {"ל": 1}, "עם": {"עם": 1}, "ום": {"ודעם": 1}, "ד": {"ודעם": 1}, "אמת": {"אמת": 1},
           "מרצ": {"מרצ": 1}, "ב": {"ב": 1}}
MAP_CUR = {t: {t: 1} for t in MAP_REF}
AG = [("מחל", "ט"), ("פה", "ל"), ("שס", "ג"), ("אמת", "מרצ")]
COAL = ["מחל", "ט", "שס", "ג"]
truth_v = group(cur, MAP_CUR, cp).sum()
truth_s = seats(truth_v.to_dict(), agreements=AG)
print("verdade 2022:", {k: v for k, v in truth_s.items() if v}, "coalizão", sum(truth_s[x] for x in COAL))
import os, ast
TAU = ast.literal_eval(os.environ.get("TAU", "(0.04, 0.06, 0.10)")); TG = float(os.environ.get("TG", "0.015"))
P = Projetor(ref, rp, MAP_REF, growth=1.032, tau=TAU, tau_g=TG)
k = cur[cur.city_id != ENV].reset_index(drop=True)
rng = np.random.default_rng(1)
size = k.groupby("city_id").valid.transform("sum")
arab = k.city_id.map(P.sec_city).fillna("geral").eq("arabe")
ordens = {
    "aleatoria": rng.permutation(len(k)),
    "pequenas_primeiro": np.argsort(np.log(size) + rng.normal(0, 1.0, len(k))),
    "arabes_por_ultimo": np.argsort(arab * 5 + np.log(size) / 3 + rng.normal(0, 1.0, len(k))),
    "grandes_primeiro": np.argsort(-np.log(size) + rng.normal(0, 1.0, len(k))),
}
ENVV = 450000
CK = [0.01, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 0.90]
rows = []
for nome, o in ordens.items():
    for f in CK:
        sub = k.iloc[o[: int(f * len(k))]]
        out, info = P.project(sub, MAP_CUR, cp, sims=150, agreements=AG, coalition=COAL, envelopes=ENVV)
        tv = 100 * truth_v / truth_v.sum()
        err = (out.pct_proj - tv.reindex(out.index)).abs()
        # parcial: o que a TV mostraria (só contado)
        pv = group(sub, MAP_CUR, cp).sum(); pv = 100 * pv / pv.sum()
        cad_err = sum(abs(out.cad_ponto.get(x, 0) - truth_s.get(x, 0)) for x in out.index) / 2
        cov = ((tv.reindex(out.index) >= out.pct_lo) & (tv.reindex(out.index) <= out.pct_hi)).mean()
        rows.append(dict(ordem=nome, pct_urnas=f, pct_votos=round(info["pct_votos"], 3), mae_pp=round(err.mean(), 3),
                         max_pp=round(err.max(), 2), mae_parcial=round((pv.reindex(out.index) - tv.reindex(out.index)).abs().mean(), 3),
                         cad_trocadas=cad_err, coal_ponto=info["coal_ponto"], coal_int=f'{info["coal_lo"]:.0f}-{info["coal_hi"]:.0f}',
                         p61=round(info["p61"], 2), cobertura=round(cov, 2),
                         meretz=round(out.pct_proj["מרצ"], 2), balad=round(out.pct_proj["ד"], 2)))
        print(rows[-1], flush=True)
R = pd.DataFrame(rows); R.to_csv(os.environ.get("OUT", "/home/claude/israel/valida_2022.csv"), index=False)
print("RESUMO", TAU, TG, "mae", R.mae_pp.mean().round(3), "cobertura", R.cobertura.mean().round(2))
