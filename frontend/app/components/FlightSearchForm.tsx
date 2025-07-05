'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import AirportSelector from './AirportSelector';
import { useSearchStore } from '../stores/searchStore';
import { getAirportByCode } from './AirportData';
import { useAirportStore } from '../stores/airportStore';

const PersianDatePicker = dynamic(() => import('./PersianDatePicker'), {
  ssr: false,
  loading: () => <div className="w-full h-10 bg-gray-200 rounded-md animate-pulse"></div>
});

interface FlightSearchFormProps {
  onSearch?: (data: any) => void; // Simplified for refactoring
}

export default function FlightSearchForm({ onSearch }: FlightSearchFormProps = {}) {
  const {
    origin,
    destination,
    departureDate,
    returnDate,
    tripType,
    passengers,
    setField,
    setTripType,
    setPassengers,
  } = useSearchStore();
  const { airports } = useAirportStore();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (onSearch) {
      onSearch({
        origin,
        destination,
        departureDate,
        returnDate: tripType === 'roundTrip' ? returnDate : undefined,
        passengers: passengers.adults + passengers.children + passengers.infants,
        tripType,
      });
    }
  };

  const swapAirports = () => {
    const temp = origin;
    setField('origin', destination);
    setField('destination', temp);
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">جستجوی پرواز</h2>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Trip Type */}
        <fieldset className="flex justify-center space-x-6 space-x-reverse">
          <legend className="sr-only">نوع سفر</legend>
          <label className="flex items-center">
            <input
              type="radio"
              name="tripType"
              value="oneWay"
              checked={tripType === 'oneWay'}
              onChange={() => setTripType('oneWay')}
              className="mr-2"
            />
            <span>یک‌طرفه</span>
          </label>
          <label className="flex items-center">
            <input
              type="radio"
              name="tripType"
              value="roundTrip"
              checked={tripType === 'roundTrip'}
              onChange={() => setTripType('roundTrip')}
              className="mr-2"
            />
            <span>رفت و برگشت</span>
          </label>
        </fieldset>

        {/* Origin and Destination */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 relative">
          <div>
            <label htmlFor="origin-selector" className="block text-sm font-medium text-gray-700 mb-2">
              مبدا
            </label>
            <AirportSelector
              value={origin}
              onChange={(value) => setField('origin', value)}
              placeholder="انتخاب فرودگاه مبدا"
            />
          </div>

          {/* Swap Button */}
          <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 z-10 hidden md:block">
            <button
              type="button"
              onClick={swapAirports}
              className="bg-blue-500 text-white p-2 rounded-full hover:bg-blue-600 transition-colors"
              title="تعویض مبدا و مقصد"
              aria-label="تعویض مبدا و مقصد"
            >
              ⇄
            </button>
          </div>

          <div>
            <label htmlFor="destination-selector" className="block text-sm font-medium text-gray-700 mb-2">
              مقصد
            </label>
            <AirportSelector
              value={destination}
              onChange={(value) => setField('destination', value)}
              placeholder="انتخاب فرودگاه مقصد"
            />
          </div>
        </div>

        {/* Dates */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="departure-date-picker" className="block text-sm font-medium text-gray-700 mb-2">
              تاریخ رفت
            </label>
            <PersianDatePicker
              value={departureDate}
              onChange={(date) => setField('departureDate', date)}
            />
          </div>

          {tripType === 'roundTrip' && (
            <div>
              <label htmlFor="return-date-picker" className="block text-sm font-medium text-gray-700 mb-2">
                تاریخ برگشت
              </label>
              <PersianDatePicker
                value={returnDate}
                onChange={(date) => setField('returnDate', date)}
              />
            </div>
          )}
        </div>

        {/* Passengers */}
        <fieldset className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <legend className="sr-only">تعداد مسافران</legend>
          <div>
            <label htmlFor="adult-passengers" className="block text-sm font-medium text-gray-700 mb-2">
              بزرگسال
            </label>
            <select
              id="adult-passengers"
              value={passengers.adults}
              onChange={(e) => setPassengers({ adults: parseInt(e.target.value) })}
              className="w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(num => (
                <option key={num} value={num}>{num}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="child-passengers" className="block text-sm font-medium text-gray-700 mb-2">
              کودک (۲-۱۱ سال)
            </label>
            <select
              id="child-passengers"
              value={passengers.children}
              onChange={(e) => setPassengers({ children: parseInt(e.target.value) })}
              className="w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {[0, 1, 2, 3, 4, 5, 6, 7, 8].map(num => (
                <option key={num} value={num}>{num}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="infant-passengers" className="block text-sm font-medium text-gray-700 mb-2">
              نوزاد (زیر ۲ سال)
            </label>
            <select
              id="infant-passengers"
              value={passengers.infants}
              onChange={(e) => setPassengers({ infants: parseInt(e.target.value) })}
              className="w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {[0, 1, 2, 3, 4].map(num => (
                <option key={num} value={num}>{num}</option>
              ))}
            </select>
          </div>
        </fieldset>

        {/* Submit Button */}
        <button
          type="submit"
          className="w-full bg-blue-600 text-white py-3 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium disabled:bg-gray-400 disabled:cursor-not-allowed"
          disabled={!origin || !destination || !departureDate}
        >
          جستجوی پرواز
        </button>

        {/* Flight Info Display */}
        {origin && destination && (
          <div className="mt-4 p-4 bg-gray-50 rounded-md">
            <p className="text-sm text-gray-600 text-center">
              <span className="font-medium">{getAirportByCode(airports, origin)?.city || origin}</span>
              <span className="mx-2">({origin})</span>
              <span className="mx-2">→</span>
              <span className="font-medium">{getAirportByCode(airports, destination)?.city || destination}</span>
              <span className="mx-2">({destination})</span>
            </p>
            <p className="text-xs text-gray-500 text-center mt-1">
              {passengers.adults + passengers.children + passengers.infants} مسافر • {tripType === 'roundTrip' ? 'رفت و برگشت' : 'یک‌طرفه'}
            </p>
          </div>
        )}
      </form>
    </div>
  );
} 