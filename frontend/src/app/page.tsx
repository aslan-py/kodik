"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import Loader from "@/app/loading";
// ⚠️ поправьте путь под ваш проект
import { type Permission } from "@/store/authSlice";
import { ProtectedRoute } from "@/components/protected-route/protected-route";
import { Button } from "@/components/ui/Button";

// "/" — единственная страница, доступная pending-пользователю, поэтому
// она должна пускать все роли явно (дефолт hasAccess исключает pending).
export const ALL_ROLES: Permission[] = [
  "pending",
  "viewer",
  "analyst",
  "admin",
];

function HomeContent() {
  const { user } = useAuth();
  const { logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (user && user.role !== "pending") {
      router.replace("/incidents");
    }
  }, [user, router]);

  if (user?.role === "pending") {
    return (
      <div className="flex flex-col gap-4 min-h-screen w-full items-center justify-center p-6 text-center">
        <p className="text-sm text-(--color-muted)">
          Ваша роль ещё не назначена администратором. Доступ к разделам появится
          после изменения роли в системе.
        </p>
        <Button
          className="block"
          onClick={() => {
            logout();
          }}
        >
          Выйти из аккаунта
        </Button>
      </div>
    );
  }

  // не-pending: показываем лоадер, пока useEffect переводит на /incidents,
  // чтобы не было пустого (белого) кадра после входа
  return <Loader />;
}

export default function HomePage() {
  return (
    <ProtectedRoute requiredRoles={ALL_ROLES}>
      <HomeContent />
    </ProtectedRoute>
  );
}
