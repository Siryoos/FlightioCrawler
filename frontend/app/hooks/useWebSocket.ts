import { useState, useEffect, useRef, useCallback } from 'react';

interface WebSocketMessage {
  type: string;
  topic: string;
  data: any;
  timestamp: string;
  message_id: string;
  user_id?: string;
}

interface ConnectionStats {
  connected: boolean;
  reconnectAttempts: number;
  lastMessageTime: Date | null;
  messagesReceived: number;
  messagesSent: number;
  latency: number;
}

interface UseWebSocketOptions {
  url: string;
  userId: string;
  autoConnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  debug?: boolean;
}

interface UseWebSocketReturn {
  // Connection state
  connected: boolean;
  connecting: boolean;
  error: string | null;
  stats: ConnectionStats;
  
  // Connection control
  connect: () => void;
  disconnect: () => void;
  reconnect: () => void;
  
  // Messaging
  sendMessage: (message: any) => void;
  subscribe: (topic: string) => void;
  unsubscribe: (topic: string) => void;
  
  // Message handlers
  onMessage: (handler: (message: WebSocketMessage) => void) => () => void;
  onCrawlerStatus: (handler: (data: any) => void) => () => void;
  onFlightUpdate: (handler: (data: any) => void) => () => void;
  onSystemMetrics: (handler: (data: any) => void) => () => void;
  onErrorAlert: (handler: (data: any) => void) => () => void;
  
  // State
  subscriptions: Set<string>;
  lastMessage: WebSocketMessage | null;
  messageHistory: WebSocketMessage[];
}

export const useWebSocket = (options: UseWebSocketOptions): UseWebSocketReturn => {
  const {
    url,
    userId,
    autoConnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
    heartbeatInterval = 30000,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    debug = false
  } = options;

  // State
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [subscriptions, setSubscriptions] = useState<Set<string>>(new Set());
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [messageHistory, setMessageHistory] = useState<WebSocketMessage[]>([]);
  const [stats, setStats] = useState<ConnectionStats>({
    connected: false,
    reconnectAttempts: 0,
    lastMessageTime: null,
    messagesReceived: 0,
    messagesSent: 0,
    latency: 0
  });

  // Refs
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const messageHandlers = useRef<Map<string, Set<(data: any) => void>>>(new Map());
  const reconnectAttempts = useRef(0);
  const lastPingTime = useRef<number>(0);

  // Debug logging
  const log = useCallback((message: string, data?: any) => {
    if (debug) {
      console.log(`[WebSocket] ${message}`, data);
    }
  }, [debug]);

  // Clear reconnect timeout
  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  // Clear heartbeat timeout
  const clearHeartbeatTimeout = useCallback(() => {
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current);
      heartbeatTimeoutRef.current = null;
    }
  }, []);

  // Start heartbeat
  const startHeartbeat = useCallback(() => {
    clearHeartbeatTimeout();
    
    const sendHeartbeat = () => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        lastPingTime.current = Date.now();
        ws.current.send(JSON.stringify({
          type: 'heartbeat',
          data: { timestamp: Date.now() }
        }));
        
        setStats(prev => ({
          ...prev,
          messagesSent: prev.messagesSent + 1
        }));
      }
      
      heartbeatTimeoutRef.current = setTimeout(sendHeartbeat, heartbeatInterval);
    };

    heartbeatTimeoutRef.current = setTimeout(sendHeartbeat, heartbeatInterval);
  }, [heartbeatInterval]);

  // Handle message
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      
      log('Received message', message);
      
      // Update stats
      setStats(prev => ({
        ...prev,
        messagesReceived: prev.messagesReceived + 1,
        lastMessageTime: new Date(),
        latency: message.type === 'heartbeat' ? Date.now() - lastPingTime.current : prev.latency
      }));
      
      // Update state
      setLastMessage(message);
      setMessageHistory(prev => {
        const newHistory = [...prev, message];
        // Keep only last 100 messages
        return newHistory.slice(-100);
      });
      
      // Call global handler
      onMessage?.(message);
      
      // Call specific handlers
      const handlers = messageHandlers.current.get(message.type);
      if (handlers) {
        handlers.forEach(handler => {
          try {
            handler(message.data);
          } catch (error) {
            console.error('Error in message handler:', error);
          }
        });
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
      setError(`Failed to parse message: ${error}`);
    }
  }, [onMessage, log]);

  // Handle connection open
  const handleOpen = useCallback(() => {
    log('WebSocket connected');
    setConnected(true);
    setConnecting(false);
    setError(null);
    reconnectAttempts.current = 0;
    
    setStats(prev => ({
      ...prev,
      connected: true,
      reconnectAttempts: 0
    }));
    
    startHeartbeat();
    onConnect?.();
    
    // Resubscribe to topics
    Array.from(subscriptions).forEach(topic => {
      ws.current?.send(JSON.stringify({
        type: 'subscribe',
        data: { topic }
      }));
    });
  }, [log, onConnect, startHeartbeat, subscriptions]);

  // Handle connection close
  const handleClose = useCallback((event: CloseEvent) => {
    log('WebSocket disconnected', { code: event.code, reason: event.reason });
    setConnected(false);
    setConnecting(false);
    
    setStats(prev => ({
      ...prev,
      connected: false
    }));
    
    clearHeartbeatTimeout();
    onDisconnect?.();
    
    // Auto-reconnect if not intentionally closed
    if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
      const timeout = Math.min(reconnectInterval * Math.pow(2, reconnectAttempts.current), 30000);
      
      log(`Reconnecting in ${timeout}ms (attempt ${reconnectAttempts.current + 1})`);
      
      reconnectTimeoutRef.current = setTimeout(() => {
        reconnectAttempts.current++;
        setStats(prev => ({
          ...prev,
          reconnectAttempts: reconnectAttempts.current
        }));
        connect();
      }, timeout);
    }
  }, [log, onDisconnect, clearHeartbeatTimeout, reconnectInterval, maxReconnectAttempts]);

  // Handle errors
  const handleError = useCallback((event: Event) => {
    log('WebSocket error', event);
    const errorMessage = `WebSocket error: ${event.type}`;
    setError(errorMessage);
    onError?.(event);
  }, [log, onError]);

  // Connect function
  const connect = useCallback(() => {
    if (connecting || connected) {
      return;
    }

    log('Connecting to WebSocket', { url, userId });
    setConnecting(true);
    setError(null);
    clearReconnectTimeout();

    try {
      const wsUrl = `${url}?user_id=${encodeURIComponent(userId)}`;
      ws.current = new WebSocket(wsUrl);
      
      ws.current.onopen = handleOpen;
      ws.current.onmessage = handleMessage;
      ws.current.onclose = handleClose;
      ws.current.onerror = handleError;
    } catch (error) {
      setError(`Failed to create WebSocket: ${error}`);
      setConnecting(false);
    }
  }, [
    connecting,
    connected,
    url,
    userId,
    log,
    clearReconnectTimeout,
    handleOpen,
    handleMessage,
    handleClose,
    handleError
  ]);

  // Disconnect function
  const disconnect = useCallback(() => {
    log('Disconnecting WebSocket');
    
    clearReconnectTimeout();
    clearHeartbeatTimeout();
    
    if (ws.current) {
      ws.current.close(1000, 'Intentional disconnect');
      ws.current = null;
    }
    
    setConnected(false);
    setConnecting(false);
    reconnectAttempts.current = 0;
  }, [log, clearReconnectTimeout, clearHeartbeatTimeout]);

  // Reconnect function
  const reconnect = useCallback(() => {
    disconnect();
    setTimeout(connect, 100);
  }, [disconnect, connect]);

  // Send message function
  const sendMessage = useCallback((message: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      const messageStr = JSON.stringify(message);
      ws.current.send(messageStr);
      
      log('Sent message', message);
      
      setStats(prev => ({
        ...prev,
        messagesSent: prev.messagesSent + 1
      }));
    } else {
      log('Cannot send message - WebSocket not connected');
      setError('Cannot send message - not connected');
    }
  }, [log]);

  // Subscribe function
  const subscribe = useCallback((topic: string) => {
    log('Subscribing to topic', topic);
    
    setSubscriptions(prev => new Set([...Array.from(prev), topic]));
    
    sendMessage({
      type: 'subscribe',
      data: { topic }
    });
  }, [log, sendMessage]);

  // Unsubscribe function
  const unsubscribe = useCallback((topic: string) => {
    log('Unsubscribing from topic', topic);
    
    setSubscriptions(prev => {
      const newSubs = new Set(prev);
      newSubs.delete(topic);
      return newSubs;
    });
    
    sendMessage({
      type: 'unsubscribe',
      data: { topic }
    });
  }, [log, sendMessage]);

  // Message handler registration
  const onMessageType = useCallback((type: string, handler: (data: any) => void) => {
    if (!messageHandlers.current.has(type)) {
      messageHandlers.current.set(type, new Set());
    }
    
    messageHandlers.current.get(type)!.add(handler);
    
    // Return cleanup function
    return () => {
      const handlers = messageHandlers.current.get(type);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          messageHandlers.current.delete(type);
        }
      }
    };
  }, []);

  // General message handler
  const onMessageHandler = useCallback((handler: (message: WebSocketMessage) => void) => {
    const wrappedHandler = (data: any) => {
      // For general message handler, we need to pass the full message
      // This will be called with the parsed message data
      handler(data as WebSocketMessage);
    };
    return onMessageType('*', wrappedHandler);
  }, [onMessageType]);

  // Specific message type handlers
  const onCrawlerStatus = useCallback((handler: (data: any) => void) => 
    onMessageType('crawler_status', handler), [onMessageType]);
  
  const onFlightUpdate = useCallback((handler: (data: any) => void) => 
    onMessageType('flight_update', handler), [onMessageType]);
  
  const onSystemMetrics = useCallback((handler: (data: any) => void) => 
    onMessageType('system_metrics', handler), [onMessageType]);
  
  const onErrorAlert = useCallback((handler: (data: any) => void) => 
    onMessageType('error_alert', handler), [onMessageType]);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }
    
    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearReconnectTimeout();
      clearHeartbeatTimeout();
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [clearReconnectTimeout, clearHeartbeatTimeout]);

  return {
    // Connection state
    connected,
    connecting,
    error,
    stats,
    
    // Connection control
    connect,
    disconnect,
    reconnect,
    
    // Messaging
    sendMessage,
    subscribe,
    unsubscribe,
    
    // Message handlers
    onMessage: onMessageHandler,
    onCrawlerStatus,
    onFlightUpdate,
    onSystemMetrics,
    onErrorAlert,
    
    // State
    subscriptions,
    lastMessage,
    messageHistory
  };
}; 