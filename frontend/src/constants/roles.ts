import { FilterOption } from "@/types/types";

export const ROLE_OPTIONS: FilterOption[] = [
  { label: "Ожидает подтверждения", value: "pending" },
  { label: "Менеджер", value: "viewer" },
  { label: "Аналитик", value: "analyst" },
  { label: "Администратор", value: "admin" },
];

export const ROLE_LABELS: Record<string, string> = Object.fromEntries(
  ROLE_OPTIONS.map((o) => [o.value, o.label]),
);