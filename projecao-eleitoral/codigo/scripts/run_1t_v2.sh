#!/bin/bash
# 1º turno refeito com sinais sem vazamento (eleitorado apto, peso histórico) e ordens pareadas
cd /home/claude/tse; mkdir -p modelo/c1tf2 modelo/multi2
export TURNO_ALVO=1 VIZ=1 COV=1x SD_SCALES=1,1.5,2,3,4 TAU_G=0.02 TAU_UF_MIN=0.027 SIMS_M=60
db() { case $1 in 2018) echo tse_1418.duckdb;; 2014) echo tse_hist.duckdb;; *) echo tse_2026.duckdb;; esac; }
export -f db
printf "f 2026\nf 2022\nf 2018\nf 2014\nm 2026\nm 2022\nm 2018\nm 2014\n" | xargs -P 2 -L 1 bash -c 'k=$0; y=$1; d=$(db $y);
 if [ $k = f ]; then ANO=$y python3 -I scripts/calibra_1t_faixa.py $d modelo/c1tf2/$y.csv > modelo/c1tf2/$y.log 2>&1;
 else ANO=$y python3 -I scripts/modelo_1t_multi.py $d modelo/multi2/$y.csv > modelo/multi2/$y.log 2>&1; fi; echo "$k $y fim"'
echo V2_OK
