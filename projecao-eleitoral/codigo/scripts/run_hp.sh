#!/bin/bash
cd /home/claude/tse
( ANO=2022 ORDEM_REAL=hist/ordem_real_2022_2t.csv python3 -I scripts/calibra_hp.py tse_2022_2026.duckdb modelo/hp/2022.csv > modelo/hp/2022.log 2>&1
  ANO=2010 python3 -I scripts/calibra_hp.py tse_hist.duckdb modelo/hp/2010.csv > modelo/hp/2010.log 2>&1 ) &
( ANO=2014 python3 -I scripts/calibra_hp.py tse_hist.duckdb modelo/hp/2014.csv > modelo/hp/2014.log 2>&1
  ANO=2006 python3 -I scripts/calibra_hp.py tse_hist.duckdb modelo/hp/2006.csv > modelo/hp/2006.log 2>&1 ) &
wait; echo HP_OK
