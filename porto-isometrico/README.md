# Porto isométrico

A Ribeira do Porto, o cais de Gaia e a Ponte Luiz I em pixel art isométrica, renderizados a partir de dados abertos.
É um protótipo do método do [Isometric NYC](https://cannoneyed.com/projects/isometric-nyc) aplicado ao Porto,
sem o passo de IA: os tiles aqui são os renders estilizados que esse passo receberia.

## Como regenerar

Precisa de Python 3 (numpy, Pillow, shapely), Node 18+ e Playwright com Chromium.

```sh
npm install                          # three.js
python3 pipeline/fetch_osmapi.py     # OSM (API oficial, em 9 quadros) e relevo -> data/
python3 pipeline/scene.py            # a cena 3D em metros locais -> web/scene/
node pipeline/render.mjs             # os tiles de 512 px, no Chromium sem tela -> web/tiles/raw/
python3 pipeline/pyramid.py          # a pirâmide de zoom do visualizador -> web/tiles/<z>/
python3 -m http.server -d web 8000   # e abrir http://localhost:8000/
```

`pipeline/fetch.py` faz o mesmo download pelo Overpass, quando ele responde.

## O que cada passo faz

- **Dados.** Prédios, ruas, jardins, árvores, pontes e o Douro vêm do OpenStreetMap; o relevo, dos Terrain Tiles
  (Mapzen/AWS). O recorte vai da Serra do Pilar aos Clérigos (`BBOX` em `pipeline/fetch.py`).
- **Cena.** Alturas pelo OSM (`height`, `building:levels`) ou estimadas pelo tipo; telhados de quatro águas nos
  prédios pequenos; os cais com parede de granito; os tabuleiros das pontes grandes nivelados; o arco da Luiz I em
  treliça; rabelos no cais de Gaia.
- **Render.** Câmera ortográfica a 30° olhando para nordeste (a projeção 2:1 da pixel art), luz em degraus, janelas
  procedurais, contorno escuro por profundidade e normais. 0,5 m por pixel.

## Dados e créditos

Dados © contribuidores do OpenStreetMap, sob a ODbL. Relevo: Terrain Tiles (Mapzen/AWS), que incluem SRTM e EU-DEM.
