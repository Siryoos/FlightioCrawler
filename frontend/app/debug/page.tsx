'use client';
import React, { useEffect, useState } from 'react';

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

interface Flight {
  flight_id: string;
  flight_number: string;
  origin: string;
  destination: string;
  departure_time: string;
  price: number;
}

export default function DebugPage() {
  const [sites, setSites] = useState<string[]>([]);
  const [site, setSite] = useState<string>('');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [flights, setFlights] = useState<Flight[]>([]);

  useEffect(() => {
    fetch('/api/v1/sites/status')
      .then((r) => r.json())
      .then((d) => {
        const names = Object.keys(d.sites || {});
        setSites(names);
        if (!site && names[0]) setSite(names[0]);
      });
  }, []);

  useEffect(() => {
    if (!site) return;
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/sites/${site}/logs`);
    ws.onmessage = (e) => {
      const entry = JSON.parse(e.data);
      setLogs((l) => [...l.slice(-199), entry]);
    };
    return () => ws.close();
  }, [site]);

  useEffect(() => {
    fetch('/flights/recent?limit=20')
      .then((r) => r.json())
      .then((d) => setFlights(d.flights || []));
  }, []);

  return (
    <main className="max-w-xl mx-auto p-4 space-y-4">
      <h1 className="text-xl font-bold text-center">صفحه اشکال‌زدایی</h1>
      <div>
        <label className="block mb-1">سایت:</label>
        <select
          className="p-2 border w-full"
          value={site}
          onChange={(e) => setSite(e.target.value)}
        >
          {sites.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <section className="border p-2 h-48 overflow-y-auto bg-white text-xs">
        {logs.map((l, i) => (
          <div key={i}>
            [{l.timestamp}] {l.level}: {l.message}
          </div>
        ))}
      </section>
      <section>
        <h2 className="font-bold mb-2">آخرین پروازها</h2>
        <table className="w-full border">
          <thead>
            <tr>
              <th className="border p-1">شماره پرواز</th>
              <th className="border p-1">مبدا</th>
              <th className="border p-1">مقصد</th>
              <th className="border p-1">تاریخ</th>
              <th className="border p-1">قیمت</th>
            </tr>
          </thead>
          <tbody>
            {flights.map((f) => (
              <tr key={f.flight_id} className="text-center">
                <td className="border p-1">{f.flight_number}</td>
                <td className="border p-1">{f.origin}</td>
                <td className="border p-1">{f.destination}</td>
                <td className="border p-1">{f.departure_time.split('T')[0]}</td>
                <td className="border p-1">{f.price}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
