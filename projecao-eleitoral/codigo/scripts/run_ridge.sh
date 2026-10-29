#!/bin/bash
cd /home/claude/tse
until [ $(ls modelo/hp/*.csv 2>/dev/null | wc -l) -ge 4 ]; do sleep 20; done
mkdir -p modelo/ridge
( ANO=2022 ORDEM_REAL=hist/ordem_real_2022_2t.csv python3 -I scripts/calibra_ridge.py tse_2022_2026.duckdb modelo/ridge/2022.csv > modelo/ridge/2022.log 2>&1
  ANO=2010 python3 -I scripts/calibra_ridge.py tse_hist.duckdb modelo/ridge/2010.csv > modelo/ridge/2010.log 2>&1 ) &
( ANO=2014 python3 -I scripts/calibra_ridge.py tse_hist.duckdb modelo/ridge/2014.csv > modelo/ridge/2014.log 2>&1
  ANO=2006 python3 -I scripts/calibra_ridge.py tse_hist.duckdb modelo/ridge/2006.csv > modelo/ridge/2006.log 2>&1 ) &
wait; echo RIDGE_OK
