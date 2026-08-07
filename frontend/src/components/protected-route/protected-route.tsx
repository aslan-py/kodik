"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { hasAccess, type Permission } from "@/store/authSlice";
import Loader from "@/app/loading";

type ProtectedRouteProps = {
  onlyUnAuth?: boolean;
  requiredRoles?: Permission[];
  children: React.ReactNode;
};

function AuthLoader() {
  return (
   <Loader />
  );
}

type Decision =
  | "loading"
  | "render"
  | "redirect-to-login"
  | "redirect-to-home";

export function ProtectedRoute({
  onlyUnAuth = false,
  requiredRoles,
  children,
}: ProtectedRouteProps) {
  const { user, isAuthenticated, status } = useAuth();
  const router = useRouter();

  // На сервере всегда рендерим loader (status там всегда "loading" —
  // SessionRestore выполняется только на клиенте). Флаг mounted гарантирует,
  // что первый клиентский рендер тоже будет loader'ом, каким бы ни было
  // реальное состояние Redux на клиенте — иначе первый клиентский рендер
  // может разойтись с серверным и React выдаст hydration mismatch.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const decision: Decision = (() => {
    if (!mounted || status === "loading") return "loading";

    if (onlyUnAuth) {
      return isAuthenticated ? "redirect-to-home" : "render";
    }

    if (!isAuthenticated) return "redirect-to-login";
    if (!hasAccess(user?.role, requiredRoles)) return "redirect-to-home";

    return "render";
  })();

  useEffect(() => {
    if (decision === "redirect-to-home") router.replace("/");
    if (decision === "redirect-to-login") router.replace("/login");
  }, [decision, router]);

  if (decision === "loading") return <AuthLoader />;
  if (decision === "render") return <>{children}</>;

  return null;
}