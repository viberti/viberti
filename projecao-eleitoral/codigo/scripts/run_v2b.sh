#!/bin/bash
# versão 2b: prior de UF 0,15 + covariáveis municipais do Censo com interações (COV=1x) + efeito UF×capital (TIPO=1), todas as eleições
cd /home/claude/tse
export SIMS=100 TAU_G=0.02 RIDGE_SEC=1000 UNC=bv ZONA=0 TAU_UF_MIN=0.15 COV=1x TIPO=1
db() { case $1 in 2006|2010|2014) echo tse_hist.duckdb;; 2018) echo tse_1418.duckdb;; 2022) echo tse_2022_2026.duckdb;; 2026) echo tse_2026.duckdb;; esac; }
job() { ano=$1; ordem=$2; nome=$3; only=$4; out=modelo/sem_v2b/${ano}_$nome; mkdir -p modelo/sem_v2b
  ( export ANO=$ano ORDEM_REAL=$ordem; [ "$only" = 1 ] && export ORDENS=real; python3 -I scripts/semaforo.py $(db $ano) $out ) > $out.log 2>&1; echo "$ano $nome fim"; }
export -f job db
{
for a in 2006 2010 2014 2018; do echo "$a hist/ordem_${a}_com_2022_2t.csv todas 0"; echo "$a hist/ordem_${a}_com_2026_2t.csv real2026_2t 1"; done
echo "2022 hist/ordem_real_2022_2t.csv todas 0"; echo "2026 hist/ordem_real_2026_2t.csv todas 0"
} | xargs -P 4 -L 1 bash -c 'job $0 $1 $2 $3'
echo V2B_OK
