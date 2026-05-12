"use client";

/**
 * EmailDraftModal — Day 6 deliverable.
 *
 * Step 1: when opened, POST /act/email/draft and show the LLM body in an
 *         editable textarea. Operator can tweak before sending.
 * Step 2: on "Send", POST /act/email/send with the (possibly edited) body.
 *         The backend will use SMTP if SMTP_* env vars are set; otherwise
 *         it just records the row as sent so the demo flow stays
 *         deliverable without configuring a relay.
 *
 * Render is a fixed overlay rather than a portal — keeps the component
 * self-contained, no extra deps. Esc / outside-click closes.
 */

import { useEffect, useRef, useState } from "react";
import { Loader2, Mail, Send, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  draftActionEmail,
  sendActionEmail,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface EmailDraftModalProps {
  /** Open / closed. */
  open: boolean;
  onClose: () => void;
  /** What anomaly / decision is this email about? */
  subjectRef: string;
  /** Data the LLM is allowed to cite (passed through to /act/email/draft). */
  context?: Record<string, unknown>;
  /** Pre-filled recipient (optional). */
  recipient?: string;
  /** Fired after a successful send so the caller can refresh action history. */
  onSent?: (actionId: number) => void;
}

type Phase = "drafting" | "ready" | "sending" | "sent" | "error";

export function EmailDraftModal({
  open,
  onClose,
  subjectRef,
  context,
  recipient: initialRecipient,
  onSent,
}: EmailDraftModalProps) {
  const [phase, setPhase] = useState<Phase>("drafting");
  const [actionId, setActionId] = useState<number | null>(null);
  const [body, setBody] = useState("");
  const [recipient, setRecipient] = useState(initialRecipient ?? "");
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  // Fetch the draft when the modal opens.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setPhase("drafting");
    setError(null);
    setActionId(null);
    setBody("");
    (async () => {
      const r = await draftActionEmail({
        subject_ref: subjectRef,
        context,
        recipient: initialRecipient,
      });
      if (cancelled) return;
      if (!r || !r.action_id) {
        setPhase("error");
        setError("Couldn't reach the API to generate a draft.");
        return;
      }
      setActionId(r.action_id);
      setBody(r.detail || "");
      setPhase("ready");
    })();
    return () => {
      cancelled = true;
    };
  }, [open, subjectRef, context, initialRecipient]);

  // Close on outside-click / Escape.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const onClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open, onClose]);

  if (!open) return null;

  const handleSend = async () => {
    if (!actionId) return;
    setPhase("sending");
    setError(null);
    const r = await sendActionEmail({ action_id: actionId, body, recipient });
    if (!r || (r.status !== "sent" && r.status !== "drafted")) {
      setPhase("error");
      setError(r?.detail || "Send failed");
      return;
    }
    setPhase("sent");
    onSent?.(actionId);
  };

  return (
    <div
      role="dialog"
      aria-label="Draft email"
      className="fixed inset-0 z-50 flex items-start justify-center px-4 py-12 bg-background/80 backdrop-blur-sm animate-fade-up-1"
    >
      <div
        ref={panelRef}
        className={cn(
          "w-full max-w-2xl rounded-xl border border-border bg-card",
          "ring-1 ring-inset ring-foreground/5 shadow-2xl",
          "flex flex-col max-h-[80vh]",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/60">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md ring-1 ring-inset ring-primary/30 bg-primary/10">
              <Mail className="h-3.5 w-3.5 text-primary" strokeWidth={2.2} />
            </div>
            <div>
              <div className="text-[0.78rem] font-semibold text-foreground">
                Draft outbound email
              </div>
              <div className="text-[0.65rem] text-muted-foreground tabular">
                {subjectRef}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="h-7 w-7 rounded-md hover:bg-[color:var(--surface-2)] inline-flex items-center justify-center text-muted-foreground"
          >
            <X className="h-3.5 w-3.5" strokeWidth={2.2} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto px-5 py-4 space-y-3">
          {phase === "drafting" && (
            <div className="flex items-center gap-2 text-[0.8rem] text-muted-foreground py-8 justify-center">
              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
              Drafting via Decision Analyst…
            </div>
          )}
          {phase === "error" && (
            <div className="rounded-md bg-[color:var(--destructive)]/10 px-3 py-2 text-[0.75rem] text-[color:var(--destructive)] ring-1 ring-inset ring-[color:var(--destructive)]/30">
              {error}
            </div>
          )}
          {(phase === "ready" || phase === "sending" || phase === "sent" || phase === "error") && (
            <>
              <div className="space-y-1.5">
                <label
                  htmlFor="draft-recipient"
                  className="text-[0.6rem] uppercase tracking-[0.1em] text-muted-foreground/70"
                >
                  Recipient
                </label>
                <input
                  id="draft-recipient"
                  type="email"
                  placeholder="seller@example.com"
                  value={recipient}
                  onChange={(e) => setRecipient(e.target.value)}
                  disabled={phase === "sending" || phase === "sent"}
                  className="tabular w-full rounded-md border border-border bg-[color:var(--surface-1)] px-2.5 py-1.5 text-[0.78rem] text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50 disabled:opacity-50"
                />
              </div>
              <div className="space-y-1.5">
                <label
                  htmlFor="draft-body"
                  className="text-[0.6rem] uppercase tracking-[0.1em] text-muted-foreground/70"
                >
                  Body (editable)
                </label>
                <textarea
                  id="draft-body"
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  disabled={phase === "sending" || phase === "sent"}
                  rows={14}
                  className="font-mono w-full rounded-md border border-border bg-[color:var(--surface-1)] px-3 py-2 text-[0.78rem] text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50 disabled:opacity-50 leading-relaxed"
                />
              </div>
              {phase === "sent" && (
                <div className="rounded-md bg-[color:var(--success)]/10 px-3 py-2 text-[0.72rem] text-[color:var(--success)] ring-1 ring-inset ring-[color:var(--success)]/30 tabular">
                  Recorded in governance.action_history (action_id={actionId}).
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border/60 bg-[color:var(--surface-1)]/60">
          {phase !== "sent" ? (
            <>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={onClose}
                disabled={phase === "sending"}
              >
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={handleSend}
                disabled={
                  phase === "drafting" || phase === "sending" || !body || !recipient
                }
                className="gap-1.5"
              >
                {phase === "sending" ? (
                  <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2.5} />
                ) : (
                  <Send className="h-3 w-3" strokeWidth={2.5} />
                )}
                {phase === "sending" ? "Sending…" : "Send"}
              </Button>
            </>
          ) : (
            <Button type="button" size="sm" onClick={onClose}>
              Close
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
