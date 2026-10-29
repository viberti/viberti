#!/bin/bash
# Compara variantes do modelo em 2022 (2T com ordem real; 1T com ordem aproximada) + ordens de estresse
cd /home/claude/tse
O=real,nordeste_primeiro,sul_sudeste_primeiro,capitais_primeiro
for v in base ZONA TIPO HUBER ZONA+TIPO+HUBER; do
  env_v=""; for f in ZONA TIPO HUBER; do [[ $v == *$f* ]] && env_v="$env_v $f=1"; done
  env $env_v ANO=2022 SIMS=150 TAU_G=0.02 TAU_UF_MIN=0.027 ORDENS=$O ORDEM_REAL=hist/ordem_real_2022_2t.csv \
     python3 -I scripts/modelo.py tse_2022_2026.duckdb modelo/var/2t_$v > modelo/var/2t_$v.log 2>&1
  env $env_v ANO=2022 TURNO_ALVO=1 SIMS=150 TAU_G=0.02 TAU_UF_MIN=0.027 ORDENS=$O ORDEM_REAL=hist/ordem_real_2022_1t.csv \
     python3 -I scripts/modelo.py tse_2022_2026.duckdb modelo/var/1t_$v > modelo/var/1t_$v.log 2>&1
  echo "feito $v"
done
echo VARIANTES_OK
