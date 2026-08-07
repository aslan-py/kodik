"use client";

import Image from "next/image";
import Link from "next/link";
import { ProtectedRoute } from "@/components/protected-route/protected-route";

export default function AuthLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ProtectedRoute onlyUnAuth>
      <div className="flex h-full w-full">
        {/* Левая часть — форма */}
        <div className="flex-1 flex-col overflow-y-auto flex min-h-full justify-between p-6 bg-(--color-light) sm:pl-24">
          <div className="flex items-start justify-between">
            <div className="font-semibold text-xl">
              Kodik+
              <span className="block pt-0.5 font-medium text-(--color-secondary) text-xs">
                Конкурентная разведка
              </span>
            </div>
            <nav className="flex gap-4 text-sm">
              <Link
                href="/login"
                className="text-(--color-secondary) hover:underline"
              >
                Вход
              </Link>
              <Link
                href="/registration"
                className="text-(--color-secondary) hover:underline"
              >
                Регистрация
              </Link>
            </nav>
          </div>
          <div className="flex-1 flex items-center">{children}</div>
          <p className="text-xs text-(--color-muted)">
            © 2026 Kodik. Все права защищены.
          </p>
        </div>

        {/* Правая часть — декоративная панель (скрыта на xl и ниже) */}
        <div className="hidden xl:flex w-[45%] bg-[#EEF4FF] relative overflow-hidden flex-col justify-end">
          <div className="pl-16 pb-60 z-10">
            <p className="text-4xl font-semibold mb-3.5">
              Вся картина рынка — в одном месте
            </p>
            <span className="text-base">
              Единое пространство конкурентной разведки
            </span>
          </div>
          <div className="bg-[#ADBFED] absolute top-0 left-[60%] w-125 h-125 blur-[160px] rounded-b-full"></div>
          <div className="bg-[#FCFCFA] absolute bottom-0 left-[60%] w-100 h-100 blur-[1600px] rounded-b-full"></div>
          <Image
            loading="eager"
            className="absolute top-0 right-0 w-full h-full object-cover"
            src={"GraphicLogin.svg"}
            width={600}
            height={540}
            alt="GraphicLogin"
          />
        </div>
      </div>
    </ProtectedRoute>
  );
}
