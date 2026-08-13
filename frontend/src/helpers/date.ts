/** Сокращённые названия месяцев для формата "DD MMM" (напр. "5 авг") */
export const shortMonthNames = [
  "янв",
  "фев",
  "мар",
  "апр",
  "май",
  "июн",
  "июл",
  "авг",
  "сен",
  "окт",
  "ноя",
  "дек",
];

/** Date → "YYYY-MM-DD" (для запросов к бэку, инпутов type=date и т.п.) */
export function formatDate(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** Date → "5 авг" (короткий формат для отображения пользователю) */
export function formatShort(d: Date): string {
  return `${d.getDate()} ${shortMonthNames[d.getMonth()]}`;
}

/** Текущая дата → "5 августа" (полное название месяца, локаль ru-RU) */
export const dateToDayView = () => {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
  }).format(new Date());
};

/**
 * "YYYY-MM-DD" → "DD.MM.YYYY" (для отображения даты с бэка пользователю)
 * ⚠️ несмотря на название, разделитель — точка, а не дефис
 */
export function toDisplayDate(d: string): string {
  if (!d) return "";
  const [year, month, day] = d.split("-");
  return `${day}.${month}.${year}`;
}

/**
 * "DD-MM-YYYY" → "YYYY-MM-DD" (для отправки даты на бэк)
 */
export function toISODate(d: string): string {
  if (!d) return "";
  const [day, month, year] = d.split("-");
  return `${year}-${month}-${day}`;
}

/** "DD.MM.YYYY" → Date (парсинг даты, введённой/показанной пользователю) */
export function parseDotDate(d: string): Date {
  const [day, month, year] = d.split(".").map(Number);
  return new Date(year, month - 1, day);
}

/** "YYYY-MM-DD" → Date, без сдвига по таймзоне (фиксируем время 00:00 локально) */
export function parseISODate(d: string): Date | undefined {
  if (!d) return undefined;
  return new Date(`${d}T00:00:00`);
}

/* ──────────────── Для CardTask ──────────────── */

/** ISO-строка с датой и временем → "26 июл, 10:47" */
export function formatDateWithTime(dateStr: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return `${d.getDate()} ${shortMonthNames[d.getMonth()]}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** ISO-строка с временем ("2026-08-05T18:15:28.912940Z") → "DD.MM.YYYY" (локальная таймзона браузера) */
export function toDotDate(isoString: string): string {
  if (!isoString) return "";
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return "";
  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const year = d.getFullYear();
  return `${day}.${month}.${year}`;
}
/**
 * "YYYY-MM-DD" → разница в днях с сегодня + распарсенная дата.
 * Общая база для formatDeadline и компонентов типа DeadlineBadge,
 * чтобы не пересчитывать diffDays в нескольких местах.
 */
export function getDeadlineStatus(
  deadline: string,
): { date: Date; diffDays: number } | null {
  const date = parseISODate(deadline);
  if (!date) return null;
  const now = new Date();
  const diffDays = Math.ceil(
    (date.getTime() -
      new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()) /
      86400000,
  );
  return { date, diffDays };
}
/**
 * "YYYY-MM-DD" → относительный формат даты
 * ("Просрочено на N дней" для прошедших дат /
 * "Сегодня" / "Завтра" / "Послезавтра" /
 * "Через N дней" для 3–7 дней, иначе "DD.MM.YYYY")
 */
export function formatDeadline(deadline: string): string {
  if (!deadline) return "";
  const status = getDeadlineStatus(deadline);
  if (!status) return deadline;
  const { diffDays } = status;
  if (diffDays < 0) return `Просрочено на ${Math.abs(diffDays)} дней`;
  if (diffDays === 0) return "Сегодня";
  if (diffDays === 1) return "Завтра";
  if (diffDays === 2) return "Послезавтра";
  if (diffDays > 2 && diffDays <= 7) return `Через ${diffDays} дней`;
  return toDisplayDate(deadline);
}
export type PeriodPreset =
  | "today" | "7days" | "30days" | "thisMonth" | "lastMonth";

export function getPresetRange(
  period: PeriodPreset,
  now: Date = new Date(),
): { from: string; to: string } {
  const today = formatDate(now);
  switch (period) {
    case "today":
      return { from: today, to: today };
    case "7days": {
      const from = new Date(now);
      from.setDate(from.getDate() - 6);
      return { from: formatDate(from), to: today };
    }
    case "30days": {
      const from = new Date(now);
      from.setDate(from.getDate() - 29);
      return { from: formatDate(from), to: today };
    }
    case "thisMonth": {
      const from = new Date(now.getFullYear(), now.getMonth(), 1);
      return { from: formatDate(from), to: today };
    }
    case "lastMonth": {
      const from = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const to = new Date(now.getFullYear(), now.getMonth(), 0);
      return { from: formatDate(from), to: formatDate(to) };
    }
  }
}