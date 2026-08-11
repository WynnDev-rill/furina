import { useEffect } from "react";
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

declare global {
  interface Window {
    FurinaEvidence?: NativeEvidenceBridge;
    __furinaDeviceEvidenceRequest?: (requestJson: string) => void;
    __furinaDeviceEvidenceDone?: (requestId: string, reportJson: string) => void;
    __furinaDeviceEvidenceSubmitted?: (requestId: string) => void;
    __furinaDeviceEvidenceError?: (requestId: string, message: string) => void;
    __furinaDeviceEvidenceTransportError?: (operation: string, requestId: string, message: string) => void;
  }
}

const QUIET_MS = 45_000;
const RETRY_MS = 60_000;
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
 * Invisible demand-driven engineering evidence agent.
 *
 * Realtime carries only a payload-free public wake signal. Request fetch and result upload are
 * authenticated by a dedicated AndroidKeyStore device key inside the native bridge, not by the
 * user's Google/Supabase login. There is no periodic request-data polling.
 */
export function FurinaDeviceEvidenceAgent() {
  useEffect(() => {
    const bridge = nativeBridge();
    if (!bridge) return;

    let disposed = false;
    let pending: EvidenceRequest | null = null;
    let runningRequestId: string | null = null;
    let pendingReport: { requestId: string; reportJson: string } | null = null;
    let lastInteractionAt = Date.now();
    let lastProbeAt = 0;
    let quietTimer: number | null = null;
    let retryTimer: number | null = null;
    let uploadRetryTimer: number | null = null;
    let signalChannel: ReturnType<typeof backupSupabase.channel> | null = null;

    const clearQuiet = () => {
      if (quietTimer != null) window.clearTimeout(quietTimer);
      quietTimer = null;
    };
    const clearRetry = () => {
      if (retryTimer != null) window.clearTimeout(retryTimer);
      retryTimer = null;
    };
    const clearUploadRetry = () => {
      if (uploadRetryTimer != null) window.clearTimeout(uploadRetryTimer);
      uploadRetryTimer = null;
    };
    const isExpired = (request: EvidenceRequest) => {
      const expires = Date.parse(request.expiresAt);
      return !Number.isFinite(expires) || expires <= Date.now();
    };
    const alreadySubmitted = (requestId: string) => localStorage.getItem(`${SUBMITTED_PREFIX}${requestId}`) === "1";

    const schedulePending = () => {
      clearQuiet();
      if (
        disposed ||
        !pending ||
        runningRequestId ||
        pendingReport ||
        isExpired(pending) ||
        alreadySubmitted(pending.requestId)
      ) return;
      const remaining = Math.max(0, QUIET_MS - (Date.now() - lastInteractionAt));
      quietTimer = window.setTimeout(() => {
        quietTimer = null;
        if (disposed || !pending || runningRequestId || pendingReport || isExpired(pending)) return;
        if (Date.now() - lastInteractionAt < QUIET_MS) {
          schedulePending();
          return;
        }
        const request = pending;
        runningRequestId = request.requestId;
        try {
          bridge.runBehavioralBenchmark(JSON.stringify(request));
        } catch {
          runningRequestId = null;
          retryTimer = window.setTimeout(schedulePending, RETRY_MS);
        }
      }, remaining);
    };

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
      }, RETRY_MS);
    };

    window.__furinaDeviceEvidenceRequest = (requestJson) => {
      if (disposed) return;
      if (!requestJson) {
        if (!pendingReport) {
          pending = null;
          runningRequestId = null;
          clearQuiet();
          clearRetry();
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
        pending = null;
        runningRequestId = null;
        clearQuiet();
        clearRetry();
        return;
      }
      pending = request;
      schedulePending();
    };

    window.__furinaDeviceEvidenceDone = (requestId, reportJson) => {
      if (disposed || !pending || pending.requestId !== requestId || runningRequestId !== requestId) return;
      pendingReport = { requestId, reportJson };
      try {
        bridge.submitBehavioralEvidence(reportJson);
      } catch {
        retryUpload();
      }
    };

    window.__furinaDeviceEvidenceSubmitted = (requestId) => {
      if (disposed || pendingReport?.requestId !== requestId) return;
      localStorage.setItem(`${SUBMITTED_PREFIX}${requestId}`, "1");
      pendingReport = null;
      pending = null;
      runningRequestId = null;
      clearQuiet();
      clearRetry();
      clearUploadRetry();
    };

    window.__furinaDeviceEvidenceError = (requestId) => {
      if (runningRequestId === requestId) runningRequestId = null;
      if (pending?.requestId === requestId && !isExpired(pending) && !pendingReport) {
        clearRetry();
        retryTimer = window.setTimeout(schedulePending, RETRY_MS);
      }
    };

    window.__furinaDeviceEvidenceTransportError = (operation, requestId) => {
      if (operation === "submit" && pendingReport?.requestId === requestId) {
        // Keep the completed raw capture in memory and retry only transport. Never spend another
        // local-model run merely because the network/backend was temporarily unavailable.
        retryUpload();
      }
    };

    const onInteraction = () => {
      lastInteractionAt = Date.now();
      clearQuiet();
      if (runningRequestId && !pendingReport) bridge.cancelBehavioralBenchmark();
      if (pending && !isExpired(pending) && !pendingReport) schedulePending();
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        ensureSignalChannel();
        probe(false);
      } else {
        stopSignalChannel();
        if (runningRequestId && !pendingReport) bridge.cancelBehavioralBenchmark();
      }
    };
    const onFocus = () => probe(false);

    document.addEventListener("pointerdown", onInteraction, { passive: true });
    document.addEventListener("keydown", onInteraction, { passive: true });
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onFocus);

    ensureSignalChannel();
    probe(true);

    return () => {
      disposed = true;
      clearQuiet();
      clearRetry();
      clearUploadRetry();
      stopSignalChannel();
      if (runningRequestId && !pendingReport) bridge.cancelBehavioralBenchmark();
      document.removeEventListener("pointerdown", onInteraction);
      document.removeEventListener("keydown", onInteraction);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onFocus);
      delete window.__furinaDeviceEvidenceRequest;
      delete window.__furinaDeviceEvidenceDone;
      delete window.__furinaDeviceEvidenceSubmitted;
      delete window.__furinaDeviceEvidenceError;
      delete window.__furinaDeviceEvidenceTransportError;
    };
  }, []);

  return null;
}
