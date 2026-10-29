# Projeção da apuração eleitoral por seção (Brasil)

Modelo que projeta o resultado final a partir das primeiras seções apuradas, comparando cada seção com a sua própria votação anterior, e semáforo que diz quando a projeção pode ser divulgada (vermelho, amarelo = vencedor, verde = percentual ± 0,5 ponto).

## Conteúdo

| Pasta ou arquivo | O que é |
|---|---|
| `protocolo_v1.json`, `protocolo_v1.sha256` | Versão congelada em 29/10/2026: parâmetros, regras do semáforo, plano de avaliação e SHA-256 de cada script |
| `verificar_hashes.py` | Confere que o código em `codigo/` é o mesmo que foi congelado |
| `codigo/load_*.py` | Carregam os dados abertos do TSE em DuckDB |
| `codigo/scripts/` | Modelo (`modelo.py`, `modelo_1t_multi.py`), ordens de chegada e semáforo (`semaforo.py`), escolha das regras (`regra_loo.py`, `regra_vencedor_loo.py`, `regra_estab.py`), leitura dos arquivos da urna (`zipindex.py`, `ber.py`, `decode_bu.py`, `crawl_bu.py`, `crawl_aux_1t.py`) e os `run_*.sh` que geram cada tabela |
| `codigo/testes/teste_vazamento.py` | Embaralha os votos das seções não apuradas e confere que a projeção não muda |
| `codigo/israel/` | Adaptação para a eleição israelense (Knesset 26) |
| `dados/ordens_reais/` | Hora de chegada de cada seção em três noites reais (ver LEIAME) |

## Reproduzir

1. Python 3.13, pandas, numpy e duckdb.
2. Baixar os dados abertos do TSE (votação por seção, detalhe da votação por seção, perfil do eleitorado) e carregar com `codigo/load_tse.py`, `load_secao.py` e `load_hist.py`. Os scripts usam caminhos absolutos da máquina original (`/home/claude/tse`); ajuste-os antes de rodar. Não alteramos os arquivos para manter os hashes do protocolo.
3. Teste de vazamento: `ANO=2026 UNC=bv SIMS=50 python3 -I codigo/testes/teste_vazamento.py <banco 2026>`.
4. Tabelas da nota: `run_sem2.sh` (2º turno, 31 ordens), `run_unc.sh` (incerteza), `run_adv.sh` (ordens adversariais), `run_alarme.sh` (alarme), `run_1t_v2.sh` (1º turno); depois `regra_loo.py modelo/sem2` e `regra_estab.py`.

A nota metodológica descreve o método, a validação e os problemas conhecidos.

## Licença

Código sob licença MIT. Dados derivados de dados abertos do TSE (licença CC-BY).
