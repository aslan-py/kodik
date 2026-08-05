"use client"

import { Button } from "@/components/ui/Button";
import { useRouter } from "next/navigation";

export default function NotFound() {
  const router = useRouter();
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
      <div className="flex justify-center text-center flex-col gap-4">
        <h2 className="text-[88px] font-semibold text-(--color-accent)">404</h2>
        <h3 className="text-3xl font-semibold">Страница не найдена</h3>
        <p className="text-[14px] text-(--color-muted)">
          Возможно, ссылка устарела или страница была перемещена.
        </p>
        <div className="max-w-40 flex flex-col m-auto gap-4 justify-center">
          <Button variant="primary">Обновить</Button>
          <Button variant="tertiary" size="small" onClick={() => router.back()}>
            Вернуться назад
          </Button>
        </div>
      </div>
    </div>
  );
}
