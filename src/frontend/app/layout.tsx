import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "WebGIS Simulasi Evakuasi Tsunami",
  description: "Mini Project Komputasi Geospasial - Simulasi Gelombang & Zona Inundasi",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="id"
      className={`${geistSans.variable} ${geistMono.variable} h-full w-full`}
      style={{ margin: 0, padding: 0 }}
    >
      <body style={{ 
        margin: 0, 
        padding: 0, 
        height: '100vh', 
        width: '100vw',
        overflow: 'hidden'
      }}>
        {children}
      </body>
    </html>
  );
}
