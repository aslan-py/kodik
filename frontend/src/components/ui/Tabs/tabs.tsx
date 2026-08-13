// components/TabsNav.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./tabs.module.css";

export interface TabItem {
  path: string;
  label: string;
}

interface TabsNavProps {
  tabs: TabItem[];
}

export default function TabsNav({ tabs }: TabsNavProps) {
  const pathname = usePathname();
  const activePath = pathname.split("/").pop();

  return (
    <nav className={styles.tabsNav} role="tablist">
      {tabs.map((tab) => (
        <Link
          key={tab.path}
          href={tab.path}
          role="tab"
          aria-selected={pathname === tab.path}
          className={`${styles.tab} ${pathname === tab.path ? styles.tabActive : ""}`}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
