import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import WalletTransactionsPage from '../app/finance/wallet/transactions/page';
import QueryProvider from '../app/components/QueryProvider';

beforeEach(() => {
  (global as any).fetch = jest.fn(() =>
    Promise.resolve({
      json: () => Promise.resolve({
        transactions: [
          { id: '1', amount: 1000, type: 'deposit', created_at: '2024-01-01T00:00:00' }
        ]
      })
    })
  ) as jest.Mock;
});

test('renders transactions after filtering', async () => {
  render(
    <QueryProvider>
      <WalletTransactionsPage />
    </QueryProvider>
  );
  fireEvent.click(screen.getByText('فیلتر'));
  await waitFor(() => screen.getByTestId('transactions-table'));
  expect(screen.getByText('1')).toBeInTheDocument();
  expect(screen.getByText('1000')).toBeInTheDocument();
});
