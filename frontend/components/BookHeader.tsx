"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { BookIcon, ImportIcon, PlusIcon } from "@/components/Icons";

const links = [
  { href: "/", label: "Estantería", icon: BookIcon },
  { href: "/nueva", label: "Nueva receta", icon: PlusIcon },
  { href: "/importar", label: "Importar video", icon: ImportIcon },
];

export function BookHeader() {
  const pathname = usePathname();

  return (
    <header className="no-print sticky top-0 z-40 border-b border-white/10 bg-desk/85 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link
          href="/"
          className="group flex items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-gold"
        >
          <span className="flex h-10 w-10 items-center justify-center rounded-full border border-gold/50 bg-gradient-to-br from-gold/30 to-wine/30 text-gold-soft shadow-inner">
            <BookIcon width={20} height={20} />
          </span>
          <span className="leading-tight">
            <span className="block font-serif text-xl tracking-wide text-paper">
              Recetario
            </span>
            <span className="block text-[0.66rem] uppercase tracking-[0.28em] text-gold-soft/80">
              con IA
            </span>
          </span>
        </Link>

        <nav aria-label="Principal" className="flex items-center gap-1 sm:gap-2">
          {links.map((link) => {
            const active =
              link.href === "/"
                ? pathname === "/"
                : pathname.startsWith(link.href);
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium transition sm:px-4 sm:text-sm ${
                  active
                    ? "border-gold/60 bg-gold/15 text-gold-soft"
                    : "border-transparent text-paper/70 hover:border-white/15 hover:bg-white/5 hover:text-paper"
                }`}
              >
                <Icon width={16} height={16} />
                <span className="hidden sm:inline">{link.label}</span>
                <span className="sr-only sm:hidden">{link.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
