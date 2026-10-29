#!/bin/bash
cd /home/claude/tse
export SD_SCALES=0.4,0.5,0.6,0.7,0.8,0.9,1.0 TAU_G=0.02 TAU_UF_MIN=0.027
( ANO=2022 ORDEM_REAL=hist/ordem_real_2022_2t.csv python3 -I scripts/calibra_faixa.py tse_2022_2026.duckdb modelo/faixa/2022.csv > modelo/faixa/2022.log 2>&1
  ANO=2026 python3 -I scripts/calibra_faixa.py tse_2026.duckdb modelo/faixa/2026.csv > modelo/faixa/2026.log 2>&1 ) &
( ANO=2014 python3 -I scripts/calibra_faixa.py tse_hist.duckdb modelo/faixa/2014.csv > modelo/faixa/2014.log 2>&1
  ANO=2010 python3 -I scripts/calibra_faixa.py tse_hist.duckdb modelo/faixa/2010.csv > modelo/faixa/2010.log 2>&1
  ANO=2006 python3 -I scripts/calibra_faixa.py tse_hist.duckdb modelo/faixa/2006.csv > modelo/faixa/2006.log 2>&1 ) &
wait; echo FAIXA_OK
