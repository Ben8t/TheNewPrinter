import { NextRequest, NextResponse } from 'next/server';

// Allowed schemes and a basic SSRF guard (no private/loopback IPs)
function isSafeUrl(raw: string): boolean {
  try {
    const u = new URL(raw);
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return false;
    const host = u.hostname;
    if (host === 'localhost' || host === '127.0.0.1' || host === '::1') return false;
    if (/^10\./.test(host) || /^192\.168\./.test(host) || /^172\.(1[6-9]|2\d|3[01])\./.test(host)) return false;
    return true;
  } catch {
    return false;
  }
}

export async function GET(request: NextRequest) {
  const url = request.nextUrl.searchParams.get('url') ?? '';

  if (!isSafeUrl(url)) {
    return new NextResponse('Invalid URL', { status: 400 });
  }

  const res = await fetch(url, { headers: { 'User-Agent': 'TheNewPrinter/1.0' } });

  if (!res.ok) {
    return new NextResponse('Upstream error', { status: 502 });
  }

  const contentType = res.headers.get('content-type') ?? 'application/octet-stream';

  // Only proxy image types pdf-lib can embed (JPEG and PNG)
  const isJpeg = contentType.includes('jpeg') || contentType.includes('jpg');
  const isPng  = contentType.includes('png');

  if (!isJpeg && !isPng) {
    // Check by magic bytes as a fallback (some servers send wrong content-type)
    const buf   = await res.arrayBuffer();
    const bytes = new Uint8Array(buf);
    const looksJpeg = bytes[0] === 0xFF && bytes[1] === 0xD8;
    const looksPng  = bytes[0] === 0x89 && bytes[1] === 0x50;
    if (!looksJpeg && !looksPng) {
      return new NextResponse('Unsupported image format', { status: 415 });
    }
    const mime = looksJpeg ? 'image/jpeg' : 'image/png';
    return new NextResponse(buf, { headers: { 'Content-Type': mime } });
  }

  const buf = await res.arrayBuffer();
  return new NextResponse(buf, { headers: { 'Content-Type': contentType } });
}
