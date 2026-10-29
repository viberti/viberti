#!/bin/bash
cd /home/claude/tse
( ANO=2022 ORDEM_REAL=hist/ordem_real_2022_2t.csv python3 -I scripts/calibra_fino.py tse_2022_2026.duckdb modelo/fino/2022.csv > modelo/fino/2022.log 2>&1
  ANO=2026 python3 -I scripts/calibra_fino.py tse_2026.duckdb modelo/fino/2026.csv > modelo/fino/2026.log 2>&1 ) &
( ANO=2014 python3 -I scripts/calibra_fino.py tse_hist.duckdb modelo/fino/2014.csv > modelo/fino/2014.log 2>&1
  ANO=2010 python3 -I scripts/calibra_fino.py tse_hist.duckdb modelo/fino/2010.csv > modelo/fino/2010.log 2>&1
  ANO=2006 python3 -I scripts/calibra_fino.py tse_hist.duckdb modelo/fino/2006.csv > modelo/fino/2006.log 2>&1 ) &
wait; echo FINO_OK
