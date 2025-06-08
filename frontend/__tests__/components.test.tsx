import { render, screen, fireEvent } from '@testing-library/react';
import MultiCitySearch from '../app/components/MultiCitySearch';
import PriceComparisonGrid from '../app/components/PriceComparisonGrid';
import CrawledDataGrid from '../app/components/CrawledDataGrid';

test('renders multi city search button', () => {
  const fn = jest.fn();
  render(<MultiCitySearch onSearch={fn} />);
  expect(screen.getByText('مسیر جدید')).toBeInTheDocument();
});

test('renders price grid rows', () => {
  render(<PriceComparisonGrid rows={[{ site: 'demo', price: 1000000 }]} />);
  expect(screen.getByText('demo')).toBeInTheDocument();
});

test('renders crawled data grid', () => {
  const flights = [
    { flight_id: '1', flight_number: 'FN1', origin: 'THR', destination: 'ISF', departure_time: '2024-01-01T00:00:00', price: 123 },
  ];
  render(<CrawledDataGrid flights={flights} />);
  expect(screen.getByText('FN1')).toBeInTheDocument();
});
