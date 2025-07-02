'use client';

import { useState } from 'react';
import AirportSelector from './AirportSelector';
import PersianDatePicker from './PersianDatePicker';
import { Airport, getAirportByCode } from './AirportData';

interface FlightSearchData {
  origin: string;
  destination: string;
  departureDate: string;
  returnDate?: string;
  passengers: number;
  tripType: 'oneWay' | 'roundTrip';
}

interface FlightSearchFormProps {
  onSearch?: (data: FlightSearchData) => void;
}

export default function FlightSearchForm({ onSearch }: FlightSearchFormProps = {}) {
  const [origin, setOrigin] = useState<string>('MHD'); // مشهد
  const [destination, setDestination] = useState<string>('IST'); // استانبول
  const [departureDate, setDepartureDate] = useState('');
  const [returnDate, setReturnDate] = useState('');
  const [tripType, setTripType] = useState<'oneWay' | 'roundTrip'>('roundTrip');
  const [passengers, setPassengers] = useState({
    adults: 1,
    children: 0,
    infants: 0
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (onSearch) {
      onSearch({
        origin,
        destination,
        departureDate,
        returnDate,
        passengers: passengers.adults + passengers.children + passengers.infants,
        tripType
      });
    }
  };

  const swapAirports = () => {
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">جستجوی پرواز</h2>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Trip Type */}
        <div className="flex justify-center space-x-6 space-x-reverse">
          <label className="flex items-center">
            <input
              type="radio"
              name="tripType"
              value="oneWay"
              checked={tripType === 'oneWay'}
              onChange={(e) => setTripType(e.target.value as 'oneWay')}
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
              onChange={(e) => setTripType(e.target.value as 'roundTrip')}
              className="mr-2"
            />
            <span>رفت و برگشت</span>
          </label>
        </div>

        {/* Origin and Destination */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 relative">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              مبدا
            </label>
            <AirportSelector
              value={origin}
              onChange={setOrigin}
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
            >
              ⇄
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              مقصد
            </label>
            <AirportSelector
              value={destination}
              onChange={setDestination}
              placeholder="انتخاب فرودگاه مقصد"
            />
          </div>
        </div>

        {/* Dates */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              تاریخ رفت
            </label>
            <PersianDatePicker
              value={departureDate}
              onChange={setDepartureDate}
            />
          </div>

          {tripType === 'roundTrip' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                تاریخ برگشت
              </label>
              <PersianDatePicker
                value={returnDate}
                onChange={setReturnDate}
              />
            </div>
          )}
        </div>

        {/* Passengers */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              بزرگسال
            </label>
            <select
              value={passengers.adults}
              onChange={(e) => setPassengers(prev => ({ ...prev, adults: parseInt(e.target.value) }))}
              className="w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(num => (
                <option key={num} value={num}>{num}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              کودک (۲-۱۱ سال)
            </label>
            <select
              value={passengers.children}
              onChange={(e) => setPassengers(prev => ({ ...prev, children: parseInt(e.target.value) }))}
              className="w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {[0, 1, 2, 3, 4, 5, 6, 7, 8].map(num => (
                <option key={num} value={num}>{num}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              نوزاد (زیر ۲ سال)
            </label>
            <select
              value={passengers.infants}
              onChange={(e) => setPassengers(prev => ({ ...prev, infants: parseInt(e.target.value) }))}
              className="w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {[0, 1, 2, 3, 4].map(num => (
                <option key={num} value={num}>{num}</option>
              ))}
            </select>
          </div>
        </div>

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
              <span className="font-medium">{getAirportByCode(origin)?.city || origin}</span>
              <span className="mx-2">({origin})</span>
              <span className="mx-2">→</span>
              <span className="font-medium">{getAirportByCode(destination)?.city || destination}</span>
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