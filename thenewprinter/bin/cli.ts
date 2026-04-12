#!/usr/bin/env node
import { Command } from 'commander';
import { chromium } from 'playwright';
import { readFile, writeFile } from 'fs/promises';
import { resolve, join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { spawn, type ChildProcess } from 'child_process';

import { buildPdf } from '../lib/pdf-generator.js';
import type { ImageFetcher } from '../lib/pdf-generator.js';
import type { PageContent, ExtractedArticle, TemplateId } from '../lib/types.js';

// ── helpers ──────────────────────────────────────────────────────────────────

async function waitForPort(url: string, timeoutMs = 30_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(1000) });
      if (res.ok || res.status < 500) return;
    } catch { /* not ready yet */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Server at ${url} did not become ready within ${timeoutMs}ms`);
}

async function startDevServer(cwd: string): Promise<{ proc: ChildProcess; url: string }> {
  const url = 'http://localhost:3000';
  const proc = spawn('npm', ['run', 'dev'], { cwd, stdio: 'pipe', detached: false });
  proc.stderr?.on('data', (d: Buffer) => process.stderr.write(d));
  await waitForPort(url);
  return { proc, url };
}

/** Convert a Node.js Buffer to a plain ArrayBuffer (safe copy, not a slice of a shared pool). */
function toArrayBuffer(buf: Buffer): ArrayBuffer {
  const ab = new ArrayBuffer(buf.byteLength);
  new Uint8Array(ab).set(buf);
  return ab;
}

// ── CLI ───────────────────────────────────────────────────────────────────────

const program = new Command();

program
  .name('thenewprinter')
  .description('Print any article as a multi-column PDF')
  .argument('<article-url>', 'URL of the article to print')
  .option('-t, --template <template>', 'two-column or three-column', 'two-column')
  .option('-o, --output <file>', 'Output PDF path (default: <article-title>.pdf)')
  .option('-s, --server <url>', 'TheNewPrinter server URL. If omitted, starts a local dev server.')
  .option('--timeout <ms>', 'Max ms to wait for layout to render', '15000')
  .action(async (articleUrl: string, opts: {
    template: string; output?: string; server?: string; timeout: string;
  }) => {
    const template: TemplateId = opts.template === 'three-column' ? 'three-column' : 'two-column';
    const layoutTimeout = parseInt(opts.timeout, 10);

    // ── Resolve server ────────────────────────────────────────────────────────
    let serverUrl = opts.server?.replace(/\/$/, '');
    let devProc: ChildProcess | null = null;

    if (!serverUrl) {
      let running = false;
      try {
        const r = await fetch('http://localhost:3000', { signal: AbortSignal.timeout(1500) });
        running = r.status < 500;
      } catch { /* not running */ }

      if (running) {
        serverUrl = 'http://localhost:3000';
        process.stderr.write('Using existing server at http://localhost:3000\n');
      } else {
        process.stderr.write('Starting dev server…\n');
        const appDir = new URL('../', import.meta.url).pathname;
        const { proc, url } = await startDevServer(appDir);
        devProc = proc;
        serverUrl = url;
        process.stderr.write('Server ready.\n');
      }
    }

    // ── Extract layout via browser ────────────────────────────────────────────
    const printUrl = `${serverUrl}/print?url=${encodeURIComponent(articleUrl)}&template=${template}`;

    const browser = await chromium.launch();
    const page    = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    let pages: PageContent[];
    let article: ExtractedArticle;

    try {
      process.stderr.write(`Extracting layout from ${printUrl}\n`);
      await page.goto(printUrl, { waitUntil: 'networkidle' });

      // Wait until PrintLayout has set window.__LAYOUT_PAGES__
      await page.waitForFunction(
        () => Array.isArray((window as unknown as Record<string, unknown>)['__LAYOUT_PAGES__']) &&
              ((window as unknown as Record<string, unknown>)['__LAYOUT_PAGES__'] as unknown[]).length > 0,
        { timeout: layoutTimeout },
      );

      const data = await page.evaluate(() => ({
        pages:   (window as unknown as Record<string, unknown>)['__LAYOUT_PAGES__'],
        article: (window as unknown as Record<string, unknown>)['__LAYOUT_ARTICLE__'],
      }));

      pages   = data.pages   as PageContent[];
      article = data.article as ExtractedArticle;
      process.stderr.write(`  Layout ready: ${pages.length} page(s)\n`);
    } finally {
      await browser.close();
      devProc?.kill();
    }

    // ── Load fonts from filesystem ────────────────────────────────────────────
    const fontsDir = join(dirname(fileURLToPath(import.meta.url)), '../public/fonts');
    const [regularBuf, boldBuf, italicBuf] = await Promise.all([
      readFile(join(fontsDir, 'lora-regular.woff')).then(toArrayBuffer),
      readFile(join(fontsDir, 'lora-bold.woff')).then(toArrayBuffer),
      readFile(join(fontsDir, 'lora-italic.woff')).then(toArrayBuffer),
    ]);

    // ── Image fetcher (Node.js — no CORS restrictions) ────────────────────────
    const fetchImage: ImageFetcher = async (url) => {
      try {
        const res = await fetch(url, { headers: { 'User-Agent': 'TheNewPrinter/1.0' } });
        return res.ok ? res.arrayBuffer() : null;
      } catch { return null; }
    };

    // ── Generate PDF with pdf-lib ─────────────────────────────────────────────
    process.stderr.write('Generating PDF…\n');
    const pdfBytes = await buildPdf(
      pages, article, template,
      { regular: regularBuf, bold: boldBuf, italic: italicBuf },
      fetchImage,
    );

    // ── Write output ──────────────────────────────────────────────────────────
    let outputPath = opts.output;
    if (!outputPath) {
      const slug = article.title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
        .slice(0, 60);
      outputPath = `${slug}.pdf`;
    }
    outputPath = resolve(process.cwd(), outputPath);
    await writeFile(outputPath, pdfBytes);
    console.log(outputPath);
  });

program.parseAsync(process.argv).catch((err) => {
  process.stderr.write(`${err.message}\n`);
  process.exit(1);
});
