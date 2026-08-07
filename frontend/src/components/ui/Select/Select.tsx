"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { Icon } from "@/components/ui/Icon/Icon";
import { SelectItem } from "./SelectItem";

import styles from "./select.module.css";

type Option = {
  label: string;
  value: string;
};

type SelectProps = {
  label?: string;
  className?: string;
  direction?: "down" | "up";
  buttonClassName?: string;
  buttonIconClassName?: string;
  buttonContent?: ReactNode;
  children?: ReactNode | ((setOpen: (open: boolean) => void) => ReactNode);
  value?: string;
  placeholder?: string;
  options?: Option[];
  onChange?: (value: string) => void;
};

export function Select({
  label,
  className = "",
  direction = "down",
  buttonClassName = "",
  buttonIconClassName = "",
  buttonContent,
  children,
  value,
  placeholder = "",
  options,
  onChange,
}: SelectProps) {
  const [open, setOpen] = useState(false);

  const rootRef = useRef<HTMLDivElement>(null);

  const listboxId = useId();
  const labelId = useId();

  useEffect(() => {
    if (!open) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  const selectedIndex =
    options?.findIndex((option) => option.value === value) ?? -1;

  const selectedLabel =
    selectedIndex >= 0 ? options?.[selectedIndex].label : undefined;

  const resolvedContent = buttonContent ?? selectedLabel ?? placeholder;

  const selectOption = (option: Option) => {
    onChange?.(option.value);
    setOpen(false);
  };
  const moveSelection = (delta: 1 | -1) => {
    if (!options?.length) return;

    if (!open) {
      setOpen(true);
      return;
    }

    const length = options.length;
    const next = (selectedIndex + delta + length) % length;
    onChange?.(options[next].value);
  };
  
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    switch (event.key) {
      case "Enter":
      case " ":
        event.preventDefault();
        setOpen((prev) => !prev);
        break;
      case "Escape":
        setOpen(false);
        break;
      case "ArrowDown":
        event.preventDefault();
        moveSelection(1);
        break;
      case "ArrowUp":
        event.preventDefault();
        moveSelection(-1);
        break;
    }
  };

  return (
    <div className={`${styles.root} ${className}`}>
      {label && (
        <label id={labelId} className={styles.label}>
          {label}
        </label>
      )}

      <div ref={rootRef} className={styles.relative}>
        <button
          type="button"
          className={`${styles.button} ${
            !selectedLabel ? styles.buttonPlaceholder : ""
          } ${buttonClassName}`}
          onClick={() => setOpen((prev) => !prev)}
          onKeyDown={handleKeyDown}
          aria-labelledby={label ? labelId : undefined}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={listboxId}
        >
          {resolvedContent}

          <Icon
            name="arrow-down"
            className={`${styles.icon} ${buttonIconClassName} ${
              open ? styles.iconOpen : ""
            }`}
          />
        </button>

        {open && (
          <div
            id={listboxId}
            role="listbox"
            className={`${styles.dropdown} ${
              direction === "up" ? styles.dropdownUp : styles.dropdownDown
            }`}
          >
            {children
              ? typeof children === "function"
                ? children(setOpen)
                : children
              : options?.map((option) => (
                  <SelectItem
                    key={option.value}
                    active={option.value === value}
                    onClick={() => selectOption(option)}
                  >
                    {option.label}
                  </SelectItem>
                ))}
          </div>
        )}
      </div>
    </div>
  );
}
