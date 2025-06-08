'use client';
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { create } from 'zustand';

type Flight = {
  flight_number: string;
  origin: string;
  destination: string;
  date: string;
  price: number;
};

interface SearchState {
  origin: string;
  destination: string;
  date: string;
  setOrigin: (v: string) => void;
  setDestination: (v: string) => void;
  setDate: (v: string) => void;
}

const useSearchStore = create<SearchState>((set) => ({
  origin: '',
  destination: '',
  date: '',
  setOrigin: (v) => set({ origin: v }),
  setDestination: (v) => set({ destination: v }),
  setDate: (v) => set({ date: v })
}));

function fetchFlights(origin: string, destination: string, date: string) {
  if (!origin || !destination || !date) return Promise.resolve([] as Flight[]);
  const params = new URLSearchParams({ origin, destination, date });
  return fetch(`/search?${params}`).then((r) => r.json()).then((d) => d.flights || []);
}

export default function Page() {
  const { origin, destination, date, setOrigin, setDestination, setDate } = useSearchStore();
  const { data: flights = [], refetch, isFetching } = useQuery({
    queryKey: ['flights', origin, destination, date],
    queryFn: () => fetchFlights(origin, destination, date),
    enabled: false
  });
  return (
    <main className="max-w-xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold mb-4 text-center">جستجوی پرواز</h1>
      <div className="space-y-2">
        <input className="w-full p-2 border" placeholder="مبدا" value={origin} onChange={(e) => setOrigin(e.target.value)} />
        <input className="w-full p-2 border" placeholder="مقصد" value={destination} onChange={(e) => setDestination(e.target.value)} />
        <input type="date" className="w-full p-2 border" value={date} onChange={(e) => setDate(e.target.value)} />
        <button className="w-full bg-blue-600 text-white p-2" onClick={() => refetch()} disabled={isFetching}>جستجو</button>
      </div>
      <div className="mt-4">
        {isFetching ? 'در حال دریافت...' : (
          flights.length ? (
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
                {flights.map((f: Flight) => (
                  <tr key={f.flight_number} className="text-center">
                    <td className="border p-1">{f.flight_number}</td>
                    <td className="border p-1">{f.origin}</td>
                    <td className="border p-1">{f.destination}</td>
                    <td className="border p-1">{f.date}</td>
                    <td className="border p-1">{f.price}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : 'نتیجه‌ای یافت نشد'
        )}
      </div>
    </main>
  );
}
