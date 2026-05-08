/* ─── Format Utilities ─── */

export const formatNumber = (n: number): string =>
  new Intl.NumberFormat("en-US").format(Math.round(n));

export const formatCurrency = (n: number): string =>
  `R$${new Intl.NumberFormat("en-US").format(Math.round(n))}`;

export const formatK = (n: number): string =>
  n >= 1000 ? `${(n / 1000).toFixed(1)}k` : formatNumber(n);

export const CHART_COLORS = [
  "#3b82f6", "#8b5cf6", "#06b6d4", "#10b981",
  "#f59e0b", "#f43f5e", "#ec4899", "#6366f1",
];
