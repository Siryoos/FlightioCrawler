'use client';
import React from 'react';

export type PriceRow = {
  site: string;
  price: number;
};

export default function PriceComparisonGrid({ rows }: { rows: PriceRow[] }) {
  if (!rows.length) return null;
  return (
    <table className="w-full border mt-4" data-testid="price-grid">
      <thead>
        <tr>
          <th className="border p-1">سایت</th>
          <th className="border p-1">قیمت</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.site} className="text-center">
            <td className="border p-1">{r.site}</td>
            <td className="border p-1">{r.price.toLocaleString('fa-IR')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
