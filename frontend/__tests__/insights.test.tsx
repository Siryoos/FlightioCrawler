import { render, screen, waitFor } from '@testing-library/react';
import ProviderInsightsPage from '../app/insights/page';

global.fetch = jest.fn(() =>
  Promise.resolve({ json: () => Promise.resolve({ insights: { flights: {}, tours: {}, hotels: {} } }) })
) as jest.Mock;

test('renders provider insights tabs', async () => {
  render(<ProviderInsightsPage />);
  await waitFor(() => expect(screen.getByText('Flights')).toBeInTheDocument());
  expect(screen.getByText('Tours')).toBeInTheDocument();
  expect(screen.getByText('Hotels')).toBeInTheDocument();
});
