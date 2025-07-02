'use client';
import React, { useState, useRef, useEffect } from 'react';
import { Airport, searchAirports } from './AirportData';
import { useAirportStore } from '../stores/airportStore';

interface AirportSelectorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export default function AirportSelector({ value, onChange, placeholder = 'انتخاب فرودگاه', className = '' }: AirportSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  
  const {
    airports,
    searchTerm,
    setSearchTerm,
    fetchAirports
  } = useAirportStore();

  useEffect(() => {
    if (airports.length === 0) {
      fetchAirports();
    }
  }, [airports.length, fetchAirports]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filtered = searchAirports(airports, searchTerm);
  const selected = airports.find(a => a.iata === value || a.icao === value || a.city === value);

  const handleSelect = (airport: Airport) => {
    onChange(airport.iata || airport.icao || airport.city);
    setIsOpen(false);
    setSearchTerm('');
  };

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <button
        type="button"
        className="w-full p-2 border border-gray-300 rounded-md bg-white text-right focus:outline-none focus:ring-2 focus:ring-blue-500"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="block truncate">
          {selected ? `${selected.city} (${selected.iata || selected.icao})` : placeholder}
        </span>
        <span className="absolute inset-y-0 left-0 flex items-center pl-2 pointer-events-none">
          <svg className="h-5 w-5 text-gray-400" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </span>
      </button>

      {isOpen && (
        <div className="absolute z-10 mt-1 w-full bg-white shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none">
          <div className="sticky top-0 z-10 bg-white">
            <input
              type="text"
              className="w-full p-2 border-b border-gray-200 focus:outline-none focus:ring-0"
              placeholder="جستجو فرودگاه..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              autoFocus
            />
          </div>

          {filtered.length === 0 ? (
            <div className="px-4 py-2 text-gray-500 text-center">فرودگاهی یافت نشد</div>
          ) : (
            filtered.map((airport, index) => (
              <button
                key={index}
                type="button"
                className="w-full text-right px-4 py-2 hover:bg-blue-50 focus:bg-blue-50 focus:outline-none"
                onClick={() => handleSelect(airport)}
              >
                <div className="flex justify-between items-center">
                  <span className="font-medium">{airport.city}</span>
                  <span className="text-sm text-gray-500">
                    {airport.iata && `${airport.iata} / `}{airport.icao}
                  </span>
                </div>
                <div className="text-sm text-gray-600 truncate">{airport.name}</div>
                {airport.type && (
                  <div className="text-xs text-gray-400">{airport.type}</div>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
