'use client'

import './styles/globals.css';
import React, { useState } from 'react';
import { Metadata } from 'next';
import QueryProvider from './components/QueryProvider';
import ErrorBoundary from './components/ErrorBoundary';
import RealTimeStatusMonitor from './components/RealTimeStatusMonitor';

// export const metadata: Metadata = { // Metadata cannot be used with 'use client'
//   title: 'FlightioCrawler',
//   description: 'Iranian flight crawler frontend'
// };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const navLinks = (
    <>
      <a href="/" className="block md:inline-block hover:underline px-3 py-2 rounded hover:bg-primary-dark transition-colors">خانه</a>
      <a href="/airports" className="block md:inline-block hover:underline px-3 py-2 rounded hover:bg-primary-dark transition-colors">فرودگاه‌ها</a>
      <a href="/sites" className="block md:inline-block hover:underline px-3 py-2 rounded hover:bg-primary-dark transition-colors">سایت‌ها</a>
      <a href="/insights" className="block md:inline-block hover:underline px-3 py-2 rounded hover:bg-primary-dark transition-colors">بینش‌ها</a>
      <a href="/jobs" className="block md:inline-block hover:underline px-3 py-2 rounded hover:bg-primary-dark transition-colors">کرول جدید</a>
      <a href="/debug" className="block md:inline-block hover:underline px-3 py-2 rounded hover:bg-primary-dark transition-colors">اشکال‌زدایی</a>
    </>
  );

  return (
    <html lang="fa" dir="rtl">
      <body className="bg-neutral-100 text-neutral-800">
        <header className="bg-primary text-white mb-4 shadow-md">
          <div className="max-w-6xl mx-auto flex items-center justify-between p-4">
            <div className="font-bold text-xl">FlightioCrawler</div>
            {/* Desktop Menu */}
            <nav className="hidden md:flex space-x-4 rtl:space-x-reverse">
              {navLinks}
            </nav>
            {/* Mobile Menu Button */}
            <button
              className="md:hidden"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
            >
              {/* Hamburger Icon */}
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={!isMenuOpen ? "M4 6h16M4 12h16m-7 6h7" : "M6 18L18 6M6 6l12 12"}></path></svg>
            </button>
          </div>
          {/* Mobile Menu */}
          {isMenuOpen && (
            <nav className="md:hidden p-4 space-y-2">
              {navLinks}
            </nav>
          )}
        </header>
        <ErrorBoundary>
          <QueryProvider>
            {children}
            <RealTimeStatusMonitor />
          </QueryProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
