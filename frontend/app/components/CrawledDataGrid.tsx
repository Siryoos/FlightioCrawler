'use client';
import React from 'react';

export type CrawledFlight = {
  flight_id: string;
  flight_number: string;
  origin: string;
  destination: string;
  departure_time: string;
  price: number;
};

export default function CrawledDataGrid({ flights }: { flights: CrawledFlight[] }) {
  if (!flights.length) return null;
  return (
    <table className="w-full border mt-4" data-testid="crawled-grid">
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
  );
}
