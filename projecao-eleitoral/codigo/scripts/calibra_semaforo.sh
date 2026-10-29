#!/bin/bash
cd /home/claude/tse
export SIMS=100 TAU_G=0.02 TAU_UF_MIN=0.027
ANO=2022 ORDEM_REAL=hist/ordem_real_2022_2t.csv python3 -I scripts/semaforo.py tse_2022_2026.duckdb modelo/sem/2022_2t > modelo/sem/2022_2t.log 2>&1; echo "2022_2t ok"
ANO=2022 TURNO_ALVO=1 ORDEM_REAL=hist/ordem_real_2022_1t.csv python3 -I scripts/semaforo.py tse_2022_2026.duckdb modelo/sem/2022_1t > modelo/sem/2022_1t.log 2>&1; echo "2022_1t ok"
for a in 2014 2010 2006; do
  ANO=$a python3 -I scripts/semaforo.py tse_hist.duckdb modelo/sem/${a}_2t > modelo/sem/${a}_2t.log 2>&1; echo "${a}_2t ok"
done
echo SEMAFORO_OK
