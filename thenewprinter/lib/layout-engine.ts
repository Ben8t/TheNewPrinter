import { prepareWithSegments, layoutNextLine, type LayoutCursor } from '@chenglou/pretext';
import type { Block, ColumnContent, RenderedBlock, PageContent } from './types';

const FONTS = {
  body: '9pt/1.45 Lora, Georgia, serif',
  h1: 'bold 20pt/1.15 Lora, Georgia, serif',
  h2: 'bold 12pt/1.3 Lora, Georgia, serif',
  h3: 'bold 10pt/1.3 Lora, Georgia, serif',
  h4: 'bold 9pt/1.3 Lora, Georgia, serif',
  blockquote: 'italic 9pt/1.45 Lora, Georgia, serif',
} as const;

function parseLineHeightPx(font: string): number {
  const match = font.match(/(\d+(?:\.\d+)?pt)\/(\d+(?:\.\d+)?)/);
  if (!match) return 14;
  const ptSize = parseFloat(match[1]);
  const multiplier = parseFloat(match[2]);
  // 1pt ≈ 1.333px at 96dpi
  return ptSize * 1.333 * multiplier;
}

function estimateImageHeight(
  block: Extract<Block, { type: 'image' }>,
  colWidthPx: number
): number {
  if (block.naturalWidth && block.naturalHeight) {
    const ratio = block.naturalHeight / block.naturalWidth;
    return Math.min(colWidthPx * ratio, colWidthPx * 0.75);
  }
  return colWidthPx * 0.5;
}

function newColumn(index: number): ColumnContent {
  return { columnIndex: index, blocks: [] };
}

function newPage(index: number, columnCount: number): PageContent {
  return {
    pageIndex: index,
    columns: Array.from({ length: columnCount }, (_, i) => newColumn(i)),
  };
}

export interface LayoutOptions {
  columnCount: 2 | 3;
  columnWidthPx: number;
  /** Available height for columns on the first page (A4 content height minus header) */
  firstPageColHeightPx: number;
  /** Available height for columns on pages 2+ (full A4 content height) */
  colHeightPx: number;
  columnBreakAfter: number[];
  /** Block indices to skip entirely (e.g. user-hidden images) */
  hiddenBlockIndices: number[];
}

export function layoutBlocks(blocks: Block[], opts: LayoutOptions): PageContent[] {
  const pages: PageContent[] = [newPage(0, opts.columnCount)];

  let pageIdx = 0;
  let col = 0;
  let usedHeight = 0;

  function currentColHeight(): number {
    return pageIdx === 0 ? opts.firstPageColHeightPx : opts.colHeightPx;
  }

  function advanceColumn() {
    col += 1;
    usedHeight = 0;
    if (col >= opts.columnCount) {
      // All columns on this page are full — start a new page
      col = 0;
      pageIdx += 1;
      pages.push(newPage(pageIdx, opts.columnCount));
    }
  }

  function currentColumns(): ColumnContent[] {
    return pages[pageIdx].columns;
  }

  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i];

    // Skip user-hidden blocks
    if (opts.hiddenBlockIndices.includes(i)) continue;

    // User-inserted explicit column break
    if (block.type === 'column-break' || opts.columnBreakAfter.includes(i - 1)) {
      advanceColumn();
      continue;
    }

    if (block.type === 'image') {
      const imgHeight = estimateImageHeight(block, opts.columnWidthPx);
      if (usedHeight + imgHeight > currentColHeight()) {
        advanceColumn();
      }
      const rb: RenderedBlock = {
        blockIndex: i,
        block,
        lines: [],
        lineHeight: 0,
        totalHeight: imgHeight,
      };
      currentColumns()[col].blocks.push(rb);
      usedHeight += imgHeight;
      continue;
    }

    if (block.type === 'list') {
      const font = FONTS.body;
      const lineHeight = parseLineHeightPx(font);
      const lines = block.items.map((item, idx) =>
        `${block.ordered ? `${idx + 1}.` : '•'} ${item}`
      );
      const totalHeight = lines.length * lineHeight;
      if (usedHeight + totalHeight > currentColHeight()) {
        advanceColumn();
      }
      currentColumns()[col].blocks.push({ blockIndex: i, block, lines, lineHeight, totalHeight });
      usedHeight += totalHeight;
      continue;
    }

    // Text block: use pretext to split into lines
    let font: string;
    if (block.type === 'heading') {
      font = FONTS[`h${block.level}` as keyof typeof FONTS] ?? FONTS.body;
    } else if (block.type === 'blockquote') {
      font = FONTS.blockquote;
    } else {
      font = FONTS.body;
    }

    const lineHeight = parseLineHeightPx(font);
    const text =
      block.type === 'paragraph' || block.type === 'heading' || block.type === 'blockquote'
        ? block.text
        : '';

    if (!text) continue;

    const prepared = prepareWithSegments(text, font);
    let cursor: LayoutCursor = { segmentIndex: 0, graphemeIndex: 0 };
    let colLines: string[] = [];

    while (true) {
      const line = layoutNextLine(prepared, cursor, opts.columnWidthPx);
      if (!line) break;

      if (usedHeight + lineHeight > currentColHeight()) {
        // Flush accumulated lines to current column, then advance
        if (colLines.length > 0) {
          currentColumns()[col].blocks.push({
            blockIndex: i,
            block,
            lines: colLines,
            lineHeight,
            totalHeight: colLines.length * lineHeight,
          });
        }
        advanceColumn();
        colLines = [];
      }

      colLines.push(line.text);
      usedHeight += lineHeight;
      cursor = line.end;
    }

    if (colLines.length > 0) {
      currentColumns()[col].blocks.push({
        blockIndex: i,
        block,
        lines: colLines,
        lineHeight,
        totalHeight: colLines.length * lineHeight,
      });
    }
  }

  return pages;
}
