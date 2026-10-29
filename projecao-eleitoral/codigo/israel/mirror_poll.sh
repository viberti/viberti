#!/bin/bash
# baixa o espelho do arquivo da CEC a cada 2 min; guarda cada versão nova e avisa quando há resultados
D=/home/claude/israel/live/espelho; mkdir -p $D; last=""
while true; do
  c=$(curl -s -o $D/tmp.json -w '%{http_code}' -m 30 https://raw.githubusercontent.com/joshuaofisrael/mapthegeneral/il-live-data/il-2026-knesset/results.json)
  if [ "$c" = "200" ]; then
    h=$(grep -v lastCheckedAt $D/tmp.json | md5sum | cut -c1-8)
    if [ "$h" != "$last" ]; then
      last=$h; t=$(date -u +%H%M%S); cp $D/tmp.json $D/r_$t.json; cp $D/tmp.json $D/ultimo.json
      python3 -I -c "import json;d=json.load(open('$D/ultimo.json'));print('ESPELHO', '$t', d.get('stage'), 'results', len(d.get('results',[])), flush=True)"
    fi
  else echo "espelho_http $c"; fi
  sleep 120
done
