/** Маппинг статусов задач */
export function statusLabel(status: string): string {
  if (status === "new") return "Новая";
  if (status === "in_progress") return "В работе";
  if (status === "done") return "Выполнена";
  return status;
}

/** Маппинг статусов для CSS-класса */
export function statusClass(status: string): string {
  if (status === "Новая" || status === "Новое" || status === "new") return "tonality tonality-neutral";
  if (status === "В работе" || status === "in_progress") return "tonality tonality-positive";
  if (status === "Выполнена" || status === "done") return "tonality tonality-positive";
  return "tonality tonality-neutral";
}

/** Маппинг приоритетов для CSS-класса */
export function priorityClass(priority: string): string {
  if (priority === "П1") return "priority priority-accent";
  if (priority === "П2") return "priority priority-strong";
  return "priority priority-muted";
}