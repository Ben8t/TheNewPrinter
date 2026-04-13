// Works in both Node.js (API route) and browser (generateAndDownloadPdf).
// Do NOT add 'use client' — this file is imported by the server-side API route.

import {
  PDFDocument, PDFFont, PDFPage, rgb,
  pushGraphicsState, popGraphicsState,
  moveTo, lineTo, closePath, clip, endPath,
} from 'pdf-lib';
import fontkit from '@pdf-lib/fontkit';
import type { ExtractedArticle, PageContent, RenderedBlock, TemplateId } from './types';
import { LIST_ITEM_GAP_PX, LIST_BLOCK_PADDING_PX } from './layout-engine';

// ─── WOFF1 → TTF conversion ──────────────────────────────────────────────────
// @pdf-lib/fontkit's tinyInflate can mishandle WOFF1 table decompression,
// producing corrupt glyph maps. Convert to raw TTF first to be safe.

async function decompressZlib(raw: Uint8Array, origLen: number): Promise<Uint8Array> {
  if (typeof DecompressionStream !== 'undefined') {
    // Browser: DecompressionStream with 'deflate' handles zlib-wrapped deflate
    const ds     = new DecompressionStream('deflate');
    const writer = ds.writable.getWriter();
    const reader = ds.readable.getReader();
    writer.write(raw as unknown as ArrayBuffer);
    writer.close();
    const chunks: Uint8Array[] = [];
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value) chunks.push(value);
    }
    const out = new Uint8Array(origLen);
    let pos = 0;
    for (const c of chunks) { out.set(c, pos); pos += c.length; }
    return out;
  } else {
    // Node.js
    const { inflateSync } = await import('zlib');
    return new Uint8Array(inflateSync(raw));
  }
}

async function woffToTtf(buf: ArrayBuffer): Promise<ArrayBuffer> {
  const view = new DataView(buf);
  // 'wOFF' magic = 0x774F4646
  if (view.getUint32(0) !== 0x774F4646) return buf; // not WOFF1 — pass through

  const flavor    = view.getUint32(4);
  const numTables = view.getUint16(12);

  interface WoffEntry { tag: number; offset: number; compLen: number; origLen: number; checksum: number }
  const entries: WoffEntry[] = [];
  for (let i = 0; i < numTables; i++) {
    const b = 44 + i * 20;
    entries.push({
      tag:      view.getUint32(b),
      offset:   view.getUint32(b + 4),
      compLen:  view.getUint32(b + 8),
      origLen:  view.getUint32(b + 12),
      checksum: view.getUint32(b + 16),
    });
  }

  // Decompress all tables
  const tables: Uint8Array[] = await Promise.all(entries.map((e) => {
    const raw = new Uint8Array(buf, e.offset, e.compLen);
    if (e.compLen === e.origLen) return Promise.resolve(raw.slice()); // uncompressed
    return decompressZlib(raw, e.origLen);
  }));

  // Compute sfnt header values
  let entrySelector = 0, maxPow2 = 1;
  while (maxPow2 * 2 <= numTables) { maxPow2 *= 2; entrySelector++; }
  const searchRange = maxPow2 * 16;
  const rangeShift  = numTables * 16 - searchRange;

  // Compute table offsets (4-byte aligned after the sfnt header)
  const headerSize = 12 + numTables * 16;
  const tableOffsets: number[] = [];
  let cursor = headerSize;
  for (const t of tables) {
    cursor = (cursor + 3) & ~3;
    tableOffsets.push(cursor);
    cursor += t.byteLength;
  }
  cursor = (cursor + 3) & ~3;

  const ttf = new Uint8Array(cursor);
  const out  = new DataView(ttf.buffer);

  // sfnt header
  out.setUint32(0,  flavor);
  out.setUint16(4,  numTables);
  out.setUint16(6,  searchRange);
  out.setUint16(8,  entrySelector);
  out.setUint16(10, rangeShift);

  // table records
  for (let i = 0; i < numTables; i++) {
    const b = 12 + i * 16;
    out.setUint32(b,      entries[i].tag);
    out.setUint32(b + 4,  entries[i].checksum);
    out.setUint32(b + 8,  tableOffsets[i]);
    out.setUint32(b + 12, entries[i].origLen);
  }

  // table data
  for (let i = 0; i < tables.length; i++) ttf.set(tables[i], tableOffsets[i]);

  return ttf.buffer;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const MM_TO_PT = 2.8346;
const PX_TO_PT = 0.75; // 96dpi screen → 72dpi PDF

// A4
const PAGE_W = 595.276;
const PAGE_H = 841.89;

// Margins (from @page CSS)
const MARGIN_TOP = 15 * MM_TO_PT; // 42.52pt
const MARGIN_LR  = 12 * MM_TO_PT; // 34.02pt

const CONTENT_W = PAGE_W - MARGIN_LR * 2; // 527.24pt
const COL_GAP   =  5 * MM_TO_PT;           // 14.17pt

// Typography
const FONT_SIZES = {
  masthead:   7,
  body:       9,
  h1:        20,
  h2:        12,
  h3:        10,
  h4:         9,
  blockquote: 9,
  byline:     8,
  excerpt:    9,
  title:     20,
};

const LINE_HEIGHTS_PT = {
  masthead:   7  * 1.4,
  body:       9  * 1.45,
  h1:        20  * 1.15,
  h2:        12  * 1.3,
  h3:        10  * 1.3,
  h4:         9  * 1.3,
  blockquote: 9  * 1.45,
  byline:     8  * 1.4,
  excerpt:    9  * 1.45,
  title:     20  * 1.15,
};

// ─── Types ────────────────────────────────────────────────────────────────────

export type ImageFetcher = (url: string) => Promise<ArrayBuffer | null>;

export interface FontBuffers {
  regular: ArrayBuffer;
  bold:    ArrayBuffer;
  italic:  ArrayBuffer;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function colPositions(colCount: number): { x: number; width: number }[] {
  const colW = (CONTENT_W - COL_GAP * (colCount - 1)) / colCount;
  return Array.from({ length: colCount }, (_, i) => ({
    x: MARGIN_LR + i * (colW + COL_GAP),
    width: colW,
  }));
}

function wrapText(text: string, font: PDFFont, size: number, maxWidth: number): string[] {
  const words = text.split(' ');
  const lines: string[] = [];
  let current = '';
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    try {
      if (font.widthOfTextAtSize(candidate, size) <= maxWidth) {
        current = candidate;
      } else {
        if (current) lines.push(current);
        current = word;
      }
    } catch {
      current = candidate;
    }
  }
  if (current) lines.push(current);
  return lines;
}

function safeDrawText(page: PDFPage, text: string, options: Parameters<PDFPage['drawText']>[1]) {
  try {
    page.drawText(text, options);
  } catch {
    const safe = text.replace(/[^\u0000-\u00FF]/g, '?');
    try { page.drawText(safe, options); } catch { /* skip */ }
  }
}

// ─── Image embedding ─────────────────────────────────────────────────────────

async function tryEmbedImage(doc: PDFDocument, url: string, fetchImage: ImageFetcher) {
  try {
    const buf = await fetchImage(url);
    if (!buf) return null;
    const bytes = new Uint8Array(buf);
    if (bytes[0] === 0xFF && bytes[1] === 0xD8) return await doc.embedJpg(buf);
    if (bytes[0] === 0x89 && bytes[1] === 0x50) return await doc.embedPng(buf);
    return null;
  } catch {
    return null;
  }
}

// ─── Header drawing ──────────────────────────────────────────────────────────

async function drawHeader(
  doc: PDFDocument,
  page: PDFPage,
  article: ExtractedArticle,
  fonts: { regular: PDFFont; bold: PDFFont; italic: PDFFont },
  fetchImage: ImageFetcher,
): Promise<number> {
  let cursorFromTop = MARGIN_TOP;
  const black = rgb(0, 0, 0);
  const grey  = rgb(0.2, 0.2, 0.2);
  const drawY = (fromTop: number) => PAGE_H - fromTop;

  // Masthead
  const publishedDate = article.publishedTime
    ? new Date(article.publishedTime).toLocaleDateString('en-US', {
        year: 'numeric', month: 'long', day: 'numeric',
      })
    : null;

  safeDrawText(page, article.siteName ?? 'TheNewPrinter', {
    x: MARGIN_LR,
    y: drawY(cursorFromTop + FONT_SIZES.masthead),
    font: fonts.regular, size: FONT_SIZES.masthead, color: grey,
  });
  if (publishedDate) {
    const dateW = fonts.regular.widthOfTextAtSize(publishedDate, FONT_SIZES.masthead);
    safeDrawText(page, publishedDate, {
      x: MARGIN_LR + CONTENT_W - dateW,
      y: drawY(cursorFromTop + FONT_SIZES.masthead),
      font: fonts.regular, size: FONT_SIZES.masthead, color: grey,
    });
  }
  cursorFromTop += LINE_HEIGHTS_PT.masthead + 2;

  page.drawLine({
    start: { x: MARGIN_LR, y: drawY(cursorFromTop) },
    end:   { x: MARGIN_LR + CONTENT_W, y: drawY(cursorFromTop) },
    thickness: 0.5, color: black,
  });
  cursorFromTop += 4;

  // Title
  for (const line of wrapText(article.title, fonts.bold, FONT_SIZES.title, CONTENT_W)) {
    safeDrawText(page, line, {
      x: MARGIN_LR,
      y: drawY(cursorFromTop + LINE_HEIGHTS_PT.title * 0.8),
      font: fonts.bold, size: FONT_SIZES.title, color: black,
    });
    cursorFromTop += LINE_HEIGHTS_PT.title;
  }
  cursorFromTop += 3;

  // Byline
  if (article.byline) {
    safeDrawText(page, article.byline, {
      x: MARGIN_LR,
      y: drawY(cursorFromTop + FONT_SIZES.byline),
      font: fonts.italic, size: FONT_SIZES.byline, color: grey,
    });
    cursorFromTop += LINE_HEIGHTS_PT.byline + 2;
  }

  // Excerpt
  if (article.excerpt) {
    for (const line of wrapText(article.excerpt, fonts.italic, FONT_SIZES.excerpt, CONTENT_W)) {
      safeDrawText(page, line, {
        x: MARGIN_LR,
        y: drawY(cursorFromTop + FONT_SIZES.excerpt),
        font: fonts.italic, size: FONT_SIZES.excerpt, color: grey,
      });
      cursorFromTop += LINE_HEIGHTS_PT.excerpt;
    }
    cursorFromTop += 3;
  }

  // Lead image (full width, max 60mm, top-cropped like object-fit: cover)
  if (article.leadImageUrl) {
    const img = await tryEmbedImage(doc, article.leadImageUrl, fetchImage);
    if (img) {
      const maxH    = 60 * MM_TO_PT;
      const dims    = img.scale(1);
      const scaledH = CONTENT_W * (dims.height / dims.width);
      const displayH = Math.min(scaledH, maxH);
      const boxTop    = PAGE_H - cursorFromTop;
      const boxBottom = boxTop - displayH;

      if (scaledH <= maxH) {
        page.drawImage(img, { x: MARGIN_LR, y: boxBottom, width: CONTENT_W, height: scaledH });
      } else {
        page.pushOperators(
          pushGraphicsState(),
          moveTo(MARGIN_LR, boxBottom),
          lineTo(MARGIN_LR + CONTENT_W, boxBottom),
          lineTo(MARGIN_LR + CONTENT_W, boxTop),
          lineTo(MARGIN_LR, boxTop),
          closePath(), clip(), endPath(),
        );
        page.drawImage(img, { x: MARGIN_LR, y: boxTop - scaledH, width: CONTENT_W, height: scaledH });
        page.pushOperators(popGraphicsState());
      }
      cursorFromTop += displayH + 4;
    }
  }

  // Rule before columns
  page.drawLine({
    start: { x: MARGIN_LR, y: drawY(cursorFromTop) },
    end:   { x: MARGIN_LR + CONTENT_W, y: drawY(cursorFromTop) },
    thickness: 0.5, color: black,
  });
  cursorFromTop += 6;

  return cursorFromTop;
}

// ─── Block drawing ────────────────────────────────────────────────────────────

function blockFontAndSize(rb: RenderedBlock, fonts: { regular: PDFFont; bold: PDFFont; italic: PDFFont }) {
  const { block } = rb;
  if (block.type === 'heading') {
    const size = FONT_SIZES[`h${block.level}` as keyof typeof FONT_SIZES] ?? 9;
    const lh   = LINE_HEIGHTS_PT[`h${block.level}` as keyof typeof LINE_HEIGHTS_PT] ?? 9 * 1.3;
    return { font: fonts.bold, size, lineHeightPt: lh };
  }
  if (block.type === 'blockquote') {
    return { font: fonts.italic, size: FONT_SIZES.blockquote, lineHeightPt: LINE_HEIGHTS_PT.blockquote };
  }
  return { font: fonts.regular, size: FONT_SIZES.body, lineHeightPt: LINE_HEIGHTS_PT.body };
}

async function drawBlock(
  doc: PDFDocument,
  page: PDFPage,
  rb: RenderedBlock,
  colX: number,
  colW: number,
  colTopY: number,
  offsetFromTop: number,
  fonts: { regular: PDFFont; bold: PDFFont; italic: PDFFont },
  fetchImage: ImageFetcher,
): Promise<number> {
  const { block } = rb;
  const black = rgb(0, 0, 0);

  if (block.type === 'image') {
    const heightPt = rb.totalHeight * PX_TO_PT;
    const img = await tryEmbedImage(doc, block.src, fetchImage);
    if (img) {
      const dims = img.scale(1);
      const ratio = dims.height / dims.width;
      const drawH = Math.min(heightPt, colW * ratio);
      const drawW = drawH / ratio;
      page.drawImage(img, { x: colX, y: colTopY - offsetFromTop - drawH, width: drawW, height: drawH });
    }
    return offsetFromTop + heightPt;
  }

  const { font, size, lineHeightPt } = blockFontAndSize(rb, fonts);
  const listItemGapPt  = LIST_ITEM_GAP_PX    * PX_TO_PT;
  const listBlockPadPt = LIST_BLOCK_PADDING_PX * PX_TO_PT;

  if (block.type === 'list') offsetFromTop += listBlockPadPt;

  if (block.type === 'blockquote') {
    const totalPt = rb.lines.filter(l => l !== '').length * lineHeightPt;
    page.drawRectangle({
      x: colX, y: colTopY - offsetFromTop - totalPt,
      width: 0.75, height: totalPt, color: rgb(0.2, 0.2, 0.2),
    });
  }

  const textX = block.type === 'blockquote' ? colX + 4 : colX;

  for (const line of rb.lines) {
    if (line === '') { offsetFromTop += listItemGapPt; continue; }
    safeDrawText(page, line, {
      x: textX,
      y: colTopY - offsetFromTop - lineHeightPt * 0.8,
      font, size, color: black,
    });
    offsetFromTop += lineHeightPt;
  }

  if (block.type === 'list') offsetFromTop += listBlockPadPt;

  return offsetFromTop;
}

// ─── Core PDF builder (works in both browser and Node.js) ────────────────────

export async function buildPdf(
  pages: PageContent[],
  article: ExtractedArticle,
  template: TemplateId,
  fontBuffers: FontBuffers,
  fetchImage: ImageFetcher,
): Promise<Uint8Array> {
  // Convert WOFF1 → TTF before embedding; fontkit's tinyInflate can mishandle
  // WOFF table decompression and produce corrupt glyph maps in the subset.
  const [regBuf, boldBuf, italicBuf] = await Promise.all([
    woffToTtf(fontBuffers.regular),
    woffToTtf(fontBuffers.bold),
    woffToTtf(fontBuffers.italic),
  ]);

  const doc = await PDFDocument.create();
  doc.registerFontkit(fontkit);
  // subset: false embeds the full font — avoids glyph outline corruption
  // that occurs when fontkit's subsetting mishandles composite/variable glyphs.
  const regular = await doc.embedFont(regBuf,    { subset: false });
  const bold    = await doc.embedFont(boldBuf,   { subset: false });
  const italic  = await doc.embedFont(italicBuf, { subset: false });

  // Disable OpenType ligature substitution (liga, clig) on all three fonts.
  // Without this, fontkit's GSUB maps "fi" → ligature glyph whose CID collides
  // with other characters in the subset, causing visual corruption.
  // NOTE: spread order matters — liga/clig must come LAST to win over any caller features.
  for (const pdfFont of [regular, bold, italic]) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fkFont = (pdfFont as any).embedder?.font;
    if (fkFont?.layout) {
      const orig = fkFont.layout.bind(fkFont);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      fkFont.layout = (text: string, features?: Record<string, unknown>, ...rest: any[]) =>
        orig(text, { ...features, liga: false, clig: false }, ...rest);
    }
  }

  const fonts   = { regular, bold, italic };

  const colCount = template === 'three-column' ? 3 : 2;
  const cols     = colPositions(colCount);

  for (let pi = 0; pi < pages.length; pi++) {
    const pageData = pages[pi];
    const pdfPage  = doc.addPage([PAGE_W, PAGE_H]);

    const colTopFromTop = pi === 0
      ? await drawHeader(doc, pdfPage, article, fonts, fetchImage)
      : MARGIN_TOP;

    const colTopY = PAGE_H - colTopFromTop;

    for (const colData of pageData.columns) {
      const { x: colX, width: colW } = cols[colData.columnIndex];
      let offsetFromTop = 0;
      for (const rb of colData.blocks) {
        offsetFromTop = await drawBlock(doc, pdfPage, rb, colX, colW, colTopY, offsetFromTop, fonts, fetchImage);
      }
    }
  }

  return doc.save();
}

// ─── Browser wrapper (server-side generation via API) ────────────────────────
// PDF generation runs in the Next.js API route (Node.js) to avoid browser-side
// font embedding issues with pdf-lib. The browser only sends the layout data.

export async function generateAndDownloadPdf(
  pages: PageContent[],
  article: ExtractedArticle,
  template: TemplateId,
): Promise<void> {
  const res = await fetch('/api/generate-pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pages, article, template }),
  });

  if (!res.ok) throw new Error(`PDF generation failed: ${res.statusText}`);

  const blob = await res.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `${article.title.replace(/[^a-z0-9]+/gi, '-').toLowerCase().slice(0, 60)}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}
