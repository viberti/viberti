"""Carrega os CSVs consolidados (_BRASIL) do TSE em um banco DuckDB.
Uso: python3 -I load_tse.py <raw_dir> <db_path>
"""
import sys, glob, os, duckdb

raw, db = sys.argv[1], sys.argv[2]
con = duckdb.connect(db)

families = [
    "votacao_candidato_munzona",
    "votacao_partido_munzona",
    "detalhe_votacao_munzona",
    "consulta_cand",
    "consulta_coligacao",
    "consulta_vagas",
]

for fam in families:
    files = sorted(glob.glob(os.path.join(raw, f"{fam}_*", f"{fam}_*_BRASIL.csv")))
    if not files:
        print("SKIP", fam); continue
    con.execute(f"DROP TABLE IF EXISTS {fam}")
    con.execute(f"""
        CREATE TABLE {fam} AS
        SELECT * FROM read_csv({files!r},
            delim=';', header=true, quote='"', encoding='latin-1',
            union_by_name=true, all_varchar=true,
            nullstr=['#NULO#','#NE#','#NULO','#NE'] )
    """)
    # tipagem: contagens (QT_*), ano, turno -> inteiro; datas DT_* -> DATE
    cols = [r[0] for r in con.execute(f"DESCRIBE {fam}").fetchall()]
    sel = []
    for c in cols:
        if c.startswith('QT_') or c in ('ANO_ELEICAO','NR_TURNO','NR_ZONA','CD_CARGO','CD_MUNICIPIO','NR_CANDIDATO','NR_PARTIDO','CD_ELEICAO'):
            sel.append(f"TRY_CAST({c} AS BIGINT) AS {c}")
        elif c.startswith('DT_') :
            sel.append(f"TRY_STRPTIME({c}, '%d/%m/%Y')::DATE AS {c}")
        elif c.startswith('VR_') or c.startswith('PC_'):
            sel.append(f"TRY_CAST(REPLACE({c}, ',', '.') AS DOUBLE) AS {c}")
        else:
            sel.append(c)
    con.execute(f"CREATE OR REPLACE TABLE {fam} AS SELECT {', '.join(sel)} FROM {fam}")
    n = con.execute(f"SELECT count(*) FROM {fam}").fetchone()[0]
    yrs = con.execute(f"SELECT ANO_ELEICAO, count(*) FROM {fam} GROUP BY 1 ORDER BY 1").fetchall()
    print(f"{fam:30s} {n:>12,} rows  {yrs}")

con.close()
