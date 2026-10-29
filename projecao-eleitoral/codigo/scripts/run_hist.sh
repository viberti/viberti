#!/bin/bash
cd /home/claude/tse
export SIMS=20 TAU_G=0.02 TAU_UF_MIN=0.027 RIDGE_SEC=1000 HIST=${HIST:-dcf}
run() { y=$1; o=modelo/sem_hist_${HIST:-dcf}; mkdir -p $o
  case $y in
  2022) ANO=2022 ORDEM_REAL=hist/ordem_real_2022_2t.csv python3 -I scripts/semaforo.py tse_2022_2026.duckdb $o/2022_2t ;;
  2026) ANO=2026 python3 -I scripts/semaforo.py tse_2026.duckdb $o/2026_2t ;;
  *) ANO=$y python3 -I scripts/semaforo.py tse_hist.duckdb $o/${y}_2t ;;
  esac > $o/${y}_2t.log 2>&1; echo "$y fim"; }
export -f run
printf "${ANOS:-2014 2022 2026 2010}" | tr " " "\n" | xargs -P 2 -I{} bash -c 'run {}'
echo HIST_OK
