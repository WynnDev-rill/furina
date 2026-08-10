import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { backupSupabase } from "@/integrations/supabase/backup-client";

export const Route = createFileRoute("/backup-auth")({
  head: () => ({ meta: [{ title: "Furina — Google Backup" }] }),
  component: BackupAuthPage,
});

function BackupAuthPage() {
  const [message, setMessage] = useState("Menyelesaikan login Google…");
  const [deepLink, setDeepLink] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const native = params.get("native") === "1";
    const code = params.get("code") || "";
    const error = params.get("error") || "";
    const errorDescription = params.get("error_description") || "";

    if (native) {
      const query = new URLSearchParams();
      if (code) query.set("code", code);
      if (error) query.set("error", error);
      if (errorDescription) query.set("error_description", errorDescription);
      const deep = `com.wynndev.furina://auth/callback?${query.toString()}`;
      const intent = `intent://auth/callback?${query.toString()}#Intent;scheme=com.wynndev.furina;package=com.wynndev.furina;end`;
      setDeepLink(deep);
      setMessage(error ? (errorDescription || error) : "Login berhasil. Mengembalikanmu ke Furina…");
      const timer = window.setTimeout(() => window.location.replace(intent), 350);
      return () => window.clearTimeout(timer);
    }

    if (error) {
      setMessage(errorDescription || error);
      return;
    }
    if (!code) {
      setMessage("Kode login Google tidak ditemukan.");
      return;
    }

    void backupSupabase.auth.exchangeCodeForSession(code).then(({ error: exchangeError }) => {
      if (exchangeError) {
        setMessage(exchangeError.message);
        return;
      }
      window.location.replace("/native");
    });
  }, []);

  return (
    <main className="grid min-h-dvh place-items-center bg-[#050712] px-5 text-white">
      <section className="w-full max-w-sm rounded-3xl border border-white/10 bg-[#0b1124] p-6 text-center shadow-2xl">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-sky-500/15 text-xl font-bold text-sky-300">G</div>
        <h1 className="mt-4 text-lg font-semibold">Google Backup Furina</h1>
        <p className="mt-2 text-sm leading-6 text-white/65">{message}</p>
        {deepLink && (
          <a href={deepLink} className="mt-5 inline-flex min-h-11 items-center justify-center rounded-xl bg-sky-500 px-4 text-sm font-semibold text-slate-950">
            Kembali ke Furina
          </a>
        )}
      </section>
    </main>
  );
}
