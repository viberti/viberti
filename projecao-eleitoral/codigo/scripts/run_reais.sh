#!/bin/bash
# replays com ordens reais: 2º turno 2026 (nova) e 1º turno 2022
cd /home/claude/tse; mkdir -p modelo/paper_2026_real modelo/sem2_real modelo/real1t
export TAU_G=0.02 TAU_UF_MIN=0.027 RIDGE_SEC=1000
CK1="0.001,0.002,0.005,0.01,0.02,0.05,0.10,0.20,0.30,0.50"
( ANO=2026 ORDEM_REAL=hist/ordem_real_2026_2t.csv ORDENS=real SIMS=300 python3 -I scripts/modelo.py tse_2026.duckdb modelo/paper_2026_real > modelo/paper_2026_real/log 2>&1; echo "replay 2026 fim"
  ANO=2026 ORDEM_REAL=hist/ordem_real_2026_2t.csv ORDENS=real SIMS=100 python3 -I scripts/semaforo.py tse_2026.duckdb modelo/sem2_real/2026_2t > modelo/sem2_real/2026_2t.log 2>&1; echo "sem 2026 fim" ) &
( export TURNO_ALVO=1 VIZ=1 COV=1x SD_SCALES=1 SIMS_M=100 ORDEM_REAL=hist/ordem_real_2022_1t.csv ORDENS=real
  ANO=2022 CKS=$CK1 python3 -I scripts/calibra_1t_faixa.py tse_2026.duckdb modelo/real1t/bin_2022.csv > modelo/real1t/bin_2022.log 2>&1; echo "1t bin fim"
  ANO=2022 CKS=$CK1 python3 -I scripts/modelo_1t_multi.py tse_2026.duckdb modelo/real1t/multi_2022.csv > modelo/real1t/multi_2022.log 2>&1; echo "1t multi fim" ) &
wait; echo REAIS_OK
