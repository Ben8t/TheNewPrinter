#!/usr/bin/env node
import { Command } from 'commander';
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { resolve } from 'path';
import { spawn, type ChildProcess } from 'child_process';

// ── helpers ──────────────────────────────────────────────────────────────────

async function waitForPort(url: string, timeoutMs = 30_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(1000) });
      if (res.ok || res.status < 500) return;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Server at ${url} did not become ready within ${timeoutMs}ms`);
}

async function startDevServer(cwd: string): Promise<{ proc: ChildProcess; url: string }> {
  const url = 'http://localhost:3000';
  const proc = spawn('npm', ['run', 'dev'], {
    cwd,
    stdio: 'pipe',
    detached: false,
  });

  proc.stderr?.on('data', (d: Buffer) => process.stderr.write(d));

  await waitForPort(url);
  return { proc, url };
}

// ── CLI ───────────────────────────────────────────────────────────────────────

const program = new Command();

program
  .name('thenewprinter')
  .description('Print any article as a multi-column PDF')
  .argument('<article-url>', 'URL of the article to print')
  .option('-t, --template <template>', 'two-column or three-column', 'two-column')
  .option('-o, --output <file>', 'Output PDF path (default: <article-title>.pdf)')
  .option(
    '-s, --server <url>',
    'TheNewPrinter server URL. If omitted, starts a local dev server automatically.',
  )
  .option('--timeout <ms>', 'Max ms to wait for layout to render', '15000')
  .action(async (articleUrl: string, opts: {
    template: string;
    output?: string;
    server?: string;
    timeout: string;
  }) => {
    const template = opts.template === 'three-column' ? 'three-column' : 'two-column';
    const layoutTimeout = parseInt(opts.timeout, 10);

    // ── Resolve server ────────────────────────────────────────────────────────
    let serverUrl = opts.server?.replace(/\/$/, '');
    let devProc: ChildProcess | null = null;

    if (!serverUrl) {
      // Check if something is already on port 3000
      let running = false;
      try {
        const r = await fetch('http://localhost:3000', { signal: AbortSignal.timeout(1500) });
        running = r.status < 500;
      } catch { /* not running */ }

      if (running) {
        serverUrl = 'http://localhost:3000';
        console.error('Using existing server at http://localhost:3000');
      } else {
        console.error('Starting dev server…');
        const appDir = new URL('../', import.meta.url).pathname;
        const { proc, url } = await startDevServer(appDir);
        devProc = proc;
        serverUrl = url;
        console.error('Server ready.');
      }
    }

    // ── Launch browser ────────────────────────────────────────────────────────
    const printUrl =
      `${serverUrl}/print?url=${encodeURIComponent(articleUrl)}&template=${template}`;

    const browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

    try {
      console.error(`Navigating to ${printUrl}`);
      await page.goto(printUrl, { waitUntil: 'networkidle' });

      // Wait until at least one print-page has rendered columns
      await page.waitForFunction(
        () => {
          const pages = document.querySelectorAll('.print-page');
          if (pages.length === 0) return false;
          // Check layout has run: at least one text-line or block-image exists
          return (
            document.querySelector('.text-line') !== null ||
            document.querySelector('.block-image') !== null
          );
        },
        { timeout: layoutTimeout },
      );

      // Give fonts + images a moment to settle
      await page.waitForTimeout(500);

      // ── Derive output path ────────────────────────────────────────────────
      let outputPath = opts.output;
      if (!outputPath) {
        const title = await page
          .locator('.article-title')
          .first()
          .textContent()
          .catch(() => null);
        const slug = (title ?? 'article')
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/^-|-$/g, '')
          .slice(0, 60);
        outputPath = `${slug}.pdf`;
      }
      outputPath = resolve(process.cwd(), outputPath);

      // ── Save PDF ──────────────────────────────────────────────────────────
      const pdf = await page.pdf({
        format: 'A4',
        margin: { top: '15mm', bottom: '20mm', left: '12mm', right: '12mm' },
        printBackground: true,
      });

      writeFileSync(outputPath, pdf);
      console.log(outputPath);
    } finally {
      await browser.close();
      if (devProc) {
        devProc.kill();
      }
    }
  });

program.parseAsync(process.argv).catch((err) => {
  console.error(err.message);
  process.exit(1);
});
