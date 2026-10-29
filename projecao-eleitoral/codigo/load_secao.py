"""Carrega as bases por seção eleitoral do TSE no mesmo DuckDB.
Uso: python3 -I load_secao.py <raw_dir> <db_path>
  votacao_secao          <- votacao_secao_<ano>_BR/*.csv      (Presidente, votos por seção x votável)
  detalhe_votacao_secao  <- detalhe_votacao_secao_<ano>/*_BRASIL.csv (aptos, comparecimento, brancos, nulos por seção x cargo)
"""
import sys, glob, os, duckdb

raw, db = sys.argv[1], sys.argv[2]
con = duckdb.connect(db)
INT = {'ANO_ELEICAO','NR_TURNO','NR_ZONA','NR_SECAO','CD_CARGO','CD_MUNICIPIO',
       'NR_VOTAVEL','CD_ELEICAO','NR_LOCAL_VOTACAO'}

sources = {
    "votacao_secao": "votacao_secao_*_BR/votacao_secao_*_BR.csv",
    "detalhe_votacao_secao": "detalhe_votacao_secao_*/detalhe_votacao_secao_*_BRASIL.csv",
}
for tbl, pat in sources.items():
    files = sorted(glob.glob(os.path.join(raw, pat)))
    print(tbl, [os.path.basename(f) for f in files])
    con.execute(f"""CREATE OR REPLACE TABLE {tbl} AS SELECT * FROM read_csv({files!r},
        delim=';', header=true, quote='"', encoding='latin-1', union_by_name=true,
        all_varchar=true, nullstr=['#NULO#','#NE#','#NULO','#NE'])""")
    cols = [r[0] for r in con.execute(f"DESCRIBE {tbl}").fetchall()]
    sel = []
    for c in cols:
        if c.startswith('QT_') or c in INT:
            sel.append(f"TRY_CAST({c} AS BIGINT) AS {c}")
        elif c.startswith('DT_'):
            sel.append(f"TRY_STRPTIME({c}, '%d/%m/%Y')::DATE AS {c}")
        elif c.startswith('VR_') or c.startswith('PC_'):
            sel.append(f"TRY_CAST(REPLACE({c}, ',', '.') AS DOUBLE) AS {c}")
        else:
            sel.append(c)
    con.execute(f"CREATE OR REPLACE TABLE {tbl} AS SELECT {', '.join(sel)} FROM {tbl}")
    print(con.execute(f"SELECT ANO_ELEICAO, NR_TURNO, count(*) FROM {tbl} GROUP BY ALL ORDER BY 1,2").fetchall())
con.close()
