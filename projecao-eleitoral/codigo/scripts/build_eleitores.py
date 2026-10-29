"""Expande os eventos dos logs (bu2t/logrdv.sqlite) numa tabela por eleitor e normaliza para hora de Brasília.
Uso: python3 -I build_eleitores.py <bu2t_dir> <duckdb>
Tabelas:
  eleitor_2t        : 1 linha por voto computado — horas locais da urna (ts_*_local) e de Brasília (ts_*_brt)
  fuso_municipio_2t : deslocamento (h) de cada município face a Brasília, inferido da abertura das urnas
Fuso: a votação nacional corre 8h–17h de Brasília; o deslocamento de cada seção = arredondamento de
(abertura local da urna − 08:00) e o do município é a moda das suas seções (robusto a urnas abertas tarde).
Exterior (ZZ) vota em hora local do país; fica em hora local e marcado com exterior=true.
"""
import sys, os, sqlite3, zlib, duckdb
import pyarrow as pa, pyarrow.parquet as pq

d, dbp = sys.argv[1], sys.argv[2]
src = sqlite3.connect(os.path.join(d, "logrdv.sqlite"), timeout=300)
pqf = os.path.join(d, "eleitores_2t.parquet")
schema = pa.schema([("sg_uf", pa.string()), ("cd_municipio", pa.int32()), ("nr_zona", pa.int32()),
                    ("nr_secao", pa.int32()), ("ordem", pa.int32()), ("t_ident", pa.string()),
                    ("t_hab", pa.string()), ("t_comp", pa.string()), ("tipo_hab", pa.string())])
w = pq.ParquetWriter(pqf, schema, compression="zstd")
cols = {k: [] for k in schema.names}; n = 0
def flush():
    global cols
    w.write_table(pa.table(cols, schema=schema)); cols = {k: [] for k in schema.names}
for uf, mun, zona, sec, ev in src.execute("SELECT uf,mun,zona,secao,ev FROM sec WHERE ev IS NOT NULL"):
    txt = zlib.decompress(ev).decode()
    if not txt: continue
    for k, rec in enumerate(txt.split(";"), 1):
        a, b, c, t = rec.split(",")
        for col, v in zip(schema.names, (uf.upper(), int(mun), int(zona), int(sec), k, a or None, b or None, c, t)):
            cols[col].append(v)
        n += 1
    if len(cols["sg_uf"]) > 2_000_000: flush()
flush(); w.close()
print("eleitores", n)

con = duckdb.connect(dbp)
# DDHHMMSS -> timestamp local em 2026-10-DD
ts = lambda c: f"make_timestamp(2026,10,CAST(substr({c},1,2) AS INT),CAST(substr({c},3,2) AS INT),CAST(substr({c},5,2) AS INT),CAST(substr({c},7,2) AS INT))"
con.execute(f"""CREATE OR REPLACE TABLE fuso_municipio_2t AS
  WITH s AS (SELECT sg_uf, cd_municipio, nr_zona, nr_secao,
               round(date_diff('minute', TIMESTAMP '2026-10-25 08:00:00', min(dt_abertura)) / 60.0)::INT AS off
             FROM bu_2t_secao GROUP BY ALL)
  SELECT sg_uf, cd_municipio, mode(off) AS desloc_h, count(*) AS n_secoes,
         min(off) AS desloc_min, max(off) AS desloc_max
  FROM s GROUP BY ALL""")
con.execute(f"""CREATE OR REPLACE TABLE eleitor_2t AS
  SELECT e.sg_uf, e.cd_municipio, e.nr_zona, e.nr_secao, e.ordem, e.tipo_hab,
         {ts('t_ident')} AS ts_ident_local, {ts('t_hab')} AS ts_hab_local, {ts('t_comp')} AS ts_comp_local,
         (e.sg_uf = 'ZZ') AS exterior, coalesce(f.desloc_h, 0) AS desloc_h,
         {ts('t_comp')} - to_hours(CASE WHEN e.sg_uf='ZZ' THEN 0 ELSE coalesce(f.desloc_h,0) END) AS ts_comp_brt,
         {ts('t_hab')}  - to_hours(CASE WHEN e.sg_uf='ZZ' THEN 0 ELSE coalesce(f.desloc_h,0) END) AS ts_hab_brt,
         date_diff('second', {ts('t_hab')}, {ts('t_comp')}) AS seg_cabine,
         date_diff('second', {ts('t_ident')}, {ts('t_hab')}) AS seg_identificacao
  FROM read_parquet('{pqf}') e LEFT JOIN fuso_municipio_2t f USING (sg_uf, cd_municipio)""")
print(con.execute("SELECT count(*), min(ts_comp_brt), max(ts_comp_brt) FROM eleitor_2t WHERE NOT exterior").fetchall())
print(con.execute("SELECT desloc_h, count(*) FROM fuso_municipio_2t GROUP BY 1 ORDER BY 1").fetchall())
con.close()
