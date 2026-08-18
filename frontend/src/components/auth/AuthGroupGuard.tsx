// components/auth/AuthGroupGuard.tsx
"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import Loader from "@/app/(navPages)/loading";

const INCIDENTS_PATH = "/incidents";
const LOGIN_PATH = "/login";
const PENDING_PATH = "/pending";

type Decision =
  | "loading"
  | "render"
  | "redirect-to-pending"
  | "redirect-to-login"
  | "redirect-to-home";

export function AuthGroupGuard({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isPending = isAuthenticated && user?.role === "pending";
  // не используем hasAccess(role, ["pending"]) тут специально —
  // hasAccess отвечает "разрешена ли эта роль", а нам нужно ровно
  // "это pending", что просто прямое сравнение

  const decision: Decision = (() => {
    if (!mounted || status === "loading") return "loading";

    if (isPending) {
      return pathname === PENDING_PATH ? "render" : "redirect-to-pending";
    }

    if (isAuthenticated) {
      // авторизован и не pending — нечего делать в auth-группе вообще
      return "redirect-to-home";
    }

    // не авторизован — доступны login/register, но не pending
    return pathname === PENDING_PATH ? "redirect-to-login" : "render";
  })();

  useEffect(() => {
    if (decision === "redirect-to-pending") router.replace(PENDING_PATH);
    if (decision === "redirect-to-login") router.replace(LOGIN_PATH);
    if (decision === "redirect-to-home") router.replace(INCIDENTS_PATH);
  }, [decision, router]);

  if (decision === "loading") return <Loader />;
  if (decision === "render") return <>{children}</>;

  return null;
}