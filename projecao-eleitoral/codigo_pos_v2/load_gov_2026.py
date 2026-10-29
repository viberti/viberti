"""2º turno de governador de 2026 no banco de governador: detalhe e votos vindos dos BUs decodificados (tse_2026.duckdb).
Depois de rodar, load_gov_uf.py 2026 baixa o 1º turno das mesmas UFs; em seguida, este script com --agrega soma no
1º turno as seções agregadas no 2º à seção principal (como no modelo presidencial).
Uso: python3 -I load_gov_2026.py <db_gov> [--agrega]"""
import sys, duckdb
dbp = sys.argv[1]; con = duckdb.connect(dbp)
con.execute("ATTACH '/home/claude/tse/tse_2026.duckdb' AS p (READ_ONLY)")
if "--agrega" not in sys.argv:
    con.execute("DELETE FROM detalhe_votacao_secao WHERE ANO_ELEICAO=2026 AND NR_TURNO=2")
    con.execute("""INSERT INTO detalhe_votacao_secao BY NAME
        SELECT 2026 ANO_ELEICAO, 2 NR_TURNO, sg_uf SG_UF, cd_municipio CD_MUNICIPIO, NULL NM_MUNICIPIO, nr_zona NR_ZONA, nr_secao NR_SECAO,
               any_value(nr_local) NR_LOCAL_VOTACAO, 3 CD_CARGO, sum(qt_aptos) QT_APTOS, sum(qt_comparecimento) QT_COMPARECIMENTO
        FROM p.bu_2t_secao WHERE cd_cargo=3 GROUP BY ALL""")
    con.execute("DELETE FROM votacao_secao WHERE ANO_ELEICAO=2026 AND NR_TURNO=2")
    con.execute("""INSERT INTO votacao_secao BY NAME
        SELECT 2026 ANO_ELEICAO, 2 NR_TURNO, sg_uf SG_UF, cd_municipio CD_MUNICIPIO, nr_zona NR_ZONA, nr_secao NR_SECAO, 3 CD_CARGO,
               CASE tipo_voto WHEN 'branco' THEN 95 WHEN 'nulo' THEN 96 ELSE nr_votavel::BIGINT END NR_VOTAVEL, sum(qt_votos) QT_VOTOS
        FROM p.bu_2t_votos WHERE cd_cargo=3 GROUP BY ALL""")
    # nomes de município para achar as capitais
    con.execute("""UPDATE detalhe_votacao_secao d SET NM_MUNICIPIO = m.nm FROM
        (SELECT DISTINCT SG_UF, CD_MUNICIPIO, NM_MUNICIPIO nm FROM detalhe_votacao_secao WHERE ANO_ELEICAO=2026 AND NR_TURNO=1) m
        WHERE d.ANO_ELEICAO=2026 AND d.NR_TURNO=2 AND d.SG_UF=m.SG_UF AND d.CD_MUNICIPIO=m.CD_MUNICIPIO""")
else:
    con.execute("""CREATE OR REPLACE TEMP TABLE mp AS SELECT sg_uf, cd_municipio, nr_zona, nr_secao, nr_secao_principal
        FROM p.bu_2t_status WHERE status='agregada'""")
    n = con.execute("""UPDATE votacao_secao v SET NR_SECAO = mp.nr_secao_principal FROM mp
        WHERE v.ANO_ELEICAO=2026 AND v.NR_TURNO=1 AND v.SG_UF=mp.sg_uf AND v.CD_MUNICIPIO=mp.cd_municipio
          AND v.NR_ZONA=mp.nr_zona AND v.NR_SECAO=mp.nr_secao""").fetchall()
    print("linhas do 1T reatribuídas à seção principal:", n, flush=True)
print(con.execute("""SELECT NR_TURNO, count(*), count(DISTINCT SG_UF) FROM votacao_secao WHERE ANO_ELEICAO=2026 GROUP BY 1""").fetchall())
con.close()
