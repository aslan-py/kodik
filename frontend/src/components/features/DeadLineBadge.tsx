import { formatShort, getDeadlineStatus, toDisplayDate } from "@/helpers/date";

interface DeadlineBadgeProps {
  deadline?: string | null; // "YYYY-MM-DD"
  isDone?: boolean;
}

/** Конец суток (23:59:59.999) для переданной даты */
function getEndOfDay(d: Date): Date {
  const end = new Date(d);
  end.setHours(23, 59, 59, 999);
  return end;
}

/** мс → "Осталось X ч Y мин" (или "Осталось X д Y ч" если больше суток) */
function formatRemaining(ms: number): string {
  if (ms <= 0) return "Истекает";
  const totalMinutes = Math.floor(ms / 60000);
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) return `Осталось ${days} д ${hours} ч`;
  if (hours > 0) return `Осталось ${hours} ч ${minutes} мин`;
  return `Осталось ${minutes} мин`;
}

export function DeadlineBadge({ deadline, isDone }: DeadlineBadgeProps) {
  if (!deadline) return <span className="text-(--color-muted)">—</span>;

  const status = getDeadlineStatus(deadline);
  if (!status) return <span className="text-(--color-muted)">—</span>;

  const { date, diffDays } = status;

  let dateLabel = formatShort(date); // "5 авг"
  let statusLabel: string;
  let dateClass = "text-(--color-ink)";
  let statusClass = "text-(--color-muted)";

  if (isDone) {
    statusLabel = "Выполнено";
    dateClass = "text-(--color-muted)";
    statusClass = "text-green-600";
  } else if (diffDays < 0) {
    statusLabel = `Просрочено на ${Math.abs(diffDays)} дней`;
    dateClass = "text-red-600";
    statusClass = "text-red-600";
  } else if (diffDays === 0) {
    dateLabel = `Сегодня, ${formatShort(date)}`;
    dateClass = "text-blue-600";
    statusLabel = formatRemaining(getEndOfDay(date).getTime() - Date.now());
  } else if (diffDays === 1) {
    dateLabel = `Завтра, ${formatShort(date)}`;
    dateClass = "text-blue-700";
    statusLabel = formatRemaining(getEndOfDay(date).getTime() - Date.now());
  } else if (diffDays === 2) {
    statusLabel = "Послезавтра";
    dateClass = "text-blue-800";
  } else if (diffDays <= 7) {
    statusLabel = `Через ${diffDays} дней`;
  } else {
    statusLabel = `По плану`;
  }

  return (
    <div className="flex flex-col leading-tight">
      <span className={`font-medium text-sm ${dateClass}`}>{dateLabel}</span>
      <span className={`text-xs ${statusClass}`}>{statusLabel}</span>
    </div>
  );
}