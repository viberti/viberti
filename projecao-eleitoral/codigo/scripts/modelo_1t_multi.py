"""1º turno com vários candidatos: parte de cada um nos votos válidos, chance de vitória no 1º turno (>50%) e de cada
candidato ir ao 2º turno, a partir de apuração parcial. Replay em várias ordens de chegada.
Mesma ideia do modelo binário: para cada candidato c (exceto o de referência, o 13), regressão ponderada de
log(v_c / v_13) da seção sobre o histórico dela (1º e 2º turno anteriores, vizinhança, perfil do município), com ridge;
efeitos de UF e município encolhidos; softmax nas seções que faltam; incerteza por simulação.
Uso: ANO=<alvo> TURNO_ALVO=1 VIZ=1 COV=1x python3 -I modelo_1t_multi.py <duckdb> <saida.csv>
"""
import os, sys, numpy as np, pandas as pd, duckdb
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "modelo.py")).read().split("# ---------- 2. ordens de chegada ----------")[0]
dbp, outp = sys.argv[1], sys.argv[2]
sys.argv = ["modelo.py", dbp, "/tmp/claude-0/multi_tmp"]
exec(src)                                      # b: seções do alvo com histórico (x1, xdir, ..., COV), TRUE etc.
FEAT = "v1"
KC = int(os.environ.get("KCAND", "5"))
con = duckdb.connect(dbp, read_only=True)
top = [r[0] for r in con.execute(f"""SELECT NR_VOTAVEL FROM votacao_secao WHERE ANO_ELEICAO={ANO} AND NR_TURNO=1
       AND CD_CARGO=1 AND NR_VOTAVEL NOT IN (95,96) GROUP BY 1 ORDER BY sum(QT_VOTOS) DESC LIMIT {KC}""").fetchall()]
assert 13 in top, top
cols_sql = ", ".join(f"sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={c}) c{c}" for c in top)
tv = con.execute(f"""SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao, {cols_sql},
       sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL NOT IN ({",".join(map(str, top))},95,96)) c_out
       FROM votacao_secao WHERE ANO_ELEICAO={ANO} AND NR_TURNO=1 AND CD_CARGO=1 GROUP BY ALL""").df().fillna(0)
con.close()
CANDS = [f"c{c}" for c in top] + ["c_out"]; REFC = "c13"; OTH = [c for c in CANDS if c != REFC]
b = b.drop(columns=[c for c in CANDS if c in b.columns]).merge(tv, on=K, how="left")
b[CANDS] = b[CANDS].fillna(0)
b["val"] = b[CANDS].sum(1)
b = b[b.val > 0].sort_values(K).reset_index(drop=True); N = len(b)   # ordem fixa: as ordens sorteadas ficam iguais entre execuções
b["s22"] = np.where(b.has1, b.a22 / b.comp1.clip(lower=1), 0.0); b["s13"] = np.where(b.has1, b.a13 / b.comp1.clip(lower=1), 0.0)
TOT = b[CANDS].sum(); TRUEV = (TOT / TOT.sum()).to_dict()
srt = sorted([c for c in CANDS if c != "c_out"], key=lambda c: -TRUEV[c])
print("alvo", ANO, "candidatos", top, "verdade %:", {c: round(100 * TRUEV[c], 2) for c in CANDS}, flush=True)
MUNI = os.environ.get("MUNI", "")
if MUNI:                                        # eleição municipal de 2 anos antes (feat_prefeito.py)
    sys.path.insert(0, here); import feat_prefeito
    MF = feat_prefeito.features(b, ANO, top)
    MCOLS = ([f"m_{c}" for c in top] + ["m_dir", "m_esq"] if "s" in MUNI else []) + \
            ([f"w_{c}" for c in top] + ["w_dir", "w_esq"] if "w" in MUNI else [])
    for c in MCOLS: b[c] = MF[c].values
    print("municipal:", MUNI, "nível de casamento:", MF.m_lvl.value_counts(normalize=True).round(3).to_dict(), flush=True)
DIRC = f"c{DIRN(ANO)}" if f"c{DIRN(ANO)}" in CANDS else None

def X_of(d):
    X = design(d)
    extra = [d[c].values for c in MCOLS] if MUNI else []
    return np.column_stack([X, d.s22, d.s13] + extra)

RIDGE = float(os.environ.get("RIDGE_M", "300"))
def project_m(rep, sims=100, rng=np.random.default_rng(0)):
    R, U = b[rep], b[~rep]
    w = np.sqrt(R.val.values.astype(float)); w = w / w.mean()
    XR, XU = X_of(R), X_of(U); kx = XR.shape[1]
    ref = R[REFC].values + 0.5
    mus, sds, fitR = {}, {}, {}
    lam = np.full(kx, RIDGE); lam[0] = 0.0
    for c in OTH:
        y = np.log((R[c].values + 0.5) / ref)
        b0 = np.zeros(kx)
        if c == DIRC: b0[1] = 1.0             # o candidato da direita segue o logit direita/13 do histórico
        A = np.vstack([XR * w[:, None], np.diag(np.sqrt(lam))]); yy = np.concatenate([y * w, np.sqrt(lam) * b0])
        beta = np.linalg.lstsq(A, yy, rcond=None)[0]
        res = y - XR @ beta
        euf, wuf = shrink(res, w, R.sg_uf.values, HP["kuf"]); res2 = res - R.sg_uf.map(euf).values
        emu, wmu = shrink(res2, w, R.mun.values, HP["kmu"]); res3 = res2 - R.mun.map(emu).fillna(0).values
        mus[c] = XU @ beta + U.sg_uf.map(euf).fillna(0).values + U.mun.map(emu).fillna(0).values
        fitR[c] = XR @ beta + R.sg_uf.map(euf).fillna(0).values + R.mun.map(emu).fillna(0).values
        tau_uf = max(np.sqrt(max(np.average(euf.values ** 2), 1e-6)), TAU_UF_MIN, 0.02)
        tau_mu = max(np.sqrt(np.average(emu.values ** 2)), 0.02)
        sds[c] = (tau_uf, wuf, tau_mu, wmu, np.sqrt(np.average(res3 ** 2, weights=w)))
    # volume: válidos ≈ comparecimento do 1T anterior × razão do município (encolhida p/ UF)
    R1 = R[R.has1]
    ruf = R1.groupby("sg_uf").val.sum() / R1.groupby("sg_uf").comp1.sum(); rnat = R1.val.sum() / max(R1.comp1.sum(), 1)
    gm = R1.groupby("mun").agg(v=("val", "sum"), c=("comp1", "sum"), uf=("sg_uf", "first"))
    rm = (gm.v + HP["kc"] * gm.uf.map(ruf)) / (gm.c + HP["kc"])
    rr = U.mun.map(rm).fillna(U.sg_uf.map(ruf)).fillna(rnat).values
    vU = np.where(U.has1, U.comp1f.fillna(0) * rr, U.aptos2 * R.val.sum() / R.aptos2.sum())
    Rsum = R[[REFC] + OTH].sum().values                                 # mesma ordem das colunas do softmax
    def softmax(eta, n):
        M = np.column_stack([np.zeros(n)] + [eta[c] for c in OTH])          # log-razão vs 13 (13 = 0)
        M = M - M.max(1, keepdims=True); P = np.exp(M); return P / P.sum(1, keepdims=True)
    # correção de agregação (média de log ≠ log da média): fator por candidato que faz o ajuste nas seções
    # apuradas bater com os votos reais delas; aplicado às que faltam
    PR = softmax(fitR, len(R)); fitted = (PR * R.val.values[:, None]).sum(0)
    fac = R[[REFC] + OTH].sum().values / np.clip(fitted, 1e-9, None)
    def total(eta):
        P = softmax(eta, len(U)) * fac[None, :]; P /= P.sum(1, keepdims=True)
        v = Rsum + (P * vU[:, None]).sum(0)                                   # ordem: [13] + OTH
        order = [REFC] + OTH
        s = dict(zip(order, v)); tot = sum(s.values())
        return {c: s[c] / tot for c in CANDS}
    point = total(mus)
    uf_codes, uf_idx = np.unique(U.sg_uf.values, return_inverse=True)
    mu_codes, mu_idx = np.unique(U.mun.values, return_inverse=True)
    sims_out = []
    for _ in range(sims):
        eta = {}
        for c in OTH:
            tau_uf, wuf, tau_mu, wmu, ssec = sds[c]
            usd = np.array([tau_uf * (HP["kuf"] / (wuf.get(u, 0) + HP["kuf"])) ** 0.5 for u in uf_codes])
            msd = np.array([tau_mu * (HP["kmu"] / (wmu.get(m, 0) + HP["kmu"])) ** 0.5 for m in mu_codes])
            eta[c] = mus[c] + rng.standard_normal() * TAU_G * 2 + (rng.standard_normal(len(uf_codes)) * usd)[uf_idx] \
                     + (rng.standard_normal(len(mu_codes)) * msd)[mu_idx]
        sims_out.append(total(eta))
    S = pd.DataFrame(sims_out)
    srt_s = S[[c for c in CANDS if c != "c_out"]]
    first = srt_s.idxmax(1); top2 = srt_s.apply(lambda r: frozenset(r.nlargest(2).index), axis=1)
    out = dict(point=point, lo=S.quantile(0.05).to_dict(), hi=S.quantile(0.95).to_dict(),
               p_win1 = float((srt_s.max(1) > 0.5).mean()),
               p_2t = {c: float(top2.apply(lambda s: c in s).mean()) for c in srt_s.columns},
               p_first = first.value_counts(normalize=True).to_dict(),
               parcial={c: Rsum[i] / Rsum.sum() for i, c in enumerate([REFC] + OTH)})
    return out

# ordens de chegada (as mesmas da calibração do 1º turno)
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
SIMS = int(os.environ.get("SIMS_M", "100"))
true_top2 = frozenset(srt[:2]); win1 = TRUEV[srt[0]] > 0.5
REGCAP = b.groupby(["reg", "capital"]).aptos2.sum()   # eleitorado apto: conhecido antes da eleição
b["hw"] = np.where(b.has1, (b.a22 + b.a13).fillna(0), 0.0)
pr1 = np.where(b.hw > 0, b.a22.fillna(0) / b.hw.replace(0, np.nan), np.nan); b["p1"] = pd.Series(pr1).fillna(np.nanmean(pr1)).values
HIST_ALL = np.average(b.p1, weights=b.hw)
rows = []
for n, o in orders.items():
    for f in CK:
        rep = pd.Series(o <= f * N, index=b.index)
        r = project_m(rep, sims=SIMS, rng=np.random.default_rng(7))
        mrc = (b[rep].groupby(["reg", "capital"]).aptos2.sum() / REGCAP).reindex(REGCAP.index).fillna(0).min()
        row = dict(ano=ANO, ordem=n, pct=f, min_regcap=float(mrc), vies_hist_pp=float(100 * (np.average(b[rep].p1, weights=b[rep].hw) - HIST_ALL)) if b[rep].hw.sum() > 0 else 99.0, p_win1=r["p_win1"], win1_real=win1,
                   p_top2_certo=float(np.prod([r["p_2t"].get(c, 0) for c in true_top2])),
                   top2_ponto_certo=frozenset(sorted([c for c in CANDS if c != "c_out"], key=lambda c: -r["point"][c])[:2]) == true_top2)
        for c in CANDS:
            row[f"e_{c}"] = 100 * (r["point"][c] - TRUEV[c]); row[f"p_{c}"] = 100 * (r["parcial"][c] - TRUEV[c])
            row[f"cob_{c}"] = r["lo"][c] <= TRUEV[c] <= r["hi"][c]
        rows.append(row)
    print(n, flush=True)
D = pd.DataFrame(rows); D.to_csv(outp, index=False)
ec = [f"e_{c}" for c in CANDS]; pc = [f"p_{c}" for c in CANDS]
D["mae"] = D[ec].abs().mean(1); D["mae_parc"] = D[pc].abs().mean(1)
print("MAE modelo", round(D.mae.mean(), 3), "| parcial", round(D.mae_parc.mean(), 3),
      "| verde: modelo", round(D[D.min_regcap >= 0.001].mae.mean(), 3), "parcial", round(D[D.min_regcap >= 0.001].mae_parc.mean(), 3), flush=True)
