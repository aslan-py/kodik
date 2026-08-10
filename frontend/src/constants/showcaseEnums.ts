import type { PriorityLevel, Tonality } from "@/api/showcaseApi";

export const priorityOptions: { label: string; value: PriorityLevel }[] = [
  { label: "П1", value: "p1" },
  { label: "П2", value: "p2" },
  { label: "П3", value: "p3" },
  { label: "П4", value: "p4" },
];

export const tonalityOptions: { label: string; value: Tonality }[] = [
  { label: "Позитивная", value: "positive" },
  { label: "Нейтральная", value: "neutral" },
  { label: "Негативная", value: "negative" },
  { label: "Тревожная", value: "alarming" },
  { label: "Не релевантно", value: "irrelevant" },
];

export function matchOptionValue<T extends string>(
  options: { label: string; value: T }[],
  rawLabel: string | undefined | null,
): T | "" {
  if (!rawLabel) return "";
  const normalized = rawLabel.trim().toLowerCase();
  const match = options.find((o) => o.label.toLowerCase() === normalized);
  return match ? match.value : "";
}