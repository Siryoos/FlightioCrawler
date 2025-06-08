'use client';
import React, { useState } from 'react';
import PersianDatePicker from './PersianDatePicker';

export type Leg = { origin: string; destination: string; date: string };

export default function MultiCitySearch({ onSearch }: { onSearch: (legs: Leg[]) => void }) {
  const [legs, setLegs] = useState<Leg[]>([{ origin: '', destination: '', date: '' }]);

  const updateLeg = (i: number, key: keyof Leg, value: string) => {
    const newLegs = legs.slice();
    newLegs[i] = { ...newLegs[i], [key]: value };
    setLegs(newLegs);
  };

  const addLeg = () => setLegs([...legs, { origin: '', destination: '', date: '' }]);

  return (
    <div className="space-y-2" data-testid="multi-city-search">
      {legs.map((leg, i) => (
        <div key={i} className="flex space-x-2 rtl:space-x-reverse">
          <input className="p-2 border flex-1" placeholder="مبدا" value={leg.origin} onChange={(e) => updateLeg(i, 'origin', e.target.value)} />
          <input className="p-2 border flex-1" placeholder="مقصد" value={leg.destination} onChange={(e) => updateLeg(i, 'destination', e.target.value)} />
          <PersianDatePicker value={leg.date} onChange={(v) => updateLeg(i, 'date', v)} />
        </div>
      ))}
      <button className="bg-green-600 text-white p-2 w-full" onClick={addLeg}>مسیر جدید</button>
      <button className="bg-blue-600 text-white p-2 w-full" onClick={() => onSearch(legs)}>جستجوی چند مسیره</button>
    </div>
  );
}
