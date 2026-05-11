/**
 * useTimeRange — shared dashboard window state.
 *
 * Day 1 deliverable (EXECUTION_HANDOFF §3, Sprint 1). Centralises:
 *   - the start/end ISO dates passed to /api/v1/kpi/*
 *   - the "preset" label the picker should show
 *   - a derived `isPartialPeriod` hint for KPI tile labelling
 *
 * Persisted to localStorage so picking a window survives a refresh while we
 * still have no auth (anchor for the future per-user preference, Day 10+).
 *
 * Anchor date: the dataset cutoff (Olist ends ~2018-09-04). We compute presets
 * relative to that, *not* `new Date()`, so the default 90-day window doesn't
 * silently drift outside the data and produce empty charts.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

/** Olist data cutoff — single source of truth for default windows.
 *  Will be replaced by the live `data_as_of` from /api/v1/kpi/summary
 *  via `setDataAsOf` as soon as the dashboard mounts. */
export const DEFAULT_DATA_CUTOFF = "2018-09-04";

export type RangePreset = "7d" | "30d" | "90d" | "365d" | "all" | "custom";

interface TimeRangeState {
  /** ISO date (YYYY-MM-DD). null = no lower bound (full dataset). */
  start: string | null;
  /** ISO date (YYYY-MM-DD). null = no upper bound (full dataset). */
  end: string | null;
  /** Last applied preset label — used by the picker UI to highlight a chip. */
  preset: RangePreset;
  /** Cached dataset cutoff; backend echoes this in /kpi/summary.data_as_of. */
  dataAsOf: string | null;

  /** Imperative setters. */
  setPreset: (p: RangePreset) => void;
  setCustom: (start: string, end: string) => void;
  setDataAsOf: (d: string | null) => void;
  reset: () => void;
}

function isoDayShift(anchorIso: string, deltaDays: number): string {
  const d = new Date(`${anchorIso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + deltaDays);
  return d.toISOString().slice(0, 10);
}

/** Resolve a preset to [start, end] given a cutoff anchor.
 *  "all" → both null (full dataset). */
export function rangeForPreset(
  preset: RangePreset,
  anchor: string,
): { start: string | null; end: string | null } {
  switch (preset) {
    case "7d":
      return { start: isoDayShift(anchor, -6), end: anchor };
    case "30d":
      return { start: isoDayShift(anchor, -29), end: anchor };
    case "90d":
      return { start: isoDayShift(anchor, -89), end: anchor };
    case "365d":
      return { start: isoDayShift(anchor, -364), end: anchor };
    case "all":
      return { start: null, end: null };
    case "custom":
      // Custom keeps whatever was last set; never derived from preset alone.
      return { start: null, end: null };
  }
}

const DEFAULT_PRESET: RangePreset = "90d";
const DEFAULT_RANGE = rangeForPreset(DEFAULT_PRESET, DEFAULT_DATA_CUTOFF);

export const useTimeRange = create<TimeRangeState>()(
  persist(
    (set, get) => ({
      start: DEFAULT_RANGE.start,
      end: DEFAULT_RANGE.end,
      preset: DEFAULT_PRESET,
      dataAsOf: null,

      setPreset: (preset) => {
        const anchor = get().dataAsOf ?? DEFAULT_DATA_CUTOFF;
        const { start, end } = rangeForPreset(preset, anchor);
        set({ preset, start, end });
      },

      setCustom: (start, end) => set({ preset: "custom", start, end }),

      setDataAsOf: (dataAsOf) => {
        // If we're on a preset, re-anchor the window to the freshly known cutoff.
        const { preset } = get();
        if (dataAsOf && preset !== "custom" && preset !== "all") {
          const { start, end } = rangeForPreset(preset, dataAsOf);
          set({ dataAsOf, start, end });
        } else {
          set({ dataAsOf });
        }
      },

      reset: () =>
        set({
          preset: DEFAULT_PRESET,
          start: DEFAULT_RANGE.start,
          end: DEFAULT_RANGE.end,
        }),
    }),
    { name: "pfa.timeRange" },
  ),
);

/** Pure helper for the KPI tile / TopBar — true when the requested window
 *  extends past the actual data cutoff (Olist historical case). */
export function isPartialPeriod(
  end: string | null,
  dataAsOf: string | null,
): boolean {
  if (!end || !dataAsOf) return false;
  return end > dataAsOf;
}
