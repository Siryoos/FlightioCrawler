import { render, screen } from '@testing-library/react';
import RootLayout from '../app/layout';

// minimal wrapper to satisfy Next.js metadata usage
function Wrapper() {
  return (
    <RootLayout>
      <div />
    </RootLayout>
  );
}

test('navigation includes link to sites', () => {
  render(<Wrapper />);
  expect(screen.getByText('\u0633\u0627\u06cc\u062a\u200c\u0647\u0627')).toBeInTheDocument();
  expect(screen.getByText('\u0628\u06cc\u0646\u0634\u200c\u0647\u0627')).toBeInTheDocument();
  expect(screen.getByText('\u06a9\u0631\u0648\u0644 \u062c\u062f\u06cc\u062f')).toBeInTheDocument();
});
