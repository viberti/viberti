# Lagoa Rodrigo de Freitas, vista do tinyrj

Cenário para o app de remo: a Lagoa e o entorno (uns 500 m além da margem) em pixel art isométrica.

## De onde vem

- **Imagens:** [tinyrj.com](https://tinyrj.com), de [@xthomasms](https://x.com/xthomasms). São os tiles públicos da
  vista 0 (`/2/data/h0/`), na cópia com o acabamento final (`filtered/`). O site credita "Dados do mapa ©Google".
- **Licença das imagens:** o site não publica nenhuma. O uso combinado é só da família, sem distribuir o app.
  Para distribuir o app ou publicar as imagens é preciso pedir autorização ao autor.
- **Por isso as imagens não estão neste repositório**, que é público: aqui ficam só o script que as baixa e os dados
  de posição. Quem roda `build.py` baixa os tiles direto do tinyrj para a própria máquina.
- **Contorno da água** (`agua-osm.json`): OpenStreetMap, relação 2138398, © contribuidores do OpenStreetMap, ODbL.

## Como gerar

```sh
pip install pillow
python build.py                 # 512 px por tile: 4736x3832 px, 20 pedaços, ~6 MB, 0,59 m/px
python build.py --nivel 256     # 2368x1916 px, 6 pedaços, ~1,5 MB, 1,17 m/px
python build.py --nivel 1024    # resolução cheia, 0,29 m/px (passa dos 8 MB)
```

Sai em `saida/`: `pedacos/<coluna>_<linha>.webp` (1024 px) e `manifest.json`.

## O que há no manifest.json

- **Grade:** `largura`, `altura`, `colunas`, `linhas` e a lista `pedacos` (arquivo, x, y, w, h).
- **Escala:** no eixo x da imagem, 1 px = 0,586 m (nível 512). No eixo y o chão aparece encolhido por cos 45°:
  1 px = 0,829 m de chão. Os prédios sobem na imagem, então o topo deles fica acima da base.
- **Projeção:** fórmula afim de latitude/longitude para pixel, válida ao nível da água, com os seis coeficientes.
- **Pontos de controle:** latitude e longitude dos quatro cantos e do centro.
- **Água:** `agua.margem` (polígono externo) e `agua.ilhas` (Piraquê e Caiçaras), em pixels da imagem composta.

## Orientação e precisão

É a vista 0 do tinyrj: câmera ortográfica a 45°, com o norte 20,8° à direita do alto. O Corcovado fica para cima e
Ipanema em baixo.

A posição foi ajustada casando o contorno da Lagoa no OpenStreetMap com a água do desenho: 95% de sobreposição, com
erro típico de poucos metros na margem. Os coeficientes de rotação e escala são os do próprio site (`turn.js`).
