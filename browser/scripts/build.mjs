// Build script: bundle JS with esbuild, copy static assets, vendored Pyodide,
// and the core wheel into dist/. No network access at build time.
//
// Usage: node scripts/build.mjs

import { build } from 'esbuild';
import { cp, mkdir, readdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const dist = join(root, 'dist');

async function main() {
  await rm(dist, { recursive: true, force: true });
  await mkdir(dist, { recursive: true });
  await mkdir(join(dist, 'wheels'), { recursive: true });

  // index.html: substitute __ARCHITHREAT_VERSION__ with version from
  // pyproject.toml so the footer shows the same version as the wheel.
  const pyproject = await readFile(join(root, '..', 'pyproject.toml'), 'utf8');
  const versionMatch = pyproject.match(/^version\s*=\s*"([^"]+)"/m);
  if (!versionMatch) throw new Error('could not find version in pyproject.toml');
  const version = versionMatch[1];
  const html = await readFile(join(root, 'index.html'), 'utf8');
  await writeFile(
    join(dist, 'index.html'),
    html.replace(/__ARCHITHREAT_VERSION__/g, version),
  );
  await cp(join(root, 'style.css'), join(dist, 'style.css'));

  // Bundle main thread JS.
  await build({
    entryPoints: [join(root, 'main.js')],
    outfile: join(dist, 'main.js'),
    bundle: true,
    minify: true,
    format: 'esm',
    target: ['es2022'],
    sourcemap: true,
  });

  // Bundle worker — separate context, classic worker (importScripts).
  await build({
    entryPoints: [join(root, 'worker.js')],
    outfile: join(dist, 'worker.js'),
    bundle: true,
    minify: true,
    format: 'iife',
    platform: 'browser',
    target: ['es2022'],
    sourcemap: true,
  });

  // Copy vendored Pyodide if present. Build still succeeds without it so
  // first-time contributors can run `npm run build` before `vendor:pyodide`,
  // but the smoke test will fail at runtime.
  const pyodideSrc = join(root, 'vendor', 'pyodide');
  const pyodideDst = join(dist, 'pyodide');
  if (existsSync(pyodideSrc)) {
    const entries = await readdir(pyodideSrc);
    const real = entries.filter((e) => e !== '.gitkeep');
    if (real.length > 0) {
      await cp(pyodideSrc, pyodideDst, { recursive: true });
      console.log(`copied vendored Pyodide (${real.length} entries)`);
    } else {
      console.warn('vendor/pyodide is empty — run `npm run vendor:pyodide`');
    }
  } else {
    console.warn('vendor/pyodide does not exist — run `npm run vendor:pyodide`');
  }

  // Copy vendored drawio viewer if present. Build still succeeds without
  // it — the Preview button stays hidden when the viewer is unavailable.
  const drawioSrc = join(root, 'vendor', 'drawio');
  const drawioDst = join(dist, 'drawio');
  if (existsSync(drawioSrc)) {
    const entries = (await readdir(drawioSrc)).filter((e) => e !== '.gitkeep');
    if (entries.length > 0) {
      await cp(drawioSrc, drawioDst, { recursive: true });
      console.log(`copied vendored drawio viewer (${entries.length} entries)`);
    } else {
      console.warn('vendor/drawio is empty — run `npm run vendor:drawio` to enable Preview');
    }
  } else {
    console.warn('vendor/drawio does not exist — run `npm run vendor:drawio` to enable Preview');
  }

  // Note about the wheel: build:wheel is a separate script so this script
  // does not depend on Python being available.
  const wheels = join(dist, 'wheels');
  const wheelEntries = existsSync(wheels) ? await readdir(wheels) : [];
  if (wheelEntries.filter((f) => f.endsWith('.whl')).length === 0) {
    console.warn('dist/wheels/ contains no .whl — run `npm run build:wheel`');
  }

  console.log(`build complete → ${dist}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
