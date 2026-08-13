// types.ts
import type { PriorityLevel, Tonality } from "@/api/showcaseApi";

export type FilterOption<T extends string = string> = {
  label: string;
  value: T;
};
export const TASK_STATUSES = {
  NEW: "open",
  IN_PROGRESS: "in_progress",
  DONE: "done",
} as const;

export type TaskStatus = (typeof TASK_STATUSES)[keyof typeof TASK_STATUSES];
// type TaskStatus = typeof TASK_STATUSES[keyof typeof TASK_STATUSES];

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  [TASK_STATUSES.NEW]: "Новая",
  [TASK_STATUSES.IN_PROGRESS]: "В работе",
  [TASK_STATUSES.DONE]: "Готово",
};
// function isTaskStatus(v: string): v is TaskStatus {
//   return (Object.values(TASK_STATUSES) as string[]).includes(v);
// }
// // ...
// status: isTaskStatus(filterValues.status) ? filterValues.status : undefined
export const TASK_STATUS_OPTIONS: FilterOption<TaskStatus>[] = Object.values(
  TASK_STATUSES,
).map((value) => ({
  value,
  label: TASK_STATUS_LABELS[value],
}));

export const USER_ROLE = {
  PENDING: "pending",
  VIEWER: "viewer",
  ANALYST: "analyst",
  ADMIN: "admin",
} as const;

export const PRIORITY_LEVEL = {
  P1: "П1",
  P2: "П2",
  P3: "П3",
  P4: "П4",
} as const;

export const PRIORITY_OPTIONS: FilterOption<PriorityLevel>[] = [
  { label: "П1", value: "p1" },
  { label: "П2", value: "p2" },
  { label: "П3", value: "p3" },
  { label: "П4", value: "p4" },
];
export const TONALITY_LEVEL = {
  positive: "positive",
  neutral: "neutral",
  negative: "negative",
  alarming: "alarming",
  irrelevant: "irrelevant",
} as const;

export const PRIORITY_LABELS: Record<PriorityLevel, string> = {
  p1: "П1",
  p2: "П2",
  p3: "П3",
  p4: "П4",
};

// Опции статуса для фильтров триггеров и конкурентов ("active"/"!active" — значения, ожидаемые бэком)
export const MONITORING_STATUS_OPTIONS: FilterOption[] = [
  { label: "Активный", value: "active" },
  { label: "Приостановлен", value: "!active" },
];

export const TONALITY_OPTIONS: FilterOption<Tonality>[] = [
  { label: "Позитивная", value: "positive" },
  { label: "Нейтральная", value: "neutral" },
  { label: "Негативная", value: "negative" },
  { label: "Тревожная", value: "alarming" },
  { label: "Не релевантно", value: "irrelevant" },
];

export function matchOptionValue<T extends string>(
  options: FilterOption<T>[],
  rawLabel: string | undefined | null,
): T | "" {
  if (!rawLabel) return "";
  const normalized = rawLabel.trim().toLowerCase();
  const match = options.find(
    (o) =>
      o.label.toLowerCase() === normalized ||
      o.value.toLowerCase() === normalized,
  );
  return match ? match.value : "";
}
