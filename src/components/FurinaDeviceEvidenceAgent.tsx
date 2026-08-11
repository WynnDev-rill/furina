import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Database, Loader2 } from "lucide-react";
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
  phase: "idle" | "requested" | "running" | "uploading" | "done";
  requestId?: string;
  detail?: string;
  completed?: number;
  total?: number;
};

declare global {
  interface Window {
    FurinaEvidence?: NativeEvidenceBridge;
    __furinaStartDeviceEvidence?: () => void;
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

function nativeBridge() {
  if (typeof window === "undefined") return undefined;
  if (window.location.pathname !== "/native") return undefined;
  if (!/(?:^|\s)FurinaAndroid\//.test(navigator.userAgent)) return undefined;
  return window.FurinaEvidence;
}

/**
 * Demand-driven engineering evidence agent.
 *
 * Realtime carries only a payload-free public wake signal. Request fetch and result upload are
 * authenticated by a dedicated AndroidKeyStore device key inside the native bridge, not by the
 * user's Google/Supabase login. There is no periodic request-data polling and no automatic model
 * benchmark: the user explicitly starts a requested capture from the temporary in-app card.
 */
export function FurinaDeviceEvidenceAgent() {
  const [ui, setUi] = useState<EvidenceUiState>({ phase: "idle" });

  useEffect(() => {
    const bridge = nativeBridge();
    if (!bridge) return;

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
      try {
        bridge.probeEvidenceRequest();
      } catch {
        // Native transport is fail-closed; lifecycle/realtime events can probe again later.
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
          // The broadcast contains no request, user, model, or credential data.
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
          detail: "Pengambilan data gagal dimulai. Coba lagi saat model AI lokal sudah siap.",
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
      if (operation === "submit" && pendingReport?.requestId === requestId) {
        // Keep the completed raw capture in memory and retry only transport. Never spend another
        // local-model run merely because the network/backend was temporarily unavailable.
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
      delete window.__furinaDeviceEvidenceRequest;
      delete window.__furinaDeviceEvidenceProgress;
      delete window.__furinaDeviceEvidenceDone;
      delete window.__furinaDeviceEvidenceSubmitted;
      delete window.__furinaDeviceEvidenceError;
      delete window.__furinaDeviceEvidenceTransportError;
    };
  }, []);

  if (ui.phase === "idle") return null;

  const runningProgress = ui.phase === "running" && ui.total
    ? `${Math.min(ui.completed ?? 0, ui.total)}/${ui.total} skenario`
    : null;
  const title = ui.phase === "requested"
    ? "Loop Engineering memerlukan data untuk perbaikan berikutnya"
    : ui.phase === "running"
      ? "Pengambilan data sedang berjalan"
      : ui.phase === "uploading"
        ? "Mengirim hasil ke Loop Engineering"
        : "Data perbaikan sudah dikirim";
  const defaultDetail = ui.phase === "requested"
    ? "Tekan Mulai saat kamu siap. Hanya skenario uji sintetis yang diproses; percakapan dan memori pribadimu tidak dikirim."
    : ui.phase === "running"
      ? "Biarkan Furina tetap terbuka sampai selesai. Tidak perlu menggunakan percakapan AI."
      : ui.phase === "uploading"
        ? "Benchmark sudah selesai. Furina sedang mengirim hasilnya ke backend engineering."
        : "Loop Engineering dapat menggunakan hasil ini pada shift berikutnya.";

  return (
    <div className="pointer-events-none fixed inset-x-0 top-[84px] z-[80] px-3">
      <div role="status" aria-live="polite" className="pointer-events-auto mx-auto max-w-md rounded-2xl border border-primary/25 bg-background/95 p-4 text-foreground shadow-2xl backdrop-blur-xl">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            {ui.phase === "running" || ui.phase === "uploading"
              ? <Loader2 className="h-[18px] w-[18px] animate-spin" />
              : ui.phase === "done"
                ? <CheckCircle2 className="h-[18px] w-[18px]" />
                : <Database className="h-[18px] w-[18px]" />}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold leading-snug">{title}</p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{ui.detail || defaultDetail}</p>
            {runningProgress && <p className="mt-2 text-xs font-medium tabular-nums text-primary">{runningProgress}</p>}
            {ui.phase === "requested" && (
              <>
                <p className="mt-2 flex items-start gap-1.5 text-[10px] leading-relaxed text-muted-foreground">
                  <AlertCircle className="mt-0.5 h-3 w-3 shrink-0" />Pastikan model AI lokal sudah terunduh dan tidak sedang menghasilkan jawaban.
                </p>
                <Button className="mt-3 min-h-10 w-full rounded-xl" onClick={() => window.__furinaStartDeviceEvidence?.()}>
                  Mulai pengambilan data
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
