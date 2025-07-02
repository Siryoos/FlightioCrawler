'use client';
import React, { useState, useRef, useEffect } from 'react';

export interface Airport {
  icao: string;
  iata: string;
  name: string;
  city: string;
  type: string;
}

const IRANIAN_AIRPORTS: Airport[] = [
  { icao: 'OIAA', iata: 'ABD', name: 'فرودگاه بین المللی آبادان', city: 'آبادان', type: 'مرز هوایی' },
  { icao: 'OISA', iata: '', name: 'فرودگاه آباده', city: 'آباده', type: 'در دست ساخت' },
  { icao: 'OICD', iata: '', name: 'فرودگاه آبدانان', city: 'آبدانان', type: 'داخلی' },
  { icao: 'OIAG', iata: 'AKW', name: 'فرودگاه آغاجاری', city: 'آغاجاری', type: 'داخلی' },
  { icao: 'OIBA', iata: 'AEU', name: 'فرودگاه ابوموسی', city: 'ابوموسی', type: 'داخلی' },
  { icao: 'OIHR', iata: 'AJK', name: 'فرودگاه اراک', city: 'اراک', type: 'مرز هوایی' },
  { icao: 'OITL', iata: 'ADU', name: 'فرودگاه اردبیل', city: 'اردبیل', type: 'مرز هوایی' },
  { icao: 'OITR', iata: 'OMH', name: 'فرودگاه بین‌المللی شهید باکری ارومیه', city: 'ارومیه', type: 'بین‌المللی' },
  { icao: 'OIFM', iata: 'IFN', name: 'فرودگاه بین‌المللی شهید بهشتی اصفهان', city: 'اصفهان', type: 'بین‌المللی' },
  { icao: 'OIAW', iata: 'AWZ', name: 'فرودگاه بین‌المللی شهید قاسم سلیمانی', city: 'اهواز', type: 'مرز هوایی' },
  { icao: 'OIZI', iata: 'IHR', name: 'فرودگاه شهدای ایرانشهر', city: 'ایرانشهر', type: 'داخلی' },
  { icao: 'OICI', iata: 'IIL', name: 'فرودگاه ایلام', city: 'ایلام', type: 'مرز هوایی' },
  { icao: 'OINB', iata: 'BBL', name: 'فرودگاه بابلسر', city: 'بابلسر', type: 'داخلی' },
  { icao: 'OIMN', iata: 'BJB', name: 'فرودگاه شهدای بجنورد', city: 'بجنورد', type: 'مرز هوایی' },
  { icao: 'OIKM', iata: 'BXR', name: 'فرودگاه بم', city: 'بم', type: 'مرز هوایی' },
  { icao: 'OITM', iata: 'ACP', name: 'فرودگاه شهید رحمتی', city: 'بناب', type: 'داخلی' },
  { icao: 'OIKB', iata: 'BND', name: 'فرودگاه بین‌المللی بندرعباس', city: 'بندرعباس', type: 'بین‌المللی' },
  { icao: 'OIKP', iata: 'HDR', name: 'فرودگاه هوادریا', city: 'بندرعباس', type: '' },
  { icao: 'OIBL', iata: 'BDH', name: 'فرودگاه بندرلنگه', city: 'بندرلنگه', type: 'مرز هوایی' },
  { icao: 'OIBB', iata: 'BUZ', name: 'فرودگاه بوشهر', city: 'بوشهر', type: 'مرز هوایی' },
  { icao: 'OIAE', iata: '', name: 'فرودگاه بهبهان', city: 'بهبهان', type: 'داخلی' },
  { icao: 'OI20', iata: 'IAQ', name: 'فرودگاه بهرگان', city: 'بهرگان،(امام‌حسن)', type: 'داخلی' },
  { icao: 'OIMB', iata: 'XBJ', name: 'فرودگاه بیرجند', city: 'بیرجند', type: 'مرز هوایی' },
  { icao: 'OITP', iata: 'PFQ', name: 'فرودگاه پارس‌آباد مغان', city: 'پارس‌آباد', type: 'داخلی' },
  { icao: 'OITH', iata: 'KHA', name: 'فرودگاه خانه', city: 'پیرانشهر', type: 'داخلی' },
  { icao: 'OITT', iata: 'TBZ', name: 'فرودگاه بین‌المللی شهید مدنی تبریز', city: 'تبریز', type: 'بین‌المللی' },
  { icao: 'OIIE', iata: 'IKA', name: 'فرودگاه بین‌المللی امام خمینی', city: 'تهران', type: 'بین‌المللی' },
  { icao: 'OIII', iata: 'THR', name: 'فرودگاه بین‌المللی مهرآباد', city: 'تهران', type: 'بین‌المللی' },
  { icao: 'OIIG', iata: '', name: 'فرودگاه قلعه‌مرغی', city: 'تهران', type: '' },
  { icao: 'OIZJ', iata: '', name: 'فرودگاه جاسک', city: 'جاسک', type: 'داخلی' },
  { icao: 'OIBX', iata: '', name: 'فرودگاه تنب بزرگ', city: 'جزیره تنب بزرگ', type: 'داخلی' },
  { icao: 'OIBQ', iata: 'KHK', name: 'فرودگاه خارگ', city: 'جزیره خارگ', type: '' },
  { icao: 'OIBS', iata: 'SXI', name: 'فرودگاه جزیره سیری', city: 'جزیره سیری', type: 'داخلی' },
  { icao: 'OIBV', iata: 'LVP', name: 'فرودگاه لاوان', city: 'جزیره لاوان', type: 'داخلی' },
  { icao: 'OIBJ', iata: 'KNR', name: 'فرودگاه توحید جم', city: 'جم', type: 'اختصاصی' },
  { icao: 'OISJ', iata: 'JAR', name: 'فرودگاه بین‌المللی جهرم', city: 'جهرم', type: 'مرز هوایی' },
  { icao: 'OIKJ', iata: 'JYR', name: 'فرودگاه جیرفت', city: 'جیرفت', type: 'داخلی' },
  { icao: 'OIZC', iata: 'ZBR', name: 'فرودگاه کنارک', city: 'چابهار', type: 'مرز هوایی' },
  { icao: 'OISD', iata: '', name: 'فرودگاه داراب', city: 'داراب', type: 'داخلی' },
  { icao: 'OIAD', iata: 'DEF', name: 'فرودگاه بین‌المللی دزفول', city: 'دزفول', type: 'بین‌المللی' },
  { icao: 'OISF', iata: 'FAZ', name: 'فرودگاه فسا', city: 'فسا', type: 'داخلی' },
  { icao: 'OIAH', iata: 'GCH', name: 'فرودگاه شهید امیدبخش گچساران', city: 'گچساران', type: 'داخلی' },
  { icao: '', iata: '', name: 'فرودگاه گنبد کاووس', city: 'گنبد کاووس', type: 'داخلی' },
  { icao: 'OING', iata: 'GBT', name: 'فرودگاه گرگان', city: 'گرگان', type: 'مرز هوایی' },
  { icao: 'OINE', iata: 'KLM', name: 'فرودگاه کلاله', city: 'کلاله', type: 'داخلی' },
  { icao: 'OIIP', iata: '', name: 'فرودگاه بین‌المللی پیام', city: 'کرج', type: 'بین‌المللی' },
  { icao: 'OIKK', iata: 'KER', name: 'فرودگاه بین‌المللی آیت‌الله هاشمی رفسنجانی کرمان', city: 'کرمان', type: 'مرز هوایی' },
  { icao: 'OICC', iata: 'KSH', name: 'فرودگاه بین‌المللی شهید اشرفی کرمانشاه', city: 'کرمانشاه', type: 'مرز هوایی' },
  { icao: 'OICK', iata: 'KHD', name: 'فرودگاه بین‌المللی شهدای خرم‌آباد', city: 'خرم‌آباد', type: 'بین المللی' },
  { icao: 'OITK', iata: 'KHY', name: 'فرودگاه خوی', city: 'خوی', type: 'داخلی' },
  { icao: 'OIBK', iata: 'KIH', name: 'فرودگاه بین‌المللی کیش', city: 'کیش', type: 'بین‌المللی' },
  { icao: 'OISR', iata: 'LFM', name: 'فرودگاه بین‌المللی شهدای لامرد', city: 'لامرد', type: 'مرز هوایی' },
  { icao: 'OISL', iata: 'LRR', name: 'فرودگاه بین‌المللی آیت‌الله آیت‌اللهی لارستان', city: 'لارستان', type: 'بین المللی' },
  { icao: 'OIAM', iata: 'MRX', name: 'فرودگاه بندرماهشهر', city: 'ماهشهر', type: 'داخلی' },
  { icao: 'OIMM', iata: 'MHD', name: 'فرودگاه بین‌المللی شهید هاشمی‌نژاد مشهد', city: 'مشهد', type: 'بین‌المللی' },
  { icao: 'OIAI', iata: '', name: 'فرودگاه مسجد سلیمان', city: 'مسجدسلیمان', type: 'داخلی' },
  { icao: 'OINN', iata: 'NSH', name: 'فرودگاه نوشهر', city: 'نوشهر', type: 'داخلی' },
  { icao: 'OIIK', iata: 'GZW', name: 'فرودگاه قزوین', city: 'قزوین', type: 'داخلی' },
  { icao: 'OIIA', iata: '', name: 'فرودگاه آزادی', city: 'قزوین', type: 'داخلی' },
  { icao: 'OIKQ', iata: 'GSM', name: 'فرودگاه بین‌المللی قشم', city: 'قشم', type: 'بین المللی' },
  { icao: '', iata: '', name: 'فرودگاه جنوبی قشم', city: 'قشم', type: 'مرز هوایی' },
  { icao: 'OIIQ', iata: '', name: 'فرودگاه بین‌المللی قم', city: 'قم', type: 'در دست احداث' },
  { icao: 'OIFK', iata: 'KSN', name: 'فرودگاه کاشان', city: 'کاشان', type: 'داخلی' },
  { icao: 'OIKR', iata: 'RJN', name: 'فرودگاه رفسنجان', city: 'رفسنجان', type: 'مرز هوایی' },
  { icao: 'OINR', iata: 'RZR', name: 'فرودگاه شهدای رامسر', city: 'رامسر', type: 'داخلی' },
  { icao: 'OIGG', iata: 'RAS', name: 'فرودگاه بین‌المللی سردار جنگل رشت', city: 'رشت', type: 'بین‌المللی' },
  { icao: 'OIMS', iata: 'AFZ', name: 'فرودگاه بین المللی شهدای سبزوار', city: 'سبزوار', type: 'مرز هوایی' },
  { icao: 'OITS', iata: 'TQZ', name: 'فرودگاه سقز', city: 'سقز', type: 'مرز هوایی' },
  { icao: '', iata: '', name: 'فرودگاه فردوس', city: 'فردوس', type: 'در حال احداث' },
  { icao: 'OICS', iata: 'SDG', name: 'فرودگاه سنندج', city: 'سنندج', type: 'مرز هوایی' },
  { icao: 'OIMC', iata: 'CKT', name: 'فرودگاه سرخس', city: 'سرخس', type: 'داخلی' },
  { icao: 'OIZS', iata: '', name: 'فرودگاه سراوان', city: 'سراوان', type: 'داخلی' },
  { icao: 'OINZ', iata: 'SRY', name: 'فرودگاه بین‌المللی دشت ناز ساری', city: 'ساری', type: 'مرز هوایی' },
  { icao: 'OIIS', iata: '', name: 'فرودگاه سمنان', city: 'سمنان', type: 'داخلی' },
  { icao: 'OI21', iata: '', name: 'فرودگاه جدید سمنان', city: 'سمنان', type: 'داخلی' },
  { icao: 'OIBI', iata: 'YEH', name: 'فرودگاه عسلویه', city: 'عسلویه', type: 'مرز هوایی' },
  { icao: 'OIBP', iata: 'PGU', name: 'فرودگاه بین‌المللی خلیج فارس', city: 'عسلویه', type: 'مرز هوایی' },
  { icao: 'OIFS', iata: 'CQD', name: 'فرودگاه بین‌المللی شهدای شهرکرد', city: 'شهرکرد', type: 'مرز هوایی' },
  { icao: 'OIMJ', iata: '', name: 'فرودگاه شاهرود', city: 'شاهرود', type: 'داخلی' },
  { icao: 'OISS', iata: 'SYZ', name: 'فرودگاه بین‌المللی شهید دستغیب شیراز', city: 'شیراز', type: 'بین‌المللی' },
  { icao: 'OIKY', iata: 'SYJ', name: 'فرودگاه سیرجان', city: 'سیرجان', type: 'داخلی' },
  { icao: 'OIMT', iata: 'TCX', name: 'فرودگاه شهدای طبس', city: 'طبس', type: 'داخلی' },
  { icao: 'OIZB', iata: 'ACZ', name: 'فرودگاه زابل', city: 'زابل', type: 'داخلی' },
  { icao: 'OIZH', iata: 'ZAH', name: 'فرودگاه بین‌المللی شهدای زاهدان', city: 'زاهدان', type: 'بین‌المللی' },
  { icao: 'OITZ', iata: 'JWN', name: 'فرودگاه زنجان', city: 'زنجان', type: 'مرز هوایی' },
  { icao: 'OISO', iata: '', name: 'فرودگاه زرقان', city: 'زرقان', type: 'آموزشی' },
  { icao: 'OIHH', iata: 'HDM', name: 'فرودگاه همدان', city: 'همدان', type: 'مرز هوایی' },
  { icao: 'OISY', iata: 'YES', name: 'فرودگاه بین المللی شهدای یاسوج', city: 'یاسوج', type: 'داخلی' },
  { icao: 'OIYY', iata: 'AZD', name: 'فرودگاه شهید صدوقی یزد', city: 'یزد', type: 'مرز هوایی' },
  { icao: 'OIFV', iata: '', name: 'فرودگاه زرین‌شهر', city: 'زرین‌شهر', type: 'داخلی' }
];

interface AirportSelectorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export default function AirportSelector({ value, onChange, placeholder = "انتخاب فرودگاه", className = "" }: AirportSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  const filteredAirports = IRANIAN_AIRPORTS.filter(airport => 
    airport.city.includes(searchTerm) || 
    airport.name.includes(searchTerm) ||
    airport.iata.toLowerCase().includes(searchTerm.toLowerCase()) ||
    airport.icao.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const selectedAirport = IRANIAN_AIRPORTS.find(airport => 
    airport.iata === value || airport.icao === value || airport.city === value
  );

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (airport: Airport) => {
    onChange(airport.iata || airport.icao || airport.city);
    setIsOpen(false);
    setSearchTerm('');
  };

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <button
        type="button"
        className="w-full p-2 border border-gray-300 rounded-md bg-white text-right focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="block truncate">
          {selectedAirport ? `${selectedAirport.city} (${selectedAirport.iata || selectedAirport.icao})` : placeholder}
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
          
          {filteredAirports.length === 0 ? (
            <div className="px-4 py-2 text-gray-500 text-center">فرودگاهی یافت نشد</div>
          ) : (
            filteredAirports.map((airport, index) => (
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