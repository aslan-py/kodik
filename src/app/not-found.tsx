import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
      <h2 className="text-xl font-semibold text-(--color-ink)">
        Страница не найдена
      </h2>
      <p className="text-sm text-(--color-secondary)">
        Запрашиваемая страница не существует.
      </p>
      <Link
        href="/incidents"
        className="rounded-lg bg-(--color-accent) px-4 py-2 text-sm text-white transition-colors hover:opacity-90"
      >
        Перейти к событиям
      </Link>
    </div>
  );
}