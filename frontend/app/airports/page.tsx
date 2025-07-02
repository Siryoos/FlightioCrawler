'use client';

import React, { useEffect, memo } from 'react';
import { useAirportStore } from '../stores/airportStore';
import { SkeletonCard } from '../components/Loading';
import {
  POPULAR_AIRPORTS,
  getAirportByCode,
  searchAirports,
  getAirportsByCountry,
  getTopAirportsByPassengers,
  Airport
} from '../components/AirportData';

export default function AirportsPage() {
  const {
    airports,
    searchTerm,
    filterCountry,
    sortBy,
    loading,
    fetchAirports,
    setSearchTerm,
    setFilterCountry,
    setSortBy,
  } = useAirportStore();

  useEffect(() => {
    if (airports.length === 0) {
      fetchAirports();
    }
  }, [fetchAirports, airports.length]);

  const popularAirports = POPULAR_AIRPORTS.map(code => getAirportByCode(airports, code)).filter(Boolean) as Airport[];

  let filteredAirports = searchTerm ? searchAirports(airports, searchTerm) : airports;

  if (filterCountry !== 'all') {
    filteredAirports = getAirportsByCountry(airports, filterCountry);
  }

  // Sort airports
  const sortedAirports = [...filteredAirports].sort((a, b) => {
    switch (sortBy) {
      case 'passengers':
        return (b.passengers || 0) - (a.passengers || 0);
      case 'city':
        return a.city.localeCompare(b.city);
      case 'country':
        return (a.country || '').localeCompare(b.country || '');
      default:
        return a.name.localeCompare(b.name);
    }
  });

  const topAirports = getTopAirportsByPassengers(airports, 10);
  const countries = Array.from(new Set(airports.map(a => a.country).filter(Boolean))).sort();

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'بین‌المللی':
        return 'bg-blue-100 text-blue-800';
      case 'مرز هوایی':
        return 'bg-green-100 text-green-800';
      case 'داخلی':
        return 'bg-gray-100 text-gray-800';
      case 'در دست ساخت':
      case 'در حال احداث':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-purple-100 text-purple-800';
    }
  };

  const formatPassengers = (passengers?: number) => {
    if (!passengers) return '-';
    if (passengers >= 1000000) {
      return `${(passengers / 1000000).toFixed(1)}M`;
    }
    return passengers.toLocaleString();
  };

  const AirportCard = memo(({ airport }: { airport: Airport }) => (
    <div className="bg-white rounded-lg shadow-md p-4 hover:shadow-lg transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-semibold text-lg text-gray-900 leading-tight">
          {airport.name}
        </h3>
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getTypeColor(airport.type)}`}>
          {airport.type}
        </span>
      </div>
      
      <div className="space-y-1 text-sm text-gray-600">
        <p><span className="font-medium">شهر:</span> {airport.city}</p>
        {airport.country && (
          <p><span className="font-medium">کشور:</span> {airport.country}</p>
        )}
        <div className="flex gap-4">
          {airport.iata && (
            <p><span className="font-medium">IATA:</span> <code className="bg-gray-100 px-1 rounded">{airport.iata}</code></p>
          )}
          {airport.icao && (
            <p><span className="font-medium">ICAO:</span> <code className="bg-gray-100 px-1 rounded">{airport.icao}</code></p>
          )}
        </div>
        {airport.passengers && (
          <p><span className="font-medium">مسافران سالانه:</span> {formatPassengers(airport.passengers)}</p>
        )}
      </div>
    </div>
  ));
  AirportCard.displayName = 'AirportCard';

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">فرودگاه‌های ایران و منطقه</h1>
        <p className="text-gray-600">
          مجموعه کاملی از فرودگاه‌های ایران و کشورهای منطقه خاورمیانه
        </p>
      </div>

      {/* Top Airports by Passengers */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">پرترافیک‌ترین فرودگاه‌ها</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {topAirports.map((airport, index) => (
            <div key={`${airport.icao}-${airport.iata}`} className="bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-2xl font-bold">#{index + 1}</span>
                <span className="text-sm opacity-90">{airport.country}</span>
              </div>
              <h3 className="font-semibold text-sm mb-1">{airport.city}</h3>
              <p className="text-xs opacity-90 mb-2">{airport.name}</p>
              <div className="flex justify-between items-center">
                <span className="font-mono text-sm">{airport.iata}</span>
                <span className="text-xs">{formatPassengers(airport.passengers)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Popular Airports */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">فرودگاه‌های پرطرفدار</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-10 gap-2">
          {popularAirports.map((airport) => (
            <div key={`${airport.icao}-${airport.iata}`} className="bg-gray-50 rounded-lg p-3 text-center hover:bg-gray-100 transition-colors">
              <div className="font-mono font-bold text-blue-600">{airport.iata}</div>
              <div className="text-xs text-gray-600 mt-1">{airport.city}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Search and Filter Controls */}
      <div className="mb-6 bg-white rounded-lg shadow-sm p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-2">
              جستجو
            </label>
            <input
              id="search"
              type="text"
              placeholder="نام فرودگاه، شهر، یا کد..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label htmlFor="country" className="block text-sm font-medium text-gray-700 mb-2">
              کشور
            </label>
            <select
              id="country"
              value={filterCountry}
              onChange={(e) => setFilterCountry(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">همه کشورها</option>
              {countries.map(country => (
                <option key={country} value={country}>{country}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="sort" className="block text-sm font-medium text-gray-700 mb-2">
              مرتب‌سازی
            </label>
            <select
              id="sort"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="name">نام فرودگاه</option>
              <option value="city">شهر</option>
              <option value="country">کشور</option>
              <option value="passengers">تعداد مسافر</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={() => {
                setSearchTerm('');
                setFilterCountry('all');
                setSortBy('name');
              }}
              className="w-full px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
            >
              پاک کردن فیلترها
            </button>
          </div>
        </div>
      </div>

      {/* Results Summary */}
      <div className="mb-4">
        <p className="text-sm text-gray-600">
          نمایش {sortedAirports.length} فرودگاه از {airports.length} فرودگاه
          {searchTerm && ` برای "${searchTerm}"`}
          {filterCountry !== 'all' && ` در ${filterCountry}`}
        </p>
      </div>

      {/* Airports Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading && airports.length === 0 ? (
          Array.from({ length: 9 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          sortedAirports.map((airport) => (
            <AirportCard key={`${airport.icao}-${airport.iata}-${airport.city}`} airport={airport} />
          ))
        )}
      </div>

      {!loading && sortedAirports.length === 0 && (
        <div className="text-center py-12 col-span-full">
          <div className="text-gray-400 text-lg mb-2">🔍</div>
          <p className="text-gray-600">هیچ فرودگاهی با این معیارها یافت نشد.</p>
          <button
            onClick={() => {
              setSearchTerm('');
              setFilterCountry('all');
            }}
            className="mt-4 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors"
          >
            نمایش همه فرودگاه‌ها
          </button>
        </div>
      )}

      {/* Statistics */}
      <div className="mt-12 bg-gray-50 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">آمار کلی</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-blue-600">{airports.length}</div>
            <div className="text-sm text-gray-600">کل فرودگاه‌ها</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-green-600">{countries.length}</div>
            <div className="text-sm text-gray-600">کشورها</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-purple-600">
              {airports.filter(a => a.type === 'بین‌المللی').length}
            </div>
            <div className="text-sm text-gray-600">بین‌المللی</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-orange-600">
              {airports.filter(a => a.passengers && a.passengers > 0).length}
            </div>
            <div className="text-sm text-gray-600">با آمار مسافر</div>
          </div>
        </div>
      </div>
    </div>
  );
} 