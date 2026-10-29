"""Variáveis da eleição municipal de dois anos antes, por seção, para o modelo de 1º turno presidencial.
Para cada candidato presidencial c (os mais votados do ano-alvo), m_c = parte dos votos válidos para prefeito (1º turno)
dados a partidos da coligação de c; também m_dir e m_esq (blocos ideológicos) e w_c = o prefeito eleito é da coligação de c.
O casamento com a seção do ano-alvo vai do mais fino ao mais grosso: seção (UF, município, zona, seção),
local de votação, zona, município.
"""
import duckdb, numpy as np, pandas as pd

PREF_DB = "/home/claude/tse/mun/pref.duckdb"
MUN_ANO = {2018: 2016, 2022: 2020, 2026: 2024}

# coligações presidenciais (números dos partidos); 2022 e 2026 da consulta_coligacao do TSE, 2018 das coligações registradas
COLIG = {
    2018: {17: [17, 28], 13: [13, 65, 90], 12: [12, 70], 45: [45, 14, 11, 22, 25, 77, 10, 23, 55], 30: [30],
           18: [18, 43], 15: [15]},
    2022: {13: [13, 65, 43, 77, 50, 18, 40, 36, 70, 90], 22: [22, 11, 10], 15: [15, 45, 23, 19], 12: [12], 44: [44]},
    2026: {22: [22], 13: [13, 65, 43, 40, 12, 50, 18], 70: [70, 36], 14: [14], 55: [55]},
}
# blocos ideológicos (partidos que existiram em algum dos anos municipais)
ESQ = [13, 65, 43, 40, 50, 18, 12, 21, 16, 80, 29]
DIR = [22, 11, 10, 44, 25, 17, 30, 28, 20, 14, 51, 27]


def features(b, ano, top):
    """b: seções do alvo (sg_uf, cd_municipio, nr_zona, nr_secao, nr_local). Devolve DataFrame alinhado a b."""
    ym = MUN_ANO[ano]
    con = duckdb.connect(PREF_DB, read_only=True)
    v = con.execute(f"""SELECT sg_uf, cd_municipio, nr_zona, nr_secao, nr_local, turno, votavel, votos
                        FROM pref WHERE ano={ym}""").df()
    con.close()
    col = COLIG[ano]
    grupos = {f"m_{c}": col.get(c, [c]) for c in top}
    grupos["m_dir"], grupos["m_esq"] = DIR, ESQ
    t1 = v[(v.turno == 1) & ~v.votavel.isin([95, 96])].copy()
    for g, parts in grupos.items():
        t1[g] = np.where(t1.votavel.isin(parts), t1.votos, 0)
    G = list(grupos)
    levels = [["sg_uf", "cd_municipio", "nr_zona", "nr_secao"], ["sg_uf", "cd_municipio", "nr_zona", "nr_local"],
              ["sg_uf", "cd_municipio", "nr_zona"], ["sg_uf", "cd_municipio"]]
    out = pd.DataFrame(index=b.index, columns=G, dtype=float); lvl = pd.Series(np.nan, index=b.index)
    bb = b[["sg_uf", "cd_municipio", "nr_zona", "nr_secao", "nr_local"]].copy()
    bb["cd_municipio"] = bb.cd_municipio.astype("int64"); bb["nr_zona"] = bb.nr_zona.astype("int64")
    bb["nr_secao"] = bb.nr_secao.astype("int64"); bb["nr_local"] = pd.to_numeric(bb.nr_local, errors="coerce")
    for i, keys in enumerate(levels):
        a = t1.groupby(keys)[G + ["votos"]].sum()
        sh = a[G].div(a.votos.clip(lower=1), axis=0).reset_index()
        need = out[G[0]].isna()
        m = bb.loc[need, keys].reset_index().merge(sh, on=keys, how="left").set_index("index")
        ok = m[G[0]].notna()
        out.loc[m.index[ok], G] = m.loc[ok, G].values; lvl.loc[m.index[ok]] = i
    # prefeito eleito: mais votado no último turno do município
    vv = v[~v.votavel.isin([95, 96])]
    fin = vv[vv.turno == vv.groupby(["sg_uf", "cd_municipio"]).turno.transform("max")].groupby(["sg_uf", "cd_municipio", "votavel"]).votos.sum().reset_index()
    win = fin.sort_values("votos").groupby(["sg_uf", "cd_municipio"]).tail(1)[["sg_uf", "cd_municipio", "votavel"]]
    wm = bb[["sg_uf", "cd_municipio"]].reset_index().merge(win, on=["sg_uf", "cd_municipio"], how="left").set_index("index").votavel
    for c in top:
        out[f"w_{c}"] = wm.isin(col.get(c, [c])).astype(float)
    out["w_dir"] = wm.isin(DIR).astype(float); out["w_esq"] = wm.isin(ESQ).astype(float)
    out["m_has"] = out[G[0]].notna().astype(float)
    out[G] = out[G].fillna(out[G].mean())
    out["m_lvl"] = lvl
    return out
