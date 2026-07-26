import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://guildless.dev"),
  title: "GUILDLESS — Built by an AI company",
  description: "See how Kimi, Claude, and Codex shipped and independently verified a playable iOS game.",
  icons: { icon: "/guildless-icon.png", shortcut: "/guildless-icon.png", apple: "/guildless-icon.png" },
  openGraph: {
    title: "GUILDLESS — Built by an AI company",
    description: "34 tests. Two rejected reviews. One independently verified iOS game.",
    images: [{ url: "/og.png", width: 1536, height: 1024, alt: "GUILDLESS NEON DRIFT production evidence" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "GUILDLESS — Built by an AI company",
    description: "Kimi designed it. Claude built it. Codex rejected it twice, then passed it.",
    images: ["/og.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className={`${geistSans.variable} ${geistMono.variable}`}>{children}</body></html>;
}
