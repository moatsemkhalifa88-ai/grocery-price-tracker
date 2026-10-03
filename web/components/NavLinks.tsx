"use client";

import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "סקירה" },
  { href: "/search", label: "חיפוש מוצר" },
  { href: "/stores", label: "סניפים" },
  { href: "/changes", label: "שינויי מחיר" },
  { href: "/about", label: "איך זה עובד" },
];

export default function NavLinks() {
  const path = usePathname() ?? "/";
  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href) || (href === "/search" && path.startsWith("/product")));
  return (
    <nav className="nav" aria-label="ניווט ראשי">
      {NAV.map((n) => (
        <a key={n.href} href={n.href} aria-current={isActive(n.href) ? "page" : undefined}>
          {n.label}
        </a>
      ))}
    </nav>
  );
}
