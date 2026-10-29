#!/bin/bash
cd /home/claude/tse
export TURNO_ALVO=1 VIZ=1 COV=1x SD_SCALES=1,1.5,2,3,4 TAU_G=0.02 TAU_UF_MIN=0.027
( ANO=2026 python3 -I scripts/calibra_1t_faixa.py tse_2026.duckdb modelo/c1tf/2026.csv > modelo/c1tf/2026.log 2>&1
  ANO=2022 python3 -I scripts/calibra_1t_faixa.py tse_2026.duckdb modelo/c1tf/2022.csv > modelo/c1tf/2022.log 2>&1 ) &
( ANO=2018 python3 -I scripts/calibra_1t_faixa.py tse_1418.duckdb modelo/c1tf/2018.csv > modelo/c1tf/2018.log 2>&1
  ANO=2014 python3 -I scripts/calibra_1t_faixa.py tse_hist.duckdb modelo/c1tf/2014.csv > modelo/c1tf/2014.log 2>&1 ) &
wait; echo C1TF_OK
