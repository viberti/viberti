#!/bin/bash
# replays dos 2os turnos de governador (anos dados) com as configurações v1 e v2b
cd /home/claude/tse
export SIMS=100 TAU_G=0.02 RIDGE_SEC=1000 UNC=bv ZONA=0
mkdir -p modelo/gov
job() { cfg=$1; ano=$2; uf=$3; out=modelo/gov/${cfg}_${ano}_${uf}.csv
  case $cfg in v1) e="TAU_UF_MIN=0.027";; v2b) e="TAU_UF_MIN=0.15 COV=1x TIPO=1";; esac
  env $e ANO=$ano GOV_UF=$uf python3 -I scripts/gov_replay.py tse_gov.duckdb $out > ${out%.csv}.log 2>&1; echo "$cfg $ano $uf $(tail -n 1 ${out%.csv}.log)"; }
export -f job
python3 -c "
import duckdb,sys
c=duckdb.connect('tse_gov.duckdb',read_only=True)
for a in sys.argv[1:]:
    for (u,) in c.execute(f'SELECT DISTINCT SG_UF FROM votacao_secao WHERE ANO_ELEICAO={a} AND NR_TURNO=2 ORDER BY 1').fetchall():
        for cfg in ('v1','v2b'): print(cfg,a,u)
" "$@" | xargs -P 2 -L 1 bash -c 'job $0 $1 $2'
echo GOV_OK
