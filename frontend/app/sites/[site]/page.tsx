'use client';
import React, { useEffect } from 'react';
import SiteBIMetrics from '../../components/SiteBIMetrics';
import { useSiteStore } from '../../stores/siteStore';

export default function SitePage({ params }: { params: { site: string } }) {
  const { site } = params;
  const { currentSiteData, fetchSiteDetails, loading } = useSiteStore();

  useEffect(() => {
    fetchSiteDetails(site);
  }, [site, fetchSiteDetails]);

  // Map SiteDetail to SiteHealth for SiteBIMetrics
  const siteHealth = currentSiteData
    ? {
        site: currentSiteData.name,
        base_url: (currentSiteData as any).base_url || '',
        url_accessible: (currentSiteData as any).url_accessible ?? false,
        http_status: (currentSiteData as any).http_status ?? undefined,
        response_time: (currentSiteData as any).response_time ?? null,
        circuit_breaker_open: (currentSiteData as any).circuit_breaker_open ?? false,
        rate_limited: (currentSiteData as any).rate_limited ?? false,
        error_count_last_hour: (currentSiteData as any).error_count_last_hour ?? 0,
        success_count_last_hour: (currentSiteData as any).success_count_last_hour ?? 0,
      }
    : null;

  return (
    <main className="max-w-xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold text-center">{site} گزارش</h1>
      {loading && !siteHealth && <p>در حال بارگذاری...</p>}
      {siteHealth && <SiteBIMetrics data={siteHealth} />}
      {!loading && !siteHealth && <p>داده‌ای برای نمایش وجود ندارد.</p>}
    </main>
  );
}
