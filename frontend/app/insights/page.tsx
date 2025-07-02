'use client';
import React, { useEffect, useState } from 'react';

type ProviderRecords = Record<string, Record<string, number>>;

interface InsightsData {
  flights: ProviderRecords;
  tours: ProviderRecords;
  hotels: ProviderRecords;
}

export default function ProviderInsightsPage() {
  const [data, setData] = useState<InsightsData | null>(null);
  const [activeTab, setActiveTab] = useState<'flights' | 'tours' | 'hotels'>('flights');

  useEffect(() => {
    fetch('/api/v1/provider-insights')
      .then((r) => r.json())
      .then((d) => setData(d.insights));
  }, []);

  if (!data) return <main className="max-w-2xl mx-auto p-4">در حال بارگذاری...</main>;

  const renderTable = (records: ProviderRecords) => {
    const first = Object.values(records)[0];
    if (!first) return <div>هیچ داده‌ای وجود ندارد</div>;
    const headers = Object.keys(first);
    return (
      <table className="w-full border text-sm" data-testid="insights-table">
        <thead>
          <tr>
            <th className="border p-1">Provider</th>
            {headers.map((h) => (
              <th key={h} className="border p-1">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(records).map(([name, metrics]) => (
            <tr key={name} className="text-center">
              <td className="border p-1">{name}</td>
              {headers.map((h) => (
                <td key={h} className="border p-1">
                  {metrics[h] as number}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <main className="max-w-2xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold text-center">Provider Insights</h1>
      <div className="flex space-x-2 rtl:space-x-reverse">
        <button
          className={`flex-1 p-2 border ${activeTab === 'flights' ? 'bg-blue-600 text-white' : 'bg-white'}`}
          onClick={() => setActiveTab('flights')}
        >
          Flights
        </button>
        <button
          className={`flex-1 p-2 border ${activeTab === 'tours' ? 'bg-blue-600 text-white' : 'bg-white'}`}
          onClick={() => setActiveTab('tours')}
        >
          Tours
        </button>
        <button
          className={`flex-1 p-2 border ${activeTab === 'hotels' ? 'bg-blue-600 text-white' : 'bg-white'}`}
          onClick={() => setActiveTab('hotels')}
        >
          Hotels
        </button>
      </div>
      {renderTable(data[activeTab])}
    </main>
  );
}
