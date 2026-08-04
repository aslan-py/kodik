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

export function formatDate(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function formatShort(d: Date): string {
  return `${d.getDate()} ${shortMonthNames[d.getMonth()]}`;
}

export const dateToDayView = () => {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
  }).format(new Date());
};

/** Парсит "DD.MM.YYYY" → Date */
export function parseDotDate(d: string): Date {
  const [day, month, year] = d.split(".").map(Number);
  return new Date(year, month - 1, day);
}

/* ──────────────── Для CardTask ──────────────── */

/** ISO-строка → "26 июл, 10:47" */
export function formatDateWithTime(dateStr: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return `${d.getDate()} ${shortMonthNames[d.getMonth()]}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** "MM-DD-YYYY HH:mm" → относительный формат (Сегодня / Завтра / Послезавтра / Через N дней) */
export function formatDeadline(deadline: string): string {
  if (!deadline) return "";
  const match = deadline.match(/^(\d{2})-(\d{2})-(\d{4}) (\d{2}):(\d{2})$/);
  if (!match) return deadline;
  const [, month, day, year, hour, minute] = match;
  const now = new Date();
  const date = new Date(Number(year), Number(month) - 1, Number(day));
  const diffDays = Math.ceil(
    (date.getTime() - new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()) / 86400000
  );
  const time = `${hour}:${minute}`;
  if (diffDays === 0) return `Сегодня, ${time}`;
  if (diffDays === 1) return `Завтра, ${time}`;
  if (diffDays === 2) return `Послезавтра, ${time}`;
  if (diffDays > 2 && diffDays <= 7) return `Через ${diffDays} дней, ${time}`;
  return `${day}.${month}.${year} ${time}`;
}

/* ──────────────── Для DateInput ──────────────── */

/** MM-DD-YYYY HH:mm → YYYY-MM-DDTHH:mm (для datetime-local) */
export function toLocalValue(value: string): string {
  if (!value) return "";
  const match = value.match(/^(\d{2})-(\d{2})-(\d{4}) (\d{2}):(\d{2})$/);
  if (!match) return "";
  const [, month, day, year, hour, minute] = match;
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

/** YYYY-MM-DDTHH:mm → MM-DD-YYYY HH:mm */
export function toDisplayValue(localValue: string): string {
  if (!localValue) return "";
  const date = new Date(localValue);
  if (isNaN(date.getTime())) return "";
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const year = date.getFullYear();
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${month}-${day}-${year} ${hour}:${minute}`;
}

/** Разница в целых днях между двумя датами (без времени) */
export function daysDiff(a: Date, b: Date): number {
  const ta = new Date(a.getFullYear(), a.getMonth(), a.getDate());
  const tb = new Date(b.getFullYear(), b.getMonth(), b.getDate());
  return Math.round((tb.getTime() - ta.getTime()) / 86400000);
}

/** "MM-DD-YYYY HH:mm" → относительный формат для DateInput */
export function formatDateDisplay(rawValue: string): string {
  if (!rawValue) return "";
  const match = rawValue.match(/^(\d{2})-(\d{2})-(\d{4}) (\d{2}):(\d{2})$/);
  if (!match) return rawValue;
  const [, month, day, year, hour, minute] = match;
  const date = new Date(+year, +month - 1, +day, +hour, +minute);
  if (isNaN(date.getTime())) return rawValue;
  const now = new Date();
  const diff = daysDiff(now, date);
  const time = `${hour}:${minute}`;
  if (diff === 0) return `Сегодня, ${time}`;
  if (diff === 1) return `Завтра, ${time}`;
  if (diff === 2) return `Послезавтра, ${time}`;
  if (diff >= 3 && diff <= 7) return `Через ${diff} дней, ${time}`;
  return `${day}.${month}.${year} ${time}`;
}