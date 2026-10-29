"""História longa por local de votação (2002–2022), para testar no modelo do 2º turno.
Para cada ano Y e local (UF, município, zona, local):
  d_Y = logit(parte da direita no 2T) - logit(parte da direita entre os dois finalistas no 1T)   [transferência no 2T]
  c_Y = logit(parte da direita no 2T de Y) - logit(parte da direita no 2T de Y-4)                 [deriva entre eleições]
ambos centrados na média nacional ponderada. Saída: hist/hist_local.parquet (formato longo).
Uso: python3 -I hist_longa.py
"""
import duckdb, numpy as np, pandas as pd
DIR = {2002: 45, 2006: 45, 2010: 45, 2014: 45, 2018: 17, 2022: 22}
DBS = {2002: "tse_hist.duckdb", 2006: "tse_hist.duckdb", 2010: "tse_hist.duckdb", 2014: "tse_hist.duckdb",
       2018: "tse_1418.duckdb", 2022: "tse_2026.duckdb"}
lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
K = ["sg_uf", "cd_municipio", "nr_zona", "nr_local"]
tab = {}
for y, db in DBS.items():
    c = duckdb.connect("/home/claude/tse/" + db, read_only=True); r = DIR[y]
    q = f"""
    WITH loc AS (SELECT DISTINCT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao, NR_LOCAL_VOTACAO nr_local
                 FROM detalhe_votacao_secao WHERE ANO_ELEICAO={y} AND NR_TURNO=1),
    v AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
            sum(QT_VOTOS) FILTER (WHERE NR_TURNO=1 AND NR_VOTAVEL={r}) a_r, sum(QT_VOTOS) FILTER (WHERE NR_TURNO=1 AND NR_VOTAVEL=13) a_13,
            sum(QT_VOTOS) FILTER (WHERE NR_TURNO=2 AND NR_VOTAVEL={r}) b_r, sum(QT_VOTOS) FILTER (WHERE NR_TURNO=2 AND NR_VOTAVEL=13) b_13
          FROM votacao_secao WHERE ANO_ELEICAO={y} AND CD_CARGO=1 GROUP BY ALL)
    SELECT loc.sg_uf, loc.cd_municipio, loc.nr_zona, loc.nr_local, sum(a_r) a_r, sum(a_13) a_13, sum(b_r) b_r, sum(b_13) b_13
    FROM v JOIN loc USING (sg_uf, cd_municipio, nr_zona, nr_secao) GROUP BY ALL"""
    d = c.execute(q).df().fillna(0); c.close()
    d = d[(d.a_r + d.a_13 > 20) & (d.b_r + d.b_13 > 20)].copy()
    d["p1"] = d.a_r / (d.a_r + d.a_13); d["p2"] = d.b_r / (d.b_r + d.b_13); d["w"] = d.b_r + d.b_13
    d["dd"] = lg(d.p2) - lg(d.p1); d["dd"] -= np.average(d.dd, weights=d.w)
    tab[y] = d; print(y, len(d), "locais", flush=True)
rows = []
for y, d in tab.items():
    x = d[K + ["dd", "w", "p2"]].copy(); x["ano"] = y
    if y - 4 in tab:
        p = tab[y - 4][K + ["p2"]].rename(columns={"p2": "p2_ant"})
        x = x.merge(p, on=K, how="left")
        x["cc"] = lg(x.p2) - lg(x.p2_ant); m = x.cc.notna()
        x.loc[m, "cc"] -= np.average(x.cc[m], weights=x.w[m])
    else: x["cc"] = np.nan
    rows.append(x[K + ["ano", "dd", "cc", "w"]])
out = pd.concat(rows); out.to_parquet("/home/claude/tse/hist/hist_local.parquet", index=False)
print(out.groupby("ano")[["dd", "cc"]].agg(["count", "std"]).round(3))
# persistência: correlação entre anos consecutivos (no mesmo local)
for y in sorted(tab)[1:]:
    a = out[out.ano == y - 4][K + ["dd", "cc"]]; b = out[out.ano == y][K + ["dd", "cc"]]
    m = a.merge(b, on=K, suffixes=("_a", "_b"))
    print(f"{y-4}->{y}: locais em comum {len(m)}, corr(dd) {m.dd_a.corr(m.dd_b):.2f}, corr(cc) {m.cc_a.corr(m.cc_b):.2f}")
