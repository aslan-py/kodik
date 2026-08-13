"use client";

import SidebarLayout from "@/components/layout/SidebarLayout";
import { ProtectedRoute } from "@/components/protected-route/protected-route";

export default function NavPagesLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ProtectedRoute requiredRoles={["viewer", "analyst", "admin"]}>
      <SidebarLayout>{children}</SidebarLayout>
    </ProtectedRoute>
  );
}
