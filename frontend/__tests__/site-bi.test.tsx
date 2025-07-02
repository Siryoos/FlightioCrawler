import { render, screen } from '@testing-library/react';
import SiteBIMetrics from '../app/components/SiteBIMetrics';

test('renders business intelligence metrics', () => {
  const data = {
    site: 'demo',
    base_url: 'https://demo',
    url_accessible: true,
    http_status: 200,
    response_time: 0.1,
    circuit_breaker_open: false,
    rate_limited: false,
    error_count_last_hour: 1,
    success_count_last_hour: 5,
  };
  render(<SiteBIMetrics data={data} />);
  expect(screen.getByText('https://demo')).toBeInTheDocument();
  expect(screen.getByText('200')).toBeInTheDocument();
});
