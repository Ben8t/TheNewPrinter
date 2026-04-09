'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

type Template = 'two-column' | 'three-column';

const EXAMPLES = [
  'https://www.nytimes.com/2025/03/article',
  'https://www.newyorker.com/magazine/essay',
  'https://www.ft.com/content/long-read',
  'https://www.wired.com/story/feature',
  'https://www.theguardian.com/culture/piece',
];

function useTypewriterPlaceholder() {
  const [placeholder, setPlaceholder] = useState('');

  useEffect(() => {
    let exIdx   = 0;
    let charIdx = 0;
    let deleting = false;
    let timeout: ReturnType<typeof setTimeout>;

    const tick = () => {
      const full = EXAMPLES[exIdx];

      if (!deleting) {
        charIdx++;
        setPlaceholder(full.slice(0, charIdx));
        if (charIdx === full.length) {
          timeout = setTimeout(() => { deleting = true; tick(); }, 1600);
          return;
        }
        timeout = setTimeout(tick, 55);
      } else {
        charIdx--;
        setPlaceholder(full.slice(0, charIdx));
        if (charIdx === 0) {
          deleting = false;
          exIdx = (exIdx + 1) % EXAMPLES.length;
          timeout = setTimeout(tick, 420);
          return;
        }
        timeout = setTimeout(tick, 18);
      }
    };

    timeout = setTimeout(tick, 900);
    return () => clearTimeout(timeout);
  }, []);

  return placeholder;
}

export function UrlForm() {
  const router    = useRouter();
  const [url,      setUrl]      = useState('');
  const [template, setTemplate] = useState<Template>('two-column');
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);
  const placeholder = useTypewriterPlaceholder();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    let parsed: URL;
    try {
      parsed = new URL(url.trim());
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') throw new Error();
    } catch {
      setError('Enter a valid article URL — must start with https://');
      return;
    }

    setLoading(true);
    router.push(`/print?url=${encodeURIComponent(parsed.href)}&template=${template}`);
  }

  return (
    <form onSubmit={handleSubmit} className="w-full space-y-5">

      {/* URL row */}
      <div className="relative flex items-stretch">
        <input
          type="text"
          value={url}
          onChange={(e) => { setUrl(e.target.value); setError(''); }}
          placeholder={placeholder}
          autoFocus
          autoComplete="off"
          spellCheck={false}
          className="
            flex-1 h-14 px-5 text-[15px] bg-white text-zinc-900 placeholder:text-zinc-300
            border border-zinc-200 rounded-l-xl rounded-r-none
            focus:outline-none focus:border-zinc-900
            transition-colors duration-150
          "
        />
        <button
          type="submit"
          disabled={loading}
          className="
            h-14 px-7 shrink-0 group
            bg-zinc-900 text-white text-[13px] font-medium tracking-wide
            rounded-r-xl rounded-l-none border border-zinc-900
            hover:bg-zinc-700 active:scale-[0.98] active:bg-zinc-800
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-all duration-150
            flex items-center gap-2.5
          "
        >
          {loading ? (
            <svg className="animate-spin" width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
              <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="9 9" strokeLinecap="round"/>
            </svg>
          ) : (
            <svg
              width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden
              className="transition-transform duration-200 group-hover:translate-x-[2px]"
            >
              <path d="M2 7h10M8 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
          Print
        </button>
      </div>

      {/* Inline error */}
      {error && (
        <p className="text-[13px] text-red-500 pl-1 animate-home-in" style={{ animationDelay: '0ms' }}>
          {error}
        </p>
      )}

      {/* Template toggle */}
      <div className="flex items-center gap-1 pl-1">
        <span className="text-[11px] text-zinc-400 mr-2.5 tracking-[0.12em] uppercase">Layout</span>
        {(['two-column', 'three-column'] as Template[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTemplate(t)}
            className={`
              px-3 py-1.5 text-[11px] rounded-lg tracking-wide transition-all duration-150
              ${template === t
                ? 'bg-zinc-900 text-white'
                : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'}
            `}
          >
            {t === 'two-column' ? '2 col' : '3 col'}
          </button>
        ))}
      </div>
    </form>
  );
}
