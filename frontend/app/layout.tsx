import './globals.css';
export const metadata = { title: 'YOSHA AI STUDIO', description: 'AI-powered creative production studio' };
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="ar" dir="rtl"><body>{children}</body></html>;
}
