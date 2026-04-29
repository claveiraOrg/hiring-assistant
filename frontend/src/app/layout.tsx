import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "hirematch — AI Hiring Assistant",
  description: "Intelligent candidate ranking and matching",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
