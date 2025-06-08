'use client';
import React, { useEffect, useState } from 'react';
import Link from 'next/link';

export default function SitesIndex() {
  const [sites, setSites] = useState<string[]>([]);
  useEffect(() => {
    fetch('/api/v1/sites/status')
      .then((r) => r.json())
      .then((d) => setSites(Object.keys(d.sites || {})));
  }, []);

  return (
    <main className="max-w-xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold text-center">Business Intelligence</h1>
      <ul className="list-disc pl-4">
        {sites.map((s) => (
          <li key={s}>
            <Link href={`/sites/${s}`}>{s}</Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
