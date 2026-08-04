"use client";

import { ProtectedRoute } from "@/components/protected-route/protected-route";

export default function AdminPagesLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <ProtectedRoute requiredPermission="admin">{children}</ProtectedRoute>;
}