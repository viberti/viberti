#!/bin/bash
# coeficientes regionais encolhidos (FEAT=reg, REGH) nas três noites com falha do verde (ordem real transplantada)
cd /home/claude/tse
export SIMS=100 TAU_G=0.02 RIDGE_SEC=1000 UNC=bv ZONA=0 ORDENS=real
job() { cfg=$1; ano=$2; ordem=$3; nome=$4; db=$5; out=modelo/sem_reg/$cfg/${ano}_$nome; mkdir -p modelo/sem_reg/$cfg
  case $cfg in
    v1reg1)  e="TAU_UF_MIN=0.027 FEAT=reg REGH=1";;
    v1reg01) e="TAU_UF_MIN=0.027 FEAT=reg REGH=0.1";;
    v2reg1)  e="TAU_UF_MIN=0.15 COV=1x TIPO=1 FEAT=reg REGH=1";;
    v2reg01) e="TAU_UF_MIN=0.15 COV=1x TIPO=1 FEAT=reg REGH=0.1";;
  esac
  ( env $e ANO=$ano ORDEM_REAL=$ordem python3 -I scripts/semaforo.py $db $out ) > $out.log 2>&1; echo "$cfg $ano $nome fim $(date +%T)"; }
export -f job
for c in v1reg1 v1reg01 v2reg1 v2reg01; do
printf "$c %s\n" "2018 hist/ordem_2018_com_2022_2t.csv real2022_2t tse_1418.duckdb" "2018 hist/ordem_2018_com_2026_2t.csv real2026_2t tse_1418.duckdb" "2006 hist/ordem_2006_com_2026_2t.csv real2026_2t tse_hist.duckdb"
done | xargs -P 3 -L 1 bash -c 'job $0 $1 $2 $3 $4'
echo REG_OK
