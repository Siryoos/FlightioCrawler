import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import SitesIndex from '../app/sites/page';

beforeEach(() => {
  (global as any).fetch = jest.fn(() =>
    Promise.resolve({ json: () => Promise.resolve({ sites: { demo: { enabled: false } } }) })
  ) as jest.Mock;
});

test('renders start crawling button for provider', async () => {
  render(<SitesIndex />);
  await waitFor(() => screen.getByText('demo'));
  expect(screen.getByText('شروع')).toBeInTheDocument();
});

test('toggles crawling state', async () => {
  render(<SitesIndex />);
  await waitFor(() => screen.getByText('demo'));
  fireEvent.click(screen.getByText('شروع'));
  expect((global.fetch as jest.Mock).mock.calls[1][0]).toBe('/api/v1/sites/demo/enable');
});
