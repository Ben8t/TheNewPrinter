# The New Printer

Reading on paper just feels better. It's slow. It's embedded in the physical. It allows raw notes.

The New Printer is a web app that turns any article URL into a clean, print-ready layout — no account, no install, no PDF export. Just open, paste, and print from your browser.

Live at **[thenewprinter.vercel.app](https://thenewprinter.vercel.app)**

## How it works

1. Paste an article URL on the home page
2. Choose 2 or 3 columns
3. Adjust column breaks by dragging handles on the print layout
4. Hit Print

The app fetches the article server-side, strips away clutter with Readability, and runs a custom text layout engine to fill columns with correctly-wrapped lines before any paint happens.

## Stack

- **Next.js 16** (App Router, server components)
- **[`@chenglou/pretext`](https://github.com/chenglou/pretext)** — font-aware text segmentation used by the layout engine
- **`@mozilla/readability`** — article extraction
- **`sanitize-html`** — server-side HTML sanitization
- **`linkedom`** — lightweight DOM for server-side parsing
- **Tailwind CSS v4**
- Deployed on **Vercel**

## Project structure

```
thenewprinter/
├── app/
│   ├── page.tsx            # Home — URL input form
│   ├── print/page.tsx      # Print view (server component)
│   └── api/extract/        # Article extraction API
├── components/
│   ├── PrintLayout.tsx     # Full print canvas
│   ├── Column.tsx          # Single column renderer
│   ├── ColumnBreakHandle.tsx  # Draggable break points
│   ├── ArticleBlock.tsx    # Block-level renderer
│   └── UrlForm.tsx         # Home form
└── lib/
    ├── extract.ts          # Fetch + Readability + sanitize
    ├── parse-blocks.ts     # HTML → typed block tree
    ├── layout-engine.ts    # Column layout (line-level)
    └── types.ts
```

## Development

```bash
cd thenewprinter
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Contributing

Contributions are welcome. Fork the repo, create a branch, open a PR.

---

**The New Printer** — because sometimes the best way to read online is offline.
