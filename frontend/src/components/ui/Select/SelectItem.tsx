"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Icon } from "@/components/ui/Icon/Icon";
import styles from "./select.module.css";

type SelectItemProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type" | "onClick"> & {
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
};

export function SelectItem({
  active = false,
  onClick,
  children,
  className = "",
  ...props
}: SelectItemProps) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      onClick={onClick}
      {...props}
      className={`${styles.item} ${active ? styles.itemActive : ""} ${className}`}
    >
      <span>{children}</span>
      {active && <Icon name="check" className={styles.checkmark} />}
    </button>
  );
}
