export interface ExtractedArticle {
  title: string;
  byline: string | null;
  siteName: string | null;
  publishedTime: string | null;
  excerpt: string | null;
  content: string; // Sanitized HTML
  leadImageUrl: string | null;
  lang: string | null;
  wordCount: number;
  sourceUrl: string;
}

export type Block =
  | { type: 'paragraph'; text: string }
  | { type: 'heading'; level: 1 | 2 | 3 | 4; text: string }
  | { type: 'image'; src: string; alt: string; naturalWidth?: number; naturalHeight?: number }
  | { type: 'blockquote'; text: string }
  | { type: 'code'; lines: string[] }
  | { type: 'list'; ordered: boolean; items: string[] }
  | { type: 'column-break' };

export type TemplateId = 'two-column' | 'three-column';

export interface ColumnContent {
  columnIndex: number;
  blocks: RenderedBlock[];
}

export interface RenderedBlock {
  blockIndex: number;
  block: Block;
  lines: string[];
  lineHeight: number;
  totalHeight: number;
}

export interface PageContent {
  pageIndex: number;
  columns: ColumnContent[];
}

export type ExtractResult =
  | { ok: true; article: ExtractedArticle }
  | { ok: false; error: string; code: 'INVALID_URL' | 'FETCH_FAILED' | 'PARSE_FAILED' };
