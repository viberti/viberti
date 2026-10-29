#!/bin/bash
# variantes de MUNVIZ nas três noites com falha do verde (ordem real transplantada)
cd /home/claude/tse
export SIMS=100 TAU_G=0.02 RIDGE_SEC=1000 UNC=bv ZONA=0 ORDENS=real
job() { cfg=$1; ano=$2; ordem=$3; nome=$4; db=$5; out=modelo/sem_mvg/$cfg/${ano}_$nome; mkdir -p modelo/sem_mvg/$cfg
  case $cfg in
    v1mv)   e="TAU_UF_MIN=0.027 MUNVIZ=1";;
    v2mv_f) e="TAU_UF_MIN=0.15 COV=1x TIPO=1 MUNVIZ=1 MUNVIZ_H=80 MUNVIZ_K=50";;
    v1mv_f) e="TAU_UF_MIN=0.027 MUNVIZ=1 MUNVIZ_H=80 MUNVIZ_K=50";;
  esac
  ( env $e ANO=$ano ORDEM_REAL=$ordem python3 -I scripts/semaforo.py $db $out ) > $out.log 2>&1; echo "$cfg $ano $nome fim $(date +%T)"; }
export -f job
for c in v1mv v2mv_f v1mv_f; do
printf "$c %s\n" "2018 hist/ordem_2018_com_2022_2t.csv real2022_2t tse_1418.duckdb" "2018 hist/ordem_2018_com_2026_2t.csv real2026_2t tse_1418.duckdb" "2006 hist/ordem_2006_com_2026_2t.csv real2026_2t tse_hist.duckdb"
done | xargs -P 3 -L 1 bash -c 'job $0 $1 $2 $3 $4'
echo MVG_OK
