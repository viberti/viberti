"""Transferência de votos 1º → 2º turno 2026 por inferência ecológica.
Etapa 1: base por seção (seções agregadas somadas na principal do 2T), em proporções do eleitorado apto.
Etapa 2: regressão ecológica de Goodman com restrições (0 <= beta <= 1, linhas somam 1), Brasil e regiões.
Uso: python3 -I transferencia.py <duckdb> <saida_dir>
"""
import os, sys, numpy as np, pandas as pd, duckdb
from scipy.optimize import minimize
dbp, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
con = duckdb.connect(dbp, read_only=True)
base = con.execute("""
WITH st AS (SELECT sg_uf, cd_municipio, nr_zona, nr_secao, CASE WHEN status='agregada' THEN nr_secao_principal ELSE nr_secao END sec2
            FROM bu_2t_status),
t1 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=22) o_flavio, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=13) o_lula,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=70) o_cury, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=14) o_renan,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=55) o_caiado, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=30) o_zema,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL NOT IN (22,13,70,14,55,30,95,96)) o_outros,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL IN (95,96)) o_branco_nulo
       FROM votacao_secao WHERE ANO_ELEICAO=2026 AND NR_TURNO=1 GROUP BY ALL),
a1 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao, max(QT_APTOS) aptos1, max(QT_COMPARECIMENTO) comp1
       FROM detalhe_votacao_secao WHERE ANO_ELEICAO=2026 AND NR_TURNO=1 AND DS_CARGO='Presidente' GROUP BY ALL),
m1 AS (SELECT t1.sg_uf, t1.cd_municipio, t1.nr_zona, coalesce(st.sec2, t1.nr_secao) nr_secao,
         sum(o_flavio) o_flavio, sum(o_lula) o_lula, sum(o_cury) o_cury, sum(o_renan) o_renan, sum(o_caiado) o_caiado,
         sum(o_zema) o_zema, sum(o_outros) o_outros, sum(o_branco_nulo) o_branco_nulo, sum(aptos1) aptos1, sum(comp1) comp1
       FROM t1 JOIN a1 USING (sg_uf, cd_municipio, nr_zona, nr_secao)
       LEFT JOIN st USING (sg_uf, cd_municipio, nr_zona, nr_secao) GROUP BY ALL),
v2 AS (SELECT sg_uf, cd_municipio, nr_zona, nr_secao,
         sum(qt_votos) FILTER (WHERE nr_votavel=22) d_22, sum(qt_votos) FILTER (WHERE nr_votavel=13) d_13,
         sum(qt_votos) FILTER (WHERE tipo_voto IN ('branco','nulo')) d_branco_nulo
       FROM bu_2t_votos WHERE cd_cargo=1 GROUP BY ALL),
s2 AS (SELECT sg_uf, cd_municipio, nr_zona, nr_secao, sum(qt_aptos) aptos2, sum(qt_comparecimento) comp2
       FROM bu_2t_secao WHERE cd_cargo=1 GROUP BY ALL)
SELECT * FROM m1 JOIN v2 USING (sg_uf, cd_municipio, nr_zona, nr_secao) JOIN s2 USING (sg_uf, cd_municipio, nr_zona, nr_secao)
WHERE sg_uf <> 'ZZ'
""").df().fillna(0)
con.close()
REG = {"N": "AC AM AP PA RO RR TO", "NE": "AL BA CE MA PB PE PI RN SE", "CO": "DF GO MS MT", "SE": "ES MG RJ SP", "S": "PR RS SC"}
UF2REG = {u: r for r, us in REG.items() for u in us.split()}
base["reg"] = base.sg_uf.map(UF2REG)
base["o_abstencao"] = (base.aptos1 - base.comp1).clip(lower=0)
base["d_abstencao"] = (base.aptos2 - base.comp2).clip(lower=0)
O = ["o_flavio", "o_lula", "o_cury", "o_renan", "o_caiado", "o_zema", "o_outros", "o_branco_nulo", "o_abstencao"]
D = ["d_22", "d_13", "d_branco_nulo", "d_abstencao"]
# consistência: usa o eleitorado do 2T como denominador comum; seções com variação grande de aptos são excluídas
base = base[(base.aptos1 > 20) & ((base.aptos2 - base.aptos1).abs() / base.aptos1 < 0.05)].copy()
base[O] = base[O].div(base[O].sum(1), axis=0); base[D] = base[D].div(base[D].sum(1), axis=0)
base.to_parquet(os.path.join(out, "base_transferencia.parquet"), index=False)
print("seções na análise:", len(base), "| eleitores", int(base.aptos2.sum()), flush=True)

def goodman(df):
    X = df[O].values; Y = df[D].values; w = df.aptos2.values.astype(float)
    w = w / w.sum()
    A = (X * w[:, None]).T @ X; Bm = (X * w[:, None]).T @ Y
    R, C = len(O), len(D)
    f = lambda b: (lambda B: np.trace(B.T @ A @ B) - 2 * np.trace(B.T @ Bm))(b.reshape(R, C))
    g = lambda b: (lambda B: (2 * A @ B - 2 * Bm).ravel())(b.reshape(R, C))
    cons = [{"type": "eq", "fun": (lambda b, r=r: b.reshape(R, C)[r].sum() - 1)} for r in range(R)]
    b0 = np.full(R * C, 1 / C)
    res = minimize(f, b0, jac=g, bounds=[(0, 1)] * (R * C), constraints=cons, method="SLSQP", options={"maxiter": 500, "ftol": 1e-12})
    assert res.success, res.message
    return pd.DataFrame(res.x.reshape(R, C), index=O, columns=D)

rows = []
for nome, df in [("Brasil", base)] + [(r, base[base.reg == r]) for r in REG]:
    B = goodman(df)
    tot = df[O].mul(df.aptos2, axis=0).sum()            # eleitores por origem
    for o in O:
        for d in D:
            rows.append(dict(area=nome, origem=o[2:], destino=d[2:], taxa=B.loc[o, d], eleitores=tot[o] * B.loc[o, d]))
    print(f"\n== {nome}  (seções {len(df):,})"); print((100 * B).round(1).to_string())
res = pd.DataFrame(rows); res.to_csv(os.path.join(out, "goodman.csv"), index=False)
# checagem: totais previstos x observados no 2T
for nome, df in [("Brasil", base)]:
    pred = res[res.area == nome].groupby("destino").eleitores.sum()
    obs = df[D].mul(df.aptos2, axis=0).sum(); obs.index = [i[2:] for i in obs.index]
    print("\nprevisto vs observado (milhões):"); print(pd.DataFrame({"previsto": pred / 1e6, "observado": obs / 1e6}).round(3))
