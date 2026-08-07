"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
      <h2 className="text-xl font-semibold text-(--color-ink)">
        Что-то пошло не так
      </h2>
      <p className="text-sm text-(--color-secondary)">
        {error.message || "Произошла непредвиденная ошибка."}
      </p>
      <button
        onClick={() => reset()}
        className="rounded-lg bg-(--color-accent) px-4 py-2 text-sm text-white transition-colors hover:opacity-90"
      >
        Попробовать снова
      </button>
    </div>
  );
}