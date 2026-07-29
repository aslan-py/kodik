"use client";

import { useState } from "react";
import Sidebar from "./Sidebar";

export default function SidebarLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div className="flex h-full w-full">
      <Sidebar isCollapsed={isCollapsed} onToggle={() => setIsCollapsed((v) => !v)} />
      <main className="flex flex-1 flex-col overflow-auto">{children}</main>
    </div>
  );
}