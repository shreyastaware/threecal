import type { Metadata } from "next";
import { Cormorant_Garamond, Geist } from "next/font/google";

import { AppProviders } from "@/components/providers/app-providers";

import "./globals.css";
import { cn } from "@/lib/utils";

const display = Cormorant_Garamond({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600"],
  style: ["normal", "italic"],
});

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

export const metadata: Metadata = {
  title: "Threecal - Sell your expertise",
  description: "Turn your expertise and availability into one considered link.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={cn(display.variable, "font-sans", geist.variable)}>
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
