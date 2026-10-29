#!/bin/bash
cd /home/claude/tse
export TURNO_ALVO=1 VIZ=1 COV=1x TAU_G=0.02 TAU_UF_MIN=0.027 SIMS_M=60
db() { case $1 in 2018) echo tse_1418.duckdb;; *) echo tse_2026.duckdb;; esac; }
jobs=""
for v in base s w; do for y in 2026 2022 2018; do jobs="$jobs $v:$y"; done; done
echo $jobs | tr ' ' '\n' | xargs -P 2 -I{} bash -c 'v=${1%%:*}; y=${1##*:}; d=$( [ $y = 2018 ] && echo tse_1418.duckdb || echo tse_2026.duckdb ); ANO=$y MUNI=$( [ $v = base ] && echo "" || echo $v ) python3 -I scripts/modelo_1t_multi.py $d modelo/multi_mun/${y}_$v.csv > modelo/multi_mun/${y}_$v.log 2>&1; echo "$v $y $(grep MAE modelo/multi_mun/${y}_$v.log)"' _ {}
echo MUN_OK
