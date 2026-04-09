export function validateUrl(input: string): URL | null {
  try {
    const url = new URL(input);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    return url;
  } catch {
    return null;
  }
}

export function resolveRelativeUrls(html: string, baseUrl: string): string {
  try {
    const base = new URL(baseUrl);
    // Resolve href and src attributes
    return html
      .replace(/(href|src)="([^"]+)"/g, (match, attr, value) => {
        try {
          const resolved = new URL(value, base).href;
          return `${attr}="${resolved}"`;
        } catch {
          return match;
        }
      })
      .replace(/(href|src)='([^']+)'/g, (match, attr, value) => {
        try {
          const resolved = new URL(value, base).href;
          return `${attr}='${resolved}'`;
        } catch {
          return match;
        }
      });
  } catch {
    return html;
  }
}

export function extractOgImage(html: string): string | null {
  const match = html.match(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i)
    ?? html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i);
  return match?.[1] ?? null;
}
