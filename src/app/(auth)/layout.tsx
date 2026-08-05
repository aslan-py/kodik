"use client";

import Image from "next/image";
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
        <div className="flex-1 overflow-y-auto">{children}</div>

        {/* Правая часть — декоративная панель (скрыта на xl и ниже) */}
        <div className="hidden xl:flex w-[45%] bg-[#EEF4FF] relative overflow-hidden flex-col justify-end">
          <div className="pl-16 pb-16 z-10">
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
