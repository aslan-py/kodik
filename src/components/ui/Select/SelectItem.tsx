"use client";

import type { ReactNode } from "react";

type SelectItemProps = {
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
};

export function SelectItem({
  active = false,
  onClick,
  children,
}: SelectItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`cursor-pointer w-full bg-(--color-background) px-3 py-2 text-left text-sm text-(--color-strong) not-even:transition-colors hover:bg-zinc-100 ${
        active ? "" : ""
      }`}
    >
      {children}
    </button>
  );
}
