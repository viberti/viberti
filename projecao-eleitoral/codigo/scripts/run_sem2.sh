#!/bin/bash
# semáforo refeito: modelo final (λ=1000), sem vazamento nos sinais, com referências simples
cd /home/claude/tse; mkdir -p modelo/sem2
export SIMS=100 TAU_G=0.02 TAU_UF_MIN=0.027 RIDGE_SEC=1000
run() { case $1 in
  2022) ANO=2022 ORDEM_REAL=hist/ordem_real_2022_2t.csv python3 -I scripts/semaforo.py tse_2022_2026.duckdb modelo/sem2/2022_2t ;;
  2026) ANO=2026 python3 -I scripts/semaforo.py tse_2026.duckdb modelo/sem2/2026_2t ;;
  *) ANO=$1 python3 -I scripts/semaforo.py tse_hist.duckdb modelo/sem2/$1_2t ;;
  esac > modelo/sem2/$1_2t.log 2>&1; echo "$1 ok $(grep -c . modelo/sem2/$1_2t/semaforo_pontos.csv 2>/dev/null)"; }
export -f run
printf "2022\n2014\n2026\n2010\n2006\n" | xargs -P 2 -I{} bash -c 'run {}'
echo SEM2_OK
