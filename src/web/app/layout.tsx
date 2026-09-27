import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "ORBIT — NOVA INK Studios",
  description: "Multi-agent studio experiment",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
