'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

interface CrawlerStatus {
  site: string;
  is_active: boolean;
  success_rate: number;
  last_crawl: string;
  error_count: number;
  response_time: number;
}

interface SystemMetrics {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  active_connections: number;
  messages_sent: number;
  uptime: number;
}

interface FlightUpdate {
  flights: any[];
  count: number;
  timestamp: string;
}

interface ErrorAlert {
  message: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  site?: string;
  timestamp: string;
}

export default function RealTimeStatusMonitor() {
  // State for different data types
  const [crawlerStatuses, setCrawlerStatuses] = useState<Record<string, CrawlerStatus>>({});
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null);
  const [recentFlights, setRecentFlights] = useState<FlightUpdate | null>(null);
  const [errorAlerts, setErrorAlerts] = useState<ErrorAlert[]>([]);
  const [isMinimized, setIsMinimized] = useState(false);

  // WebSocket connection
  const websocket = useWebSocket({
    url: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/api/v1/websocket/connect',
    userId: 'dashboard_user',
    autoConnect: true,
    debug: process.env.NODE_ENV === 'development',
    onConnect: () => {
      console.log('WebSocket connected to real-time monitor');
    },
    onDisconnect: () => {
      console.log('WebSocket disconnected from real-time monitor');
    },
    onError: (error) => {
      console.error('WebSocket error in real-time monitor:', error);
    }
  });

  // Subscribe to topics on connection
  useEffect(() => {
    if (websocket.connected) {
      websocket.subscribe('crawler_status');
      websocket.subscribe('system_metrics');
      websocket.subscribe('flight_updates');
      websocket.subscribe('error_alerts');
    }
  }, [websocket.connected, websocket.subscribe]);

  // Handle crawler status updates
  useEffect(() => {
    const unsubscribe = websocket.onCrawlerStatus((data) => {
      if (data.site && data.status) {
        setCrawlerStatuses(prev => ({
          ...prev,
          [data.site]: data.status
        }));
      }
    });

    return unsubscribe;
  }, [websocket.onCrawlerStatus]);

  // Handle system metrics updates
  useEffect(() => {
    const unsubscribe = websocket.onSystemMetrics((data) => {
      if (data.metrics) {
        setSystemMetrics(data.metrics);
      }
    });

    return unsubscribe;
  }, [websocket.onSystemMetrics]);

  // Handle flight updates
  useEffect(() => {
    const unsubscribe = websocket.onFlightUpdate((data) => {
      setRecentFlights(data);
    });

    return unsubscribe;
  }, [websocket.onFlightUpdate]);

  // Handle error alerts
  useEffect(() => {
    const unsubscribe = websocket.onErrorAlert((data) => {
      const alert: ErrorAlert = {
        message: data.message || 'Unknown error',
        severity: data.severity || 'medium',
        site: data.site,
        timestamp: data.timestamp || new Date().toISOString()
      };

      setErrorAlerts(prev => {
        const newAlerts = [alert, ...prev];
        // Keep only last 10 alerts
        return newAlerts.slice(0, 10);
      });

      // Auto-remove alerts after 30 seconds
      setTimeout(() => {
        setErrorAlerts(prev => 
          prev.filter(a => a.timestamp !== alert.timestamp)
        );
      }, 30000);
    });

    return unsubscribe;
  }, [websocket.onErrorAlert]);

  // Helper functions
  const getStatusColor = (isActive: boolean, successRate: number) => {
    if (!isActive) return 'bg-gray-500';
    if (successRate >= 0.8) return 'bg-green-500';
    if (successRate >= 0.5) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getMetricColor = (percent: number) => {
    if (percent < 50) return 'text-green-600';
    if (percent < 80) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getSeverityColor = (severity: ErrorAlert['severity']) => {
    switch (severity) {
      case 'low': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const formatTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString();
    } catch {
      return 'Invalid time';
    }
  };

  if (isMinimized) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <button
          onClick={() => setIsMinimized(false)}
          className="bg-blue-600 text-white p-3 rounded-full shadow-lg hover:bg-blue-700 transition-colors"
          title="Show Real-Time Monitor"
        >
          <div className="flex items-center space-x-2">
            <div className={`w-3 h-3 rounded-full ${websocket.connected ? 'bg-green-400' : 'bg-red-400'}`}></div>
            <span className="text-sm font-medium">Monitor</span>
          </div>
        </button>
      </div>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 w-96 bg-white border border-gray-300 rounded-lg shadow-xl z-50 max-h-96 overflow-hidden">
      {/* Header */}
      <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className={`w-3 h-3 rounded-full ${websocket.connected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <h3 className="text-sm font-semibold text-gray-900">Real-Time Monitor</h3>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-xs text-gray-500">
            {websocket.stats.messagesReceived} msgs
          </span>
          <button
            onClick={() => setIsMinimized(true)}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            title="Minimize"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
            </svg>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="overflow-y-auto max-h-80">
        {/* Connection Status */}
        {!websocket.connected && (
          <div className="p-3 bg-red-50 border-b border-red-200">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></div>
              <span className="text-sm text-red-700">
                {websocket.connecting ? 'Connecting...' : 'Disconnected'}
              </span>
              {websocket.error && (
                <span className="text-xs text-red-600">({websocket.error})</span>
              )}
            </div>
          </div>
        )}

        {/* Error Alerts */}
        {errorAlerts.length > 0 && (
          <div className="p-3 border-b border-gray-200">
            <h4 className="text-xs font-semibold text-gray-700 mb-2">Recent Alerts</h4>
            <div className="space-y-2">
              {errorAlerts.slice(0, 3).map((alert, index) => (
                <div
                  key={alert.timestamp}
                  className={`p-2 rounded text-xs border ${getSeverityColor(alert.severity)}`}
                >
                  <div className="font-medium">{alert.message}</div>
                  {alert.site && (
                    <div className="text-xs opacity-75 mt-1">Site: {alert.site}</div>
                  )}
                  <div className="text-xs opacity-75 mt-1">
                    {formatTime(alert.timestamp)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Crawler Status */}
        {Object.keys(crawlerStatuses).length > 0 && (
          <div className="p-3 border-b border-gray-200">
            <h4 className="text-xs font-semibold text-gray-700 mb-2">Crawler Status</h4>
            <div className="space-y-2">
              {Object.entries(crawlerStatuses).slice(0, 4).map(([site, status]) => (
                <div key={site} className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <div
                      className={`w-2 h-2 rounded-full ${getStatusColor(status.is_active, status.success_rate)}`}
                    ></div>
                    <span className="text-xs font-medium text-gray-700 truncate">
                      {site}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500">
                    {Math.round(status.success_rate * 100)}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* System Metrics */}
        {systemMetrics && (
          <div className="p-3 border-b border-gray-200">
            <h4 className="text-xs font-semibold text-gray-700 mb-2">System Health</h4>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-600">CPU</span>
                <span className={getMetricColor(systemMetrics.cpu_percent)}>
                  {Math.round(systemMetrics.cpu_percent)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Memory</span>
                <span className={getMetricColor(systemMetrics.memory_percent)}>
                  {Math.round(systemMetrics.memory_percent)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Connections</span>
                <span className="text-gray-700">{systemMetrics.active_connections}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Uptime</span>
                <span className="text-gray-700">{formatUptime(systemMetrics.uptime)}</span>
              </div>
            </div>
          </div>
        )}

        {/* Recent Flights */}
        {recentFlights && recentFlights.count > 0 && (
          <div className="p-3 border-b border-gray-200">
            <h4 className="text-xs font-semibold text-gray-700 mb-2">Recent Flights</h4>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-600">New flights found</span>
              <span className="text-green-600 font-medium">{recentFlights.count}</span>
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Last update: {formatTime(recentFlights.timestamp)}
            </div>
          </div>
        )}

        {/* WebSocket Stats */}
        <div className="p-3 bg-gray-50">
          <h4 className="text-xs font-semibold text-gray-700 mb-2">Connection Stats</h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex justify-between">
              <span className="text-gray-600">Messages</span>
              <span className="text-gray-700">{websocket.stats.messagesReceived}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Latency</span>
              <span className="text-gray-700">{websocket.stats.latency}ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Subscriptions</span>
              <span className="text-gray-700">{websocket.subscriptions.size}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Reconnects</span>
              <span className="text-gray-700">{websocket.stats.reconnectAttempts}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
        <div className="text-xs text-gray-500">
          Last: {websocket.stats.lastMessageTime?.toLocaleTimeString() || 'Never'}
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={websocket.reconnect}
            className="text-xs text-blue-600 hover:text-blue-800 transition-colors"
            disabled={websocket.connecting}
          >
            {websocket.connecting ? 'Connecting...' : 'Reconnect'}
          </button>
        </div>
      </div>
    </div>
  );
} 