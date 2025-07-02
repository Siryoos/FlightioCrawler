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
          <nav className="max-w-6xl mx-auto flex space-x-4 rtl:space-x-reverse p-4">
            <a href="/" className="hover:underline px-2 py-1 rounded hover:bg-blue-700 transition-colors">خانه</a>
            <a href="/airports" className="hover:underline px-2 py-1 rounded hover:bg-blue-700 transition-colors">فرودگاه‌ها</a>
            <a href="/sites" className="hover:underline px-2 py-1 rounded hover:bg-blue-700 transition-colors">سایت‌ها</a>
            <a href="/insights" className="hover:underline px-2 py-1 rounded hover:bg-blue-700 transition-colors">بینش‌ها</a>
            <a href="/jobs" className="hover:underline px-2 py-1 rounded hover:bg-blue-700 transition-colors">کرول جدید</a>
            <a href="/debug" className="hover:underline px-2 py-1 rounded hover:bg-blue-700 transition-colors">اشکال‌زدایی</a>
          </nav>
        </header>
        <QueryProvider>
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}
