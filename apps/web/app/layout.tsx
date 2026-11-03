import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "DROPSpy Radar · Ad intelligence",
  description: "Discover product signals from transparent ad research.",
};
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
