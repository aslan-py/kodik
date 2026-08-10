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

/** Маппинг приоритетов для CSS-класса */
export function priorityClass(priority: string): string {
  if (priority === "П1") return "priority priority-accent";
  if (priority === "П2") return "priority priority-strong";
  return "priority priority-muted";
}