import type { Metadata } from 'next';
import '@fontsource-variable/geist';
import './globals.css';

export const metadata: Metadata = {
  title: 'ShiftPilot · Your week, in order',
  description: 'Build a weekly roster, review coverage, and repair shifts with less disruption.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
