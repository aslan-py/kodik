/** Маппинг статусов задач */
export function statusLabel(status: string): string {
  if (status === "open" || status === "new") return "Новая";
  if (status === "in_progress") return "В работе";
  if (status === "done") return "Выполнена";
  return status;
}

/** Маппинг статусов для CSS-класса */
export function statusClass(status: string): string {
  if (status === "open" || status === "new") return "status-task status-task-open";
  if (status === "in_progress") return "status-task status-task-progress";
  if (status === "done") return "status-task status-task-done";
  return "status-task status-task-open";
}

/** Маппинг тональности для CSS-класса */
export function tonalityClass(tonality: string): string {
  if (tonality === "позитивная") return "tonality tonality-positive";
  if (tonality === "нейтральная") return "tonality tonality-neutral";
  if (tonality === "нерелевантная") return "tonality tonality-spam";
  return "tonality tonality-negative";
}

/** Маппинг приоритетов для CSS-класса */
export function priorityClass(priority: string): string {
  if (priority === "П1") return "priority priority-accent";
  if (priority === "П2") return "priority priority-strong";
  return "priority priority-muted";
}