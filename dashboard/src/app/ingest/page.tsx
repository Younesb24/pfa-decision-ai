"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileSpreadsheet,
  Loader2,
  Upload,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AuthGate } from "@/components/auth-gate";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// ── Types ──────────────────────────────────────────────────────────────

interface ColumnPreview {
  name: string;
  dtype: string;
  null_count: number;
  null_pct: number;
  sample: string | null;
}

interface UploadResponse {
  source_id: number;
  original_filename: string;
  storage_path: string;
  size_bytes: number;
  row_count: number;
  column_count: number;
  suggested_table: string;
  columns: ColumnPreview[];
}

interface SourceEntry {
  id: number;
  uploaded_at: string;
  original_filename: string;
  size_bytes: number;
  row_count: number | null;
  column_count: number | null;
  suggested_table: string | null;
  status: string;
  error: string | null;
}

// ── Helpers ────────────────────────────────────────────────────────────

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatRelative(iso: string): string {
  try {
    const then = new Date(iso).getTime();
    const delta = (Date.now() - then) / 1000;
    if (delta < 60) return `${Math.round(delta)}s ago`;
    if (delta < 3600) return `${Math.round(delta / 60)}m ago`;
    if (delta < 86400) return `${Math.round(delta / 3600)}h ago`;
    return `${Math.round(delta / 86400)}d ago`;
  } catch {
    return iso;
  }
}

const DTYPE_TONE: Record<string, string> = {
  int: "text-primary",
  float: "text-primary",
  date: "text-[color:var(--warning)]",
  bool: "text-[color:var(--success)]",
  string: "text-muted-foreground",
};

// ── Page ───────────────────────────────────────────────────────────────

function IngestPageInner() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<UploadResponse | null>(null);
  const [sources, setSources] = useState<SourceEntry[] | null>(null);

  async function loadSources() {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    try {
      const r = await fetch(`${API_BASE}/ingest/sources`, { headers });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as { sources: SourceEntry[] };
      setSources(j.sources);
    } catch (e) {
      setSources([]);
      console.warn("source list failed", e);
    }
  }

  useEffect(() => {
    void loadSources();
  }, []);

  async function doUpload(file: File) {
    setError(null);
    setUploading(true);
    setPreview(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const r = await fetch(`${API_BASE}/ingest/upload`, {
        method: "POST",
        body: fd,
        headers,
      });
      if (r.status === 401 || r.status === 403) {
        setError("You don't have permission to upload — sign in as ops or admin.");
        return;
      }
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(typeof body?.detail === "string" ? body.detail : `Upload failed (${r.status})`);
        return;
      }
      setPreview(body as UploadResponse);
      void loadSources();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void doUpload(file);
  }

  function handlePick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void doUpload(file);
    e.target.value = ""; // allow re-upload of the same file
  }

  return (
    <main className="min-h-screen bg-background px-6 py-8 max-w-5xl mx-auto space-y-6">
      <header className="space-y-1">
        <div className="text-xs uppercase tracking-widest text-muted-foreground">
          Ingest
        </div>
        <h1 className="text-2xl font-semibold">Connect a new data source</h1>
        <p className="text-sm text-muted-foreground">
          Drop a CSV to profile its schema and stage it for a dbt model.
          Files are stored under <code className="text-foreground">data/ingest/</code>;
          a row is written to <code className="text-foreground">governance.source_registry</code>.
        </p>
      </header>

      {/* Drop zone */}
      <Card
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors",
          dragOver ? "border-primary bg-primary/5" : "border-border hover:bg-muted/30",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={handlePick}
        />
        <div className="flex flex-col items-center gap-2">
          {uploading ? (
            <Loader2 className="h-8 w-8 animate-spin text-primary" strokeWidth={1.5} />
          ) : (
            <Upload className="h-8 w-8 text-muted-foreground" strokeWidth={1.5} />
          )}
          <div className="text-sm font-medium">
            {uploading ? "Profiling…" : "Drop a CSV here, or click to select"}
          </div>
          <div className="text-xs text-muted-foreground">CSV · max 200 MB</div>
        </div>
      </Card>

      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <div>{error}</div>
        </div>
      )}

      {/* Preview of the latest upload */}
      {preview && <SchemaPreview preview={preview} />}

      {/* Connected sources list */}
      <SourcesList sources={sources} />
    </main>
  );
}

function SchemaPreview({ preview }: { preview: UploadResponse }) {
  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-[color:var(--success)]" />
            <h2 className="font-semibold">Profiled: {preview.original_filename}</h2>
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {preview.row_count.toLocaleString()} rows · {preview.column_count} cols ·{" "}
            {formatBytes(preview.size_bytes)}
          </div>
        </div>
        <Badge variant="outline">{preview.suggested_table}</Badge>
      </div>

      <div className="rounded-md border overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-muted/40 text-muted-foreground">
            <tr>
              <th className="text-left px-3 py-2 font-medium">Column</th>
              <th className="text-left px-3 py-2 font-medium">Type</th>
              <th className="text-right px-3 py-2 font-medium">Null %</th>
              <th className="text-left px-3 py-2 font-medium">Sample</th>
            </tr>
          </thead>
          <tbody>
            {preview.columns.map((c) => (
              <tr key={c.name} className="border-t">
                <td className="px-3 py-2 font-mono">{c.name}</td>
                <td className={cn("px-3 py-2 font-mono", DTYPE_TONE[c.dtype] ?? "")}>
                  {c.dtype}
                </td>
                <td className="px-3 py-2 text-right tabular">
                  {(c.null_pct * 100).toFixed(1)}%
                </td>
                <td className="px-3 py-2 font-mono text-muted-foreground truncate max-w-[260px]">
                  {c.sample ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-xs text-muted-foreground">
        Stored at <code className="text-foreground">{preview.storage_path}</code>. dbt staging
        scaffold isn&apos;t auto-generated yet — registry entry id{" "}
        <code className="text-foreground">{preview.source_id}</code> is the handoff.
      </div>
    </Card>
  );
}

function SourcesList({ sources }: { sources: SourceEntry[] | null }) {
  const empty = useMemo(() => sources != null && sources.length === 0, [sources]);

  return (
    <Card className="p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Connected sources</h2>
        <Badge variant="outline">{sources?.length ?? "…"}</Badge>
      </div>
      {sources == null && (
        <div className="space-y-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      )}
      {empty && (
        <div className="text-sm text-muted-foreground py-6 text-center">
          No uploads yet. Drop a file above to get started.
        </div>
      )}
      {sources && sources.length > 0 && (
        <div className="rounded-md border overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-muted/40 text-muted-foreground">
              <tr>
                <th className="text-left px-3 py-2 font-medium">File</th>
                <th className="text-left px-3 py-2 font-medium">Table</th>
                <th className="text-right px-3 py-2 font-medium">Rows</th>
                <th className="text-right px-3 py-2 font-medium">Cols</th>
                <th className="text-right px-3 py-2 font-medium">Size</th>
                <th className="text-left px-3 py-2 font-medium">Status</th>
                <th className="text-right px-3 py-2 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id} className="border-t">
                  <td className="px-3 py-2 font-mono flex items-center gap-1.5">
                    <FileSpreadsheet className="h-3 w-3 text-muted-foreground" />
                    <span className="truncate max-w-[200px]">{s.original_filename}</span>
                  </td>
                  <td className="px-3 py-2 font-mono">{s.suggested_table ?? "—"}</td>
                  <td className="px-3 py-2 text-right tabular">
                    {s.row_count?.toLocaleString() ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right tabular">{s.column_count ?? "—"}</td>
                  <td className="px-3 py-2 text-right tabular">{formatBytes(s.size_bytes)}</td>
                  <td className="px-3 py-2">
                    <StatusPill status={s.status} />
                  </td>
                  <td className="px-3 py-2 text-right text-muted-foreground">
                    {formatRelative(s.uploaded_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "profiled"
      ? "bg-primary/10 text-primary"
      : status === "modeled"
        ? "bg-[color:var(--success)]/10 text-[color:var(--success)]"
        : "bg-destructive/10 text-destructive";
  return (
    <span className={cn("rounded-md px-1.5 py-0.5 text-[0.62rem] font-semibold uppercase", tone)}>
      {status}
    </span>
  );
}

export default function IngestPage() {
  return (
    <AuthGate minRole="ops">
      <IngestPageInner />
    </AuthGate>
  );
}
