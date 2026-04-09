import { Readability } from '@mozilla/readability';
import { parseHTML } from 'linkedom';
import sanitizeHtml from 'sanitize-html';
import { validateUrl, resolveRelativeUrls, extractOgImage } from './utils';
import type { ExtractedArticle, ExtractResult } from './types';

export async function extractArticle(rawUrl: string): Promise<ExtractResult> {
  const url = validateUrl(rawUrl);
  if (!url) {
    return { ok: false, error: 'Invalid URL', code: 'INVALID_URL' };
  }

  let html: string;
  try {
    const res = await fetch(url.href, {
      headers: {
        'User-Agent':
          'Mozilla/5.0 (compatible; TheNewPrinter/1.0; +https://thenewprinter.app)',
        Accept: 'text/html,application/xhtml+xml',
      },
      next: { revalidate: 3600 },
    });
    if (!res.ok) {
      return {
        ok: false,
        error: `Fetch failed: ${res.status} ${res.statusText}`,
        code: 'FETCH_FAILED',
      };
    }
    html = await res.text();
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : 'Fetch failed',
      code: 'FETCH_FAILED',
    };
  }

  const leadImageUrl = extractOgImage(html);

  try {
    const { document } = parseHTML(html);
    const reader = new Readability(document as unknown as Document);
    const article = reader.parse();

    if (!article) {
      return { ok: false, error: 'Could not parse article content', code: 'PARSE_FAILED' };
    }

    const sanitized = sanitizeHtml(article.content ?? '', {
      allowedTags: [
        'p', 'br', 'b', 'i', 'em', 'strong', 'a', 'ul', 'ol', 'li',
        'h1', 'h2', 'h3', 'h4', 'blockquote', 'img', 'figure', 'figcaption',
        'div', 'span',
      ],
      allowedAttributes: {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
      },
    });

    const resolvedContent = resolveRelativeUrls(sanitized, url.href);

    const extracted: ExtractedArticle = {
      title: article.title ?? '',
      byline: article.byline ?? null,
      siteName: article.siteName ?? null,
      publishedTime: article.publishedTime ?? null,
      excerpt: article.excerpt ?? null,
      content: resolvedContent,
      leadImageUrl: leadImageUrl,
      lang: article.lang ?? null,
      wordCount: article.length ?? 0,
      sourceUrl: url.href,
    };

    return { ok: true, article: extracted };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : 'Parse failed',
      code: 'PARSE_FAILED',
    };
  }
}
