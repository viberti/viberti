#!/bin/bash
cd /home/claude/tse
export TURNO_ALVO=1 VIZ=1 COV=1x TAU_G=0.02 TAU_UF_MIN=0.027
( ANO=2026 python3 -I scripts/modelo_1t_multi.py tse_2026.duckdb modelo/multi/2026.csv > modelo/multi/2026.log 2>&1
  ANO=2022 python3 -I scripts/modelo_1t_multi.py tse_2026.duckdb modelo/multi/2022.csv > modelo/multi/2022.log 2>&1 ) &
( ANO=2018 python3 -I scripts/modelo_1t_multi.py tse_1418.duckdb modelo/multi/2018.csv > modelo/multi/2018.log 2>&1
  ANO=2014 python3 -I scripts/modelo_1t_multi.py tse_hist.duckdb modelo/multi/2014.csv > modelo/multi/2014.log 2>&1 ) &
wait; echo MULTI_OK
