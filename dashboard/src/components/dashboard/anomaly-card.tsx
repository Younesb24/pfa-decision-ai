"use client";

/**
 * AnomalyCard — one row in the Anomaly Stream panel.
 *
 * Day 1 deliverable. Adds the [Mark reviewed] / [Dismiss] / [Escalate] buttons
 * that POST to /api/v1/governance/review with subject_type="alert" and a
 * stable subject_ref of "{metric}@{date}". On success the row collapses into
 * a muted "Reviewed by you" state — the audit trail keeps the full history.
 *
 * The component does NOT optimistically discard the alert from the parent's
 * list: the audit row is what matters, the UI just dims this card so the
 * operator sees what's already been triaged.
 */

import { useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  Check,
  ChevronUp,
  CircleSlash,
  Flame,
  Mail,
  MessageSquare,
} from "lucide-react";
import type { AnomalyAlert, ReviewDecision } from "@/lib/types";
import { escalateAction, fireActionWebhook, submitReview } from "@/lib/api";
import { cn } from "@/lib/utils";
import { EmailDraftModal } from "./email-draft-modal";

interface AnomalyCardProps {
  alert: AnomalyAlert;
}

type ReviewState =
  | { kind: "idle" }
  | { kind: "saving"; decision: ReviewDecision }
  | { kind: "saved"; decision: ReviewDecision }
  | { kind: "error"; message: string };

const DECISION_LABEL: Record<ReviewDecision, string> = {
  acknowledge: "Acknowledged",
  dismiss: "Dismissed",
  escalate: "Escalated",
};

type ActionToast =
  | { kind: "idle" }
  | { kind: "pending"; what: string }
  | { kind: "done"; what: string; detail?: string }
  | { kind: "error"; what: string; message: string };

export function AnomalyCard({ alert }: AnomalyCardProps) {
  const [state, setState] = useState<ReviewState>({ kind: "idle" });
  const [emailOpen, setEmailOpen] = useState(false);
  const [action, setAction] = useState<ActionToast>({ kind: "idle" });

  const isCritical = alert.severity === "critical";
  const isUp = alert.direction === "high";
  const subjectRef = `${alert.metric}@${alert.date}`;

  const handle = async (decision: ReviewDecision) => {
    setState({ kind: "saving", decision });
    const result = await submitReview({ subject_ref: subjectRef, decision });
    if (result.recorded) {
      setState({ kind: "saved", decision });
    } else {
      setState({
        kind: "error",
        message: "Audit log unavailable — run scripts/audit_log_migration.sql",
      });
    }
  };

  /** Day 5/6: fire a MessageSquare webhook with this anomaly's context. */
  const handleMessageSquare = async () => {
    setAction({ kind: "pending", what: "MessageSquare" });
    const r = await fireActionWebhook({
      subject_ref: subjectRef,
      channel: "slack",
      title: `[${alert.severity.toUpperCase()}] ${alert.metric.replace(/_/g, " ")}`,
      body:
        `${alert.metric} = ${formatValue(alert.metric, alert.value)} on ${alert.date} ` +
        `(z=${alert.z_score}, direction=${alert.direction}).`,
      severity: alert.severity === "critical" ? "critical" : "warning",
    });
    if (!r) {
      setAction({ kind: "error", what: "MessageSquare", message: "API unreachable" });
      return;
    }
    setAction({ kind: "done", what: "MessageSquare", detail: r.detail || r.status || "" });
  };

  /** Day 5/6: open a critical alert in governance.alerts. */
  const handleEscalate = async () => {
    setAction({ kind: "pending", what: "Escalate" });
    const r = await escalateAction({
      subject_ref: subjectRef,
      severity: "critical",
      reason: `${alert.metric} z=${alert.z_score} on ${alert.date} (${alert.direction})`,
    });
    if (!r) {
      setAction({ kind: "error", what: "Escalate", message: "API unreachable" });
      return;
    }
    setAction({ kind: "done", what: "Escalate", detail: r.detail || "" });
  };

  const reviewed = state.kind === "saved";

  return (
    <li
      className={cn(
        "group flex flex-col gap-2 px-3 py-2.5 transition-colors",
        "hover:bg-[color:var(--surface-2)]",
        reviewed && "opacity-60",
      )}
      aria-label={`Anomaly on ${alert.metric}`}
    >
      <div className="flex items-center gap-3">
        <span
          className={cn(
            "relative flex h-1.5 w-1.5 shrink-0 rounded-full",
            isCritical
              ? "bg-[color:var(--destructive)] text-[color:var(--destructive)]"
              : "bg-[color:var(--warning)] text-[color:var(--warning)]",
            !reviewed && "pulse-dot",
          )}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-[0.78rem] font-medium text-foreground truncate">
            <span>{alert.metric.replace(/_/g, " ")}</span>
            {isUp ? (
              <ArrowUpRight
                className="h-3 w-3 text-[color:var(--warning)]"
                strokeWidth={2.5}
              />
            ) : (
              <ArrowDownRight
                className="h-3 w-3 text-[color:var(--destructive)]"
                strokeWidth={2.5}
              />
            )}
          </div>
          <div className="flex items-center gap-2 text-[0.66rem] text-muted-foreground tabular">
            <span>{alert.date}</span>
            <span className="opacity-40">·</span>
            <span>z = {alert.z_score}</span>
            <span className="opacity-40">·</span>
            <span>value {formatValue(alert.metric, alert.value)}</span>
          </div>
        </div>
        <span
          className={cn(
            "tabular text-[0.6rem] font-semibold uppercase tracking-[0.08em] shrink-0",
            isCritical
              ? "text-[color:var(--destructive)]"
              : "text-[color:var(--warning)]",
          )}
        >
          {alert.severity}
        </span>
      </div>

      {/* Action row — Mark-as-Reviewed wiring. */}
      <div className="flex items-center justify-between pl-4">
        {reviewed ? (
          <div className="flex items-center gap-1.5 text-[0.65rem] text-[color:var(--success)] tabular">
            <Check className="h-3 w-3" strokeWidth={2.5} />
            <span>{DECISION_LABEL[(state as { decision: ReviewDecision }).decision]}</span>
            <span className="opacity-50 text-muted-foreground">· logged to audit</span>
          </div>
        ) : state.kind === "error" ? (
          <div className="text-[0.6rem] text-[color:var(--destructive)] tabular">
            {state.message}
          </div>
        ) : (
          <div className="flex items-center gap-1">
            <ReviewButton
              decision="acknowledge"
              icon={<Check className="h-3 w-3" strokeWidth={2.5} />}
              label="Mark reviewed"
              tone="success"
              busy={state.kind === "saving" && state.decision === "acknowledge"}
              onClick={() => handle("acknowledge")}
            />
            <ReviewButton
              decision="dismiss"
              icon={<CircleSlash className="h-3 w-3" strokeWidth={2.5} />}
              label="Dismiss"
              tone="neutral"
              busy={state.kind === "saving" && state.decision === "dismiss"}
              onClick={() => handle("dismiss")}
            />
            {isCritical && (
              <ReviewButton
                decision="escalate"
                icon={<Flame className="h-3 w-3" strokeWidth={2.5} />}
                label="Escalate"
                tone="danger"
                busy={state.kind === "saving" && state.decision === "escalate"}
                onClick={() => handle("escalate")}
              />
            )}
          </div>
        )}
        <span className="hidden sm:inline-flex items-center gap-1 text-[0.55rem] text-muted-foreground/60 tabular">
          <ChevronUp className="h-2.5 w-2.5" strokeWidth={2} />
          {subjectRef}
        </span>
      </div>

      {/* ─── Action Center row (Day 5/6) ─── */}
      {!reviewed && (
        <div className="flex items-center flex-wrap gap-1 pl-4 border-t border-border/40 pt-1.5">
          <span className="text-[0.55rem] uppercase tracking-[0.08em] text-muted-foreground/60 mr-1">
            Act:
          </span>
          <ActionButton
            icon={<Mail className="h-3 w-3" strokeWidth={2.5} />}
            label="Draft email"
            onClick={() => setEmailOpen(true)}
          />
          <ActionButton
            icon={<MessageSquare className="h-3 w-3" strokeWidth={2.5} />}
            label="Send to MessageSquare"
            onClick={handleMessageSquare}
            busy={action.kind === "pending" && action.what === "MessageSquare"}
          />
          {isCritical && (
            <ActionButton
              icon={<Flame className="h-3 w-3" strokeWidth={2.5} />}
              label="Escalate"
              tone="danger"
              onClick={handleEscalate}
              busy={action.kind === "pending" && action.what === "Escalate"}
            />
          )}
          {action.kind === "done" && (
            <span className="text-[0.6rem] text-[color:var(--success)] tabular ml-1.5">
              ✓ {action.what} · {(action.detail || "").slice(0, 60)}
            </span>
          )}
          {action.kind === "error" && (
            <span className="text-[0.6rem] text-[color:var(--destructive)] tabular ml-1.5">
              {action.what}: {action.message}
            </span>
          )}
        </div>
      )}

      <EmailDraftModal
        open={emailOpen}
        onClose={() => setEmailOpen(false)}
        subjectRef={subjectRef}
        context={{
          metric: alert.metric,
          date: alert.date,
          value: alert.value,
          z_score: alert.z_score,
          direction: alert.direction,
          severity: alert.severity,
        }}
        onSent={(actionId) =>
          setAction({ kind: "done", what: "Email", detail: `action_id=${actionId}` })
        }
      />
    </li>
  );
}


function ActionButton({
  icon,
  label,
  tone,
  busy,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  tone?: "neutral" | "danger";
  busy?: boolean;
  onClick: () => void;
}) {
  const toneClass =
    tone === "danger"
      ? "text-[color:var(--destructive)] hover:bg-[color:var(--destructive)]/10 ring-[color:var(--destructive)]/30"
      : "text-muted-foreground hover:bg-[color:var(--surface-2)] hover:text-foreground ring-foreground/10";
  return (
    <button
      type="button"
      disabled={busy}
      onClick={onClick}
      className={cn(
        "tabular inline-flex items-center gap-1 rounded-md px-1.5 py-0.5",
        "text-[0.62rem] font-medium ring-1 ring-inset",
        "transition-colors disabled:opacity-50",
        toneClass,
      )}
    >
      {icon}
      <span>{busy ? "…" : label}</span>
    </button>
  );
}

function ReviewButton({
  icon,
  label,
  tone,
  busy,
  onClick,
}: {
  decision: ReviewDecision;
  icon: React.ReactNode;
  label: string;
  tone: "success" | "neutral" | "danger";
  busy: boolean;
  onClick: () => void;
}) {
  const toneClass =
    tone === "success"
      ? "text-[color:var(--success)] hover:bg-[color:var(--success)]/10 ring-[color:var(--success)]/30"
      : tone === "danger"
        ? "text-[color:var(--destructive)] hover:bg-[color:var(--destructive)]/10 ring-[color:var(--destructive)]/30"
        : "text-muted-foreground hover:bg-[color:var(--surface-2)] ring-foreground/10";

  return (
    <button
      type="button"
      disabled={busy}
      onClick={onClick}
      className={cn(
        "tabular inline-flex items-center gap-1 rounded-md px-1.5 py-0.5",
        "text-[0.62rem] font-medium ring-1 ring-inset",
        "transition-colors disabled:opacity-50",
        toneClass,
      )}
    >
      {icon}
      <span>{busy ? "…" : label}</span>
    </button>
  );
}

function formatValue(metric: string, v: number): string {
  if (metric.includes("rate")) return `${v.toFixed(2)}%`;
  if (metric.includes("gmv")) return `R$${Math.round(v).toLocaleString()}`;
  return Math.round(v).toLocaleString();
}
