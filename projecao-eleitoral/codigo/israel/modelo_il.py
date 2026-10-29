"""Projeção de cadeiras do Knesset a partir da contagem parcial, urna a urna (kalpi).
Princípio do modelo brasileiro: cada lugar tende a repetir o seu padrão; mede-se, nas urnas já contadas, a razão
entre o voto observado de cada lista e o esperado pelo histórico, e aplica-se às que faltam.
Como a numeração das urnas muda entre eleições, a unidade de referência é o "bloco": localidade × (nº da urna // 5),
números vizinhos = mesma vizinhança. Urnas novas caem no bloco de 20 ou na localidade.
Razões encolhidas: nacional → setor (árabe / haredi / geral) → comissão regional → localidade.
Cadeiras: barreira 3,25%, Bader-Ofer (D'Hondt), acordos de sobras. Incerteza por simulação.
"""
import numpy as np, pandas as pd

ENV = 9999          # "מעטפות חיצוניות" (envelopes duplos: militares, diplomatas, hospitais, presos...)
B1, B2 = 5, 20

def load_kalpi(path, enc="utf-8-sig"):
    d = pd.read_csv(path, encoding=enc)
    d.columns = [c.strip() for c in d.columns]
    d = d.rename(columns={"סמל ועדה": "committee", "שם ישוב": "city", "סמל ישוב": "city_id", "קלפי": "kalpi",
                          "בזב": "eligible", "מצביעים": "voters", "פסולים": "invalid", "כשרים": "valid"})
    meta = {"committee", "city", "city_id", "kalpi", "eligible", "voters", "invalid", "valid", "ברזל", "ריכוז", "שופט", "חיצוניות", "קלפי אחרת"}
    parties = [c for c in d.columns if c not in meta and not c.startswith("Unnamed")]
    d[parties] = d[parties].apply(pd.to_numeric, errors="coerce").fillna(0)
    for c in ("eligible", "voters", "invalid", "valid", "city_id"): d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
    d["city_id"] = d.city_id.astype(int)
    n = pd.to_numeric(d.kalpi, errors="coerce").fillna(0).astype(int)
    d["b1"] = d.city_id.astype(str) + "-" + (n // B1).astype(str)
    d["b2"] = d.city_id.astype(str) + "-" + (n // B2).astype(str)
    return d, parties

def group(d, mapping, parties):
    """Agrega as letras de uma eleição nas listas-alvo. mapping: alvo -> {letra: peso}. Resto vai para _outros."""
    out = pd.DataFrame(index=d.index); used = set()
    for t, olds in mapping.items():
        olds = {o: w for o, w in olds.items() if o in parties}; used |= set(olds)
        out[t] = sum(d[o] * w for o, w in olds.items()) if olds else 0.0
    out["_outros"] = d[[p for p in parties if p not in used]].sum(axis=1)
    return out

def dhondt(votes, n):
    q = sorted(((v / k, name) for name, v in votes.items() for k in range(1, n + 1)), reverse=True)
    out = dict.fromkeys(votes, 0)
    for _, name in q[:n]: out[name] += 1
    return out

def seats(votes, threshold=0.0325, agreements=(), total=120):
    tot = sum(votes.values())
    passed = {k: v for k, v in votes.items() if not k.startswith("_") and v >= threshold * tot}
    groups, inag = {}, set()
    for a, b in agreements:
        if a in passed and b in passed: groups[a + "+" + b] = (a, b); inag |= {a, b}
    blocks = {g: passed[a] + passed[b] for g, (a, b) in groups.items()}
    blocks.update({k: v for k, v in passed.items() if k not in inag})
    res = dict.fromkeys(votes, 0)
    for k, n in dhondt(blocks, total).items():
        if k in groups:
            a, b = groups[k]; sub = dhondt({a: passed[a], b: passed[b]}, n); res[a] += sub[a]; res[b] += sub[b]
        else: res[k] += n
    return res

class Projetor:
    def __init__(self, ref, ref_parties, mapping_ref, arab=("עם", "ום", "ד", "ודעם"), haredi=("שס", "ג"),
                 k_sec=20000.0, k_com=6000.0, k_loc=1500.0, tau=(0.04, 0.06, 0.10), tau_g=0.015, growth=1.0, env_sd=0.25):
        """ref: urnas da eleição de referência (anterior), mapping_ref: lista-alvo -> {letra antiga: peso} (proxy)."""
        r = ref[ref.city_id != ENV]
        G = group(r, mapping_ref, ref_parties); self.T = list(G.columns)
        A = r[[p for p in arab if p in ref_parties]].sum(axis=1); H = r[[p for p in haredi if p in ref_parties]].sum(axis=1)
        base = pd.concat([r[["b1", "b2", "city_id", "committee", "valid", "eligible"]], G, A.rename("_a"), H.rename("_h")], axis=1)
        def agg(level):
            g = base.groupby(level).agg({**{t: "sum" for t in self.T + ["valid", "eligible", "_a", "_h"]},
                                         "city_id": "first", "committee": "first"})
            return g
        self.u = agg("b1")                                    # universo de blocos da referência
        self.s1 = self.u[self.T].div(self.u.valid.clip(lower=1), axis=0)
        g2 = agg("b2"); self.s2 = g2[self.T].div(g2.valid.clip(lower=1), axis=0)
        gc = agg("city_id"); self.sc = gc[self.T].div(gc.valid.clip(lower=1), axis=0)
        def sect(g): return pd.Series(np.where(g._a > 0.5 * g.valid, "arabe", np.where(g._h > 0.5 * g.valid, "haredi", "geral")), index=g.index)
        self.u["sector"] = sect(self.u); self.sec_city = sect(gc); self.com_city = gc.committee
        self.snat = self.u[self.T].sum() / self.u.valid.sum()
        self.tr = [g.valid / g.eligible.clip(lower=1) for g in (self.u, g2, gc)]      # comparecimento válido histórico
        self.tr_nat = self.u.valid.sum() / self.u.eligible.sum()
        e = ref[ref.city_id == ENV]                                   # envelopes duplos na referência: viés por lista
        if len(e) and e.valid.sum() > 0:
            es = group(e, mapping_ref, ref_parties)[self.T].sum(); es = es / es.sum()
            self.env_ratio = ((es + 1e-4) / (self.snat / self.snat.sum() + 1e-4)).clip(0.2, 5).values
        else: self.env_ratio = np.ones(len(self.T))
        self.k = (k_sec, k_com, k_loc); self.tau = tau; self.tau_g = tau_g; self.growth = growth; self.env_sd = env_sd

    def expected_shares(self, cur):
        """Partes esperadas (histórico) para cada urna corrente: bloco 5 → bloco 20 → localidade → nacional."""
        S = self.s1.reindex(cur.b1.values).to_numpy(copy=True)
        for alt, key in ((self.s2, cur.b2.values), (self.sc, cur.city_id.values)):
            m = np.isnan(S[:, 0]); S[m] = alt.reindex(key[m]).values
        m = np.isnan(S[:, 0]); S[m] = self.snat.values
        return S

    def project(self, cur, mapping_cur, cur_parties, sims=300, seed=0, agreements=(), coalition=(), envelopes=0.0):
        """cur: urnas já contadas na eleição corrente (formato expb). envelopes: votos válidos esperados nos envelopes
        duplos (contados dias depois) — entram com a distribuição nacional projetada + ruído."""
        rng = np.random.default_rng(seed); T = self.T
        env_obs = cur[cur.city_id == ENV]; c = cur[(cur.city_id != ENV) & (cur.valid > 0)].copy()
        O = group(c, mapping_cur, cur_parties)[T].values                         # votos observados
        E = self.expected_shares(c) * c.valid.values[:, None]                    # esperados pelo histórico
        sec = self.sec_city.reindex(c.city_id).fillna("geral").values
        com = c.committee.values; loc = c.city_id.values
        def ratios(keys, parent, k):
            df = pd.DataFrame(np.hstack([O, E]), columns=[f"o{i}" for i in range(len(T))] + [f"e{i}" for i in range(len(T))])
            g = df.groupby(keys).sum()
            o = g[[f"o{i}" for i in range(len(T))]].values; e = g[[f"e{i}" for i in range(len(T))]].values
            par = parent(g.index)
            return pd.DataFrame((o + k * par) / (e + k), index=g.index), pd.Series(e.sum(1), index=g.index)
        r_nat = (O.sum(0) + 1) / (E.sum(0) + 1)
        r_sec, _ = ratios(sec, lambda idx: np.tile(r_nat, (len(idx), 1)), self.k[0])
        def sec_r(s): return r_sec.reindex(s).fillna(pd.Series(r_nat)).values if len(s) else np.zeros((0, len(T)))
        def sec_of_com(cm):
            cs = self.u.groupby("committee").sector.agg(lambda s: s.mode().iat[0]); return cs.reindex(cm).fillna("geral").values
        r_com, _ = ratios(com, lambda idx: self._fill(r_sec, sec_of_com(idx), r_nat), self.k[1])
        def com_rr(cm, sc):
            x = r_com.reindex(cm).to_numpy(copy=True); m = np.isnan(x[:, 0]); x[m] = self._fill(r_sec, sc[m], r_nat); return x
        r_loc, _ = ratios(loc, lambda idx: com_rr(self.com_city.reindex(idx).values, self.sec_city.reindex(idx).fillna("geral").values), self.k[2])
        # urnas que faltam. Eleitores: por localidade, (eleitores da referência × crescimento) − já contados; dentro da
        # localidade, repartidos pelos blocos ainda não cobertos. Votos válidos = eleitores × comparecimento histórico do
        # bloco × razão de comparecimento observada (encolhida localidade → comissão → setor → nacional).
        U = self.u
        tr_exp = self.tr[0].reindex(c.b1.values).to_numpy(copy=True)
        for alt, key in ((self.tr[1], c.b2.values), (self.tr[2], c.city_id.values)):
            m = np.isnan(tr_exp); tr_exp[m] = alt.reindex(key[m]).values
        tr_exp = np.where(np.isnan(tr_exp), self.tr_nat, tr_exp)
        ev = tr_exp * c.eligible.values                                   # válidos esperados nas contadas
        df = pd.DataFrame({"o": c.valid.values, "e": ev, "sec": sec, "com": com, "loc": loc})
        q_nat = (df.o.sum() + 1) / (df.e.sum() + 1)
        gs = df.groupby("sec")[["o", "e"]].sum(); q_sec = (gs.o + 20000 * q_nat) / (gs.e + 20000)
        gcm = df.groupby("com")[["o", "e"]].sum(); sec_c = pd.Series(sec_of_com(gcm.index), index=gcm.index)
        pc = sec_c.map(q_sec).fillna(q_nat); q_com = (gcm.o + 6000 * pc) / (gcm.e + 6000)
        gl = df.groupby("loc")[["o", "e"]].sum()
        pl = pd.Series(self.com_city.reindex(gl.index).values, index=gl.index).map(q_com)
        pl = pl.fillna(pd.Series(self.sec_city.reindex(gl.index).values, index=gl.index).map(q_sec)).fillna(q_nat)
        q_loc = (gl.o + 1500 * pl) / (gl.e + 1500)
        q = U.city_id.map(q_loc)
        q = q.fillna(U.committee.map(q_com)).fillna(U.sector.map(q_sec)).fillna(q_nat).values
        elig_ref = U.eligible.values * self.growth
        cnt_be = c.groupby("b1").eligible.sum().reindex(U.index).fillna(0).values
        free_b = np.clip(elig_ref - cnt_be, 0, None)
        city_rem = pd.Series(elig_ref, index=U.index).groupby(U.city_id.values).sum().sub(
                    c.groupby("city_id").eligible.sum(), fill_value=0).clip(lower=0)
        free_city = pd.Series(free_b).groupby(U.city_id.values).sum()
        scale = (city_rem / free_city.replace(0, np.nan)).fillna(0).clip(upper=1.0)
        rem_e = free_b * U.city_id.map(scale).fillna(1.0).values
        V = rem_e * self.tr[0].values * q
        keep = V > 0; R = U[keep]; V = V[keep]
        Rsec = R.sector.values; Rcom = R.committee.values; Rloc = R.city_id.values
        RR = r_loc.reindex(Rloc).to_numpy(copy=True); m = np.isnan(RR[:, 0])
        RR[m] = com_rr(Rcom[m], Rsec[m])
        M = self.s1.loc[R.index].values * RR
        f_loc = np.where(np.isin(Rloc, r_loc.index), 0.4, 1.0); f_com = np.where(np.isin(Rcom, r_com.index), 0.4, 1.0)
        f_sec = np.where(np.isin(Rsec, r_sec.index), 0.4, 1.0)
        _, li = np.unique(Rloc, return_inverse=True); _, ci = np.unique(Rcom, return_inverse=True); _, si = np.unique(Rsec, return_inverse=True)
        tau_s, tau_c, tau_l = self.tau
        Osum = O.sum(0); Envobs = group(env_obs, mapping_cur, cur_parties)[T].values.sum(0) if len(env_obs) else np.zeros(len(T))
        env_rest = max(envelopes - env_obs.valid.sum(), 0)
        def total(Mx, eps_env):
            P = Mx / np.clip(Mx.sum(1, keepdims=True), 1e-12, None)
            v = Osum + (P * V[:, None]).sum(0)
            sh = v / v.sum() * self.env_ratio * np.exp(eps_env); sh /= sh.sum()
            return v + Envobs + env_rest * sh
        point = total(M, np.zeros(len(T)))
        SV, SS = [], []
        for _ in range(sims):
            z = (rng.standard_normal(len(T)) * self.tau_g)[None, :]
            zs = rng.standard_normal((si.max() + 1, len(T))) * tau_s
            zc = rng.standard_normal((ci.max() + 1, len(T))) * tau_c
            zl = rng.standard_normal((li.max() + 1, len(T))) * tau_l
            Ms = M * np.exp(z + zs[si] * f_sec[:, None] + zc[ci] * f_com[:, None] + zl[li] * f_loc[:, None])
            v = total(Ms, rng.standard_normal(len(T)) * self.env_sd)
            SV.append(v); SS.append(seats(dict(zip(T, v)), agreements=agreements))
        sv = pd.DataFrame(SV, columns=T); ss = pd.DataFrame(SS); sh = sv.div(sv.sum(1), axis=0)
        out = pd.DataFrame({"pct_proj": 100 * point / point.sum(), "pct_lo": 100 * sh.quantile(0.05).values,
                            "pct_hi": 100 * sh.quantile(0.95).values}, index=T)
        out["cad_ponto"] = pd.Series(seats(dict(zip(T, point)), agreements=agreements))
        out["cad_med"] = ss.median(); out["cad_lo"] = ss.quantile(0.05); out["cad_hi"] = ss.quantile(0.95)
        out["p_barreira"] = (sh >= 0.0325).mean()
        info = dict(urnas=len(c), votos_contados=int(c.valid.sum()), pct_votos=float(c.valid.sum() / (c.valid.sum() + V.sum())))
        if coalition:
            coal = ss[[x for x in coalition if x in ss]].sum(1)
            info.update(p61=float((coal >= 61).mean()), coal_ponto=int(sum(out.cad_ponto.get(x, 0) for x in coalition)),
                        coal_med=float(coal.median()), coal_lo=float(coal.quantile(0.05)), coal_hi=float(coal.quantile(0.95)))
        return out, info

    @staticmethod
    def _fill(r_sec, secs, r_nat):
        x = r_sec.reindex(secs).to_numpy(copy=True)
        m = np.isnan(x[:, 0]) if x.ndim == 2 and len(x) else np.zeros(len(secs), bool)
        if len(x): x[m] = r_nat
        return x
