import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'small_LLM — Private AI, on your terms', description: 'A self-hosted AI platform powered by open-weight models.' };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body>{children}</body></html>; }
