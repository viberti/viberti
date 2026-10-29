"""Carrega votacao_secao (Presidente) e detalhe_votacao_secao de anos antigos num DuckDB separado.
Uso: python3 -I load_hist.py <zips_dir> <db> <ano> [<ano>...]"""
import sys, os, zipfile, tempfile, shutil, duckdb
zd, dbp, anos = sys.argv[1], sys.argv[2], sys.argv[3:]
con = duckdb.connect(dbp)
INT = {'ANO_ELEICAO','NR_TURNO','NR_ZONA','NR_SECAO','CD_CARGO','CD_MUNICIPIO','NR_VOTAVEL','CD_ELEICAO','NR_LOCAL_VOTACAO'}
def typed(cols):
    out = []
    for c in cols:
        if c.startswith('QT_') or c in INT: out.append(f"TRY_CAST({c} AS BIGINT) AS {c}")
        elif c.startswith('DT_'): out.append(f"TRY_STRPTIME({c}, '%d/%m/%Y')::DATE AS {c}")
        else: out.append(c)
    return ", ".join(out)
for ano in anos:
    for tbl, zname, pick in (("votacao_secao", f"votacao_secao_{ano}_BR.zip", "_BR.csv"),
                             ("detalhe_votacao_secao", f"detalhe_votacao_secao_{ano}.zip", "_BRASIL.csv")):
        tmp = tempfile.mkdtemp(dir="/home/claude/tse")
        z = zipfile.ZipFile(os.path.join(zd, zname)); nm = [n for n in z.namelist() if n.endswith(pick)][0]
        z.extract(nm, tmp); f = os.path.join(tmp, nm)
        con.execute(f"""CREATE OR REPLACE TEMP TABLE t AS SELECT * FROM read_csv('{f}', delim=';', header=true,
            quote='"', encoding='latin-1', all_varchar=true, nullstr=['#NULO#','#NE#','#NULO','#NE'])""")
        cols = [r[0] for r in con.execute("DESCRIBE t").fetchall()]
        where = "WHERE TRY_CAST(CD_CARGO AS INT)=1" if "CD_CARGO" in cols else ""
        sel = f"SELECT {typed(cols)} FROM t {where}"
        exists = con.execute(f"SELECT count(*) FROM information_schema.tables WHERE table_name='{tbl}'").fetchone()[0]
        if exists: con.execute(f"INSERT INTO {tbl} BY NAME {sel}")
        else: con.execute(f"CREATE TABLE {tbl} AS {sel}")
        shutil.rmtree(tmp)
        print(ano, tbl, con.execute(f"SELECT NR_TURNO, count(*) FROM {tbl} WHERE ANO_ELEICAO={ano} GROUP BY 1 ORDER BY 1").fetchall(), flush=True)
con.close()
