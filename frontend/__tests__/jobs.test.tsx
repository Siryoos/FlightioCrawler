import { render, screen } from '@testing-library/react';
import CrawlJobPage from '../app/jobs/page';

test('renders crawl job inputs', () => {
  render(<CrawlJobPage />);
  expect(screen.getByPlaceholderText('مبدا')).toBeInTheDocument();
  expect(screen.getByPlaceholderText('مقصد')).toBeInTheDocument();
});
