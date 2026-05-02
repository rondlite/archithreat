// One-time vendoring step: download a pinned drawio viewer bundle into
// vendor/drawio/. Run once after cloning, or whenever the pinned version
// changes. Network access is required only here, never at build or runtime.
//
// Usage: node scripts/vendor-drawio.mjs

import { createWriteStream } from 'node:fs';
import { mkdir, readdir, rm } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { pipeline } from 'node:stream/promises';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const dst = join(root, 'vendor', 'drawio');

// Pinned drawio release. Bump deliberately and re-test the Preview button.
const VERSION = '24.7.17';
const URL =
  `https://raw.githubusercontent.com/jgraph/drawio/v${VERSION}/src/main/webapp/js/viewer-static.min.js`;

async function fetchTo(url, dest) {
  console.log(`fetching ${url}`);
  const res = await fetch(url, { redirect: 'follow' });
  if (!res.ok || !res.body) throw new Error(`fetch failed: ${res.status} ${res.statusText}`);
  await pipeline(res.body, createWriteStream(dest));
}

async function main() {
  await mkdir(dst, { recursive: true });
  for (const e of await readdir(dst)) {
    if (e !== '.gitkeep') await rm(join(dst, e), { recursive: true, force: true });
  }
  await fetchTo(URL, join(dst, 'viewer-static.min.js'));
  console.log(`drawio viewer v${VERSION} vendored → ${dst}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
