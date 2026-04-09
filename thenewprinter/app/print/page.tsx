import { extractArticle } from '@/lib/extract';
import { PrintLayout } from '@/components/PrintLayout';
import { PrintButton } from '@/components/PrintButton';
import Link from 'next/link';
import type { TemplateId } from '@/lib/types';

interface PageProps {
  searchParams: Promise<{ url?: string; template?: string }>;
}

export default async function PrintPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const rawUrl = params.url ?? '';
  const template = (params.template === 'three-column' ? 'three-column' : 'two-column') as TemplateId;

  if (!rawUrl) {
    return (
      <ErrorView
        error="No URL provided."
        hint="Go back and enter an article URL."
      />
    );
  }

  const result = await extractArticle(rawUrl);

  if (!result.ok) {
    return <ErrorView error={result.error} />;
  }

  const otherTemplate: TemplateId = template === 'two-column' ? 'three-column' : 'two-column';
  const otherLabel = template === 'two-column' ? '3 Columns' : '2 Columns';

  return (
    <>
      <div className="print-hidden fixed top-4 right-4 z-50 flex gap-2">
        <Link
          href={`/print?url=${encodeURIComponent(rawUrl)}&template=${otherTemplate}`}
          className="px-4 py-2 bg-white border border-gray-300 text-sm rounded hover:bg-gray-50 transition-colors"
        >
          {otherLabel}
        </Link>
        <PrintButton />
      </div>
      <PrintLayout article={result.article} template={template} />
    </>
  );
}

function ErrorView({ error, hint }: { error: string; hint?: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="max-w-md text-center space-y-4">
        <h1 className="text-xl font-semibold">Could not load article</h1>
        <p className="text-gray-600 text-sm">{error}</p>
        {hint && <p className="text-gray-500 text-sm">{hint}</p>}
        <Link href="/" className="inline-block mt-4 text-sm underline">
          Try another URL
        </Link>
      </div>
    </div>
  );
}
