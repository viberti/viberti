"""Versão MUNICIPAL do modelo: usa só o que o TSE divulga em tempo real por município
(votos parciais, eleitorado apurado), sem saber que seções já chegaram.
Compara com o modelo por seção nas mesmas noites simuladas.
Uso: ANO=... [ORDEM_REAL=...] python3 -I modelo_mun.py <duckdb> <saida.csv>
"""
import os, sys, numpy as np, pandas as pd
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "modelo.py")).read().split("# ---------- 2. ordens de chegada ----------")[0]
dbp, outp = sys.argv[1], sys.argv[2]
sys.argv = ["modelo.py", dbp, "/tmp/claude-0/mun_tmp"]
exec(src)   # b, design, shrink, project, TRUE, N, K, HP, TAU_G, TAU_UF_MIN, lg, il

# ---- histórico agregado por município (conhecido antes da eleição) ----
agg = b.groupby("mun").agg(sg_uf=("sg_uf", "first"), reg=("reg", "first"), capital=("capital", "first"),
    a22=("a22", "sum"), a13=("a13", "sum"), a_dir=("a_dir", "sum"), a_out=("a_out", "sum"), a_bn=("a_bn", "sum"),
    comp1=("comp1", "sum"), b22=("b22", "sum"), b13=("b13", "sum"), aptos=("aptos2", "sum"))
agg["has1"] = (agg.a22 + agg.a13) > 0
agg["x1"] = np.where(agg.has1, lg(agg.a22 / (agg.a22 + agg.a13).replace(0, np.nan)), 0.0)
for c_, src_ in (("xdir", "a_dir"), ("xout", "a_out"), ("xbn", "a_bn")):
    agg[c_] = np.where(agg.comp1 > 0, agg[src_] / agg.comp1.replace(0, np.nan), 0.0)
agg["has22"] = (agg.b22 + agg.b13) > 0
agg["x22"] = np.where(agg.has22, lg(agg.b22 / (agg.b22 + agg.b13).replace(0, np.nan)), 0.0)
agg["lmun"] = np.log(agg.aptos)
agg = agg.fillna(0)
# variância entre seções dentro do município (logit do 1T), conhecida antes da eleição
_v = b[b.has1].groupby("mun").x1.var()
agg["s2w"] = _v.reindex(agg.index).fillna(_v.median()).clip(lower=0.01)
MUN = agg.index.values
RIDGE = float(os.environ.get("RIDGE", "50"))

def project_mun(rep, sims=100, rng=np.random.default_rng(0)):
    R = b[rep]
    p = R.groupby("mun").agg(v22=("v22", "sum"), val2=("val2", "sum"), ap=("aptos2", "sum"), nsec=("val2", "size"))
    m = agg.join(p, how="left").fillna({"v22": 0, "val2": 0, "ap": 0, "nsec": 0})
    seen = m[m.val2 > 0]
    y = lg(seen.v22 / seen.val2).values; X = design(seen)
    samp = (seen.s2w / seen.nsec).values           # ruído de amostragem da parcial do município
    tau2 = 0.02
    for _ in range(3):                             # regressão ponderada por precisão + tau² por momentos
        w = 1 / np.sqrt(tau2 + samp)
        # ridge rumo à "mudança uniforme" (coef. 1 no logit do 1T, 0 no resto; intercepto livre)
        k = X.shape[1]; b0 = np.zeros(k); b0[1] = 1.0
        lam = np.full(k, RIDGE); lam[0] = 0.0
        A = np.vstack([X * w[:, None], np.diag(np.sqrt(lam))]); yy = np.concatenate([y * w, np.sqrt(lam) * b0])
        beta = np.linalg.lstsq(A, yy, rcond=None)[0]
        res = y - X @ beta
        tau2 = max(np.average(res ** 2 - samp, weights=w ** 2), 0.002)
    kuf = HP["kuf"]
    kuf = kuf * w.mean() / 15.8                    # mesma escala do modelo por seção
    euf, wuf = shrink(res, w, seen.sg_uf.values, kuf)
    res2 = res - seen.sg_uf.map(euf).values
    shr = tau2 / (tau2 + samp)                     # quanto do desvio é do município (e não das seções que chegaram)
    emu = pd.Series(res2 * shr, index=seen.index)
    tau_uf = max(np.sqrt(max(np.average(euf.values ** 2), 1e-6)), 0.02, TAU_UF_MIN)
    mu_sd_seen = pd.Series(np.sqrt(tau2 * (1 - shr)), index=seen.index)
    kmu = HP["kmu"]; s_sec = 0.0
    mu = design(m) @ beta + m.sg_uf.map(euf).fillna(0).values + pd.Series(m.index).map(emu).fillna(0).values
    # votos válidos que faltam: eleitorado ainda não apurado × taxa (aptos→válidos) do município, encolhida p/ UF
    rate_uf = (seen.groupby("sg_uf").val2.sum() / seen.groupby("sg_uf").ap.sum())
    rate_nat = seen.val2.sum() / seen.ap.sum()
    kc = HP["kc"]
    rate = (m.val2 + kc * m.sg_uf.map(rate_uf).fillna(rate_nat)) / (m.ap + kc)
    falta = np.maximum(m.aptos - m.ap, 0) * rate
    pm = il(mu)
    tot22 = m.v22.sum(); totv = m.val2.sum()
    out = {"parcial": tot22 / totv, "modelo": (tot22 + (falta * pm).sum()) / (totv + falta.sum())}
    ufs = m.sg_uf.values; uc, ui = np.unique(ufs, return_inverse=True)
    uf_sd = np.array([tau_uf * (kuf / (wuf.get(u, 0) + kuf)) ** 0.5 for u in uc])
    mu_sd = mu_sd_seen.reindex(m.index).fillna(np.sqrt(tau2)).values
    sims_v = [out["modelo"]] if sims == 0 else []
    for _ in range(sims):
        e = mu + rng.standard_normal() * TAU_G + (rng.standard_normal(len(uc)) * uf_sd)[ui] \
            + rng.standard_normal(len(m)) * mu_sd
        sims_v.append((tot22 + (falta * il(e)).sum()) / (totv + falta.sum()))
    out["lo"], out["hi"] = np.percentile(sims_v, [5, 95])
    return out

rng = np.random.default_rng(11); REGS = ["N", "NE", "CO", "SE", "S"]; noise = lambda: rng.permutation(N) / N
orders = {}
if os.environ.get("ORDEM_REAL"):
    o = pd.read_csv(os.environ["ORDEM_REAL"], parse_dates=["t_real"]); tr = b[K].merge(o, on=K, how="left").t_real
    orders["real"] = tr.fillna(tr.max()).rank(method="first").values
if b.t_rec.notna().any(): orders["proxy"] = b.t_rec.rank(method="first").values
for i in range(3): orders[f"aleatoria_{i}"] = rng.permutation(N) + 1
for i in range(5):
    dr = {r: rng.uniform(0, 60) for r in REGS + ["EXT"]}; du = {u: rng.uniform(0, 30) for u in b.sg_uf.unique()}
    t = b.reg.map(dr) + b.sg_uf.map(du) + b.capital * rng.uniform(-20, 20) + rng.exponential(25, N)
    orders[f"realista_{i}"] = t.rank(method="first").values
# dentro de cada município, chegada enviesada pelo histórico (o pior caso para a versão municipal)
orders["vies_intra_mun"] = (b.mun.map({m_: rng.uniform(0, 1) for m_ in MUN}) + 0.3 * pd.Series(b.x1).rank(pct=True) + 0.05 * rng.random(N)).rank(method="first").values
CK = [0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.50]
rows = []
for n, o in orders.items():
    for f in CK:
        rep = pd.Series(o <= f * N, index=b.index)
        s = project(rep, sims=100); mm = project_mun(rep)
        rows.append(dict(ordem=n, pct=f, parcial=100 * s["parcial"], secao=100 * s["modelo"], secao_lo=100 * s["lo"], secao_hi=100 * s["hi"],
                         municipio=100 * mm["modelo"], mun_lo=100 * mm["lo"], mun_hi=100 * mm["hi"], verdade=100 * TRUE))
    print(n, "ok", flush=True)
d = pd.DataFrame(rows); d.to_csv(outp, index=False)
d["e_sec"] = (d.secao - d.verdade).abs(); d["e_mun"] = (d.municipio - d.verdade).abs()
d["cob_sec"] = (d.secao_lo <= d.verdade) & (d.verdade <= d.secao_hi); d["cob_mun"] = (d.mun_lo <= d.verdade) & (d.verdade <= d.mun_hi)
print(d.groupby("ordem")[["e_sec", "e_mun"]].mean().round(3)); print(d.groupby("pct")[["e_sec", "e_mun"]].mean().round(3))
print("cobertura seção", d.cob_sec.mean(), "município", d.cob_mun.mean())
