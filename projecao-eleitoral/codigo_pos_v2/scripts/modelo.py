"""Projeção do 2º turno de 2026 (Presidente) a partir de apuração parcial — replay da noite eleitoral.
Uso: python3 -I modelo.py <duckdb> <saida_dir>

Unidade: seção do 2º turno (seções agregadas somadas na principal).
Alvo: % do 22 (Flávio) nos votos válidos (13+22).
Métodos comparados em cada ponto da apuração:
  parcial   — o que já foi apurado (o que a TV mostra)
  uf        — extrapola a % parcial de cada UF ao eleitorado da UF (projeção "ingênua")
  modelo    — consistência da seção: logit(s2) = f(logit 22/(22+13) no 1T, votos dos eliminados, 2T 2022)
              + efeito hierárquico UF → município estimado só com seções já apuradas (Pavía 2005; Gelman);
              comparecimento previsto pela razão comparecimento 2T/1T do município (encolhida para a UF).
Incerteza do modelo: simulação gaussiana dos efeitos de UF/município não observados + resíduo da seção.
"""
import sys, os, json, numpy as np, pandas as pd, duckdb

dbp, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
con = duckdb.connect(dbp, read_only=True)
K = ["sg_uf", "cd_municipio", "nr_zona", "nr_secao"]
REG = {"N": "AC AM AP PA RO RR TO", "NE": "AL BA CE MA PB PE PI RN SE", "CO": "DF GO MS MT",
       "SE": "ES MG RJ SP", "S": "PR RS SC", "EXT": "ZZ"}
UF2REG = {u: r for r, us in REG.items() for u in us.split()}

# ---------- 1. base por seção ----------
ANO = int(os.environ.get("ANO", "2026"))
DIRMAP = {2002: 45, 2006: 45, 2010: 45, 2014: 45, 2018: 17}
DIRN = lambda a: DIRMAP.get(a, 22)          # número do candidato de direita no 2º turno daquele ano
# eliminados principais = os 4 mais votados no 1T fora 13/22 (regra fixa, igual para qualquer ano)
top4 = [r[0] for r in con.execute(f"""SELECT NR_VOTAVEL FROM votacao_secao WHERE ANO_ELEICAO={ANO} AND NR_TURNO=1
          AND NR_VOTAVEL NOT IN (13,{DIRN(ANO)},95,96) GROUP BY 1 ORDER BY sum(QT_VOTOS) DESC LIMIT 4""").fetchall()]
T4 = ",".join(map(str, top4)); print("eliminados principais", ANO, top4, flush=True)
T1 = f"""t1 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={DIRN(ANO)}) a22, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=13) a13,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL IN ({T4})) a_dir,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL NOT IN ({DIRN(ANO)},13,{T4},95,96)) a_out,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL IN (95,96)) a_bn, sum(QT_VOTOS) comp1
       FROM votacao_secao WHERE ANO_ELEICAO={ANO} AND NR_TURNO=1 GROUP BY ALL)"""
TURNO = int(os.environ.get("TURNO_ALVO", "2"))
GOV_UF = os.environ.get("GOV_UF", "")   # 2º turno de governador numa UF (banco de load_gov.py); alvo = finalista mais votado no 1T
if GOV_UF:
    fin = [r[0] for r in con.execute(f"""SELECT NR_VOTAVEL FROM votacao_secao WHERE ANO_ELEICAO={ANO} AND NR_TURNO=2 AND SG_UF='{GOV_UF}'
             AND NR_VOTAVEL NOT IN (95,96) GROUP BY 1""").fetchall()]
    assert len(fin) == 2, fin
    fin = [r[0] for r in con.execute(f"""SELECT NR_VOTAVEL FROM votacao_secao WHERE ANO_ELEICAO={ANO} AND NR_TURNO=1 AND SG_UF='{GOV_UF}'
             AND NR_VOTAVEL IN ({fin[0]},{fin[1]}) GROUP BY 1 ORDER BY sum(QT_VOTOS) DESC""").fetchall()]
    GA, GB = fin
    top4 = [r[0] for r in con.execute(f"""SELECT NR_VOTAVEL FROM votacao_secao WHERE ANO_ELEICAO={ANO} AND NR_TURNO=1 AND SG_UF='{GOV_UF}'
             AND NR_VOTAVEL NOT IN ({GA},{GB},95,96) GROUP BY 1 ORDER BY sum(QT_VOTOS) DESC LIMIT 4""").fetchall()] or [-1]
    T4 = ",".join(map(str, top4)); print("governador", ANO, GOV_UF, "finalistas", GA, GB, "eliminados", top4, flush=True)
    W = f"ANO_ELEICAO={ANO} AND SG_UF='{GOV_UF}'"
    base = con.execute(f"""
WITH s2 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
              any_value(NR_LOCAL_VOTACAO) nr_local, max(QT_APTOS) aptos2, max(QT_COMPARECIMENTO) comp2
            FROM detalhe_votacao_secao WHERE {W} AND NR_TURNO=2 GROUP BY ALL),
v2 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={GA}) v22, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={GB}) v13
       FROM votacao_secao WHERE {W} AND NR_TURNO=2 GROUP BY ALL),
t1 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={GA}) a22, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={GB}) a13,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL IN ({T4})) a_dir,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL NOT IN ({GA},{GB},{T4},95,96)) a_out,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL IN (95,96)) a_bn, sum(QT_VOTOS) comp1
       FROM votacao_secao WHERE {W} AND NR_TURNO=1 GROUP BY ALL)
SELECT s2.*, v2.v22, v2.v13, NULL::TIMESTAMP t_rec, t1.a22, t1.a13, t1.a_dir, t1.a_out, t1.a_bn, t1.comp1,
       NULL::BIGINT b22, NULL::BIGINT b13
FROM s2 JOIN v2 USING (sg_uf, cd_municipio, nr_zona, nr_secao)
        LEFT JOIN t1 USING (sg_uf, cd_municipio, nr_zona, nr_secao)
""").df()
elif TURNO == 1:
    REF = ANO - 4; DIR = DIRN(REF)
    top4 = [r[0] for r in con.execute(f"""SELECT NR_VOTAVEL FROM votacao_secao WHERE ANO_ELEICAO={REF} AND NR_TURNO=1
          AND NR_VOTAVEL NOT IN (13,{DIR},95,96) GROUP BY 1 ORDER BY sum(QT_VOTOS) DESC LIMIT 4""").fetchall()]
    T4 = ",".join(map(str, top4)); print("alvo 1T", ANO, "histórico", REF, "eliminados", top4, flush=True)
    base = con.execute(f"""
WITH s2 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
              any_value(NR_LOCAL_VOTACAO) nr_local, max(QT_APTOS) aptos2, max(QT_COMPARECIMENTO) comp2
            FROM detalhe_votacao_secao WHERE ANO_ELEICAO={ANO} AND NR_TURNO=1 AND DS_CARGO='Presidente' GROUP BY ALL),
v2 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={DIRN(ANO)}) v22, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=13) v13
       FROM votacao_secao WHERE ANO_ELEICAO={ANO} AND NR_TURNO=1 GROUP BY ALL),
t1 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={DIR}) a22, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=13) a13,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL IN ({T4})) a_dir,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL NOT IN ({DIR},13,{T4},95,96)) a_out,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL IN (95,96)) a_bn, sum(QT_VOTOS) comp1
       FROM votacao_secao WHERE ANO_ELEICAO={REF} AND NR_TURNO=1 GROUP BY ALL),
pr AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
          sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={DIR}) b22, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=13) b13
        FROM votacao_secao WHERE ANO_ELEICAO={REF} AND NR_TURNO=2 GROUP BY ALL)
SELECT s2.*, v2.v22, v2.v13, NULL::TIMESTAMP t_rec, t1.a22, t1.a13, t1.a_dir, t1.a_out, t1.a_bn, t1.comp1,
       pr.b22, pr.b13
FROM s2 JOIN v2 USING (sg_uf, cd_municipio, nr_zona, nr_secao)
        LEFT JOIN t1 USING (sg_uf, cd_municipio, nr_zona, nr_secao)
        LEFT JOIN pr USING (sg_uf, cd_municipio, nr_zona, nr_secao)
""").df()
    if os.environ.get("VIZ", "0") == "1":
        # lição de Israel: seção sem par no histórico herda o perfil da vizinhança —
        # mesmo local de votação na mesma zona → zona → município (partes e comparecimento/aptos)
        ref = con.execute(f"""
WITH d AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
             any_value(NR_LOCAL_VOTACAO) nr_local, max(QT_APTOS) aptos1 FROM detalhe_votacao_secao
           WHERE ANO_ELEICAO={REF} AND NR_TURNO=1 AND CD_CARGO=1 GROUP BY ALL),
{T1.replace("ANO_ELEICAO={ANO}", "ANO_ELEICAO={REF}").replace("NR_VOTAVEL={DIRN(ANO)}", "NR_VOTAVEL={DIR}")},
pr AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
          sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={DIR}) b22, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=13) b13
        FROM votacao_secao WHERE ANO_ELEICAO={REF} AND NR_TURNO=2 GROUP BY ALL)
SELECT d.*, t1.a22, t1.a13, t1.a_dir, t1.a_out, t1.a_bn, t1.comp1, pr.b22, pr.b13
FROM d JOIN t1 USING (sg_uf, cd_municipio, nr_zona, nr_secao) LEFT JOIN pr USING (sg_uf, cd_municipio, nr_zona, nr_secao)""").df().fillna(0)
        F = ["a22", "a13", "a_dir", "a_out", "a_bn", "comp1", "b22", "b13"]
        base["viz"] = 0
        miss = base.comp1.isna()
        print("seções sem par exato no histórico:", f"{miss.mean():.1%}", flush=True)
        for lvl, keys in ((1, ["sg_uf", "cd_municipio", "nr_zona", "nr_local"]), (2, ["sg_uf", "cd_municipio", "nr_zona"]),
                          (3, ["sg_uf", "cd_municipio"])):
            miss = base.comp1.isna()
            if not miss.any(): break
            g = ref.groupby(keys)[F + ["aptos1"]].sum().reset_index()
            m = base.loc[miss, keys + ["aptos2"]].merge(g, on=keys, how="left")
            fac = (m.aptos2 / m.aptos1.replace(0, np.nan)).values       # reescala p/ o tamanho da seção nova
            for c_ in F: base.loc[miss, c_] = (m[c_] * fac).values
            base.loc[miss & base.comp1.notna(), "viz"] = lvl
            print(f"  nível {lvl} {keys[-1]}: preenchidas {(base.viz == lvl).sum():,}", flush=True)
elif ANO == 2026:
    base = con.execute(f"""
WITH st AS (SELECT sg_uf, cd_municipio, nr_zona, nr_secao, status, nr_secao_principal,
                   try_strptime(dr||' '||hr, '%d/%m/%Y %H:%M:%S') AS t_rec FROM bu_2t_status),
v2 AS (SELECT sg_uf, cd_municipio, nr_zona, nr_secao,
         sum(qt_votos) FILTER (WHERE nr_votavel=22) AS v22, sum(qt_votos) FILTER (WHERE nr_votavel=13) AS v13
       FROM bu_2t_votos WHERE cd_cargo=1 GROUP BY ALL),
s2 AS (SELECT sg_uf, cd_municipio, nr_zona, nr_secao, any_value(nr_local) nr_local,
              sum(qt_aptos) aptos2, sum(qt_comparecimento) comp2 FROM bu_2t_secao WHERE cd_cargo=1 GROUP BY ALL),
mp AS (SELECT sg_uf, cd_municipio, nr_zona, nr_secao,
              CASE WHEN status='agregada' THEN nr_secao_principal ELSE nr_secao END AS sec2 FROM st),
{T1},
t1m AS (SELECT t1.sg_uf, t1.cd_municipio, t1.nr_zona, coalesce(mp.sec2, t1.nr_secao) nr_secao,
          sum(a22) a22, sum(a13) a13, sum(a_dir) a_dir, sum(a_out) a_out, sum(a_bn) a_bn, sum(comp1) comp1
        FROM t1 LEFT JOIN mp USING (sg_uf, cd_municipio, nr_zona, nr_secao) GROUP BY ALL),
p22 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
          sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=22) b22, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=13) b13
        FROM votacao_secao WHERE ANO_ELEICAO=2022 AND NR_TURNO=2 GROUP BY ALL)
SELECT s2.*, v2.v22, v2.v13, st.t_rec, t1m.a22, t1m.a13, t1m.a_dir, t1m.a_out, t1m.a_bn, t1m.comp1,
       p22.b22, p22.b13
FROM s2 JOIN v2 USING (sg_uf, cd_municipio, nr_zona, nr_secao)
        JOIN st USING (sg_uf, cd_municipio, nr_zona, nr_secao)
        LEFT JOIN t1m USING (sg_uf, cd_municipio, nr_zona, nr_secao)
        LEFT JOIN p22 USING (sg_uf, cd_municipio, nr_zona, nr_secao)
""").df()
else:   # teste independente: 2º turno de ANO, histórico = 1º turno de ANO + 2º turno de ANO-4
    REF = ANO - 4; DIR = DIRN(REF)
    base = con.execute(f"""
WITH s2 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
              any_value(NR_LOCAL_VOTACAO) nr_local, max(QT_APTOS) aptos2, max(QT_COMPARECIMENTO) comp2
            FROM detalhe_votacao_secao WHERE ANO_ELEICAO={ANO} AND NR_TURNO=2 AND DS_CARGO='Presidente' GROUP BY ALL),
v2 AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
         sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={DIRN(ANO)}) v22, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=13) v13
       FROM votacao_secao WHERE ANO_ELEICAO={ANO} AND NR_TURNO=2 GROUP BY ALL),
{T1},
pr AS (SELECT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
          sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL={DIR}) b22, sum(QT_VOTOS) FILTER (WHERE NR_VOTAVEL=13) b13
        FROM votacao_secao WHERE ANO_ELEICAO={REF} AND NR_TURNO=2 GROUP BY ALL)
SELECT s2.*, v2.v22, v2.v13, NULL::TIMESTAMP t_rec, t1.a22, t1.a13, t1.a_dir, t1.a_out, t1.a_bn, t1.comp1,
       pr.b22, pr.b13
FROM s2 JOIN v2 USING (sg_uf, cd_municipio, nr_zona, nr_secao)
        LEFT JOIN t1 USING (sg_uf, cd_municipio, nr_zona, nr_secao)
        LEFT JOIN pr USING (sg_uf, cd_municipio, nr_zona, nr_secao)
""").df()
CAPITAIS = {"AC": "RIO BRANCO", "AL": "MACEIO", "AM": "MANAUS", "AP": "MACAPA", "BA": "SALVADOR", "CE": "FORTALEZA",
    "DF": "BRASILIA", "ES": "VITORIA", "GO": "GOIANIA", "MA": "SAO LUIS", "MG": "BELO HORIZONTE", "MS": "CAMPO GRANDE",
    "MT": "CUIABA", "PA": "BELEM", "PB": "JOAO PESSOA", "PE": "RECIFE", "PI": "TERESINA", "PR": "CURITIBA",
    "RJ": "RIO DE JANEIRO", "RN": "NATAL", "RO": "PORTO VELHO", "RR": "BOA VISTA", "RS": "PORTO ALEGRE",
    "SC": "FLORIANOPOLIS", "SE": "ARACAJU", "SP": "SAO PAULO", "TO": "PALMAS"}
munnm = con.execute(f"""SELECT DISTINCT SG_UF sg_uf, CD_MUNICIPIO cd_municipio, strip_accents(upper(NM_MUNICIPIO)) nm
   FROM detalhe_votacao_secao WHERE ANO_ELEICAO={ANO} AND CD_CARGO={3 if GOV_UF else 1}""").df()
capm = munnm[munnm.apply(lambda r: CAPITAIS.get(r.sg_uf) == r.nm, axis=1)]
print("capitais encontradas:", len(capm), flush=True)
con.close()

b = base.copy()
for c_ in ("v22", "v13", "b22", "b13"):
    b[c_] = b[c_].fillna(0)
m1 = b.comp1.notna()
for c_ in ("a22", "a13", "a_dir", "a_out", "a_bn"):
    b.loc[m1, c_] = b.loc[m1, c_].fillna(0)
b["reg"] = b.sg_uf.map(UF2REG)
b["mun"] = b.sg_uf + "-" + b.cd_municipio.astype(str)
b["val2"] = b.v22 + b.v13
print("seções com aptos e sem votos válidos (excluídas):", int(((b.val2 == 0) & (b.aptos2 > 0)).sum()), "de", len(b), flush=True)
b = b[b.val2 > 0].sort_values(K).reset_index(drop=True)   # ordem fixa: ordens sorteadas iguais entre execuções
lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
il = lambda x: 1 / (1 + np.exp(-x))
has1 = b.a22.notna() & ((b.a22 + b.a13) > 0) & (b.comp1 > 0)
b["has1"] = has1
b["x1"] = np.where(has1, lg(b.a22 / (b.a22 + b.a13)), 0.0)
b["xdir"] = np.where(has1, (b.a_dir / b.comp1), 0.0)
b["xout"] = np.where(has1, (b.a_out / b.comp1), 0.0)
b["xbn"] = np.where(has1, (b.a_bn / b.comp1), 0.0)
h22 = (b.b22 + b.b13) > 0
b["has22"] = h22
b["x22"] = np.where(h22, lg(b.b22 / (b.b22 + b.b13)), 0.0)
b["y"] = lg(b.v22 / b.val2)
b["comp1f"] = np.where(has1, b.comp1, np.nan)
b["capital"] = (b.sg_uf + "-" + b.cd_municipio.astype(str)).isin(capm.sg_uf + "-" + capm.cd_municipio.astype(str))
b["lmun"] = np.log(b.groupby("mun").aptos2.transform("sum"))
COV = os.environ.get("COV", "")
HIST = os.environ.get("HIST", "")   # história longa por local de votação (hist_longa.py): d = transferência 1T→2T, c = deriva, f = fatores
if HIST:
    H = pd.read_parquet("/home/claude/tse/hist/hist_local.parquet"); H = H[H.ano < ANO]
    KL = ["sg_uf", "cd_municipio", "nr_zona", "nr_local"]
    last = H[H.ano == H.ano.max()][KL + ["dd", "cc"]].rename(columns={"dd": "h_dlast", "cc": "h_clast"})
    g = H.groupby(KL); n = g.dd.count()
    hm = (g.dd.sum() / (n + 1.0)).rename("h_dmean").reset_index()            # média encolhida para 0
    M = H.pivot_table(index=KL, columns="ano", values="dd").fillna(0.0)       # locais × anos: quem se move junto
    Z = (M - M.mean()) / M.std().replace(0, 1)
    U, S, Vt = np.linalg.svd(Z.values, full_matrices=False)
    fac = pd.DataFrame(U[:, :2] * S[:2] / np.sqrt(len(Z)), index=M.index, columns=["h_f1", "h_f2"]).reset_index()
    F = last.merge(hm, on=KL, how="outer").merge(fac, on=KL, how="outer")
    HC = ["h_dlast", "h_clast", "h_dmean", "h_f1", "h_f2"]
    bl = b[KL].copy(); bl["nr_local"] = pd.to_numeric(bl.nr_local, errors="coerce")
    for c_ in ("cd_municipio", "nr_zona"): bl[c_] = bl[c_].astype("int64")
    F["nr_local"] = pd.to_numeric(F.nr_local, errors="coerce")
    for c_ in ("cd_municipio", "nr_zona"): F[c_] = F[c_].astype("int64")
    m1 = bl.merge(F, on=KL, how="left")
    Fz = F.groupby(KL[:3])[HC].mean().reset_index()                           # sem o local: média da zona
    m2 = bl[KL[:3]].merge(Fz, on=KL[:3], how="left")
    for c_ in HC: b[c_] = m1[c_].fillna(m2[c_]).fillna(0.0).values
    b["h_has"] = m1.h_dmean.notna().astype(float).values
    print("história longa: casadas pelo local", round(b.h_has.mean(), 3), flush=True)
if COV:   # perfil do município (Censo 2022): ajuda a transferir a mudança aprendida numa região para outra
    ib = pd.read_parquet("/home/claude/tse/ibge/ibge_mun.parquet")[["codigo_tse", "uf", "alfab_15m", "pib_pc_2023", "pct_evangelica", "pct_branca"]]
    ib = ib.rename(columns={"codigo_tse": "cd_municipio", "uf": "sg_uf"}); ib["cd_municipio"] = ib.cd_municipio.astype(int)
    b = b.merge(ib, on=["sg_uf", "cd_municipio"], how="left")
    for c_, ref_ in (("alfab_15m", None), ("pib_pc_2023", None), ("pct_evangelica", None), ("pct_branca", None)):
        b[c_] = b[c_].fillna(b[c_].median())
    b["c_alf"] = (b.alfab_15m - b.alfab_15m.mean()) / b.alfab_15m.std()
    b["c_pib"] = (np.log(b.pib_pc_2023) - np.log(b.pib_pc_2023).mean()) / np.log(b.pib_pc_2023).std()
    b["c_evg"] = (b.pct_evangelica - b.pct_evangelica.mean()) / b.pct_evangelica.std()
    b["c_bra"] = (b.pct_branca - b.pct_branca.mean()) / b.pct_branca.std()
TRUE = b.v22.sum() / b.val2.sum()
N = len(b)
print(f"seções {N:,} | com 1T {has1.mean():.1%} | com 2022 {h22.mean():.1%} | verdade 22 = {TRUE:.4%}", flush=True)

MUNVIZ = os.environ.get("MUNVIZ", "0") == "1"   # efeito do município previsto pelos municípios vizinhos já apurados
if MUNVIZ:
    from scipy.spatial import cKDTree
    MV_H = float(os.environ.get("MUNVIZ_H", "40"))     # largura do núcleo gaussiano, km
    MV_K = float(os.environ.get("MUNVIZ_K", "200"))    # pseudo-peso da previsão por vizinhos (encolhe para 0)
    MV_N = int(os.environ.get("MUNVIZ_N", "20"))       # vizinhos considerados
    cc = pd.read_parquet("/home/claude/tse/ibge/mun_coord.parquet")
    cc["mun"] = cc.sg_uf + "-" + cc.cd_municipio.astype(int).astype(str)
    MV_MUNS = np.array(sorted(b.mun.unique()))
    xy = pd.DataFrame({"mun": MV_MUNS}).merge(cc[["mun", "lat", "lon"]], on="mun", how="left")
    ok = xy.lat.notna().values
    P = np.column_stack([xy.lat.values * 111.0, xy.lon.values * 111.0 * np.cos(np.deg2rad(xy.lat.values))])
    MV_NB = np.full((len(MV_MUNS), MV_N), -1); MV_KW = np.zeros((len(MV_MUNS), MV_N))
    tree = cKDTree(P[ok]); idx_ok = np.where(ok)[0]
    dd, ii = tree.query(P[ok], k=MV_N + 1)
    MV_NB[ok] = idx_ok[ii[:, 1:]]; MV_KW[ok] = np.exp(-0.5 * (dd[:, 1:] / MV_H) ** 2)
    print(f"MUNVIZ: {ok.mean():.1%} dos municípios com coordenadas; h={MV_H} km, k={MV_K}", flush=True)

FEAT = os.environ.get("FEAT", "v1")
REGH = float(os.environ.get("REGH", "1"))
TAU_UF_S0 = float(os.environ.get("TAU_UF_S0", "0"))   # >0: hiperprior de τ_UF com escala histórica S0 (logit)
TAU_UF_NU = float(os.environ.get("TAU_UF_NU", "5"))   # graus de liberdade = eleições passadas   # multiplicador do ridge nos desvios regionais (FEAT=reg)
TAU_UF_MIN = float(os.environ.get("TAU_UF_MIN", "0"))
ORACLE_T = os.environ.get("ORACLE_T", "0") == "1"
ZONA = os.environ.get("ZONA", "0") == "1"      # nível zona eleitoral dentro do município
TIPO = os.environ.get("TIPO", "0") == "1"      # efeito capital/interior por UF, com incerteza própria
UNC = os.environ.get("UNC", "")                # fontes extras de incerteza: b = coeficientes (sanduíche por município), v = volume por município
HUBER = os.environ.get("HUBER", "0") == "1"    # regressão robusta (IRLS de Huber)   # diagnóstico: usa os válidos reais nas seções não apuradas

def design(d):
    if FEAT == "v2":
        x1c = d.x1 - 0.0
        return np.column_stack([np.ones(len(d)), d.x1, d.xdir, d.xout, d.xbn, d.x22, d.has22.astype(float),
                                d.has1.astype(float), d.capital.astype(float), d.lmun - 10,
                                x1c ** 2, d.xdir * x1c, d.xout * x1c, d.xbn * x1c, d.x22 * x1c,
                                (d.lmun - 10) * x1c, d.capital.astype(float) * x1c])
    cols = [np.ones(len(d)), d.x1, d.xdir, d.xout, d.xbn, d.x22, d.has22.astype(float),
            d.has1.astype(float), d.capital.astype(float), d.lmun - 10]
    if "viz" in d: cols += [(d.viz == 1).astype(float), (d.viz >= 2).astype(float)]
    if HIST:
        cols += [d.h_has] + ([d.h_dlast, d.h_dmean] if "d" in HIST else []) + ([d.h_clast] if "c" in HIST else []) + ([d.h_f1, d.h_f2] if "f" in HIST else [])
    if COV:
        cols += [d.c_alf, d.c_pib, d.c_evg, d.c_bra]
        if "x" in COV: cols += [d.c_alf * d.x1, d.c_evg * d.x1, d.c_bra * d.x1, d.c_pib * d.x1]
    if FEAT == "reg":   # transferência dos eliminados e do branco/nulo varia por região (lição do PyEI)
        for r in ("N", "NE", "CO", "S"):
            dr = (d.reg == r).astype(float)
            cols += [dr, d.xdir * dr, d.xout * dr, d.xbn * dr, d.x1 * dr]
    return np.column_stack(cols)

def shrink(resid, w, groups, k):
    """média ponderada por grupo encolhida para 0 com pseudo-peso k (empirical Bayes simples)."""
    df = pd.DataFrame({"g": groups, "rw": resid * w, "w": w})
    s = df.groupby("g").agg(rw=("rw", "sum"), w=("w", "sum"))
    return (s.rw / (s.w + k)), s.w

TAU_G = float(os.environ.get("TAU_G", "0.03"))
SD_SCALES = [float(x) for x in os.environ.get("SD_SCALES", "").split(",") if x]   # calibração: escalas extras do ruído
HP = {"kuf": float(os.environ.get("KUF", "400")), "kmu": float(os.environ.get("KMU", "60")),
      "kc": float(os.environ.get("KC", "3000")), "wpow": float(os.environ.get("WPOW", "0.5")),
      "ridge": float(os.environ.get("RIDGE_SEC", "0")),
      "radapt": float(os.environ.get("RIDGE_ADAPT", "0"))}   # >0: ridge efetivo = ridge * k/(k + seções apuradas)   # sd (logit) de um desvio comum a todo o não apurado

def project(rep, sims=int(os.environ.get("SIMS", "300")), rng=np.random.default_rng(0)):
    R, U = b[rep], b[~rep]
    out = {"parcial": R.v22.sum() / R.val2.sum()}
    # --- uf ingênuo: % parcial da UF × eleitores válidos esperados da UF (aptos × comparecimento parcial)
    tot = 0; t22 = 0; nat = out["parcial"]
    for uf, g in b.groupby("sg_uf"):
        r = g[rep[g.index]]
        share = r.v22.sum() / r.val2.sum() if len(r) else nat
        vrate = r.val2.sum() / r.aptos2.sum() if len(r) else R.val2.sum() / R.aptos2.sum()
        v = g.aptos2.sum() * vrate
        tot += v; t22 += v * share
    out["uf"] = t22 / tot
    # --- modelo
    w = R.val2.values.astype(float) ** HP["wpow"]   # peso das seções (0,5 = raiz dos votos)
    w = w * (np.sqrt(R.val2.values).mean() / w.mean())   # mesma escala média da raiz, p/ os k serem comparáveis
    X = design(R); y = R.y.values
    rid = HP["ridge"] * (HP["radapt"] / (HP["radapt"] + len(R)) if HP["radapt"] > 0 else 1.0)
    if rid > 0:   # ridge rumo à mudança uniforme: coef. 1 no logit do 1T, 0 no resto, intercepto livre
        kx = X.shape[1]; b0 = np.zeros(kx); b0[1] = 1.0
        lam = np.full(kx, rid * (w ** 2).mean()); lam[0] = 0.0
        if FEAT == "reg": lam[-20:] *= REGH   # coeficientes regionais = nacional + desvio encolhido para 0
        A = np.vstack([X * w[:, None], np.diag(np.sqrt(lam))]); yy = np.concatenate([y * w, np.sqrt(lam) * b0])
        beta = np.linalg.lstsq(A, yy, rcond=None)[0]
    else:
        beta = np.linalg.lstsq(X * w[:, None], y * w, rcond=None)[0]
    if HUBER:
        for _ in range(5):
            r_ = y - X @ beta; sc = 1.4826 * np.median(np.abs(r_)) + 1e-9
            hw = np.minimum(1, 1.345 * sc / (np.abs(r_) + 1e-12)); ww = w * np.sqrt(hw)
            beta = np.linalg.lstsq(X * ww[:, None], y * ww, rcond=None)[0]
    res = y - X @ beta
    kuf, kmu = HP["kuf"], HP["kmu"]                # pseudo-pesos do encolhimento
    euf, wuf = shrink(res, w, R.sg_uf.values, kuf)
    res2 = res - R.sg_uf.map(euf).values
    gtR = (R.sg_uf + np.where(R.capital, "-C", "-I")).values
    if TIPO:
        etp, wtp = shrink(res2, w, gtR, kuf)
        res2 = res2 - pd.Series(gtR).map(etp).values
    emu, wmu = shrink(res2, w, R.mun.values, kmu)
    if MUNVIZ:   # previsão por vizinhos: média ponderada por núcleo dos efeitos brutos dos vizinhos apurados; vira a média a priori
        rwm = (emu * (wmu + kmu)).reindex(MV_MUNS).fillna(0).values; wm = wmu.reindex(MV_MUNS).fillna(0).values
        nb = MV_NB; valid = nb >= 0; nbc = np.where(valid, nb, 0)
        num = (MV_KW * rwm[nbc] * valid).sum(1); den = (MV_KW * wm[nbc] * valid).sum(1)
        pred = pd.Series(num / (den + MV_K), index=MV_MUNS)
        emu = (emu * (wmu + kmu) + kmu * pred.reindex(emu.index)) / (wmu + kmu)
        emu = pd.concat([emu, pred.drop(emu.index, errors="ignore")])   # municípios não apurados: a previsão
    res3 = res2 - R.mun.map(emu).fillna(0).values
    gzR = (R.mun + "-" + R.nr_zona.astype(str)).values
    if ZONA:
        ezo, wzo = shrink(res3, w, gzR, kmu)
        res3 = res3 - pd.Series(gzR).map(ezo).values
    s_sec = np.sqrt(np.average(res3 ** 2, weights=w))
    # variâncias dos efeitos (método dos momentos, grosseiro)
    tau_uf = max(np.sqrt(max(np.average(euf.values ** 2) , 1e-6)), 0.02, TAU_UF_MIN)
    if TAU_UF_S0 > 0:   # hiperprior qui-quadrado inverso escalado: histórico (S0, NU eleições) + efeitos de UF já estimados
        rel = (wuf / (wuf + kuf)).reindex(euf.index).fillna(0); raw = euf / rel.where(rel > 0)
        n_eff = float(rel.sum()); m2 = float((rel * raw.fillna(0) ** 2).sum() / n_eff) if n_eff > 0 else 0.0
        tau_uf = max(np.sqrt((TAU_UF_NU * TAU_UF_S0 ** 2 + n_eff * m2) / (TAU_UF_NU + n_eff)), 0.02)
    tau_mu = max(np.sqrt(np.average(emu.reindex(wmu.index).values ** 2)), 0.02)
    XU = design(U)
    fu = U.sg_uf.map(euf); fm = U.mun.map(emu)
    mu = XU @ beta + fu.fillna(0).values + fm.fillna(0).values
    gtU = (U.sg_uf + np.where(U.capital, "-C", "-I")).values
    gzU = (U.mun + "-" + U.nr_zona.astype(str)).values
    if TIPO: mu = mu + pd.Series(gtU).map(etp).fillna(0).values
    if ZONA: mu = mu + pd.Series(gzU).map(ezo).fillna(0).values
    # comparecimento: válidos 2T ≈ comp1 × razão do município (encolhida p/ UF; fallback aptos × taxa da UF)
    R1 = R[R.has1]
    ruf = (R1.groupby("sg_uf").val2.sum() / R1.groupby("sg_uf").comp1.sum())
    rnat = R1.val2.sum() / R1.comp1.sum()
    gm = R1.groupby("mun").agg(v=("val2", "sum"), c=("comp1", "sum"), uf=("sg_uf", "first"))
    kc = HP["kc"]
    rm = (gm.v + kc * gm.uf.map(ruf)) / (gm.c + kc)
    rr = U.mun.map(rm).fillna(U.sg_uf.map(ruf)).fillna(rnat).values
    aprate = R.val2.sum() / R.aptos2.sum()
    vU = np.where(U.has1, U.comp1f.fillna(0) * rr, U.aptos2 * aprate)
    if ORACLE_T: vU = U.val2.values.astype(float)
    # --- referências simples, com o mesmo volume vU: mudança uniforme nacional e por UF × capital/interior
    hR = R.has1.values; dR = (R.y - R.x1).values; wR = R.val2.values.astype(float)
    d_nat = np.average(dR[hR], weights=wR[hR]) if hR.any() else 0.0
    gR = (R.sg_uf + np.where(R.capital, "-C", "-I")).values
    dg = pd.DataFrame({"g": gR[hR], "dw": dR[hR] * wR[hR], "w": wR[hR]}).groupby("g").sum()
    dg = dg.dw / dg.w
    gU2 = pd.Series((U.sg_uf + np.where(U.capital, "-C", "-I")).values)
    hU = U.has1.values; p_parc = R.v22.sum() / R.val2.sum()
    for nome, sh in (("swing", np.full(len(U), d_nat)), ("swing_ufcap", gU2.map(dg).fillna(d_nat).values)):
        pU = np.where(hU, il(U.x1.values + sh), p_parc)
        out[nome] = (R.v22.sum() + (vU * pU).sum()) / (R.val2.sum() + vU.sum())
    # pontual
    p = il(mu)
    out["modelo"] = (R.v22.sum() + (vU * p).sum()) / (R.val2.sum() + vU.sum())
    # simulação
    ufs = U.sg_uf.values; muns = U.mun.values
    uf_codes, uf_idx = np.unique(ufs, return_inverse=True)
    mu_codes, mu_idx = np.unique(muns, return_inverse=True)
    # incerteza do efeito: sem dados -> tau; com dados -> tau * k/(w+k)
    uf_sd = np.array([tau_uf * (kuf / (wuf.get(u, 0) + kuf)) ** 0.5 for u in uf_codes])
    mu_sd = np.array([tau_mu * (kmu / (wmu.get(m, 0) + kmu)) ** 0.5 for m in mu_codes])
    if TIPO:
        tp_codes, tp_idx = np.unique(gtU, return_inverse=True)
        tau_tp = max(np.sqrt(np.average(etp.values ** 2)) if len(etp) else 0, TAU_UF_MIN)
        tp_sd = np.array([tau_tp * (kuf / (wtp.get(g, 0) + kuf)) ** 0.5 for g in tp_codes])
    # incerteza extra (revisão externa): coeficientes, volume e zona
    if "b" in UNC:
        lamv = (np.full(X.shape[1], rid * (w ** 2).mean()) if rid > 0 else np.zeros(X.shape[1])); lamv[0] = 0.0
        if FEAT == "reg" and rid > 0: lamv[-20:] *= REGH
        Binv = np.linalg.pinv((X * (w ** 2)[:, None]).T @ X + np.diag(lamv))
        Sg = pd.DataFrame(X * (w ** 2 * res)[:, None]).groupby(R.mun.values).sum().values   # escores somados por município
        Vb = Binv @ (Sg.T @ Sg) @ Binv
        ev, evec = np.linalg.eigh((Vb + Vb.T) / 2); Lb = evec * np.sqrt(np.clip(ev, 0, None))
    if "v" in UNC:
        lr = np.log((gm.v / gm.c).clip(lower=1e-6)) - np.log(gm.uf.map(ruf))
        tau_v = max(np.sqrt(np.average(lr ** 2, weights=gm.c)), 0.01)
        v_sd = np.array([tau_v * (kc / (gm.c.get(m, 0) + kc)) ** 0.5 for m in mu_codes])
    if ZONA:
        zo_codes, zo_idx = np.unique(gzU, return_inverse=True)
        tau_zo = max(np.sqrt(np.average(ezo.values ** 2)) if len(ezo) else 0, 0.02)
        zo_sd = np.array([tau_zo * (kmu / (wzo.get(g, 0) + kmu)) ** 0.5 for g in zo_codes])
    sims_v = [out["modelo"]] if sims == 0 else []
    sims_s = {s: [] for s in SD_SCALES}          # mesma simulação com o ruído multiplicado por s (calibração da faixa)
    for _ in range(sims):
        z = rng.standard_normal() * TAU_G + (rng.standard_normal(len(uf_codes)) * uf_sd)[uf_idx] + (rng.standard_normal(len(mu_codes)) * mu_sd)[mu_idx] \
               + rng.standard_normal(len(U)) * s_sec \
               + ((rng.standard_normal(len(tp_codes)) * tp_sd)[tp_idx] if TIPO else 0) \
               + ((rng.standard_normal(len(zo_codes)) * zo_sd)[zo_idx] if ZONA else 0)
        if "b" in UNC: z = z + XU @ (Lb @ rng.standard_normal(Lb.shape[1]))
        vUs = vU * np.exp((rng.standard_normal(len(mu_codes)) * v_sd)[mu_idx]) if "v" in UNC else vU
        sims_v.append((R.v22.sum() + (vUs * il(mu + z)).sum()) / (R.val2.sum() + vUs.sum()))
        for s in SD_SCALES:
            sims_s[s].append((R.v22.sum() + (vU * il(mu + s * z)).sum()) / (R.val2.sum() + vU.sum()))
    out["lo"], out["hi"] = np.percentile(sims_v, [5, 95])
    for s in SD_SCALES:
        if sims_s[s]: out[f"lo_{s}"], out[f"hi_{s}"] = np.percentile(sims_s[s], [5, 95])
    return out

# ---------- 2. ordens de chegada ----------
rng = np.random.default_rng(42)
orders = {}
if os.environ.get("ORDEM_REAL"):
    o = pd.read_csv(os.environ["ORDEM_REAL"], parse_dates=["t_real"])
    tr = b[K].merge(o, on=K, how="left").t_real
    orders["real"] = tr.fillna(tr.max()).rank(method="first").values
if b.t_rec.notna().any():
    orders["proxy_repositorio"] = b.t_rec.rank(method="first").values
orders |= {
    "aleatoria": rng.permutation(N),
    "nordeste_primeiro": (b.reg.map({"NE": 0, "N": 1, "CO": 2, "SE": 3, "S": 4, "EXT": 5}) * N + rng.permutation(N)).rank(method="first").values,
    "sul_sudeste_primeiro": (b.reg.map({"S": 0, "SE": 1, "CO": 2, "N": 3, "NE": 4, "EXT": 5}) * N + rng.permutation(N)).rank(method="first").values,
    "capitais_primeiro": ((~b.capital).astype(int) * N + rng.permutation(N)).rank(method="first").values,
}
if os.environ.get("ORDENS"):
    orders = {k: v for k, v in orders.items() if k in os.environ["ORDENS"].split(",")}
CK = [0.001, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.6776, 0.75, 0.90]
rows = []
for name, o in orders.items():
    for f in CK:
        rep = pd.Series(o <= f * N, index=b.index)
        if rep.sum() < 50 or (~rep).sum() < 1: continue
        r = project(rep)
        rows.append(dict(ordem=name, pct_secoes=f, **{k: v * 100 for k, v in r.items()}))
        print(name, f, {k: round(v * 100, 2) for k, v in r.items()}, flush=True)
res = pd.DataFrame(rows)
res["verdade"] = TRUE * 100
for m in ("parcial", "uf", "swing", "swing_ufcap", "modelo"):
    res[f"erro_{m}"] = res[m] - res.verdade
res["cobre"] = (res.lo <= res.verdade) & (res.verdade <= res.hi)
res.to_csv(os.path.join(out, "replay.csv"), index=False)
json.dump({"ano": ANO, "eliminados": top4, "verdade_22": TRUE * 100, "n_secoes": int(N), "ufs": sorted(b.sg_uf.unique().tolist())},
          open(os.path.join(out, "meta.json"), "w"))
print(res.groupby("ordem")[["erro_parcial", "erro_uf", "erro_modelo"]].apply(lambda d: d.abs().mean()).round(2))
print("cobertura 90%:", res.cobre.mean())
