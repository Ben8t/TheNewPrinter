import { readFile } from 'fs/promises';
import { existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { NextRequest, NextResponse } from 'next/server';
import { buildPdf } from '@/lib/pdf-generator';
import type { PageContent, ExtractedArticle, TemplateId } from '@/lib/types';

const FONT_FILE = 'LiberationSans-Regular.ttf';

// Resolve fonts directory — cwd can be the repo root or the Next.js app root
// depending on how npm run dev was invoked.
function fontsDir(): string {
  const candidates = [
    join(process.cwd(), 'public', 'fonts'),
    join(process.cwd(), 'thenewprinter', 'public', 'fonts'),
  ];
  // Also try relative to this file's location (works in some build outputs)
  try {
    candidates.unshift(join(dirname(fileURLToPath(import.meta.url)), '../../../../public/fonts'));
  } catch { /* import.meta.url may not be a file: URL in Turbopack dev */ }

  return candidates.find(d => existsSync(join(d, FONT_FILE))) ?? candidates[0];
}

export async function POST(req: NextRequest) {
  let pages: PageContent[], article: ExtractedArticle, template: TemplateId;
  try {
    const body = await req.json();
    pages    = body.pages;
    article  = body.article;
    template = body.template ?? 'two-column';
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  // Load Liberation Sans font files from filesystem (server-side only)
  const dir = fontsDir();
  let regular: ArrayBuffer, bold: ArrayBuffer, italic: ArrayBuffer;
  try {
    [regular, bold, italic] = await Promise.all([
      readFile(join(dir, 'LiberationSans-Regular.ttf')).then(b => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer),
      readFile(join(dir, 'LiberationSans-Bold.ttf')).then(b    => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer),
      readFile(join(dir, 'LiberationSans-Italic.ttf')).then(b  => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer),
    ]);
  } catch (err) {
    console.error('[generate-pdf] font load failed from', dir, ':', err);
    return NextResponse.json({ error: `Font load failed: ${err}` }, { status: 500 });
  }

  // Proxy images server-side (no CORS restrictions)
  const fetchImage = async (url: string): Promise<ArrayBuffer | null> => {
    try {
      const res = await fetch(url, { headers: { 'User-Agent': 'TheNewPrinter/1.0' } });
      return res.ok ? res.arrayBuffer() : null;
    } catch { return null; }
  };

  let pdfBytes: Uint8Array;
  try {
    pdfBytes = await buildPdf(pages, article, template, { regular, bold, italic }, fetchImage);
  } catch (err) {
    console.error('[generate-pdf] buildPdf failed:', err);
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }

  const slug = article.title
    .replace(/[^a-z0-9]+/gi, '-')
    .toLowerCase()
    .slice(0, 60);

  return new NextResponse(Buffer.from(pdfBytes), {
    status: 200,
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': `attachment; filename="${slug}.pdf"`,
    },
  });
}
