'use client';
import React, { useEffect, useState } from 'react';
import SiteBIMetrics from '../../components/SiteBIMetrics';

export default function SitePage({ params }: { params: { site: string } }) {
  const { site } = params;
  const [data, setData] = useState<any | null>(null);
  useEffect(() => {
    fetch(`/api/v1/sites/${site}/health`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null));
  }, [site]);

  return (
    <main className="max-w-xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold text-center">{site} گزارش</h1>
      {data ? <SiteBIMetrics data={data} /> : 'در حال بارگذاری...'}
    </main>
  );
}
