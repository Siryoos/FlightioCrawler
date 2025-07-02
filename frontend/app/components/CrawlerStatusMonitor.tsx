'use client';
import React, { useEffect, useState } from 'react';

export default function CrawlerStatusMonitor() {
  const [status, setStatus] = useState<string>('connecting');

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:3000/api/status');
    ws.onopen = () => setStatus('connected');
    ws.onerror = () => setStatus('error');
    ws.onclose = () => setStatus('closed');
    return () => ws.close();
  }, []);

  return (
    <div className="text-sm text-gray-700" data-testid="crawler-status">
      وضعیت اتصال خزنده: {status}
    </div>
  );
}
