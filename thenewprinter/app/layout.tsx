import type { Metadata } from 'next';
import { Lora, Inter, Instrument_Serif } from 'next/font/google';
import './globals.css';
import '../styles/print.css';

const lora = Lora({
  variable: '--font-lora',
  subsets: ['latin'],
  display: 'swap',
});

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
  display: 'swap',
});

const instrumentSerif = Instrument_Serif({
  variable: '--font-berkshire',
  subsets: ['latin'],
  weight: '400',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'TheNewPrinter',
  description: 'Print any article as a beautiful multi-column PDF',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${lora.variable} ${inter.variable} ${instrumentSerif.variable}`}>
      <body className="min-h-screen bg-white">{children}</body>
    </html>
  );
}
