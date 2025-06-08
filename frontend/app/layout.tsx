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
        <QueryProvider>
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}
