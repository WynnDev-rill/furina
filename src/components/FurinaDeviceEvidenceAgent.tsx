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
  runBehavioralBenchmark(requestJson: string): void;
  cancelBehavioralBenchmark(): void;
};

declare global {
  interface Window {
    FurinaEvidence?: NativeEvidenceBridge;
    __furinaDeviceEvidenceDone?: (requestId: string, reportJson: string) => void;
    __furinaDeviceEvidenceError?: (requestId: string, message: string) => void;
  }
}

const QUIET_MS = 45_000;
const RETRY_MS = 60_000;
const PROBE_THROTTLE_MS = 60_000;
const SUBMITTED_PREFIX = "furina:device-evidence:submitted:";

function nativeBridge() {
  if (typeof window === "undefined") return undefined;
  if (window.location.pathname !== "/native") return undefined;
  if (!/(?:^|\s)FurinaAndroid\//.test(navigator.userAgent)) return undefined;
  return window.FurinaEvidence;
}

/** Invisible demand-driven engineering evidence agent. */
export function FurinaDeviceEvidenceAgent() {
  useEffect(() => {
    const bridge = nativeBridge();
    if (!bridge) return;

    let disposed = false;
    let pending: EvidenceRequest | null = null;
    let runningRequestId: string | null = null;
    let lastInteractionAt = Date.now();
    let lastProbeAt = 0;
    let quietTimer: number | null = null;
    let retryTimer: number | null = null;

    const clearQuiet = () => {
      if (quietTimer != null) window.clearTimeout(quietTimer);
      quietTimer = null;
    };
    const clearRetry = () => {
      if (retryTimer != null) window.clearTimeout(retryTimer);
      retryTimer = null;
    };
    const isExpired = (request: EvidenceRequest) => {
      const expires = Date.parse(request.expiresAt);
      return !Number.isFinite(expires) || expires <= Date.now();
    };
    const alreadySubmitted = (requestId: string) => localStorage.getItem(`${SUBMITTED_PREFIX}${requestId}`) === "1";

    const schedulePending = () => {
      clearQuiet();
      if (disposed || !pending || runningRequestId || isExpired(pending) || alreadySubmitted(pending.requestId)) return;
      const remaining = Math.max(0, QUIET_MS - (Date.now() - lastInteractionAt));
      quietTimer = window.setTimeout(() => {
        quietTimer = null;
        if (disposed || !pending || runningRequestId || isExpired(pending)) return;
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

    const probe = async (force = false) => {
      if (disposed || document.visibilityState !== "visible") return;
      const now = Date.now();
      if (!force && now - lastProbeAt < PROBE_THROTTLE_MS) return;
      lastProbeAt = now;
      const { data: auth } = await backupSupabase.auth.getSession();
      if (disposed || !auth.session) return;
      const { data, error } = await backupSupabase.functions.invoke("furina-device-evidence", {
        body: { action: "request" },
      });
      if (disposed || error) return;
      const request = (data as { request?: EvidenceRequest | null } | null)?.request ?? null;
      if (!request || request.schemaVersion !== 1 || isExpired(request) || alreadySubmitted(request.requestId)) {
        pending = null;
        clearQuiet();
        clearRetry();
        return;
      }
      pending = request;
      schedulePending();
    };

    const submit = async (requestId: string, reportJson: string) => {
      if (disposed || !pending || pending.requestId !== requestId) return;
      let result: unknown;
      try {
        result = JSON.parse(reportJson);
      } catch {
        runningRequestId = null;
        return;
      }
      const { data: auth } = await backupSupabase.auth.getSession();
      if (disposed || !auth.session) {
        runningRequestId = null;
        return;
      }
      const { error } = await backupSupabase.functions.invoke("furina-device-evidence", {
        body: { action: "result", result },
      });
      runningRequestId = null;
      if (!error) {
        localStorage.setItem(`${SUBMITTED_PREFIX}${requestId}`, "1");
        pending = null;
        clearQuiet();
        clearRetry();
      } else if (pending && !isExpired(pending)) {
        retryTimer = window.setTimeout(schedulePending, RETRY_MS);
      }
    };

    window.__furinaDeviceEvidenceDone = (requestId, reportJson) => void submit(requestId, reportJson);
    window.__furinaDeviceEvidenceError = (requestId) => {
      if (runningRequestId === requestId) runningRequestId = null;
      if (pending?.requestId === requestId && !isExpired(pending)) {
        clearRetry();
        retryTimer = window.setTimeout(schedulePending, RETRY_MS);
      }
    };

    const onInteraction = () => {
      lastInteractionAt = Date.now();
      clearQuiet();
      if (runningRequestId) bridge.cancelBehavioralBenchmark();
      if (pending && !isExpired(pending)) schedulePending();
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") void probe(false);
      else if (runningRequestId) bridge.cancelBehavioralBenchmark();
    };
    const onFocus = () => void probe(false);

    document.addEventListener("pointerdown", onInteraction, { passive: true });
    document.addEventListener("keydown", onInteraction, { passive: true });
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onFocus);

    const { data: authListener } = backupSupabase.auth.onAuthStateChange((_event, session) => {
      if (session) void probe(true);
      else {
        pending = null;
        if (runningRequestId) bridge.cancelBehavioralBenchmark();
        runningRequestId = null;
        clearQuiet();
        clearRetry();
      }
    });
    void probe(true);

    return () => {
      disposed = true;
      clearQuiet();
      clearRetry();
      if (runningRequestId) bridge.cancelBehavioralBenchmark();
      document.removeEventListener("pointerdown", onInteraction);
      document.removeEventListener("keydown", onInteraction);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onFocus);
      authListener.subscription.unsubscribe();
      delete window.__furinaDeviceEvidenceDone;
      delete window.__furinaDeviceEvidenceError;
    };
  }, []);

  return null;
}
