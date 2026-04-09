import { UrlForm } from '@/components/UrlForm';
import { AnimatedWord } from '@/components/AnimatedWord';

export default function Home() {
  return (
    <main className="min-h-[100dvh] bg-white flex flex-col">

      {/* ── Wordmark ─────────────────────────────────────────────────────── */}
      <header
        className="px-8 md:px-14 py-7 border-b border-zinc-100 animate-home-in"
        style={{ animationDelay: '0ms' }}
      >
        <span className="text-[13px] text-zinc-900 select-none" style={{ fontFamily: 'var(--font-berkshire)' }}>
          The New Printer
        </span>
      </header>

      {/* ── Main content — centered ───────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center px-8 py-16">
        <div className="w-full max-w-xl text-center">

          <h1
            className="text-[2.75rem] md:text-[3.5rem] leading-[1.05] text-zinc-900 mb-5 animate-home-in"
            style={{ animationDelay: '60ms', fontFamily: 'var(--font-berkshire)' }}
          >
            Print <AnimatedWord />,<br />
            <span className="text-zinc-400">the way you want it.</span>
          </h1>

          <p
            className="text-[15px] text-zinc-500 leading-relaxed mb-10 animate-home-in"
            style={{ animationDelay: '120ms' }}
          >
            Paste a link. Set your columns. Adjust. Print.
          </p>

          <div className="animate-home-in text-left" style={{ animationDelay: '180ms' }}>
            <UrlForm />
          </div>
        </div>
      </div>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <footer
        className="px-8 md:px-14 py-6 border-t border-zinc-100 animate-home-in"
        style={{ animationDelay: '240ms' }}
      >
        <p className="text-[11px] text-zinc-300 tracking-wide">
          Works with most editorial sites &mdash; no account needed.
        </p>
      </footer>

    </main>
  );
}
