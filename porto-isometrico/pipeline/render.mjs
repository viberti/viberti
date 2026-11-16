// Renderiza todos os tiles com o Chromium sem tela: serve o projeto num servidor local,
// abre web/render.html e grava cada tile em web/tiles/raw/<coluna>_<linha>.png.
//
// Uso: node pipeline/render.mjs [c0 c1 r0 r1]   (sem argumentos: o mapa todo)
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const ROOT = fileURLToPath(new URL("..", import.meta.url));
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json",
  ".png": "image/png", ".bin": "application/octet-stream" };

const server = createServer(async (req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, "http://x").pathname)).replace(/^(\.\.[/\\])+/, "");
  const file = path.startsWith("/node_modules/") ? join(ROOT, path) : join(ROOT, "web", path);
  try {
    const body = await readFile(file);
    res.writeHead(200, { "Content-Type": TYPES[extname(file)] || "application/octet-stream" });
    res.end(body);
  } catch { res.writeHead(404); res.end(); }
});
await new Promise(r => server.listen(0, "127.0.0.1", r));
const port = server.address().port;

const browser = await chromium.launch();
const page = await browser.newPage();
page.on("console", m => { if (m.type() === "error" || m.type() === "warning") console.log("[página]", m.text()); });
page.on("pageerror", e => console.log("[página]", e.message));
await page.goto(`http://127.0.0.1:${port}/render.html`);
const info = await page.evaluate(() => window.ready).catch(async e => { console.log(await page.evaluate(() => window.failed)); throw e; });
const g = info.grid;
const [c0, c1, r0, r1] = process.argv.length >= 6 ? process.argv.slice(2, 6).map(Number) : [g.c0, g.c1, g.r0, g.r1];
console.log(`grade: colunas ${g.c0}..${g.c1}, linhas ${g.r0}..${g.r1}; a renderizar ${c0}..${c1} x ${r0}..${r1}`);

const outDir = join(ROOT, "web", "tiles", "raw");
await mkdir(outDir, { recursive: true });
const kept = [];
const t0 = Date.now();
for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) {
  const url = await page.evaluate(([c, r]) => window.R.renderTile(c, r), [c, r]);
  if (!url) continue;
  await writeFile(join(outDir, `${c}_${r}.png`), Buffer.from(url.split(",")[1], "base64"));
  kept.push([c, r]);
  process.stdout.write(`\r${kept.length} tiles, ${((Date.now() - t0) / 1000).toFixed(0)} s`);
}
console.log();
await writeFile(join(ROOT, "web", "tiles", "grid.json"), JSON.stringify({ ...info, rendered: kept }));
await browser.close();
server.close();
