import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import SidebarLayout from "@/components/layout/SidebarLayout";
import { StoreProvider } from "@/store/StoreProvider";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "My App",
  description: "Next.js app with sidebar navigation",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="flex h-full">
        <StoreProvider>
          <SidebarLayout>{children}</SidebarLayout>
        </StoreProvider>
      </body>
    </html>
  );
}
