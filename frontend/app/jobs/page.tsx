'use client';
import React, { useState } from 'react';

export default function CrawlJobPage() {
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [result, setResult] = useState('');

  const createJob = async () => {
    if (!origin || !destination || !start || !end) return;
    const dates: string[] = [];
    for (let d = new Date(start); d <= new Date(end); d.setDate(d.getDate() + 1)) {
      dates.push(new Date(d).toISOString().split('T')[0]);
    }
    const res = await fetch('/crawl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ origin, destination, dates })
    });
    const data = await res.json();
    setResult(JSON.stringify(data, null, 2));
  };

  return (
    <main className="max-w-xl mx-auto p-4 space-y-2">
      <h1 className="text-2xl font-bold text-center">ساخت کار خزش</h1>
      <input className="w-full p-2 border" placeholder="مبدا" value={origin} onChange={e => setOrigin(e.target.value)} />
      <input className="w-full p-2 border" placeholder="مقصد" value={destination} onChange={e => setDestination(e.target.value)} />
      <input type="date" className="w-full p-2 border" value={start} onChange={e => setStart(e.target.value)} />
      <input type="date" className="w-full p-2 border" value={end} onChange={e => setEnd(e.target.value)} />
      <button className="w-full bg-blue-600 text-white p-2" onClick={createJob}>ایجاد کار</button>
      {result && <pre className="bg-white p-2 whitespace-pre-wrap">{result}</pre>}
    </main>
  );
}
