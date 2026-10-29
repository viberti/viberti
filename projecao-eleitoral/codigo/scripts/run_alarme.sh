#!/bin/bash
# alarme de correlação intra-município: ordens realistas, aleatórias, extremas, reais e adversariais
cd /home/claude/tse
export SIMS=100 TAU_G=0.02 TAU_UF_MIN=0.027 RIDGE_SEC=1000 UNC=bv ZONA=0 ADV=1
O="real,aleatoria_0,aleatoria_1,capitais_primeiro,NE_primeiro,S_primeiro,pro22_primeiro"; for i in 0 1 2 3; do O="$O,realista_$i,adv_dir_$i,adv_esq_$i,adv_meio_$i"; done; export ORDENS=$O
run() { y=$1; o=modelo/sem_alarme; mkdir -p $o
  case $y in
  2022) ANO=2022 ORDEM_REAL=hist/ordem_real_2022_2t.csv python3 -I scripts/semaforo.py tse_2022_2026.duckdb $o/2022_2t ;;
  2026) ANO=2026 ORDEM_REAL=hist/ordem_real_2026_2t.csv python3 -I scripts/semaforo.py tse_2026.duckdb $o/2026_2t ;;
  *) ANO=$y python3 -I scripts/semaforo.py tse_hist.duckdb $o/${y}_2t ;;
  esac > $o/${y}_2t.log 2>&1; echo "$y fim"; }
export -f run
printf "2014\n2022\n2026\n2010\n2006\n" | xargs -P 3 -I{} bash -c 'run {}'
echo ALARME_OK
