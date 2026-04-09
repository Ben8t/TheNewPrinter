import { NextRequest, NextResponse } from 'next/server';
import { extractArticle } from '@/lib/extract';

export async function GET(request: NextRequest) {
  const url = request.nextUrl.searchParams.get('url') ?? '';
  const result = await extractArticle(url);

  if (!result.ok) {
    const status = result.code === 'INVALID_URL' ? 400 : result.code === 'FETCH_FAILED' ? 502 : 422;
    return NextResponse.json(result, { status });
  }

  return NextResponse.json(result);
}
