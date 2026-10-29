"""Carrega correspondências esperadas (seção -> urna) do 2º turno 2026.
Uso: python3 -I load_cesp.py <cesp_raw_dir> <db_path>"""
import sys, os, duckdb
raw, db = sys.argv[1], sys.argv[2]
con = duckdb.connect(db)
for tbl, pre in (("corresp_esperada_secao","csec"), ("corresp_esperada_contingencia","ccont")):
    pat = os.path.join(raw, "*", f"{pre}_2t_*.csv")
    con.execute(f"""CREATE OR REPLACE TABLE {tbl} AS
      SELECT TRY_STRPTIME(DT_GERACAO,'%d/%m/%Y')::DATE AS DT_GERACAO, * EXCLUDE (DT_GERACAO),
             2 AS NR_TURNO, regexp_extract(filename,'_(\\d{{12}})\\.csv$',1) AS VERSAO_ARQUIVO
      FROM read_csv('{pat}', delim=';', header=true, quote='"', encoding='latin-1',
                    all_varchar=true, filename=true)""")
    for c in ('AA_ELEICAO','NR_ZONA','NR_SECAO','NR_LOCAL_VOTACAO','NR_URNA_ESPERADA'):
        cols=[r[0] for r in con.execute(f"DESCRIBE {tbl}").fetchall()]
        if c in cols:
            con.execute(f"ALTER TABLE {tbl} ALTER {c} TYPE BIGINT USING TRY_CAST({c} AS BIGINT)")
    con.execute(f"ALTER TABLE {tbl} DROP COLUMN filename")
    print(tbl, con.execute(f"SELECT DT_GERACAO, count(*), sum((ST_CORRESP_ALTERADA='S')::INT) FROM {tbl} GROUP BY 1 ORDER BY 1").fetchall())
con.close()
