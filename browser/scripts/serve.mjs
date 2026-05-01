// Tiny static dev server for dist/. No dependencies; for local development only.
// Usage: node scripts/serve.mjs [port]

import { createServer } from 'node:http';
import { createReadStream, existsSync, statSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..', 'dist');
const port = Number(process.argv[2] || process.env.PORT || 8080);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.wasm': 'application/wasm',
  '.whl': 'application/octet-stream',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.map': 'application/json; charset=utf-8',
  '.data': 'application/octet-stream',
  '.zip': 'application/zip',
};

if (!existsSync(root)) {
  console.error(`dist/ not found at ${root}. Run \`npm run build\` first.`);
  process.exit(1);
}

const server = createServer((req, res) => {
  const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
  let safe = normalize(urlPath).replace(/^\/+/, '');
  if (safe === '' || safe.endsWith('/')) safe = join(safe, 'index.html');
  const filePath = join(root, safe);

  if (!filePath.startsWith(root)) {
    res.writeHead(403);
    res.end('forbidden');
    return;
  }
  if (!existsSync(filePath) || !statSync(filePath).isFile()) {
    res.writeHead(404);
    res.end('not found');
    return;
  }
  const type = MIME[extname(filePath)] || 'application/octet-stream';
  // Pyodide and SharedArrayBuffer are happier with these headers.
  res.writeHead(200, {
    'Content-Type': type,
    'Cache-Control': 'no-store',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Embedder-Policy': 'require-corp',
    'Cross-Origin-Resource-Policy': 'same-origin',
  });
  createReadStream(filePath).pipe(res);
});

server.listen(port, '127.0.0.1', () => {
  console.log(`archithreat browser shell → http://127.0.0.1:${port}/`);
});
