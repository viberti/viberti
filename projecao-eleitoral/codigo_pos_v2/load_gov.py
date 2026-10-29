"""Carrega votos por seção e detalhe por seção do cargo de Governador (CD_CARGO=3), 1º e 2º turnos, num DuckDB.
Uso: python3 -I load_gov.py <zips_dir> <db> <ano> [<ano>...]"""
import sys, os, zipfile, tempfile, shutil, duckdb
zd, dbp, anos = sys.argv[1], sys.argv[2], sys.argv[3:]
con = duckdb.connect(dbp)
INT = {'ANO_ELEICAO', 'NR_TURNO', 'NR_ZONA', 'NR_SECAO', 'CD_CARGO', 'CD_MUNICIPIO', 'NR_VOTAVEL', 'NR_LOCAL_VOTACAO'}
KEEP = {"votacao_secao": ["ANO_ELEICAO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
                          "NR_LOCAL_VOTACAO", "CD_CARGO", "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS"],
        "detalhe_votacao_secao": ["ANO_ELEICAO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
                                  "NR_LOCAL_VOTACAO", "CD_CARGO", "QT_APTOS", "QT_COMPARECIMENTO"]}
def typed(cols):
    return ", ".join(f"TRY_CAST({c} AS BIGINT) AS {c}" if (c.startswith('QT_') or c in INT) else c for c in cols)
for ano in anos:
    for tbl, zname, pick in (("votacao_secao", f"votacao_secao_{ano}_BR.zip", "_BR.csv"),
                             ("detalhe_votacao_secao", f"detalhe_votacao_secao_{ano}.zip", "_BRASIL.csv")):
        tmp = tempfile.mkdtemp(dir="/home/claude/tse")
        z = zipfile.ZipFile(os.path.join(zd, zname)); nm = [n for n in z.namelist() if n.endswith(pick)][0]
        z.extract(nm, tmp); f = os.path.join(tmp, nm)
        con.execute(f"""CREATE OR REPLACE TEMP TABLE t AS SELECT * FROM read_csv('{f}', delim=';', header=true,
            quote='"', encoding='latin-1', all_varchar=true, nullstr=['#NULO#','#NE#','#NULO','#NE'])
            WHERE TRY_CAST(CD_CARGO AS INT)=3""")
        cols = [c for c in KEEP[tbl] if c in [r[0] for r in con.execute("DESCRIBE t").fetchall()]]
        sel = f"SELECT {typed(cols)} FROM t"
        exists = con.execute(f"SELECT count(*) FROM information_schema.tables WHERE table_name='{tbl}'").fetchone()[0]
        if exists: con.execute(f"INSERT INTO {tbl} BY NAME {sel}")
        else: con.execute(f"CREATE TABLE {tbl} AS {sel}")
        shutil.rmtree(tmp)
        print(ano, tbl, con.execute(f"SELECT NR_TURNO, count(*), count(DISTINCT SG_UF) FROM {tbl} WHERE ANO_ELEICAO={ano} GROUP BY 1 ORDER BY 1").fetchall(), flush=True)
con.close()
