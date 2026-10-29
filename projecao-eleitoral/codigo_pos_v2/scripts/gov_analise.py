"""Resume os replays de governador: modelo × mudança uniforme capital/interior × parcial, por disputa e no conjunto,
com intervalo por bootstrap das disputas (a unidade de evidência). Uso: python3 -I gov_analise.py [pasta]"""
import sys, glob, os, numpy as np, pandas as pd
pasta = sys.argv[1] if len(sys.argv) > 1 else "modelo/gov"
fs = glob.glob(os.path.join(pasta, "v*_*.csv"))
d = pd.concat([pd.read_csv(f).assign(cfg=os.path.basename(f).split("_")[0]) for f in fs], ignore_index=True)
d = d[(d.pct_secoes >= 0.005) & (d.pct_secoes <= 0.5)].copy()
for m in ("modelo", "swing_ufcap", "parcial", "swing"): d[f"e_{m}"] = (d[m] - d.verdade).abs()
d["cob"] = (d.lo <= d.verdade) & (d.verdade <= d.hi)
d["disputa"] = d.ano.astype(str) + " " + d.uf
d["margem"] = (d.verdade - 50).abs()
rng = np.random.default_rng(0)
def boot(x, n=5000):
    x = np.asarray(x); i = rng.integers(0, len(x), (n, len(x))); m = x[i].mean(1)
    return np.percentile(m, [2.5, 97.5])
pd.set_option("display.width", 220)
for sub, nome in ((d, "todas as ordens"), (d[d.ordem == "real"], "ordem real")):
    print(f"\n######## {nome}")
    for cfg, g in sub.groupby("cfg"):
        p = g.groupby("disputa").agg(modelo=("e_modelo", "mean"), swing=("e_swing_ufcap", "mean"), parcial=("e_parcial", "mean"),
                                     cob=("cob", "mean"), margem=("margem", "first"))
        dif = p.swing - p.modelo; lo, hi = boot(dif)
        rat = (p.modelo / p.swing); lr, hr = boot(np.log(rat))
        print(f"[{cfg}] {len(p)} disputas | erro médio: modelo {p.modelo.mean():.2f}, mudança uniforme {p.swing.mean():.2f}, parcial {p.parcial.mean():.2f}"
              f" | uniforme − modelo = {dif.mean():.2f} (IC95% {lo:.2f} a {hi:.2f}) | razão modelo/uniforme {np.exp(np.log(rat).mean()):.2f}"
              f" (IC95% {np.exp(lr):.2f} a {np.exp(hr):.2f}) | modelo melhor em {(dif > 0).sum()} de {len(p)} | faixa de 90% acerta {100 * p.cob.mean():.0f}%")
        if nome == "ordem real" or cfg == "v1":
            print(p.round(2).sort_values("margem").to_string())
# fase
print("\n######## por fase (todas as ordens)")
fase = pd.cut(d.pct_secoes, [0, 0.01, 0.05, 0.15, 0.5])
print(d.groupby(["cfg", fase], observed=True)[["e_modelo", "e_swing_ufcap", "e_parcial", "cob"]].mean().round(3).to_string())
# anúncio do vencedor: projeção a ≥ 1 ponto de 50% com ≥ 5% das seções (análogo simples dentro da UF)
print("\n######## vencedor errado com |projeção − 50| ≥ 1 (pontos)")
for cfg, g in d.groupby("cfg"):
    a = g[(g.modelo - 50).abs() >= 1]; err = a[np.sign(a.modelo - 50) != np.sign(a.verdade - 50)]
    print(cfg, len(a), "anúncios,", len(err), "errados", err[["disputa", "ordem", "pct_secoes", "modelo", "verdade"]].round(2).values.tolist()[:8])
