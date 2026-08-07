import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";

import appCss from "../styles.css?url";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0b0911] px-4 text-white">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold">404</h1>
        <h2 className="mt-4 text-xl font-semibold">Halaman tidak ditemukan</h2>
        <p className="mt-2 text-sm text-white/55">Mirei menunggumu di halaman utama.</p>
        <div className="mt-6">
          <Link to="/" className="inline-flex min-h-12 items-center justify-center rounded-xl bg-pink-300 px-5 py-3 text-sm font-medium text-[#281426] transition hover:bg-pink-200">
            Kembali ke Mirei
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
    <div className="flex min-h-screen items-center justify-center bg-[#0b0911] px-4 text-white">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight">Mirei tidak dapat dimuat</h1>
        <p className="mt-2 text-sm leading-relaxed text-white/60">Renderer atau koneksi mengalami masalah. Muat ulang antarmuka untuk mencoba lagi.</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex min-h-12 items-center justify-center rounded-xl bg-pink-300 px-5 py-3 text-sm font-medium text-[#281426] transition hover:bg-pink-200"
          >
            Coba lagi
          </button>
          <a href="/" className="inline-flex min-h-12 items-center justify-center rounded-xl border border-white/15 bg-white/5 px-5 py-3 text-sm font-medium text-white transition hover:bg-white/10">
            Kembali
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
      {
        name: "viewport",
        content: "width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content",
      },
      { title: "Mirei — Virtual Companion" },
      {
        name: "description",
        content: "Original Japanese-speaking virtual companion with switchable VRM 3D and Inochi2D renderers, contextual animation, voice, touch reactions, and local memory.",
      },
      { name: "theme-color", content: "#0b0911" },
      { name: "color-scheme", content: "dark" },
      { name: "mobile-web-app-capable", content: "yes" },
      { name: "apple-mobile-web-app-capable", content: "yes" },
      { name: "apple-mobile-web-app-status-bar-style", content: "black-translucent" },
      { name: "apple-mobile-web-app-title", content: "Mirei" },
      { property: "og:title", content: "Mirei — Virtual Companion" },
      {
        property: "og:description",
        content: "An original Japanese-speaking virtual companion with switchable 3D and 2D character engines.",
      },
      { property: "og:type", content: "website" },
      { property: "og:image", content: "/icon-512.png" },
      { name: "twitter:card", content: "summary" },
      { name: "twitter:title", content: "Mirei — Virtual Companion" },
      {
        name: "twitter:description",
        content: "Interactive Japanese-speaking companion with VRM 3D, Inochi2D, voice and contextual reactions.",
      },
      { name: "twitter:image", content: "/icon-512.png" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "stylesheet", href: "/mirei-polish.css?v=ux3" },
      { rel: "stylesheet", href: "/mirei-final.css?v=ux3" },
      { rel: "preconnect", href: "https://cdn.jsdelivr.net", crossOrigin: "anonymous" },
      { rel: "dns-prefetch", href: "https://aihorde.net" },
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
    <html lang="ja">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <script src="/mirei-cleanup.js?v=ux3" defer />
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  return (
    <QueryClientProvider client={queryClient}>
      <Outlet />
    </QueryClientProvider>
  );
}
