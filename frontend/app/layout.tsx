import type { Metadata } from "next";
import type { ReactNode } from "react";

import { BookHeader } from "@/components/BookHeader";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Recetario · de TikTok a tu libro de cocina",
    template: "%s · Recetario",
  },
  description:
    "Convierte videos de TikTok en recetas estructuradas, edítalas y guárdalas en un recetario con forma de libro.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen font-sans antialiased">
        <BookHeader />
        <main className="mx-auto w-full max-w-6xl px-4 pb-20 pt-8 sm:px-6">
          {children}
        </main>
        <footer className="no-print mx-auto w-full max-w-6xl px-4 pb-8 text-xs text-paper/45 sm:px-6">
          <p>
            Recetario personal · las recetas citan siempre a su autor y a la
            fuente original.
          </p>
        </footer>
      </body>
    </html>
  );
}
