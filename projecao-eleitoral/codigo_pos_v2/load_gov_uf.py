"""Baixa votacao_secao_<ano>_<UF>.zip das UFs com 2º turno de governador e carrega só o cargo 3 (1º e 2º turnos).
As UFs vêm do detalhe por seção já carregado (load_gov.py). Apaga cada zip depois de carregar.
Uso: python3 -I load_gov_uf.py <db> <ano> [<ano>...]"""
import sys, io, os, zipfile, tempfile, shutil, subprocess, duckdb
dbp, anos = sys.argv[1], sys.argv[2:]
con = duckdb.connect(dbp)
URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_{a}_{u}.zip"
COLS = ["ANO_ELEICAO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_LOCAL_VOTACAO",
        "CD_CARGO", "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS"]
INT = {'ANO_ELEICAO', 'NR_TURNO', 'NR_ZONA', 'NR_SECAO', 'CD_CARGO', 'CD_MUNICIPIO', 'NR_VOTAVEL', 'NR_LOCAL_VOTACAO', 'QT_VOTOS'}
for ano in anos:
    ufs = [r[0] for r in con.execute(f"SELECT DISTINCT SG_UF FROM detalhe_votacao_secao WHERE ANO_ELEICAO={ano} AND NR_TURNO=2 ORDER BY 1").fetchall()]
    print(ano, "UFs com 2º turno:", ufs, flush=True)
    for u in ufs:
        if con.execute(f"SELECT count(*) FROM information_schema.tables WHERE table_name='votacao_secao'").fetchone()[0] and \
           con.execute(f"SELECT count(*) FROM votacao_secao WHERE ANO_ELEICAO={ano} AND SG_UF='{u}' AND NR_TURNO=1").fetchone()[0]:
            print("  já carregada", u, flush=True); continue
        tmp = tempfile.mkdtemp(dir="/home/claude/tse"); zp = os.path.join(tmp, "z.zip")
        r = subprocess.run(["curl", "-sS", "-f", "-o", zp, URL.format(a=ano, u=u)])
        if r.returncode: print("  falhou download", u, flush=True); shutil.rmtree(tmp); continue
        z = zipfile.ZipFile(zp); nms = [n for n in z.namelist() if n.lower().endswith(".csv")]
        for nm in nms:
            # filtra o cargo 3 lendo o CSV do zip em fluxo (os arquivos de SP e MG passam de vários GB)
            f = os.path.join(tmp, "f.csv")
            with z.open(nm) as src, open(f, "w", encoding="latin-1") as dst:
                it = io.TextIOWrapper(src, encoding="latin-1", newline="")
                head = next(it); dst.write(head); ic = [h.strip('"') for h in head.rstrip("\r\n").split(";")].index("CD_CARGO")
                for ln in it:
                    if ln.split(";", ic + 1)[ic].strip('"') == "3": dst.write(ln)
            con.execute(f"""CREATE OR REPLACE TEMP TABLE t AS SELECT * FROM read_csv('{f}', delim=';', header=true,
                quote='"', encoding='latin-1', all_varchar=true, nullstr=['#NULO#','#NE#','#NULO','#NE'])
                WHERE TRY_CAST(CD_CARGO AS INT)=3""")
            have = [c[0] for c in con.execute("DESCRIBE t").fetchall()]
            sel = "SELECT " + ", ".join((f"TRY_CAST({c} AS BIGINT) AS {c}" if c in INT else c) for c in COLS if c in have) + " FROM t"
            ex = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='votacao_secao'").fetchone()[0]
            con.execute(f"INSERT INTO votacao_secao BY NAME {sel}" if ex else f"CREATE TABLE votacao_secao AS {sel}")
            os.remove(f)
        z.close(); shutil.rmtree(tmp)
        print("  ", u, con.execute(f"SELECT NR_TURNO, count(*) FROM votacao_secao WHERE ANO_ELEICAO={ano} AND SG_UF='{u}' GROUP BY 1 ORDER BY 1").fetchall(), flush=True)
con.close()
