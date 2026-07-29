interface Props {
  lastUpdated?: Date | string | null;
  className?: string;
}

export default function DataUpdateStatus({ lastUpdated, className = '' }: Props) {
  const now = new Date();

  const updated = lastUpdated
    ? typeof lastUpdated === 'string' ? new Date(lastUpdated) : lastUpdated
    : null;

  const valid = updated && !isNaN(updated.getTime());
  const diffMinutes = valid ? Math.floor((now.getTime() - updated.getTime()) / 60000) : Infinity;
  const timeStr = valid
    ? `${String(updated.getHours()).padStart(2, '0')}:${String(updated.getMinutes()).padStart(2, '0')}`
    : '';

  const color = diffMinutes >= 60 ? 'bg-yellow-500' : 'bg-green-500';

  let label: string;
  if (!valid) {
    label = 'Дата обновления неизвестна';
  } else if (diffMinutes < 10) {
    label = diffMinutes <= 1
      ? 'Данные обновлены меньше минуты назад'
      : `Данные обновлены ${diffMinutes} мин. назад`;
  } else if (diffMinutes >= 60) {
    label = `Последнее обновление: сегодня, ${timeStr}`;
  } else {
    label = `Данные обновлены ${diffMinutes} мин. назад`;
  }

  return (
    <div className={`flex items-center gap-2 text-sm text-(--color-secondary) ${className}`}>
      <span className={`inline-block w-2.5 h-2.5 rounded-full ${color}`} />
      <span>{label}</span>
    </div>
  );
}
