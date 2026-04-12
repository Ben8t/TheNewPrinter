import type { Block } from './types';

// Container tags whose children we recurse into rather than treating as a block
const CONTAINER_TAGS = new Set([
  'div', 'section', 'article', 'main', 'aside', 'header', 'footer',
  'nav', 'span', 'body',
]);

// Tags we skip entirely (navigation, scripts, ads, etc.)
const SKIP_TAGS = new Set([
  'script', 'style', 'noscript', 'iframe', 'button', 'form',
  'input', 'select', 'textarea', 'svg', 'canvas',
]);

function normalizeText(el: Element): string {
  return (el.textContent ?? '').replace(/\s+/g, ' ').trim();
}

function extractImage(img: Element): Block | null {
  const src = img.getAttribute('src') ?? '';
  if (!src || src.startsWith('data:')) return null;
  const w = img.getAttribute('width');
  const h = img.getAttribute('height');
  return {
    type: 'image',
    src,
    alt: img.getAttribute('alt') ?? '',
    ...(w ? { naturalWidth: parseInt(w) } : {}),
    ...(h ? { naturalHeight: parseInt(h) } : {}),
  };
}

function walkElement(el: Element, blocks: Block[]): void {
  const tag = el.tagName.toLowerCase();

  if (SKIP_TAGS.has(tag)) return;

  // ── Headings — always extract, regardless of nesting depth ───────────────
  if (/^h[1-6]$/.test(tag)) {
    const level = Math.min(parseInt(tag[1]), 4) as 1 | 2 | 3 | 4;
    const text = normalizeText(el);
    if (text) blocks.push({ type: 'heading', level, text });
    return;
  }

  // ── Paragraph ─────────────────────────────────────────────────────────────
  if (tag === 'p') {
    // A <p> may contain an <img> — extract image then text separately
    const img = el.querySelector('img');
    if (img) {
      const block = extractImage(img);
      if (block) blocks.push(block);
    }
    // Also grab any text in the paragraph
    const text = normalizeText(el);
    if (text) blocks.push({ type: 'paragraph', text });
    return;
  }

  // ── Blockquote ────────────────────────────────────────────────────────────
  if (tag === 'blockquote') {
    const text = normalizeText(el);
    if (text) blocks.push({ type: 'blockquote', text });
    return;
  }

  // ── Lists ─────────────────────────────────────────────────────────────────
  if (tag === 'ul' || tag === 'ol') {
    const items = Array.from(el.querySelectorAll('li'))
      .map((li) => normalizeText(li))
      .filter(Boolean);
    if (items.length) blocks.push({ type: 'list', ordered: tag === 'ol', items });
    return;
  }

  // ── Images ────────────────────────────────────────────────────────────────
  if (tag === 'img') {
    const block = extractImage(el);
    if (block) blocks.push(block);
    return;
  }

  // ── Figure — prefer the img inside, ignore caption text ──────────────────
  if (tag === 'figure') {
    const img = el.querySelector('img');
    if (img) {
      const block = extractImage(img);
      if (block) blocks.push(block);
    }
    return;
  }

  // ── Containers — recurse into children ───────────────────────────────────
  if (CONTAINER_TAGS.has(tag)) {
    // Before recursing, check if this container has any block-level children.
    // If it only has inline content (no child elements), treat it as a paragraph.
    const hasBlockChildren = Array.from(el.children).some((child) => {
      const ct = child.tagName.toLowerCase();
      return !SKIP_TAGS.has(ct);
    });

    if (!hasBlockChildren && el.children.length === 0) {
      // Pure text node inside a container
      const text = normalizeText(el);
      if (text) blocks.push({ type: 'paragraph', text });
      return;
    }

    for (const child of Array.from(el.children)) {
      walkElement(child, blocks);
    }
    return;
  }

  // ── Fallback: any other element with text becomes a paragraph ─────────────
  const text = normalizeText(el);
  if (text) blocks.push({ type: 'paragraph', text });
}

export function parseBlocks(html: string): Block[] {
  let doc: Document;
  if (typeof DOMParser !== 'undefined') {
    doc = new DOMParser().parseFromString(html, 'text/html');
  } else {
    // Node.js: use linkedom
    const { parseHTML } = require('linkedom') as typeof import('linkedom');
    doc = parseHTML(html).document as unknown as Document;
  }

  const blocks: Block[] = [];

  for (const child of Array.from(doc.body.children)) {
    walkElement(child, blocks);
  }

  // Deduplicate consecutive identical paragraphs (can arise from p + container both matching)
  return blocks.filter((b, i, arr) => {
    if (i === 0) return true;
    const prev = arr[i - 1];
    if (b.type === 'paragraph' && prev.type === 'paragraph' && b.text === prev.text) return false;
    if (b.type === 'heading' && prev.type === 'heading' && b.text === prev.text && b.level === prev.level) return false;
    return true;
  });
}
