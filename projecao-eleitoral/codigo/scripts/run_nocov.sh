#!/bin/bash
# 1º turno sem covariáveis do Censo (só vizinhança), mesmas ordens pareadas de c1tf2
cd /home/claude/tse; mkdir -p modelo/c1tf2_nocov
until grep -q V2_OK /tmp/claude-0/-home-claude/23b31615-b4b0-59b9-8f9c-e580664c69d4/tasks/b7d9z6r20.output; do sleep 30; done
export TURNO_ALVO=1 VIZ=1 COV= SD_SCALES=1 TAU_G=0.02 TAU_UF_MIN=0.027
db() { case $1 in 2018) echo tse_1418.duckdb;; 2014) echo tse_hist.duckdb;; *) echo tse_2026.duckdb;; esac; }
export -f db
printf "2026\n2022\n2018\n2014\n" | xargs -P 2 -I{} bash -c 'ANO={} python3 -I scripts/calibra_1t_faixa.py $(db {}) modelo/c1tf2_nocov/{}.csv > modelo/c1tf2_nocov/{}.log 2>&1; echo "{} fim"'
echo NOCOV_OK
