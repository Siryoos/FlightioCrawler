'use client';
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { create } from 'zustand';
import MultiCitySearch, { Leg } from './components/MultiCitySearch';
import FlightSearchForm from './components/FlightSearchForm';
import PriceComparisonGrid, { PriceRow } from './components/PriceComparisonGrid';
import CrawlerStatusMonitor from './components/CrawlerStatusMonitor';
import CrawledDataGrid, { CrawledFlight } from './components/CrawledDataGrid';

type Flight = {
  flight_number: string;
  origin: string;
  destination: string;
  date: string;
  price: number;
};

interface FlightSearchData {
  origin: string;
  destination: string;
  departureDate: string;
  returnDate?: string;
  passengers: number;
  tripType: 'oneWay' | 'roundTrip';
}

interface SearchState {
  searchData: FlightSearchData;
  setSearchData: (data: FlightSearchData) => void;
}

const useSearchStore = create<SearchState>((set) => ({
  searchData: {
    origin: '',
    destination: '',
    departureDate: '',
    returnDate: '',
    passengers: 1,
    tripType: 'oneWay'
  },
  setSearchData: (data) => set({ searchData: data })
}));

function fetchFlights(origin: string, destination: string, date: string) {
  if (!origin || !destination || !date) return Promise.resolve([] as Flight[]);
  const params = new URLSearchParams({ origin, destination, date });
  return fetch(`/search?${params}`).then((r) => r.json()).then((d) => d.flights || []);
}

function fetchCrawled(limit: number) {
  return fetch(`/flights/recent?limit=${limit}`)
    .then((r) => r.json())
    .then((d) => d.flights || []);
}

export default function Page() {
  const { searchData, setSearchData } = useSearchStore();
  const [priceRows, setPriceRows] = useState<PriceRow[]>([]);
  const [activeTab, setActiveTab] = useState<'search' | 'crawled'>('search');
  
  const { data: flights = [], refetch, isFetching } = useQuery({
    queryKey: ['flights', searchData.origin, searchData.destination, searchData.departureDate],
    queryFn: () => fetchFlights(searchData.origin, searchData.destination, searchData.departureDate),
    enabled: false
  });

  const { data: crawled = [], refetch: refetchCrawled } = useQuery<CrawledFlight[]>({
    queryKey: ['crawled', activeTab],
    queryFn: () => fetchCrawled(1000),
    enabled: activeTab === 'crawled'
  });

  const handleSearch = (data: FlightSearchData) => {
    setSearchData(data);
    // Trigger the search with new data
    setTimeout(() => refetch(), 100);
  };

  const handleMultiSearch = async (legs: Leg[]) => {
    const rows: PriceRow[] = [];
    for (const leg of legs) {
      const fs: Flight[] = await fetchFlights(leg.origin, leg.destination, leg.date);
      if (fs[0]) rows.push({ site: `${leg.origin}-${leg.destination}`, price: fs[0].price });
    }
    setPriceRows(rows);
  };

  return (
    <main className="max-w-4xl mx-auto p-4 space-y-6">
      <h1 className="text-3xl font-bold mb-6 text-center">جستجوی پرواز ایران</h1>
      <CrawlerStatusMonitor />
      
      <div className="flex space-x-2 rtl:space-x-reverse my-4">
        <button
          className={`flex-1 p-3 border rounded-md font-medium ${activeTab === 'search' ? 'bg-blue-600 text-white' : 'bg-white hover:bg-gray-50'}`}
          onClick={() => setActiveTab('search')}
          data-testid="tab-search"
        >
          جستجو
        </button>
        <button
          className={`flex-1 p-3 border rounded-md font-medium ${activeTab === 'crawled' ? 'bg-blue-600 text-white' : 'bg-white hover:bg-gray-50'}`}
          onClick={() => { setActiveTab('crawled'); refetchCrawled(); }}
          data-testid="tab-crawled"
        >
          داده‌های خزیده‌شده
        </button>
      </div>

      {activeTab === 'search' ? (
        <>
          <FlightSearchForm onSearch={handleSearch} />
          
          <div className="mt-6">
            {isFetching ? (
              <div className="text-center py-8">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p className="mt-2">در حال جستجو...</p>
              </div>
            ) : (
              flights.length ? (
                <div className="bg-white rounded-lg shadow overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-right text-sm font-medium text-gray-900">شماره پرواز</th>
                        <th className="px-4 py-3 text-right text-sm font-medium text-gray-900">مبدا</th>
                        <th className="px-4 py-3 text-right text-sm font-medium text-gray-900">مقصد</th>
                        <th className="px-4 py-3 text-right text-sm font-medium text-gray-900">تاریخ</th>
                        <th className="px-4 py-3 text-right text-sm font-medium text-gray-900">قیمت</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {flights.map((f: Flight) => (
                        <tr key={f.flight_number} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm">{f.flight_number}</td>
                          <td className="px-4 py-3 text-sm">{f.origin}</td>
                          <td className="px-4 py-3 text-sm">{f.destination}</td>
                          <td className="px-4 py-3 text-sm">{f.date}</td>
                          <td className="px-4 py-3 text-sm font-medium">{f.price?.toLocaleString()} تومان</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : searchData.origin && searchData.destination && searchData.departureDate ? (
                <div className="text-center py-8 text-gray-500">
                  نتیجه‌ای برای جستجوی شما یافت نشد
                </div>
              ) : null
            )}
          </div>

          <div className="mt-8">
            <h2 className="text-xl font-semibold mb-4">جستجوی چند مسیره</h2>
            <MultiCitySearch onSearch={handleMultiSearch} />
            <PriceComparisonGrid rows={priceRows} />
          </div>
        </>
      ) : (
        <div className="mt-8" data-testid="crawled-tab">
          <CrawledDataGrid flights={crawled} />
        </div>
      )}
    </main>
  );
}
