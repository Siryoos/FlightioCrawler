'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useRouter } from 'next/navigation';

// Error types and interfaces
interface ErrorInfo {
  id: string;
  type: ErrorType;
  severity: ErrorSeverity;
  title: string;
  message: string;
  timestamp: Date;
  context?: Record<string, any>;
  retryable: boolean;
  retryCount: number;
  maxRetries: number;
  autoRetryDelay?: number;
  onRetry?: () => Promise<void> | void;
  onDismiss?: () => void;
  actionLabel?: string;
  actionHandler?: () => void;
  persistent?: boolean;
}

enum ErrorType {
  NETWORK = 'network',
  API = 'api',
  VALIDATION = 'validation',
  AUTHENTICATION = 'authentication',
  AUTHORIZATION = 'authorization',
  OFFLINE = 'offline',
  TIMEOUT = 'timeout',
  UNKNOWN = 'unknown',
  CRAWLER = 'crawler',
  WEBSOCKET = 'websocket'
}

enum ErrorSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

interface ErrorHandlerContextType {
  errors: ErrorInfo[];
  isOffline: boolean;
  showError: (error: Partial<ErrorInfo>) => string;
  hideError: (id: string) => void;
  clearErrors: () => void;
  retryError: (id: string) => Promise<void>;
  handleError: (error: Error, context?: Record<string, any>) => string;
  createNetworkError: (message: string, retryFn?: () => Promise<void>) => string;
  createValidationError: (message: string, context?: Record<string, any>) => string;
  createOfflineError: () => string;
}

// Error context
const ErrorHandlerContext = createContext<ErrorHandlerContextType | null>(null);

// Custom hook to use error handler
export const useErrorHandler = () => {
  const context = useContext(ErrorHandlerContext);
  if (!context) {
    throw new Error('useErrorHandler must be used within an ErrorHandlerProvider');
  }
  return context;
};

// Error classification utility
class ErrorClassifier {
  static classifyError(error: Error | any): { type: ErrorType; severity: ErrorSeverity; retryable: boolean } {
    // Network errors
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      return { type: ErrorType.NETWORK, severity: ErrorSeverity.MEDIUM, retryable: true };
    }
    
    if (error.name === 'AbortError' || error.message.includes('timeout')) {
      return { type: ErrorType.TIMEOUT, severity: ErrorSeverity.MEDIUM, retryable: true };
    }

    // API errors based on status code
    if (error.status) {
      if (error.status === 401) {
        return { type: ErrorType.AUTHENTICATION, severity: ErrorSeverity.HIGH, retryable: false };
      }
      if (error.status === 403) {
        return { type: ErrorType.AUTHORIZATION, severity: ErrorSeverity.HIGH, retryable: false };
      }
      if (error.status >= 400 && error.status < 500) {
        return { type: ErrorType.VALIDATION, severity: ErrorSeverity.MEDIUM, retryable: false };
      }
      if (error.status >= 500) {
        return { type: ErrorType.API, severity: ErrorSeverity.HIGH, retryable: true };
      }
    }

    // WebSocket errors
    if (error.message && error.message.includes('WebSocket')) {
      return { type: ErrorType.WEBSOCKET, severity: ErrorSeverity.MEDIUM, retryable: true };
    }

    // Crawler-specific errors
    if (error.message && (error.message.includes('crawl') || error.message.includes('scrape'))) {
      return { type: ErrorType.CRAWLER, severity: ErrorSeverity.MEDIUM, retryable: true };
    }

    // Default
    return { type: ErrorType.UNKNOWN, severity: ErrorSeverity.MEDIUM, retryable: false };
  }

  static getFriendlyMessage(error: Error | any, type: ErrorType): string {
    const baseMessages = {
      [ErrorType.NETWORK]: 'اتصال به اینترنت را بررسی کنید',
      [ErrorType.API]: 'خطا در سرور - لطفاً دوباره تلاش کنید',
      [ErrorType.VALIDATION]: 'اطلاعات وارد شده صحیح نیست',
      [ErrorType.AUTHENTICATION]: 'لطفاً دوباره وارد شوید',
      [ErrorType.AUTHORIZATION]: 'شما دسترسی لازم را ندارید',
      [ErrorType.OFFLINE]: 'اتصال اینترنت برقرار نیست',
      [ErrorType.TIMEOUT]: 'زمان درخواست تمام شد',
      [ErrorType.CRAWLER]: 'خطا در دریافت اطلاعات پرواز',
      [ErrorType.WEBSOCKET]: 'خطا در اتصال بلادرنگ',
      [ErrorType.UNKNOWN]: 'خطای غیرمنتظره‌ای رخ داد'
    };

    return baseMessages[type] || baseMessages[ErrorType.UNKNOWN];
  }

  static getRetryDelay(retryCount: number, type: ErrorType): number {
    const baseDelays = {
      [ErrorType.NETWORK]: 2000,
      [ErrorType.API]: 1000,
      [ErrorType.VALIDATION]: 500,
      [ErrorType.AUTHENTICATION]: 2000,
      [ErrorType.AUTHORIZATION]: 2000,
      [ErrorType.OFFLINE]: 5000,
      [ErrorType.TIMEOUT]: 3000,
      [ErrorType.WEBSOCKET]: 1000,
      [ErrorType.CRAWLER]: 5000,
      [ErrorType.UNKNOWN]: 2000
    };

    const baseDelay = baseDelays[type] || 2000;
    return Math.min(baseDelay * Math.pow(2, retryCount), 30000); // Max 30 seconds
  }
}

// Error Handler Provider Component
interface ErrorHandlerProviderProps {
  children: ReactNode;
  maxErrors?: number;
  enableOfflineDetection?: boolean;
  enableAutoRetry?: boolean;
}

export const ErrorHandlerProvider: React.FC<ErrorHandlerProviderProps> = ({
  children,
  maxErrors = 10,
  enableOfflineDetection = true,
  enableAutoRetry = true
}) => {
  const [errors, setErrors] = useState<ErrorInfo[]>([]);
  const [isOffline, setIsOffline] = useState(false);
  const router = useRouter();

  // Offline detection
  useEffect(() => {
    if (!enableOfflineDetection) return;

    const handleOnline = () => {
      setIsOffline(false);
      
      // Auto-retry failed requests when coming back online
      if (enableAutoRetry) {
        const retryableErrors = errors.filter(e => e.retryable && e.type === ErrorType.NETWORK);
        retryableErrors.forEach(error => {
          if (error.onRetry) {
            setTimeout(() => retryError(error.id), 1000);
          }
        });
      }
    };

    const handleOffline = () => {
      setIsOffline(true);
      showError({
        type: ErrorType.OFFLINE,
        severity: ErrorSeverity.HIGH,
        title: 'اتصال قطع شد',
        message: 'اتصال اینترنت برقرار نیست',
        retryable: false,
        persistent: true
      });
    };

    // Initial check
    setIsOffline(!navigator.onLine);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [enableOfflineDetection, enableAutoRetry, errors]);

  // Generate unique error ID
  const generateErrorId = () => `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

  // Show error function
  const showError = useCallback((errorData: Partial<ErrorInfo>): string => {
    const id = errorData.id || generateErrorId();
    
    const error: ErrorInfo = {
      id,
      type: errorData.type || ErrorType.UNKNOWN,
      severity: errorData.severity || ErrorSeverity.MEDIUM,
      title: errorData.title || 'خطا',
      message: errorData.message || 'خطای غیرمنتظره‌ای رخ داد',
      timestamp: new Date(),
      context: errorData.context,
      retryable: errorData.retryable ?? false,
      retryCount: errorData.retryCount || 0,
      maxRetries: errorData.maxRetries || 3,
      autoRetryDelay: errorData.autoRetryDelay,
      onRetry: errorData.onRetry,
      onDismiss: errorData.onDismiss,
      actionLabel: errorData.actionLabel,
      actionHandler: errorData.actionHandler,
      persistent: errorData.persistent || false
    };

    setErrors(prev => {
      // Remove oldest errors if max limit reached
      const newErrors = [...prev, error];
      if (newErrors.length > maxErrors) {
        return newErrors.slice(-maxErrors);
      }
      return newErrors;
    });

    // Auto-retry if enabled and retryable
    if (enableAutoRetry && error.retryable && error.onRetry && error.autoRetryDelay) {
      setTimeout(() => {
        retryError(id);
      }, error.autoRetryDelay);
    }

    // Auto-dismiss non-persistent errors after delay
    if (!error.persistent) {
      const dismissDelay = error.severity === ErrorSeverity.CRITICAL ? 10000 : 5000;
      setTimeout(() => {
        hideError(id);
      }, dismissDelay);
    }

    return id;
  }, [maxErrors, enableAutoRetry]);

  // Hide error function
  const hideError = useCallback((id: string) => {
    setErrors(prev => {
      const error = prev.find(e => e.id === id);
      if (error?.onDismiss) {
        error.onDismiss();
      }
      return prev.filter(e => e.id !== id);
    });
  }, []);

  // Clear all errors
  const clearErrors = useCallback(() => {
    setErrors([]);
  }, []);

  // Retry error function
  const retryError = useCallback(async (id: string) => {
    const error = errors.find(e => e.id === id);
    if (!error || !error.retryable || !error.onRetry) return;

    if (error.retryCount >= error.maxRetries) {
      // Max retries reached, update error
      setErrors(prev => prev.map(e => 
        e.id === id 
          ? { ...e, retryable: false, message: `${e.message} (حداکثر تلاش انجام شد)` }
          : e
      ));
      return;
    }

    try {
      // Update retry count
      setErrors(prev => prev.map(e => 
        e.id === id ? { ...e, retryCount: e.retryCount + 1 } : e
      ));

      await error.onRetry();
      
      // Success - remove error
      hideError(id);
    } catch (retryErr) {
      // Retry failed, schedule next retry
      const delay = ErrorClassifier.getRetryDelay(error.retryCount, error.type);
      
      setErrors(prev => prev.map(e => 
        e.id === id 
          ? { 
              ...e, 
              message: `${error.message} (تلاش ${error.retryCount + 1})`,
              autoRetryDelay: delay
            }
          : e
      ));

      if (enableAutoRetry && error.retryCount + 1 < error.maxRetries) {
        setTimeout(() => retryError(id), delay);
      }
    }
  }, [errors, hideError, enableAutoRetry]);

  // Handle generic error
  const handleError = useCallback((error: Error | any, context?: Record<string, any>): string => {
    const { type, severity, retryable } = ErrorClassifier.classifyError(error);
    const friendlyMessage = ErrorClassifier.getFriendlyMessage(error, type);

    return showError({
      type,
      severity,
      title: 'خطا',
      message: friendlyMessage,
      retryable,
      context: {
        ...context,
        originalError: error.message,
        stack: error.stack
      }
    });
  }, [showError]);

  // Create specific error types
  const createNetworkError = useCallback((message: string, retryFn?: () => Promise<void>): string => {
    return showError({
      type: ErrorType.NETWORK,
      severity: ErrorSeverity.MEDIUM,
      title: 'خطای اتصال',
      message,
      retryable: !!retryFn,
      onRetry: retryFn,
      autoRetryDelay: retryFn ? 2000 : undefined
    });
  }, [showError]);

  const createValidationError = useCallback((message: string, context?: Record<string, any>): string => {
    return showError({
      type: ErrorType.VALIDATION,
      severity: ErrorSeverity.MEDIUM,
      title: 'خطای اعتبارسنجی',
      message,
      retryable: false,
      context
    });
  }, [showError]);

  const createOfflineError = useCallback((): string => {
    return showError({
      type: ErrorType.OFFLINE,
      severity: ErrorSeverity.HIGH,
      title: 'اتصال قطع شد',
      message: 'اتصال اینترنت را بررسی کنید',
      retryable: false,
      persistent: true
    });
  }, [showError]);

  const contextValue: ErrorHandlerContextType = {
    errors,
    isOffline,
    showError,
    hideError,
    clearErrors,
    retryError,
    handleError,
    createNetworkError,
    createValidationError,
    createOfflineError
  };

  return (
    <ErrorHandlerContext.Provider value={contextValue}>
      {children}
      <ErrorToastContainer />
    </ErrorHandlerContext.Provider>
  );
};

// Error Toast Container Component
const ErrorToastContainer: React.FC = () => {
  const { errors, hideError, retryError } = useErrorHandler();

  const getSeverityStyles = (severity: ErrorSeverity): string => {
    const styles = {
      [ErrorSeverity.LOW]: 'bg-blue-50 border-blue-200 text-blue-800',
      [ErrorSeverity.MEDIUM]: 'bg-yellow-50 border-yellow-200 text-yellow-800',
      [ErrorSeverity.HIGH]: 'bg-orange-50 border-orange-200 text-orange-800',
      [ErrorSeverity.CRITICAL]: 'bg-red-50 border-red-200 text-red-800'
    };
    return styles[severity];
  };

  const getSeverityIcon = (severity: ErrorSeverity): string => {
    const icons = {
      [ErrorSeverity.LOW]: '💡',
      [ErrorSeverity.MEDIUM]: '⚠️',
      [ErrorSeverity.HIGH]: '🚨',
      [ErrorSeverity.CRITICAL]: '🔴'
    };
    return icons[severity];
  };

  return (
    <div className="fixed top-4 left-4 z-50 space-y-3 max-w-md">
      {errors.map((error) => (
        <div
          key={error.id}
          className={`p-4 rounded-lg border shadow-lg transition-all duration-300 ${getSeverityStyles(error.severity)}`}
          role="alert"
        >
          <div className="flex items-start space-x-3 rtl:space-x-reverse">
            <span className="text-lg">{getSeverityIcon(error.severity)}</span>
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-semibold">{error.title}</h4>
              <p className="text-sm mt-1">{error.message}</p>
              
              {error.retryable && (
                <div className="mt-2 text-xs opacity-75">
                  تلاش {error.retryCount} از {error.maxRetries}
                </div>
              )}
              
              <div className="flex items-center space-x-2 rtl:space-x-reverse mt-3">
                {error.retryable && (
                  <button
                    onClick={() => retryError(error.id)}
                    className="text-xs px-2 py-1 bg-white bg-opacity-50 rounded hover:bg-opacity-75 transition-colors"
                  >
                    تلاش مجدد
                  </button>
                )}
                
                {error.actionLabel && error.actionHandler && (
                  <button
                    onClick={error.actionHandler}
                    className="text-xs px-2 py-1 bg-white bg-opacity-50 rounded hover:bg-opacity-75 transition-colors"
                  >
                    {error.actionLabel}
                  </button>
                )}
                
                <button
                  onClick={() => hideError(error.id)}
                  className="text-xs px-2 py-1 bg-white bg-opacity-50 rounded hover:bg-opacity-75 transition-colors"
                >
                  بستن
                </button>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// Higher-order component for error boundaries
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

export class EnhancedErrorBoundary extends React.Component<
  { children: ReactNode; fallback?: React.ComponentType<{ error: Error; retry: () => void }> },
  ErrorBoundaryState
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error, errorInfo: null };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ errorInfo });
    
    // Log error to monitoring service
    console.error('Error boundary caught error:', error, errorInfo);
  }

  retry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      const FallbackComponent = this.props.fallback || DefaultErrorFallback;
      return <FallbackComponent error={this.state.error!} retry={this.retry} />;
    }

    return this.props.children;
  }
}

// Default error fallback component
const DefaultErrorFallback: React.FC<{ error: Error; retry: () => void }> = ({ error, retry }) => (
  <div className="min-h-screen flex items-center justify-center bg-gray-50">
    <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6 text-center">
      <div className="text-6xl mb-4">😵</div>
      <h1 className="text-xl font-bold text-gray-900 mb-2">مشکلی پیش آمده</h1>
      <p className="text-gray-600 mb-4">
        متأسفانه خطای غیرمنتظره‌ای رخ داده است
      </p>
      <button
        onClick={retry}
        className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors"
      >
        تلاش مجدد
      </button>
      {process.env.NODE_ENV === 'development' && (
        <details className="mt-4 text-left">
          <summary className="cursor-pointer text-sm text-gray-500">جزئیات خطا</summary>
          <pre className="mt-2 text-xs text-red-600 whitespace-pre-wrap">
            {error.message}
            {error.stack}
          </pre>
        </details>
      )}
    </div>
  </div>
);

// API wrapper with error handling
export const createApiWrapper = (baseUrl: string = '/api') => {
  const handleApiError = (error: any): never => {
    const errorHandler = useErrorHandler();
    errorHandler.handleError(error);
    throw error;
  };

  const apiRequest = async (
    endpoint: string,
    options: RequestInit = {},
    retryCount = 0
  ): Promise<Response> => {
    const url = `${baseUrl}${endpoint}`;
    const controller = new AbortController();
    
    // Set timeout
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        }
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }
      
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      
      // Implement retry logic for certain errors
      if (retryCount < 3 && (
        error instanceof TypeError && error.message.includes('fetch') ||
        (error as any).name === 'AbortError'
      )) {
        const delay = Math.pow(2, retryCount) * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
        return apiRequest(endpoint, options, retryCount + 1);
      }
      
      throw error;
    }
  };

  return {
    get: (endpoint: string, options?: RequestInit) => 
      apiRequest(endpoint, { ...options, method: 'GET' }),
    
    post: (endpoint: string, data?: any, options?: RequestInit) =>
      apiRequest(endpoint, {
        ...options,
        method: 'POST',
        body: data ? JSON.stringify(data) : undefined
      }),
    
    put: (endpoint: string, data?: any, options?: RequestInit) =>
      apiRequest(endpoint, {
        ...options,
        method: 'PUT',
        body: data ? JSON.stringify(data) : undefined
      }),
    
    delete: (endpoint: string, options?: RequestInit) =>
      apiRequest(endpoint, { ...options, method: 'DELETE' })
  };
};

// Export error types for use in other components
export { ErrorType, ErrorSeverity };
export type { ErrorInfo }; 