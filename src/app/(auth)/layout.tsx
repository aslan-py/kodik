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
      <>
      {children}
      <div className="flex w-full bg-[#EEF4FF] relative">
        <div className="pl-60.5 pb-60.5 self-end z-10">
          <p className="text-4xl font-semibold mb-3.5">
            Вся картина рынка — в одном месте
          </p>
          <span className="text-base">
            Единое пространство конкурентной разведки
          </span>
        </div>
        <div className="bg-[#ADBFED] fixed top-0 left-[70%] overflow-hidden w-125 h-125 blur-[160px] rounded-b-full"></div>
        <div className="bg-[#FCFCFA] fixed overflow-hidden bottom-0 left-[70%] w-100 h-100 blur-[1600px] rounded-b-full"></div>
        <Image
          loading="eager"
          className="absolute top-0 right-0 w-full h-full object-cover"
          src={"GraphicLogin.svg"}
          width={600}
          height={540}
          alt="GraphicLogin"
        ></Image>
      </div>
      </>
    </ProtectedRoute>
  );
}
