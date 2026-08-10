"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import UserSidebarProfile from "./UserSidebarProfile";
import { Icon } from "@/components/ui/Icon/Icon";
import { usePermission } from "@/hooks/useAuth";
import { Divider } from "../ui/Divider";

const baseItems = [{ href: "/incidents", label: "События" }];
const viewerItems = [{ href: "/myTask", label: "Мои задачи" }];

const adminSubItems = [
  { href: "monitoring", label: "Мониторинг" },
  { href: "filtring", label: "Фильтрация" },
  { href: "classification", label: "Классификация" },
  { href: "users", label: "Пользователи" },
];

export default function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const pathname = usePathname();

  const canViewer = usePermission(["viewer"]);
  const canAdmin = usePermission(["analyst", "admin"]);
  const canAnalyst = usePermission(["analyst", "admin"]);

  const navItems = [
    ...baseItems,
    ...(canViewer ? viewerItems : []),
    ...(canAdmin || canAnalyst ? [{ href: "/task", label: "Задачи" }] : []),
  ];

  const isAdminActive = adminSubItems.some((item) => pathname === item.href);

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
          {navItems.map((item) => {
            const isActive = pathname === item.href;

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`block rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${isCollapsed ? "text-center" : ""} ${
                    isActive
                      ? "bg-[#222A39] font-semibold text-white"
                      : "text-(--color-text-navbar) hover:bg-zinc-800"
                  }`}
                  title={isCollapsed ? item.label : undefined}
                >
                  {isCollapsed ? item.label.charAt(0) : item.label}
                </Link>
              </li>
            );
          })}

          {canAdmin && (
            <li>
              <button
                onClick={() => setAdminOpen((v) => !v)}
                className={`w-full flex items-center justify-between rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                  isCollapsed ? "justify-center" : ""
                } ${
                  isAdminActive || adminOpen
                    ? "bg-[#222A39] font-semibold text-white"
                    : "text-(--color-text-navbar) hover:bg-zinc-800"
                }`}
                title={isCollapsed ? "Администрирование" : undefined}
              >
                {isCollapsed ? "А" : "Администрирование"}
                {!isCollapsed && (
                  <Icon
                    name="arrow-down"
                    className={`h-3 w-3 transition-transform duration-200 ${
                      adminOpen ? "rotate-180" : ""
                    }`}
                  />
                )}
              </button>
              {adminOpen && !isCollapsed && (
                <ul className="ml-4 mt-1 space-y-1 border-l border-(--color-border) pl-2">
                  {adminSubItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                      <li key={item.href}>
                        <Link
                          href={item.href}
                          className={`block rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                            isActive
                              ? "bg-[#222A39] font-semibold text-white"
                              : "text-(--color-text-navbar) hover:bg-zinc-800"
                          }`}
                        >
                          {item.label}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          )}
          <Divider></Divider>
          <li >
            <Link
              href={process.env.NEXT_PUBLIC_ANALYTICS_URL ?? "#"}
              target="_blank"
              rel="noopener noreferrer"
              className={`flex gap-1 items-center rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${isCollapsed ? "text-center" : ""} text-(--color-text-navbar) hover:bg-zinc-800`}
              title={isCollapsed ? "Аналитика" : undefined}
            >
              {isCollapsed ? "А" : "Аналитика"}
            <Icon name="open-source" className="text-[#9A9EA4]"></Icon>
            </Link>
          </li>
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
        <Icon
          name="arrow-down"
          className={`h-3 w-3 transition-transform duration-300 ${isCollapsed ? "rotate-90" : "-rotate-90"}`}
        />
      </button>
    </aside>
  );
}
