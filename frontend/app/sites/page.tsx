'use client';
import React, { useEffect } from 'react';
import Link from 'next/link';
import { useSiteStore } from '../stores/siteStore';
import LoadingSpinner from '../components/Loading';

export default function SitesIndex() {
  const { sites, loading, fetchSites, toggleSiteStatus } = useSiteStore();

  useEffect(() => {
    // Fetch sites only if the store is empty
    if (Object.keys(sites).length === 0) {
      fetchSites();
    }
  }, [fetchSites, sites]);

  if (loading && Object.keys(sites).length === 0) {
    return (
      <main className="max-w-xl mx-auto p-4 space-y-4">
        <h1 className="text-2xl font-bold text-center">Business Intelligence</h1>
        <LoadingSpinner />
      </main>
    );
  }

  return (
    <main className="max-w-xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold text-center">Business Intelligence</h1>
      <ul className="list-disc pl-4 space-y-2">
        {Object.entries(sites).map(([name, info]) => (
          <li key={name} className="flex items-center space-x-2 rtl:space-x-reverse">
            <Link href={`/sites/${name}`} className="flex-1 hover:underline">
              {name}
            </Link>
            <button
              className={`px-2 py-1 text-sm text-white ${info.status === 'active' ? 'bg-red-600' : 'bg-green-600'}`}
              onClick={() => toggleSiteStatus(name)}
            >
              {info.status === 'active' ? 'توقف' : 'شروع'}
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
