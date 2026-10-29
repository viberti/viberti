"""Baixa o perfil do eleitorado por seção (TSE 2026) UF a UF, resume cada seção e apaga o bruto.
Saída: perfil/<UF>.parquet com 1 linha por seção (contagens; percentagens calculadas depois).
Uso: python3 -I perfil_secao.py <out_dir>
"""
import os, sys, zipfile, shutil, subprocess, duckdb
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()
URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitor_secao/perfil_eleitor_secao_2026_{}.zip"
Q = "TRY_CAST(QT_ELEITORES AS BIGINT)"
def s(cond): return f"sum(CASE WHEN {cond} THEN {Q} ELSE 0 END)"
SEL = f"""
  SG_UF sg_uf, TRY_CAST(CD_MUNICIPIO AS BIGINT) cd_municipio, TRY_CAST(NR_ZONA AS BIGINT) nr_zona,
  TRY_CAST(NR_SECAO AS BIGINT) nr_secao, any_value(TRY_CAST(NR_LOCAL_VOTACAO AS BIGINT)) nr_local,
  sum({Q}) eleitores, sum(TRY_CAST(QT_ELEITORES_BIOMETRIA AS BIGINT)) biometria,
  {s("CD_GENERO='4'")} fem,
  {s("TRY_CAST(CD_FAIXA_ETARIA AS INT) BETWEEN 1600 AND 2124")} id16_24,
  {s("TRY_CAST(CD_FAIXA_ETARIA AS INT) BETWEEN 2529 AND 3034")} id25_34,
  {s("TRY_CAST(CD_FAIXA_ETARIA AS INT) BETWEEN 3539 AND 4044")} id35_44,
  {s("TRY_CAST(CD_FAIXA_ETARIA AS INT) BETWEEN 4549 AND 5559")} id45_59,
  {s("TRY_CAST(CD_FAIXA_ETARIA AS INT) >= 6064")} id60m,
  {s("CD_GRAU_ESCOLARIDADE IN ('1','2','3')")} esc_fund_inc,
  {s("CD_GRAU_ESCOLARIDADE IN ('4','5')")} esc_fund_comp,
  {s("CD_GRAU_ESCOLARIDADE = '6'")} esc_medio,
  {s("CD_GRAU_ESCOLARIDADE IN ('7','8')")} esc_superior,
  {s("CD_GRAU_ESCOLARIDADE = '8'")} esc_superior_comp,
  {s("CD_RACA_COR = '1'")} rc_branca, {s("CD_RACA_COR = '2'")} rc_preta, {s("CD_RACA_COR = '3'")} rc_parda,
  {s("CD_RACA_COR = '4'")} rc_indigena, {s("CD_RACA_COR = '5'")} rc_amarela,
  {s("CD_RACA_COR IN ('1','2','3','4','5')")} rc_informada,
  {s("CD_ESTADO_CIVIL = '3'")} casado
"""
for uf in UFS:
    dst = os.path.join(out, f"{uf}.parquet")
    if os.path.exists(dst): print(uf, "já feito", flush=True); continue
    tmp = os.path.join(out, "tmp"); os.makedirs(tmp, exist_ok=True)
    zp = os.path.join(tmp, f"{uf}.zip")
    subprocess.run(["curl", "-sS", "-m", "3600", "--retry", "3", "-o", zp, URL.format(uf)], check=True)
    with zipfile.ZipFile(zp) as z:
        nm = [n for n in z.namelist() if n.endswith(".csv")][0]; z.extract(nm, tmp)
    os.remove(zp)
    f = os.path.join(tmp, nm)
    con = duckdb.connect()
    con.execute(f"""COPY (SELECT {SEL} FROM read_csv('{f}', delim=';', header=true, quote='"', encoding='latin-1', all_varchar=true)
                 GROUP BY 1,2,3,4) TO '{dst}' (FORMAT parquet)""")
    n = con.execute(f"SELECT count(*), sum(eleitores) FROM '{dst}'").fetchone()
    con.close(); shutil.rmtree(tmp)
    print(uf, "seções", n[0], "eleitores", n[1], flush=True)
print("PERFIL_OK")
