import { readFile } from 'fs/promises';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { NextRequest, NextResponse } from 'next/server';
import { buildPdf } from '@/lib/pdf-generator';
import type { PageContent, ExtractedArticle, TemplateId } from '@/lib/types';

// Resolve fonts directory relative to this file (works in dev and after build)
function fontsDir(): string {
  try {
    return join(dirname(fileURLToPath(import.meta.url)), '../../../../public/fonts');
  } catch {
    return join(process.cwd(), 'public/fonts');
  }
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
  const [regular, bold, italic] = await Promise.all([
    readFile(join(dir, 'LiberationSans-Regular.ttf')).then(b => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer),
    readFile(join(dir, 'LiberationSans-Bold.ttf')).then(b    => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer),
    readFile(join(dir, 'LiberationSans-Italic.ttf')).then(b  => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer),
  ]);

  // Proxy images server-side (no CORS restrictions)
  const fetchImage = async (url: string): Promise<ArrayBuffer | null> => {
    try {
      const res = await fetch(url, { headers: { 'User-Agent': 'TheNewPrinter/1.0' } });
      return res.ok ? res.arrayBuffer() : null;
    } catch { return null; }
  };

  const pdfBytes = await buildPdf(pages, article, template, { regular, bold, italic }, fetchImage);

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
