"use client";

import { useRef, useState, useEffect, type ReactNode } from "react";
import { Icon } from "@/components/ui/Icon/Icon";

type SelectProps = {
  label?: string;
  className?: string;
  direction?: "down" | "up";
  buttonClassName?: string;
  buttonIconClassName?: string;
  buttonContent: ReactNode;
  children: ReactNode | ((setOpen: (open: boolean) => void) => ReactNode);
};

export function Select({
  label,
  className = "",
  direction = "down",
  buttonClassName = "",
  buttonIconClassName = "",
  buttonContent,
  children,
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const openRef = useRef(open);
  openRef.current = open;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (openRef.current && ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <label
      className={`flex flex-col gap-2 text-xs text-(--color-muted) cursor-pointer ${className}`}
    >
      {label ? <span>{label}</span> : null}
      <div ref={ref} className="relative">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className={`cursor-pointer flex w-full items-center justify-between gap-2 rounded-xlpx-3 text-sm outline-none transition not-first:${buttonClassName}`}
        >
          {buttonContent}
          <Icon name="arrow-down"
            className={`h-4 w-4 transition-transform ${buttonIconClassName} ${open ? "rotate-180" : ""}`}
          />
        </button>
        {open && (
          <div
            className={`absolute left-0 right-0 z-10 overflow-hidden rounded-xl shadow-lg ${
              direction === "up" ? "bottom-full mb-1" : "top-full mt-1"
            }`}
          >
            {typeof children === "function" ? children(setOpen) : children}
          </div>
        )}
      </div>
    </label>
  );
}
