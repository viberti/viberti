"""Intervalos por bootstrap para a comparação do 2º turno presidencial (modelo × métodos simples).
Unidade reamostrada: a ordem de chegada dentro de cada eleição (os cortes de uma mesma ordem andam juntos);
no conjunto, bootstrap em dois estágios: eleições, depois ordens dentro de cada eleição sorteada.
Uso: python3 -I bootstrap_pres.py"""
import glob, numpy as np, pandas as pd
rng = np.random.default_rng(2026)
B = 4000
F = {"2006": "modelo/sem_bv/2006_2t", "2010": "modelo/sem_bv/2010_2t", "2014": "modelo/sem_bv/2014_2t",
     "2018": "modelo/sem_2018/2018_2t", "2022": "modelo/sem_bv/2022_2t", "2026": "modelo/sem_bv/2026_2t"}
MET = {"parcial": "erro_parcial_pp", "uf": "erro_uf_pp", "nacional": "erro_swing_pp", "ufcap": "erro_swing_ufcap_pp", "modelo": "erro_pp"}
por = {}
for a, p in F.items():
    d = pd.read_csv(f"{p}/semaforo_pontos.csv"); d = d[(d.pct_secoes >= 0.005) & (d.pct_secoes <= 0.5)]
    # erro absoluto médio por ordem (cada ordem tem os mesmos 10 cortes)
    por[a] = d.assign(**{k: d[v].abs() for k, v in MET.items()}).groupby("ordem")[list(MET)].mean()
def ci(x): return np.percentile(x, [2.5, 97.5])
rows = []
for a, g in por.items():
    n = len(g); idx = rng.integers(0, n, (B, n))
    bs = {k: g[k].values[idx].mean(1) for k in MET}
    dif = bs["ufcap"] - bs["modelo"]; rat = bs["modelo"] / bs["ufcap"]
    row = dict(eleicao=a, ordens=n)
    for k in MET:
        lo, hi = ci(bs[k]); row[k] = f"{g[k].mean():.2f} ({lo:.2f}–{hi:.2f})"
    lo, hi = ci(dif); row["ufcap−modelo"] = f"{(g.ufcap - g.modelo).mean():.2f} ({lo:.2f}–{hi:.2f})"
    lo, hi = ci(rat); row["modelo÷ufcap"] = f"{g.modelo.mean() / g.ufcap.mean():.2f} ({lo:.2f}–{hi:.2f})"
    rows.append(row)
# dois estágios: média entre eleições
el = list(por); stats = {k: [] for k in ("modelo", "ufcap", "dif", "rat")}
for _ in range(B):
    es = rng.choice(el, len(el), replace=True); m = []; u = []
    for a in es:
        g = por[a]; i = rng.integers(0, len(g), len(g)); m.append(g.modelo.values[i].mean()); u.append(g.ufcap.values[i].mean())
    m, u = np.mean(m), np.mean(u); stats["modelo"].append(m); stats["ufcap"].append(u); stats["dif"].append(u - m); stats["rat"].append(m / u)
pm = np.mean([por[a].modelo.mean() for a in el]); pu = np.mean([por[a].ufcap.mean() for a in el])
rows.append(dict(eleicao="média das 6 (dois estágios)", ordens=sum(len(por[a]) for a in el),
                 modelo=f"{pm:.2f} ({ci(stats['modelo'])[0]:.2f}–{ci(stats['modelo'])[1]:.2f})",
                 ufcap=f"{pu:.2f} ({ci(stats['ufcap'])[0]:.2f}–{ci(stats['ufcap'])[1]:.2f})",
                 **{"ufcap−modelo": f"{pu - pm:.2f} ({ci(stats['dif'])[0]:.2f}–{ci(stats['dif'])[1]:.2f})",
                    "modelo÷ufcap": f"{pm / pu:.2f} ({ci(stats['rat'])[0]:.2f}–{ci(stats['rat'])[1]:.2f})"}))
out = pd.DataFrame(rows)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(out.to_string(index=False))
out.to_csv("modelo/bootstrap_pres.csv", index=False)
# regra verde (v1): fração de pontos verdes com erro ≤ 0,5, bootstrap em dois estágios
ns = {}; exec(open("scripts/semaforo_v2.py").read().split("if __name__")[0], ns); ns["VERDE_MIN_SECOES"] = 0.0
L = {}
for a, p in F.items():
    d = pd.read_csv(f"{p}/semaforo_pontos.csv").assign(fonte=a)
    if "corr_intra" not in d: d["corr_intra"] = np.nan
    l = ns["luzes"](d); l["ok"] = (l.modelo - l.verdade).abs() <= 0.5
    L[a] = l[l.luz == "verde"].groupby("ordem").ok.agg(["sum", "count"])
tot = sum(L[a]["sum"].sum() for a in el) / sum(L[a]["count"].sum() for a in el)
fr = []
for _ in range(B):
    s = c = 0
    for a in rng.choice(el, len(el), replace=True):
        g = L[a]; i = rng.integers(0, len(g), len(g)); s += g["sum"].values[i].sum(); c += g["count"].values[i].sum()
    fr.append(s / c)
print(f"\nverde (v1, 31 ordens simuladas, 6 eleições): {100 * tot:.1f}% dos pontos verdes com erro ≤ 0,5 "
      f"(IC95% {100 * ci(fr)[0]:.1f}–{100 * ci(fr)[1]:.1f}); pontos verdes {sum(L[a]['count'].sum() for a in el)}")
