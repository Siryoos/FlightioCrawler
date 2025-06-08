'use client';
import React from 'react';

interface SiteHealth {
  site: string;
  base_url: string;
  url_accessible?: boolean;
  http_status?: number;
  response_time?: number | null;
  circuit_breaker_open?: boolean;
  rate_limited?: boolean;
  error_count_last_hour?: number;
  success_count_last_hour?: number;
}

export default function SiteBIMetrics({ data }: { data: SiteHealth }) {
  if (!data) return null;
  return (
    <table className="w-full border" data-testid="site-bi-table">
      <tbody>
        <tr>
          <td className="border p-1">URL</td>
          <td className="border p-1">{data.base_url}</td>
        </tr>
        <tr>
          <td className="border p-1">Accessible</td>
          <td className="border p-1">{data.url_accessible ? 'yes' : 'no'}</td>
        </tr>
        <tr>
          <td className="border p-1">Status</td>
          <td className="border p-1">{data.http_status ?? '-'}</td>
        </tr>
        <tr>
          <td className="border p-1">Response Time</td>
          <td className="border p-1">{data.response_time ?? '-'}</td>
        </tr>
        <tr>
          <td className="border p-1">Circuit Breaker</td>
          <td className="border p-1">{data.circuit_breaker_open ? 'open' : 'closed'}</td>
        </tr>
        <tr>
          <td className="border p-1">Rate Limited</td>
          <td className="border p-1">{data.rate_limited ? 'yes' : 'no'}</td>
        </tr>
        <tr>
          <td className="border p-1">Errors Last Hour</td>
          <td className="border p-1">{data.error_count_last_hour}</td>
        </tr>
        <tr>
          <td className="border p-1">Success Last Hour</td>
          <td className="border p-1">{data.success_count_last_hour}</td>
        </tr>
      </tbody>
    </table>
  );
}
