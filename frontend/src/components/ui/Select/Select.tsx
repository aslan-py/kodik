"use client";

import {
  useEffect,
  useId,
  useMemo,
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
  disabled?: boolean;
  searchable?: boolean;
  searchPlaceholder?: string;
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
  disabled = false,
  searchable = false,
  searchPlaceholder = "Поиск...",
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const rootRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const listboxId = useId();
  const labelId = useId();

  useEffect(() => {
    if (!open) return;

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest("[data-portal-popover]")) return; // клик внутри вложенного портального попапа — не закрываем
      if (rootRef.current && !rootRef.current.contains(target)) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // сброс поиска при закрытии, автофокус поля при открытии
  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }
    if (searchable) {
      searchInputRef.current?.focus();
    }
  }, [open, searchable]);

  const filteredOptions = useMemo(() => {
    if (!options) return options;
    if (!searchable || !query.trim()) return options;
    const q = query.trim().toLowerCase();
    return options.filter((option) => option.label.toLowerCase().includes(q));
  }, [options, searchable, query]);

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
    const list = filteredOptions;
    if (!list?.length) return;

    if (!open) {
      setOpen(true);
      return;
    }

    const currentIndex = list.findIndex((option) => option.value === value);
    const length = list.length;
    const next = (currentIndex + delta + length) % length;
    onChange?.(list[next].value);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
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

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    switch (event.key) {
      case "Escape":
        setOpen(false);
        break;
      case "Enter": {
        event.preventDefault();
        if (filteredOptions?.length === 1) {
          selectOption(filteredOptions[0]);
        }
        break;
      }
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
          onClick={() => !disabled && setOpen((prev) => !prev)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
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

        {open && !disabled && (
          <div
            id={listboxId}
            role="listbox"
            className={`${styles.dropdown} ${
              direction === "up" ? styles.dropdownUp : styles.dropdownDown
            }`}
          >
            {children ? (
              typeof children === "function" ? (
                children(setOpen)
              ) : (
                children
              )
            ) : (
              <>
                {searchable && (
                  <input
                    ref={searchInputRef}
                    type="text"
                    className={styles.searchInput}
                    placeholder={searchPlaceholder}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleSearchKeyDown}
                    onClick={(e) => e.stopPropagation()}
                  />
                )}
                {filteredOptions?.length ? (
                  filteredOptions.map((option) => (
                    <SelectItem
                      key={option.value}
                      active={option.value === value}
                      onClick={() => selectOption(option)}
                    >
                      {option.label}
                    </SelectItem>
                  ))
                ) : searchable ? (
                  <div className={styles.emptyState}>Ничего не найдено</div>
                ) : null}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}