import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, CheckCircle2, Database, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { backupSupabase } from "@/integrations/supabase/backup-client";

type EvidenceRequest = {
  schemaVersion: number;
  requestId: string;
  targetCommit: string;
  benchmarkVersion: string;
  expiresAt: string;
  inputs: {
    schemaVersion: number;
    benchmarkVersion: string;
    scenarios: Array<{
      scenarioId: string;
      setup: Array<{ role: "user" | "assistant"; content: string }>;
      user: string;
    }>;
  };
};

type NativeEvidenceBridge = {
  evidenceInfo(): string;
  probeEvidenceRequest(): void;
  submitBehavioralEvidence(reportJson: string): void;
  runBehavioralBenchmark(requestJson: string): void;
  cancelBehavioralBenchmark(): void;
};

type EvidenceUiState = {
  phase: "checking" | "idle" | "requested" | "running" | "uploading" | "done" | "error";
  requestId?: string;
  detail?: string;
  completed?: number;
  total?: number;
};

declare global {
  interface Window {
    FurinaEvidence?: NativeEvidenceBridge;
    __furinaStartDeviceEvidence?: () => void;
    __furinaRefreshDeviceEvidence?: () => void;
    __furinaDeviceEvidenceRequest?: (requestJson: string) => void;
    __furinaDeviceEvidenceProgress?: (requestId: string, completed: number, total: number) => void;
    __furinaDeviceEvidenceDone?: (requestId: string, reportJson: string) => void;
    __furinaDeviceEvidenceSubmitted?: (requestId: string) => void;
    __furinaDeviceEvidenceError?: (requestId: string, message: string) => void;
    __furinaDeviceEvidenceTransportError?: (operation: string, requestId: string, message: string) => void;
  }
}

const UPLOAD_RETRY_MS = 60_000;
const PROBE_THROTTLE_MS = 60_000;
const SIGNAL_TOPIC = "furina-device-evidence-signal";
const SUBMITTED_PREFIX = "furina:device-evidence:submitted:";
const SETTINGS_HOST_ATTR = "data-furina-loop-engineering-settings";

function isNativeEvidenceSurface() {
  return typeof window !== "undefined"
    && window.location.pathname === "/native"
    && /(?:^|\s)FurinaAndroid\//.test(navigator.userAgent);
}

function nativeBridge() {
  if (!isNativeEvidenceSurface()) return undefined;
  return window.FurinaEvidence;
}

function findSettingsScroller() {
  if (typeof document === "undefined") return null;
  const dialogs = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]'));
  const settings = dialogs.find((dialog) => {
    const text = dialog.textContent || "";
    return text.includes("Pengaturan") && text.includes("Identitas, mesin AI, suara, memori, dan backup.");
  });
  if (!settings) return null;
  return Array.from(settings.querySelectorAll<HTMLElement>("div")).find((node) =>
    node.classList.contains("overflow-y-auto") && node.classList.contains("flex-1")
  ) ?? settings;
}

/**
 * Demand-driven engineering evidence agent.
 *
 * The agent stays invisible in the chat surface. A compact status card is mounted at the top of
 * Furina Settings whenever that sheet is open, so the user can always tell whether Loop
 * Engineering needs device data. The local benchmark never starts automatically.
 */
export function FurinaDeviceEvidenceAgent() {
  const [ui, setUi] = useState<EvidenceUiState>({ phase: "checking" });
  const [settingsHost, setSettingsHost] = useState<HTMLElement | null>(null);
  const [bridgeEpoch, setBridgeEpoch] = useState(0);

  useEffect(() => {
    if (typeof document === "undefined" || !isNativeEvidenceSurface()) return;

    let currentHost: HTMLElement | null = null;
    const syncHost = () => {
      const target = findSettingsScroller();
      if (!target) {
        currentHost = null;
        setSettingsHost(null);
        return;
      }
      const existing = target.querySelector<HTMLElement>(`[${SETTINGS_HOST_ATTR}]`);
      if (existing) {
        currentHost = existing;
        setSettingsHost(existing);
        return;
      }
      const host = document.createElement("div");
      host.setAttribute(SETTINGS_HOST_ATTR, "true");
      host.className = "mb-6";
      target.prepend(host);
      currentHost = host;
      setSettingsHost(host);
    };

    syncHost();
    const observer = new MutationObserver(() => {
      if (currentHost && document.body.contains(currentHost)) return;
      syncHost();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      if (currentHost?.parentElement) currentHost.remove();
    };
  }, []);

  useEffect(() => {
    if (!isNativeEvidenceSurface()) return;
    const bridge = nativeBridge();
    if (!bridge) {
      setUi({ phase: "checking", detail: "Menyiapkan koneksi Loop Engineering…" });
      const retry = window.setTimeout(() => setBridgeEpoch((value) => value + 1), 1_000);
      return () => window.clearTimeout(retry);
    }

    let disposed = false;
    let pending: EvidenceRequest | null = null;
    let runningRequestId: string | null = null;
    let pendingReport: { requestId: string; reportJson: string } | null = null;
    let lastProbeAt = 0;
    let uploadRetryTimer: number | null = null;
    let doneTimer: number | null = null;
    let signalChannel: ReturnType<typeof backupSupabase.channel> | null = null;

    const clearUploadRetry = () => {
      if (uploadRetryTimer != null) window.clearTimeout(uploadRetryTimer);
      uploadRetryTimer = null;
    };
    const clearDoneTimer = () => {
      if (doneTimer != null) window.clearTimeout(doneTimer);
      doneTimer = null;
    };
    const isExpired = (request: EvidenceRequest) => {
      const expires = Date.parse(request.expiresAt);
      return !Number.isFinite(expires) || expires <= Date.now();
    };
    const alreadySubmitted = (requestId: string) => localStorage.getItem(`${SUBMITTED_PREFIX}${requestId}`) === "1";

    const probe = (force = false) => {
      if (disposed || document.visibilityState !== "visible") return;
      const now = Date.now();
      if (!force && now - lastProbeAt < PROBE_THROTTLE_MS) return;
      lastProbeAt = now;
      if (!pending && !runningRequestId && !pendingReport) {
        setUi({ phase: "checking", detail: "Memeriksa apakah perbaikan berikutnya memerlukan data perangkat…" });
      }
      try {
        bridge.probeEvidenceRequest();
      } catch {
        setUi({ phase: "error", detail: "Status belum dapat diperiksa. Coba lagi saat jaringan siap." });
      }
    };

    const stopSignalChannel = () => {
      const channel = signalChannel;
      signalChannel = null;
      if (channel) void backupSupabase.removeChannel(channel);
    };

    const ensureSignalChannel = () => {
      if (disposed || signalChannel || document.visibilityState !== "visible") return;
      signalChannel = backupSupabase
        .channel(SIGNAL_TOPIC)
        .on("broadcast", { event: "request" }, () => {
          probe(true);
        })
        .subscribe();
    };

    const retryUpload = () => {
      clearUploadRetry();
      if (disposed || !pendingReport || !pending || isExpired(pending)) return;
      uploadRetryTimer = window.setTimeout(() => {
        uploadRetryTimer = null;
        if (disposed || !pendingReport || !pending || isExpired(pending)) return;
        try {
          bridge.submitBehavioralEvidence(pendingReport.reportJson);
        } catch {
          retryUpload();
        }
      }, UPLOAD_RETRY_MS);
    };

    window.__furinaRefreshDeviceEvidence = () => probe(true);

    window.__furinaStartDeviceEvidence = () => {
      if (disposed || !pending || runningRequestId || pendingReport) return;
      if (isExpired(pending) || alreadySubmitted(pending.requestId)) {
        pending = null;
        setUi({ phase: "idle" });
        return;
      }
      const request = pending;
      runningRequestId = request.requestId;
      setUi({
        phase: "running",
        requestId: request.requestId,
        completed: 0,
        total: request.inputs.scenarios.length,
      });
      try {
        bridge.runBehavioralBenchmark(JSON.stringify(request));
      } catch {
        runningRequestId = null;
        setUi({
          phase: "requested",
          requestId: request.requestId,
          detail: "Pengambilan data gagal dimulai. Pastikan model AI lokal sudah siap.",
        });
      }
    };

    window.__furinaDeviceEvidenceRequest = (requestJson) => {
      if (disposed) return;
      if (!requestJson) {
        if (!pendingReport && !runningRequestId) {
          pending = null;
          setUi({ phase: "idle" });
        }
        return;
      }
      let request: EvidenceRequest;
      try {
        request = JSON.parse(requestJson) as EvidenceRequest;
      } catch {
        setUi({ phase: "error", detail: "Permintaan data engineering tidak dapat dibaca." });
        return;
      }
      if (request.schemaVersion !== 1 || isExpired(request) || alreadySubmitted(request.requestId)) {
        if (!pendingReport && !runningRequestId) {
          pending = null;
          setUi({ phase: "idle" });
        }
        return;
      }
      pending = request;
      if (runningRequestId === request.requestId || pendingReport?.requestId === request.requestId) return;
      clearDoneTimer();
      setUi({ phase: "requested", requestId: request.requestId });
    };

    window.__furinaDeviceEvidenceProgress = (requestId, completed, total) => {
      if (disposed || runningRequestId !== requestId) return;
      setUi({
        phase: "running",
        requestId,
        completed: Math.max(0, completed),
        total: Math.max(1, total),
      });
    };

    window.__furinaDeviceEvidenceDone = (requestId, reportJson) => {
      if (disposed || !pending || pending.requestId !== requestId || runningRequestId !== requestId) return;
      pendingReport = { requestId, reportJson };
      setUi({ phase: "uploading", requestId });
      try {
        bridge.submitBehavioralEvidence(reportJson);
      } catch {
        setUi({ phase: "uploading", requestId, detail: "Upload tertunda. Furina akan mencoba mengirim hasil yang sama lagi." });
        retryUpload();
      }
    };

    window.__furinaDeviceEvidenceSubmitted = (requestId) => {
      if (disposed || pendingReport?.requestId !== requestId) return;
      localStorage.setItem(`${SUBMITTED_PREFIX}${requestId}`, "1");
      pendingReport = null;
      pending = null;
      runningRequestId = null;
      clearUploadRetry();
      setUi({ phase: "done", requestId });
      clearDoneTimer();
      doneTimer = window.setTimeout(() => {
        if (!disposed) setUi({ phase: "idle" });
      }, 6_000);
    };

    window.__furinaDeviceEvidenceError = (requestId, message) => {
      if (disposed || runningRequestId !== requestId) return;
      runningRequestId = null;
      if (!pending || pending.requestId !== requestId || isExpired(pending)) {
        pending = null;
        setUi({ phase: "idle" });
        return;
      }
      const detail = message === "ai_busy"
        ? "AI sedang digunakan. Tunggu percakapan selesai lalu tekan Mulai lagi."
        : message === "cancelled"
          ? "Pengambilan data terhenti. Tekan Mulai lagi saat kamu siap."
          : `Pengambilan data belum selesai: ${message}`;
      setUi({ phase: "requested", requestId, detail });
    };

    window.__furinaDeviceEvidenceTransportError = (operation, requestId) => {
      if (operation === "probe" && !runningRequestId && !pendingReport) {
        setUi({ phase: "error", detail: "Tidak dapat memeriksa status Loop Engineering. Periksa jaringan lalu coba lagi." });
        return;
      }
      if (operation === "submit" && pendingReport?.requestId === requestId) {
        setUi({ phase: "uploading", requestId, detail: "Jaringan/backend belum siap. Hasil tersimpan sementara dan akan dikirim ulang." });
        retryUpload();
      }
    };

    const onVisible = () => {
      if (document.visibilityState === "visible") {
        ensureSignalChannel();
        probe(false);
      } else {
        stopSignalChannel();
      }
    };
    const onFocus = () => probe(false);

    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onFocus);

    ensureSignalChannel();
    probe(true);

    return () => {
      disposed = true;
      clearUploadRetry();
      clearDoneTimer();
      stopSignalChannel();
      if (runningRequestId && !pendingReport) bridge.cancelBehavioralBenchmark();
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onFocus);
      delete window.__furinaStartDeviceEvidence;
      delete window.__furinaRefreshDeviceEvidence;
      delete window.__furinaDeviceEvidenceRequest;
      delete window.__furinaDeviceEvidenceProgress;
      delete window.__furinaDeviceEvidenceDone;
      delete window.__furinaDeviceEvidenceSubmitted;
      delete window.__furinaDeviceEvidenceError;
      delete window.__furinaDeviceEvidenceTransportError;
    };
  }, [bridgeEpoch]);

  if (!settingsHost) return null;

  const actionRequired = ui.phase === "requested";
  const healthy = ui.phase === "idle" || ui.phase === "done";
  const busy = ui.phase === "checking" || ui.phase === "running" || ui.phase === "uploading";
  const progress = ui.phase === "running" && ui.total
    ? `${Math.min(ui.completed ?? 0, ui.total)}/${ui.total}`
    : null;

  const statusLabel = actionRequired
    ? "Data diperlukan"
    : healthy
      ? ui.phase === "done" ? "Data terkirim" : "Tidak perlu tindakan"
      : ui.phase === "error"
        ? "Status belum tersedia"
        : ui.phase === "running"
          ? `Mengambil data${progress ? ` · ${progress}` : ""}`
          : ui.phase === "uploading"
            ? "Mengirim data"
            : "Memeriksa";

  const detail = ui.detail || (actionRequired
    ? "Perbaikan berikutnya menunggu data perangkat. Tekan tombol di bawah saat kamu siap."
    : ui.phase === "idle"
      ? "Loop Engineering tidak sedang membutuhkan data tambahan dari perangkat ini."
      : ui.phase === "running"
        ? "Biarkan Furina tetap terbuka sampai seluruh skenario selesai."
        : ui.phase === "uploading"
          ? "Benchmark selesai dan hasil sedang dikirim ke backend engineering."
          : ui.phase === "done"
            ? "Hasil sudah tersedia untuk shift Loop Engineering berikutnya."
            : ui.phase === "error"
              ? "Status kebutuhan data belum dapat dipastikan."
              : "Memeriksa kebutuhan data engineering terbaru…");

  return createPortal(
    <section className={`rounded-2xl border p-4 shadow-sm ${actionRequired
      ? "border-red-500/35 bg-red-500/[.07]"
      : healthy
        ? "border-emerald-500/30 bg-emerald-500/[.06]"
        : ui.phase === "error"
          ? "border-amber-500/30 bg-amber-500/[.06]"
          : "border-amber-500/25 bg-amber-500/[.05]"}`}>
      <div className="flex items-start gap-3">
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${actionRequired
          ? "bg-red-500/[.12] text-red-500"
          : healthy
            ? "bg-emerald-500/[.12] text-emerald-500"
            : "bg-amber-500/[.12] text-amber-500"}`}>
          {busy
            ? <Loader2 className="h-[18px] w-[18px] animate-spin" />
            : healthy
              ? <CheckCircle2 className="h-[18px] w-[18px]" />
              : ui.phase === "error"
                ? <AlertTriangle className="h-[18px] w-[18px]" />
                : <Database className="h-[18px] w-[18px]" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold">Loop Engineering</p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">Data untuk perbaikan aplikasi</p>
            </div>
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold ${actionRequired
              ? "border-red-500/25 bg-red-500/10 text-red-500"
              : healthy
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-500"
                : "border-amber-500/25 bg-amber-500/10 text-amber-500"}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${actionRequired ? "bg-red-500" : healthy ? "bg-emerald-500" : "bg-amber-500"}`} />
              {statusLabel}
            </span>
          </div>

          <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">{detail}</p>
          <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground/80">Hanya skenario uji sintetis yang diproses. Percakapan dan memori pribadi tidak dikirim.</p>

          {actionRequired ? (
            <Button className="mt-3 min-h-10 w-full rounded-xl bg-red-500 text-white hover:bg-red-500/90" onClick={() => window.__furinaStartDeviceEvidence?.()}>
              <Database className="mr-2 h-4 w-4" />Mulai pengambilan data
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className="mt-2 h-9 px-2 text-xs text-muted-foreground"
              disabled={ui.phase === "running" || ui.phase === "uploading"}
              onClick={() => window.__furinaRefreshDeviceEvidence?.()}
            >
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${ui.phase === "checking" ? "animate-spin" : ""}`} />Periksa lagi
            </Button>
          )}
        </div>
      </div>
    </section>,
    settingsHost,
  );
}
