"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import UserSidebarProfile from "../user/UserSidebarProfile";
import { Icon } from "@/components/ui/Icon/Icon";

const navItems = [
  { href: "/incidents", label: "События" },
  { href: "/alerts", label: "Уведомления" },
  { href: "/dashboard", label: "Дашборд" },
  { href: "/sources", label: "Источники" },
  { href: "/competitors", label: "Конкуренты" },
];

export default function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const pathname = usePathname();

  return (
    <aside
      className={`relative flex pb-6 h-full flex-col border-r border-(--color-border) bg-(--color-dark) transition-all duration-300 ${isCollapsed ? "w-16" : "w-64"}`}
    >
      <div className="pt-8 px-5 pb-16">
        <div className="flex items-center gap-3">
          <div className={isCollapsed ? "hidden" : ""}>
            <h1 className="text-lg font-semibold leading-tight text-white">
              Kodik+
            </h1>
            <p className="text-xs text-(--color-secondary)">
              Конкурентная разведка
            </p>
          </div>
          {isCollapsed && (
            <span className="text-lg font-semibold text-white mx-auto">K+</span>
          )}
        </div>
      </div>

      <nav className="flex-1 px-3">
        <ul className="space-y-1">
          {navItems.map((item, index) => {
            const isActive = pathname === item.href;

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`block rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${isCollapsed ? "text-center" : ""} ${
                    isActive
                      ? "bg-[#222A39] font-semibold text-white"
                      : " text-(--color-text-navbar) hover:bg-zinc-800"
                  }`}
                  title={isCollapsed ? item.label : undefined}
                >
                  {isCollapsed ? item.label.charAt(0) : item.label}
                </Link>
                {/* {index === 2 && (
                  <div className="my-2 h-px bg-(--color-border)" />
                )} */}
              </li>
            );
          })}
        </ul>
      </nav>
      <div className={isCollapsed ? "hidden" : ""}>
        <UserSidebarProfile />
      </div>
      <button
        onClick={() => setIsCollapsed((v) => !v)}
        className="absolute -right-3 top-8 flex h-6 w-6 items-center justify-center rounded-full border border-(--color-border) bg-(--color-dark) text-(--color-secondary) hover:text-white transition-colors cursor-pointer"
        title={isCollapsed ? "Развернуть" : "Свернуть"}
      >
        <Icon name="arrow-down"
          className={`h-3 w-3 transition-transform duration-300 ${isCollapsed ? "rotate-90" : "-rotate-90"}`}
        />
      </button>
    </aside>
  );
}
