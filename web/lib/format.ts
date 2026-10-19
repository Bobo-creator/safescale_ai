import type { Signal } from "./types";

export const percent = (share: number) => `${Math.round(share * 100)}%`;

export const lift = (x: number) => `${x.toFixed(1)}×`;

export const CATEGORY_LABELS: Record<string, string> = {
  fire_overheating: "Fire / overheating",
  burn: "Burn",
  electrical_shock: "Electrical shock",
  choking: "Choking",
  suffocation_strangulation: "Suffocation / strangulation",
  laceration: "Laceration",
  fall: "Fall / tip-over",
  entrapment: "Entrapment / crush",
  poisoning: "Poisoning / toxic exposure",
  crash_loss_of_control: "Crash / loss of control",
  drowning: "Drowning",
  other: "Other / unspecified injury",
};

export const categoryLabel = (code: string) => CATEGORY_LABELS[code] ?? code;

export const SIGNAL_STYLES: Record<Signal, { text: string; bg: string; bar: string }> = {
  HIGH: { text: "text-high", bg: "bg-high-soft", bar: "bg-high" },
  MODERATE: { text: "text-moderate", bg: "bg-moderate-soft", bar: "bg-moderate" },
  LOW: { text: "text-low", bg: "bg-low-soft", bar: "bg-low" },
};

export const SIGNAL_WORDS: Record<Signal, string> = {
  HIGH: "High",
  MODERATE: "Moderate",
  LOW: "Low",
};

export function joinLabels(labels: string[]): string {
  if (labels.length <= 1) return labels.join("");
  return `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "Date unknown";
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
