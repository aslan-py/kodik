"use client";

// import { useRouter } from "next/navigation";
// import { useEffect } from "react";
// import { useAuth } from "@/hooks/useAuth";
import type { Permission } from "@/store/authSlice";

type ProtectedRouteProps = {
  onlyUnAuth?: boolean;
  requiredPermission?: Permission;
  children: React.ReactNode;
};

// export function ProtectedRoute({
//   onlyUnAuth,
//   requiredPermission,
//   children,
// }: ProtectedRouteProps) {
//   const { user, isAuthenticated } = useAuth();
//   const router = useRouter();

//   useEffect(() => {
//     if (onlyUnAuth) {
//       // Страницы логина/регистрации — только для неавторизованных
//       if (isAuthenticated) {
//         router.replace("/incidents");
//       }
//     } else {
//       // Остальные страницы — только для авторизованных
//       if (!isAuthenticated) {
//         router.replace("/login");
//       } else if (
//         requiredPermission &&
//         !user?.permissions.includes(requiredPermission)
//       ) {
//         router.replace("/incidents");
//       }
//     }
//   }, [isAuthenticated, user, onlyUnAuth, requiredPermission, router]);

//   // Пока проверка не пройдена — ничего не рендерим
//   if (onlyUnAuth) {
//     if (isAuthenticated) return null;
//     return <>{children}</>;
//   }

//   if (!isAuthenticated) return null;
//   if (requiredPermission && !user?.permissions.includes(requiredPermission))
//     return null;

//   return <>{children}</>;
// }

export function ProtectedRoute({
  onlyUnAuth,
  requiredPermission,
  children,
}: ProtectedRouteProps) {
  // ТЕСТОВЫЙ РЕЖИМ: защита отключена, все роуты доступны
  return <>{children}</>;
}