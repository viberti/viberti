#!/bin/bash
# cobertura da faixa com incerteza extra: bv = coeficientes + volume; bvz = + zona eleitoral
cd /home/claude/tse
export SIMS=100 TAU_G=0.02 TAU_UF_MIN=0.027 RIDGE_SEC=1000
run() { v=$1; y=$2; o=modelo/sem_$v; mkdir -p $o
  case $v in bv) export UNC=bv ZONA=0;; bvz) export UNC=bv ZONA=1;; esac
  case $y in
  2022) ANO=2022 ORDEM_REAL=hist/ordem_real_2022_2t.csv python3 -I scripts/semaforo.py tse_2022_2026.duckdb $o/2022_2t ;;
  2026) ANO=2026 python3 -I scripts/semaforo.py tse_2026.duckdb $o/2026_2t ;;
  *) ANO=$y python3 -I scripts/semaforo.py tse_hist.duckdb $o/${y}_2t ;;
  esac > $o/${y}_2t.log 2>&1; echo "$v $y fim"; }
export -f run
printf "bv 2014\nbv 2006\nbv 2010\nbv 2022\nbv 2026\nbvz 2014\nbvz 2006\nbvz 2010\nbvz 2022\nbvz 2026\n" | xargs -P 2 -L 1 bash -c 'run $0 $1'
echo UNC_OK
