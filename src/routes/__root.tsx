import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { FurinaCloudBackupCard } from "@/components/FurinaCloudBackupCard";
import { FurinaDeviceEvidenceAgent } from "@/components/FurinaDeviceEvidenceAgent";

import appCss from "../styles.css?url";

const CLOUD_VOICE_DISCLOSURE_KEY = "furina:privacy:cloud-voice-v1";

function NativeCloudVoiceDisclosure() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!navigator.userAgent.includes("FurinaAndroid/")) return;
    if (window.localStorage.getItem(CLOUD_VOICE_DISCLOSURE_KEY) === "acknowledged") return;
    setOpen(true);
  }, []);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-end justify-center bg-black/70 p-4 sm:items-center" role="dialog" aria-modal="true" aria-labelledby="cloud-voice-privacy-title">
      <div className="w-full max-w-lg rounded-3xl border border-white/10 bg-[#0b0b14] p-5 text-white shadow-2xl">
        <h2 id="cloud-voice-privacy-title" className="text-lg font-semibold">Privasi suara Furina</h2>
        <p className="mt-3 text-sm leading-6 text-white/75">
          Chat dengan model lokal tetap diproses di perangkat. Fitur suara cloud bersifat opsional dan terpisah dari AI lokal.
        </p>
        <p className="mt-2 text-sm leading-6 text-white/75">
          Jika fitur suara cloud digunakan, teks dapat dikirim ke layanan terjemahan dan VOICEVOX, sedangkan sampel suara untuk voice clone dapat diunggah ke layanan pemrosesan eksternal. Jangan kirim sampel suara yang sensitif jika kamu tidak ingin data tersebut keluar dari perangkat.
        </p>
        <button
          type="button"
          className="mt-5 min-h-11 w-full rounded-2xl bg-white px-4 py-2.5 text-sm font-semibold text-black"
          onClick={() => {
            window.localStorage.setItem(CLOUD_VOICE_DISCLOSURE_KEY, "acknowledged");
            setOpen(false);
          }}
        >
          Mengerti
        </button>
      </div>
    </div>
  );
}

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing or head back home.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1, viewport-fit=cover" },
      { title: "Furina — AI Companion" },
      { name: "description", content: "Personal anime AI companion with natural Japanese voice, memory, and a customizable Furina character." },
      { name: "theme-color", content: "#0b0b14" },
      { name: "mobile-web-app-capable", content: "yes" },
      { name: "apple-mobile-web-app-capable", content: "yes" },
      { name: "apple-mobile-web-app-status-bar-style", content: "black-translucent" },
      { name: "apple-mobile-web-app-title", content: "Furina" },
      { property: "og:title", content: "Furina — AI Companion" },
      { property: "og:description", content: "Personal AI companion with voice, memory, and Furina personality." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "manifest", href: "/manifest.webmanifest" },
      { rel: "icon", type: "image/png", sizes: "192x192", href: "/icon-192.png" },
      { rel: "icon", type: "image/png", sizes: "512x512", href: "/icon-512.png" },
      { rel: "apple-touch-icon", sizes: "192x192", href: "/icon-192.png" },
      { rel: "apple-touch-icon", sizes: "512x512", href: "/icon-512.png" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
      <Outlet />
      <FurinaCloudBackupCard />
      <FurinaDeviceEvidenceAgent />
      <NativeCloudVoiceDisclosure />
    </QueryClientProvider>
  );
}
