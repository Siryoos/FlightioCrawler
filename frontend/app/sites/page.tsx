'use client';
import React, { useEffect, useState } from 'react';
import Link from 'next/link';

interface SiteInfo {
  enabled: boolean;
}

export default function SitesIndex() {
  const [sites, setSites] = useState<Record<string, SiteInfo>>({});
  useEffect(() => {
    fetch('/api/v1/sites/status')
      .then((r) => r.json())
      .then((d) => setSites(d.sites || {}));
  }, []);

  const toggle = async (name: string, enable: boolean) => {
    await fetch(`/api/v1/sites/${name}/${enable ? 'enable' : 'disable'}`, {
      method: 'POST'
    });
    setSites((s) => ({ ...s, [name]: { ...s[name], enabled: enable } }));
  };

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
              className="px-2 py-1 text-sm text-white bg-blue-600"
              onClick={() => toggle(name, !info.enabled)}
            >
              {info.enabled ? 'توقف' : 'شروع'}
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
