import './styles/globals.css';
import React from 'react';
import { Metadata } from 'next';
import QueryProvider from './components/QueryProvider';

export const metadata: Metadata = {
  title: 'FlightioCrawler',
  description: 'Iranian flight crawler frontend'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl">
      <body className="bg-gray-100 text-gray-900">
        <header className="bg-blue-600 text-white mb-4">
          <nav className="max-w-xl mx-auto flex space-x-4 rtl:space-x-reverse p-2">
            <a href="/" className="hover:underline">خانه</a>
            <a href="/sites" className="hover:underline">سایت‌ها</a>
            <a href="/debug" className="hover:underline">اشکال‌زدایی</a>
          </nav>
        </header>
        <QueryProvider>
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}
