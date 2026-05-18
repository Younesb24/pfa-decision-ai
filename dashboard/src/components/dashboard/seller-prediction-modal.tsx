"use client";

/**
 * SellerPredictionModal — XGBoost prediction visibility surface.
 *
 * Opens on Seller Risk Scorecard row click. POSTs to /ml/predict/late-delivery
 * for the chosen seller, then renders the probability gauge, the top-3
 * contributing factors (importance x deviation heuristic), and a concrete
 * recommendation. This is the "AI is doing real work" moment in the demo —
 * the model is making a prediction with evidence, not just narrating tiles.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Brain,
  CheckCircle2,
  Loader2,
  X,
} from "lucide-react";
import { predictLateDelivery } from "@/lib/api";
import { LateDeliveryPrediction } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SellerPredictionModalProps {
  open: boolean;
  onClose: () => void;
  sellerId: string | null;
}

type Phase = "loading" | "ready" | "error";

// Brazilian state names so the State chip reads e.g. "São Paulo (SP)" instead
// of a bare "SP" that means nothing to a non-Brazilian audience.
const BR_STATES: Record<string, string> = {
  SP: "São Paulo",
  RJ: "Rio de Janeiro",
  MG: "Minas Gerais",
  RS: "Rio Grande do Sul",
  PR: "Paraná",
  SC: "Santa Catarina",
  BA: "Bahia",
  DF: "Distrito Federal",
  GO: "Goiás",
  PE: "Pernambuco",
  ES: "Espírito Santo",
  CE: "Ceará",
};

function expandState(code: string | null): string {
  if (!code) return "—";
  const upper = code.toUpperCase();
  const full = BR_STATES[upper];
  return full ? `${full} (${upper})` : upper;
}

const RISK_STYLE: Record<
  LateDeliveryPrediction["risk_label"],
  { ring: string; bg: string; text: string; icon: typeof AlertTriangle; label: string }
> = {
  high: {
    ring: "ring-[color:var(--destructive)]/40",
    bg: "bg-[color:var(--destructive)]/10",
    text: "text-[color:var(--destructive)]",
    icon: AlertTriangle,
    label: "HIGH RISK",
  },
  medium: {
    ring: "ring-[color:var(--warning)]/40",
    bg: "bg-[color:var(--warning)]/10",
    text: "text-[color:var(--warning)]",
    icon: AlertTriangle,
    label: "MEDIUM RISK",
  },
  low: {
    ring: "ring-[color:var(--success)]/40",
    bg: "bg-[color:var(--success)]/10",
    text: "text-[color:var(--success)]",
    icon: CheckCircle2,
    label: "LOW RISK",
  },
};

export function SellerPredictionModal({
  open,
  onClose,
  sellerId,
}: SellerPredictionModalProps) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [prediction, setPrediction] = useState<LateDeliveryPrediction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open || !sellerId) return;
    let cancelled = false;
    setPhase("loading");
    setPrediction(null);
    setError(null);

    predictLateDelivery(sellerId)
      .then((p) => {
        if (cancelled) return;
        setPrediction(p);
        setPhase("ready");
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Prediction failed");
        setPhase("error");
      });

    return () => {
      cancelled = true;
    };
  }, [open, sellerId]);

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

  const probabilityPct = useMemo(
    () => (prediction ? Math.round(prediction.probability * 100) : 0),
    [prediction],
  );

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-label="Late delivery prediction"
      className="fixed inset-0 z-50 flex items-start justify-center px-4 py-12 bg-background/80 backdrop-blur-sm animate-fade-up-1"
    >
      <div
        ref={panelRef}
        className={cn(
          "w-full max-w-2xl rounded-xl border border-border bg-card",
          "ring-1 ring-inset ring-foreground/5 shadow-2xl",
          "flex flex-col max-h-[85vh]",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/60">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md ring-1 ring-inset ring-primary/30 bg-primary/10">
              <Brain className="h-3.5 w-3.5 text-primary" strokeWidth={2.2} />
            </div>
            <div>
              <div className="text-[0.78rem] font-semibold text-foreground">
                Late Delivery Prediction
              </div>
              <div className="text-[0.65rem] text-muted-foreground tabular font-mono">
                seller {sellerId?.slice(0, 16)}…
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
        <div className="flex-1 overflow-auto px-5 py-4 space-y-4">
          {phase === "loading" && (
            <div className="flex items-center gap-2 text-[0.8rem] text-muted-foreground py-12 justify-center">
              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
              Scoring with XGBoost…
            </div>
          )}

          {phase === "error" && (
            <div className="rounded-md bg-[color:var(--destructive)]/10 px-3 py-2 text-[0.75rem] text-[color:var(--destructive)] ring-1 ring-inset ring-[color:var(--destructive)]/30">
              {error}
            </div>
          )}

          {phase === "ready" && prediction && (
            <>
              {/* Two paired signals: backward-looking history vs forward-looking prediction.
                  Each gets its own badge so the user can see when they agree (both red, both
                  green) and — more interestingly — when they diverge. The composite
                  scorecard data feeds the historical card; the XGBoost output feeds the
                  prediction card. */}
              <RiskSignalCard
                kind="historical"
                label={prediction.historical_risk_label}
                primary={`${prediction.seller_context.late_delivery_rate_pct.toFixed(1)}%`}
                primaryHint="late delivery rate"
                secondary={`${prediction.seller_context.avg_review_score.toFixed(1)}★ rating · risk score ${prediction.seller_context.seller_risk_score.toFixed(0)}`}
              />
              <RiskSignalCard
                kind="predicted"
                label={prediction.risk_label}
                primary={`${probabilityPct}%`}
                primaryHint="probability for a typical next order"
                secondary={`Model threshold ${(prediction.threshold * 100).toFixed(0)}% · ${prediction.predicted_late ? "predicted late" : "predicted on-time"}`}
              />
              <div className="text-[0.62rem] text-muted-foreground italic px-1 -mt-1">
                Prediction scenario: a typical next order under default conditions —
                same-state delivery, average product, no holiday or weekend effect.
              </div>

              {prediction.historical_risk_label !== prediction.risk_label && (
                <div className="rounded-md bg-[color:var(--surface-2)] ring-1 ring-inset ring-border/60 px-3 py-2 text-[0.7rem] text-muted-foreground leading-relaxed">
                  <span className="font-medium text-foreground">Signals diverge.</span>{" "}
                  {prediction.historical_risk_label === "high"
                    ? "History is poor, but the model predicts a typical next order under safe defaults (same-state delivery, average product). The prediction would shift if conditions worsen — see top factors below."
                    : "The model flags this specific order scenario as risky even though the seller's track record is clean — see top factors below for what's driving the prediction."}
                </div>
              )}

              {/* Compact context — state + volume aren't in the risk cards. */}
              <section>
                <div className="grid grid-cols-2 gap-2">
                  <ContextStat label="State" value={expandState(prediction.seller_context.state)} />
                  <ContextStat
                    label="Total orders"
                    value={prediction.seller_context.total_orders.toString()}
                  />
                </div>
              </section>

              {/* Main risk signals (heuristic-based, not SHAP — see model card). */}
              <section>
                <div className="text-[0.6rem] uppercase tracking-[0.08em] text-muted-foreground mb-2">
                  Main risk signals
                </div>
                {prediction.top_factors.length === 0 ? (
                  <div className="text-[0.7rem] text-muted-foreground italic">
                    No factor stood out — seller scored near the marketplace baseline.
                  </div>
                ) : (
                  <ul className="space-y-1.5">
                    {prediction.top_factors.map((f) => (
                      <FactorRow key={f.feature} factor={f} />
                    ))}
                  </ul>
                )}
              </section>

              {/* Recommendation */}
              <section>
                <div className="text-[0.6rem] uppercase tracking-[0.08em] text-muted-foreground mb-2">
                  Recommended action
                </div>
                <div className="rounded-md bg-[color:var(--surface-2)] px-3 py-2.5 text-[0.78rem] text-foreground leading-relaxed">
                  {prediction.recommendation}
                </div>
              </section>

              {/* Model footer */}
              <div className="pt-2 border-t border-border/40 text-[0.6rem] text-muted-foreground tabular flex justify-between">
                <span>
                  {prediction.model.name} · {prediction.model.n_features} features
                </span>
                <span>importance × deviation explanation</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function RiskSignalCard({
  kind,
  label,
  primary,
  primaryHint,
  secondary,
}: {
  kind: "historical" | "predicted";
  label: LateDeliveryPrediction["risk_label"];
  primary: string;
  primaryHint: string;
  secondary: string;
}) {
  const style = RISK_STYLE[label];
  const Icon = style.icon;
  const heading =
    kind === "historical" ? "Historical risk (past orders)" : "Predicted risk (next typical order)";
  const source = kind === "historical" ? "from scorecard" : "from XGBoost";
  return (
    <div
      className={cn(
        "rounded-lg p-4 ring-1 ring-inset flex items-center gap-4",
        style.ring,
        style.bg,
      )}
    >
      <Icon className={cn("h-7 w-7 shrink-0", style.text)} strokeWidth={2} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <div className="text-[0.6rem] uppercase tracking-[0.08em] text-muted-foreground">
            {heading}
          </div>
          <div className={cn("text-[0.55rem] font-semibold tracking-[0.1em]", style.text)}>
            {style.label}
          </div>
        </div>
        <div className="flex items-baseline gap-2 mt-0.5">
          <span className="tabular text-2xl font-semibold text-foreground">{primary}</span>
          <span className="text-[0.7rem] text-muted-foreground">{primaryHint}</span>
        </div>
        <div className="text-[0.62rem] text-muted-foreground mt-1 tabular">
          {secondary} · <span className="opacity-70">{source}</span>
        </div>
      </div>
    </div>
  );
}

function ContextStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-[color:var(--surface-2)] px-2.5 py-2">
      <div className="text-[0.55rem] uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </div>
      <div className="tabular text-[0.85rem] font-medium text-foreground mt-0.5">
        {value}
      </div>
    </div>
  );
}

function FactorRow({
  factor,
}: {
  factor: LateDeliveryPrediction["top_factors"][number];
}) {
  const increases = factor.direction === "increases";
  const Arrow = increases ? ArrowUp : ArrowDown;
  const tone = increases ? "text-[color:var(--destructive)]" : "text-[color:var(--success)]";
  return (
    <li className="flex items-center gap-3 rounded-md bg-[color:var(--surface-2)] px-3 py-2">
      <Arrow className={cn("h-3.5 w-3.5 shrink-0", tone)} strokeWidth={2.2} />
      <div className="flex-1 min-w-0">
        <div className="text-[0.75rem] text-foreground truncate">{factor.label}</div>
        <div className="text-[0.62rem] text-muted-foreground tabular">
          value {factor.value} · {increases ? "raises" : "lowers"} risk
        </div>
      </div>
      <div className={cn("tabular text-[0.78rem] font-semibold", tone)}>
        {increases ? "+" : "−"}
        {factor.contribution_pct.toFixed(0)}%
      </div>
    </li>
  );
}
