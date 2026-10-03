import type { Metadata } from "next";
import NavLinks from "@/components/NavLinks";
import "./globals.css";

export const metadata: Metadata = {
  title: "מחירון — כמה עולה אותו סל בכל רשת",
  description: "השוואה יומית של מחירי מדף ומבצעים ברשתות השיווק, מתוך קובצי חוק שקיפות המחירים.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700;800&family=Unbounded:wght@500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="glow" aria-hidden />
        <a className="skip" href="#main">דילוג לתוכן</a>
        <header className="topbar">
          <div className="wrap topbar-inner">
            <a href="/" className="brand" aria-label="מחירון — דף הבית">
              <span className="brand-mark" aria-hidden>₪</span>
              <span className="brand-name">מחירון</span>
            </a>
            <NavLinks />
          </div>
        </header>
        <main id="main" className="wrap">{children}</main>
        <footer className="footer">
          <div className="wrap">
            הנתונים מקובצי חוק הגנת הצרכן (שקיפות מחירים) שהרשתות מפרסמות כל יום. מחירי מבצע מחושבים ליחידה ועשויים
            להיות מקורבים. נבנה על ידי מועתסם ח׳ליפה ·{" "}
            <a href={process.env.NEXT_PUBLIC_GITHUB_URL ?? "#"}>קוד המקור ב-GitHub</a>
          </div>
        </footer>
      </body>
    </html>
  );
}
