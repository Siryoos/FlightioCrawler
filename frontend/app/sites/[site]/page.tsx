'use client';
import React, { useEffect } from 'react';
import SiteBIMetrics from '../../components/SiteBIMetrics';
import { useSiteStore } from '../../../stores/siteStore';

export default function SitePage({ params }: { params: { site: string } }) {
  const { site } = params;
  const { currentSiteData, fetchSiteDetails, loading } = useSiteStore();

  useEffect(() => {
    fetchSiteDetails(site);
  }, [site, fetchSiteDetails]);

  return (
    <main className="max-w-xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold text-center">{site} گزارش</h1>
      {loading && !currentSiteData && <p>در حال بارگذاری...</p>}
      {currentSiteData && <SiteBIMetrics data={currentSiteData} />}
      {!loading && !currentSiteData && <p>داده‌ای برای نمایش وجود ندارد.</p>}
    </main>
  );
}
