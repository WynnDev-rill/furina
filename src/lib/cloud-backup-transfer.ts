export type CloudBridge = {
  openExternal(url: string): void;
  prepareBackup(requestId: string): void;
  beginRestore(requestId: string): void;
  appendRestoreChunk(requestId: string, base64Chunk: string): void;
  finishRestore(requestId: string): void;
};

type BackupWaiter = {
  chunks: string[];
  fileName: string;
  sizeBytes: number;
  resolve: (value: { base64: string; fileName: string; sizeBytes: number }) => void;
  reject: (reason: Error) => void;
  timer: number;
};

type RestoreWaiter = { resolve: () => void; reject: (reason: Error) => void; timer: number };

export function cloudBridge(): CloudBridge | undefined {
  return (window as unknown as { FurinaCloud?: CloudBridge }).FurinaCloud;
}

export function base64ToBlob(base64: string) {
  const binary = atob(base64);
  const parts: Uint8Array[] = [];
  for (let offset = 0; offset < binary.length; offset += 512 * 1024) {
    const slice = binary.slice(offset, offset + 512 * 1024);
    const bytes = new Uint8Array(slice.length);
    for (let i = 0; i < slice.length; i += 1) bytes[i] = slice.charCodeAt(i);
    parts.push(bytes);
  }
  return new Blob(parts, { type: "application/octet-stream" });
}

export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Gagal membaca backup cloud"));
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.slice(result.indexOf(",") + 1) : result);
    };
    reader.readAsDataURL(blob);
  });
}

export class NativeCloudTransfer {
  private backups = new Map<string, BackupWaiter>();
  private restores = new Map<string, RestoreWaiter>();
  private previous: Record<string, unknown> = {};

  install(onAuth: (rawUrl: string) => void) {
    const g = window as unknown as Record<string, unknown>;
    for (const key of ["__furinaCloudAuthCallback", "__furinaCloudBackupStart", "__furinaCloudBackupChunk", "__furinaCloudBackupError", "__furinaCloudRestoreDone"]) {
      this.previous[key] = g[key];
    }
    g.__furinaCloudAuthCallback = onAuth;
    g.__furinaCloudBackupStart = (id: string, fileName: string, sizeBytes: number) => {
      const w = this.backups.get(id); if (!w) return; w.fileName = fileName; w.sizeBytes = sizeBytes;
    };
    g.__furinaCloudBackupChunk = (id: string, chunk: string, done: boolean) => {
      const w = this.backups.get(id); if (!w) return; w.chunks.push(chunk); if (!done) return;
      clearTimeout(w.timer); this.backups.delete(id); w.resolve({ base64: w.chunks.join(""), fileName: w.fileName, sizeBytes: w.sizeBytes });
    };
    g.__furinaCloudBackupError = (id: string, message: string) => {
      const w = this.backups.get(id); if (!w) return; clearTimeout(w.timer); this.backups.delete(id); w.reject(new Error(message));
    };
    g.__furinaCloudRestoreDone = (id: string, success: boolean, message: string) => {
      const w = this.restores.get(id); if (!w) return; clearTimeout(w.timer); this.restores.delete(id);
      success ? w.resolve() : w.reject(new Error(message));
    };
  }

  uninstall() {
    const g = window as unknown as Record<string, unknown>;
    Object.entries(this.previous).forEach(([k, v]) => { g[k] = v; });
    this.backups.forEach((w) => { clearTimeout(w.timer); w.reject(new Error("Backup dibatalkan")); });
    this.restores.forEach((w) => { clearTimeout(w.timer); w.reject(new Error("Restore dibatalkan")); });
    this.backups.clear(); this.restores.clear();
  }

  prepareBackup() {
    const bridge = cloudBridge();
    if (!bridge) return Promise.reject(new Error("Backup cloud hanya tersedia di APK Furina terbaru."));
    const id = crypto.randomUUID();
    return new Promise<{ base64: string; fileName: string; sizeBytes: number }>((resolve, reject) => {
      const timer = window.setTimeout(() => { this.backups.delete(id); reject(new Error("Persiapan backup terlalu lama.")); }, 120_000);
      this.backups.set(id, { chunks: [], fileName: "latest.furina", sizeBytes: 0, resolve, reject, timer });
      bridge.prepareBackup(id);
    });
  }

  async restore(base64: string) {
    const bridge = cloudBridge();
    if (!bridge) throw new Error("Restore cloud hanya tersedia di APK Furina terbaru.");
    const id = crypto.randomUUID();
    const completion = new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(() => { this.restores.delete(id); reject(new Error("Restore terlalu lama.")); }, 120_000);
      this.restores.set(id, { resolve, reject, timer });
    });
    bridge.beginRestore(id);
    for (let offset = 0; offset < base64.length; offset += 196_608) bridge.appendRestoreChunk(id, base64.slice(offset, offset + 196_608));
    bridge.finishRestore(id);
    await completion;
  }
}
