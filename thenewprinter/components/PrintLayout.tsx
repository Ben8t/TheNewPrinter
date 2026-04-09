'use client';

import { useEffect, useRef, useState } from 'react';
import { parseBlocks } from '@/lib/parse-blocks';
import { layoutBlocks } from '@/lib/layout-engine';
import { Column } from './Column';
import type { ExtractedArticle, Block, PageContent, TemplateId } from '@/lib/types';

const A4_CONTENT_H_PX = 990; // 262mm at 96dpi
const COL_GAP_PX = 19;       // 5mm at 96dpi

interface Props {
  article: ExtractedArticle;
  template: TemplateId;
}

export function PrintLayout({ article, template }: Props) {
  const pageRef     = useRef<HTMLDivElement>(null);
  // Sentinel sits immediately above the column area; its offsetTop from the
  // page top gives the exact space consumed by header + lead image + all margins.
  const sentinelRef = useRef<HTMLDivElement>(null);
  const printing    = useRef(false);

  const [blocks,             setBlocks]             = useState<Block[]>([]);
  const [breakAfter,         setBreakAfter]         = useState<number[]>([]);
  const [hiddenImageIndices, setHiddenImageIndices] = useState<number[]>([]);
  const [pages,              setPages]              = useState<PageContent[]>([]);
  const [colW,               setColW]               = useState<number | null>(null);
  const [aboveColH,          setAboveColH]          = useState<number>(120); // space above columns on page 1

  // Parse blocks once
  useEffect(() => {
    setBlocks(parseBlocks(article.content));
  }, [article.content]);

  // Freeze / thaw around print dialog
  useEffect(() => {
    const freeze = () => { printing.current = true; };
    const thaw   = () => { printing.current = false; };
    window.addEventListener('beforeprint', freeze);
    window.addEventListener('afterprint',  thaw);
    return () => {
      window.removeEventListener('beforeprint', freeze);
      window.removeEventListener('afterprint',  thaw);
    };
  }, []);

  // Measure column width via ResizeObserver on the page div
  useEffect(() => {
    if (!pageRef.current) return;
    const observer = new ResizeObserver(([entry]) => {
      if (printing.current) return;
      const w = entry.contentRect.width;
      const colCount = template === 'three-column' ? 3 : 2;
      setColW((w - COL_GAP_PX * (colCount - 1)) / colCount);
    });
    observer.observe(pageRef.current);
    return () => observer.disconnect();
  }, [template]);

  // Measure space above columns after every render (catches margin changes, image load, etc.)
  useEffect(() => {
    if (printing.current) return;
    if (!pageRef.current || !sentinelRef.current) return;
    const pageTop     = pageRef.current.getBoundingClientRect().top;
    const sentinelTop = sentinelRef.current.getBoundingClientRect().top;
    const measured    = sentinelTop - pageTop;
    if (measured > 0 && Math.abs(measured - aboveColH) > 1) {
      setAboveColH(measured);
    }
  });

  // Run pretext layout
  useEffect(() => {
    if (printing.current) return;
    if (!colW || blocks.length === 0) return;
    const run = () => {
      const colCount = template === 'three-column' ? 3 : 2;
      setPages(layoutBlocks(blocks, {
        columnCount: colCount,
        columnWidthPx: colW,
        firstPageColHeightPx: Math.max(A4_CONTENT_H_PX - aboveColH, 200),
        colHeightPx: A4_CONTENT_H_PX,
        columnBreakAfter: breakAfter,
        hiddenBlockIndices: hiddenImageIndices,
      }));
    };
    if (document.fonts.status === 'loaded') run();
    else document.fonts.ready.then(run);
  }, [blocks, colW, aboveColH, breakAfter, hiddenImageIndices, template]);

  const colCount = template === 'three-column' ? 3 : 2;

  const publishedDate = article.publishedTime
    ? new Date(article.publishedTime).toLocaleDateString('en-US', {
        year: 'numeric', month: 'long', day: 'numeric',
      })
    : null;

  const handleInsertBreak   = (idx: number) =>
    setBreakAfter((prev) => [...prev, idx].sort((a, b) => a - b));
  const handleUndoBreak     = () =>
    setBreakAfter((prev) => prev.slice(0, -1));
  const handleRemoveImage   = (idx: number) =>
    setHiddenImageIndices((prev) => prev.includes(idx) ? prev : [...prev, idx]);
  const handleRestoreImages = () => setHiddenImageIndices([]);

  const renderColumns = (page: PageContent) =>
    page.columns.map((col) => (
      <Column
        key={col.columnIndex}
        content={col}
        onInsertBreak={handleInsertBreak}
        onRemoveImage={handleRemoveImage}
      />
    ));

  return (
    <div className="pages-wrapper" lang={article.lang ?? 'en'}>

      {/* ── Control bar ──────────────────────────────────────────────────── */}
      <div className="print-hidden" style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 40, display: 'flex', gap: 8 }}>
        {hiddenImageIndices.length > 0 && (
          <button className="ctrl-btn ctrl-btn--active" onClick={handleRestoreImages}>
            Restore {hiddenImageIndices.length} image{hiddenImageIndices.length > 1 ? 's' : ''}
          </button>
        )}
        <button className="ctrl-btn" onClick={handleUndoBreak} disabled={breakAfter.length === 0}>
          Undo break{breakAfter.length > 0 ? ` (${breakAfter.length})` : ''}
        </button>
      </div>

      {/* ── Page 1 ───────────────────────────────────────────────────────── */}
      <div className="print-page" ref={pageRef}>
        <header className="article-header">
          <div className="masthead">
            <span>{article.siteName ?? 'TheNewPrinter'}</span>
            {publishedDate && <span>{publishedDate}</span>}
          </div>
          <h1 className="article-title">{article.title}</h1>
          {article.byline  && <p className="byline">{article.byline}</p>}
          {article.excerpt && <p className="excerpt">{article.excerpt}</p>}
          {article.leadImageUrl && (
            <div className="article-lead-image">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={article.leadImageUrl} alt={article.title} />
            </div>
          )}
        </header>

        {/* Sentinel: zero-height marker whose top measures all space above columns */}
        <div ref={sentinelRef} style={{ height: 0, overflow: 'hidden' }} />

        {pages.length === 0 ? (
          <div className="layout-loading">Computing layout…</div>
        ) : (
          <div className={`article-columns cols-${colCount}`}>
            {renderColumns(pages[0])}
          </div>
        )}
      </div>

      {/* ── Pages 2+ ─────────────────────────────────────────────────────── */}
      {pages.slice(1).map((page) => (
        <div key={page.pageIndex} className="print-page">
          <div className={`article-columns cols-${colCount}`}>
            {renderColumns(page)}
          </div>
        </div>
      ))}
    </div>
  );
}
