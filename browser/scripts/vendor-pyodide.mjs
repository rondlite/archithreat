// One-time vendoring step: download a pinned Pyodide release tarball into
// vendor/pyodide/. Run this once after cloning the repo, or whenever the
// pinned version changes. Network access is required only here, never at
// build or runtime.
//
// Usage: node scripts/vendor-pyodide.mjs

import { createWriteStream, existsSync } from 'node:fs';
import { mkdir, readdir, rename, rm } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { pipeline } from 'node:stream/promises';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const dst = join(root, 'vendor', 'pyodide');

// Pinned Pyodide version. Bump deliberately and re-test.
const VERSION = '0.26.4';
const URL = `https://github.com/pyodide/pyodide/releases/download/${VERSION}/pyodide-${VERSION}.tar.bz2`;

async function fetchTo(url, dest) {
  console.log(`fetching ${url}`);
  const res = await fetch(url, { redirect: 'follow' });
  if (!res.ok || !res.body) throw new Error(`fetch failed: ${res.status}`);
  await pipeline(res.body, createWriteStream(dest));
}

function run(cmd, args, opts = {}) {
  return new Promise((res, rej) => {
    const p = spawn(cmd, args, { stdio: 'inherit', ...opts });
    p.on('exit', (code) => (code === 0 ? res() : rej(new Error(`${cmd} exit ${code}`))));
  });
}

async function main() {
  await mkdir(dst, { recursive: true });
  // Clear out any previous contents except .gitkeep.
  for (const e of await readdir(dst)) {
    if (e !== '.gitkeep') await rm(join(dst, e), { recursive: true, force: true });
  }
  const tarPath = join(dst, `pyodide-${VERSION}.tar.bz2`);
  await fetchTo(URL, tarPath);
  console.log('extracting…');
  await run('tar', ['-xjf', tarPath, '-C', dst]);
  // Tarball extracts into vendor/pyodide/pyodide/* — flatten it.
  const inner = join(dst, 'pyodide');
  if (existsSync(inner)) {
    for (const e of await readdir(inner)) {
      await rename(join(inner, e), join(dst, e));
    }
    await rm(inner, { recursive: true, force: true });
  }
  await rm(tarPath, { force: true });
  console.log(`vendored Pyodide ${VERSION} → ${dst}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
