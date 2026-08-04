"use client";

import type { ReactNode } from "react";
import { Icon } from "@/components/ui/Icon/Icon";
import styles from "./select.module.css";

type SelectItemProps = {
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
};

export function SelectItem({
  active = false,
  onClick,
  children,
  ...props
}: SelectItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      {...props}
      className={`${styles.item} ${active ? styles.itemActive : ""}`}
    >
      <span>{children}</span>
      {active && <Icon name="check" className={styles.checkmark} />}
    </button>
  );
}
