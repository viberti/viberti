#!/bin/bash
# ordens transplantadas (v1) e versão 2 (TAU_UF_MIN=0,15) em todas as eleições
cd /home/claude/tse
export SIMS=100 TAU_G=0.02 RIDGE_SEC=1000 UNC=bv ZONA=0
db() { case $1 in 2006|2010|2014) echo tse_hist.duckdb;; 2018) echo tse_1418.duckdb;; 2022) echo tse_2022_2026.duckdb;; 2026) echo tse_2026.duckdb;; esac; }
job() { ver=$1; ano=$2; ordem=$3; nome=$4; only=$5
  tau=0.027; [ $ver = v2 ] && tau=0.15
  out=modelo/sem_$ver/${ano}_$nome; mkdir -p modelo/sem_$ver
  ( export TAU_UF_MIN=$tau ANO=$ano; [ -n "$ordem" ] && export ORDEM_REAL=$ordem; [ -n "$only" ] && export ORDENS=real
    python3 -I scripts/semaforo.py $(db $ano) $out ) > $out.log 2>&1; echo "$ver $ano $nome fim"; }
export -f job db
{
for a in 2006 2010 2014; do for s in 2022_2t 2026_2t; do echo "v1 $a hist/ordem_${a}_com_$s.csv real$s 1"; done; done
for a in 2006 2010 2014 2018; do echo "v2 $a hist/ordem_${a}_com_2022_2t.csv todas x"; echo "v2 $a hist/ordem_${a}_com_2026_2t.csv real2026_2t 1"; done
echo "v2 2022 hist/ordem_real_2022_2t.csv todas x"; echo "v2 2026 hist/ordem_real_2026_2t.csv todas x"
} | xargs -P 4 -L 1 bash -c 'only=$4; [ "$only" = x ] && only=""; job $0 $1 $2 $3 $only'
echo V2_OK
