import { render, screen, fireEvent } from '@testing-library/react';
import MultiCitySearch from '../app/components/MultiCitySearch';
import PriceComparisonGrid from '../app/components/PriceComparisonGrid';

test('renders multi city search button', () => {
  const fn = jest.fn();
  render(<MultiCitySearch onSearch={fn} />);
  expect(screen.getByText('مسیر جدید')).toBeInTheDocument();
});

test('renders price grid rows', () => {
  render(<PriceComparisonGrid rows={[{ site: 'demo', price: 1000000 }]} />);
  expect(screen.getByText('demo')).toBeInTheDocument();
});
