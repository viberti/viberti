#!/bin/bash
cd /home/claude/tse
export TURNO_ALVO=1 VIZ=1 COV=1
( ANO=2026 python3 -I scripts/calibra_1t.py tse_2026.duckdb modelo/c1t/2026.csv > modelo/c1t/2026.log 2>&1
  ANO=2022 python3 -I scripts/calibra_1t.py tse_2026.duckdb modelo/c1t/2022.csv > modelo/c1t/2022.log 2>&1 ) &
( ANO=2018 python3 -I scripts/calibra_1t.py tse_1418.duckdb modelo/c1t/2018.csv > modelo/c1t/2018.log 2>&1
  ANO=2014 python3 -I scripts/calibra_1t.py tse_hist.duckdb modelo/c1t/2014.csv > modelo/c1t/2014.log 2>&1 ) &
wait; echo C1T_OK
