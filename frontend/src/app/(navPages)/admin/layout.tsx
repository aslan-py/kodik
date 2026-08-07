"use client";

import { ProtectedRoute } from "@/components/protected-route/protected-route";

export default function AdminLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <ProtectedRoute requiredRoles={["admin"]}>{children}</ProtectedRoute>;
}