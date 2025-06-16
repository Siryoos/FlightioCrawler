'use client';
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

interface Transaction {
  id: string;
  amount: number;
  type: string;
  created_at: string;
}

function fetchTransactions(start: string, end: string, type: string) {
  const params = new URLSearchParams();
  if (start) params.append('start', start);
  if (end) params.append('end', end);
  if (type && type !== 'all') params.append('type', type);
  const qs = params.toString();
  return fetch(`/finance/wallet/transactions${qs ? `?${qs}` : ''}`)
    .then((r) => r.json())
    .then((d) => d.transactions as Transaction[] || []);
}

export default function WalletTransactionsPage() {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [type, setType] = useState('all');
  const {
    data: transactions = [],
    refetch,
    isFetching
  } = useQuery({
    queryKey: ['transactions', start, end, type],
    queryFn: () => fetchTransactions(start, end, type),
    enabled: false
  });

  return (
    <main className="max-w-xl mx-auto p-4 space-y-4">
      <h1 className="text-xl font-bold text-center">تاریخچه تراکنش‌های کیف پول</h1>
      <div className="space-y-2">
        <input type="date" className="w-full p-2 border" value={start} onChange={(e) => setStart(e.target.value)} />
        <input type="date" className="w-full p-2 border" value={end} onChange={(e) => setEnd(e.target.value)} />
        <select className="w-full p-2 border" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="all">همه</option>
          <option value="deposit">واریز</option>
          <option value="withdraw">برداشت</option>
        </select>
        <button className="w-full bg-blue-600 text-white p-2" onClick={() => refetch()} disabled={isFetching}>فیلتر</button>
      </div>
      <div className="mt-4">
        {isFetching ? 'در حال دریافت...' : (
          transactions.length ? (
            <table className="w-full border text-sm" data-testid="transactions-table">
              <thead>
                <tr>
                  <th className="border p-1">شناسه</th>
                  <th className="border p-1">مبلغ</th>
                  <th className="border p-1">نوع</th>
                  <th className="border p-1">تاریخ</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t) => (
                  <tr key={t.id} className="text-center">
                    <td className="border p-1">{t.id}</td>
                    <td className="border p-1">{t.amount}</td>
                    <td className="border p-1">{t.type}</td>
                    <td className="border p-1">{t.created_at.split('T')[0]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : 'هیچ تراکنشی یافت نشد'
        )}
      </div>
    </main>
  );
}
