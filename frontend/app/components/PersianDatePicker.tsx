'use client';
import React from 'react';

export default function PersianDatePicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="date"
      className="w-full p-2 border"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      data-testid="persian-date-picker"
    />
  );
}
