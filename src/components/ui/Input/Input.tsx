"use client";

import { ReactNode, InputHTMLAttributes, TextareaHTMLAttributes } from "react";

type BaseInputProps = {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  inputClassName?: string;
  width?: string;
  height?: string;
  startIcon?: ReactNode;
};

type SingleLineProps = BaseInputProps & {
  multiline?: false;
  placeholder?: string;
  type?: string;
  inputProps?: InputHTMLAttributes<HTMLInputElement>;
};

type MultiLineProps = BaseInputProps & {
  multiline: true;
  placeholder?: string;
  textareaProps?: TextareaHTMLAttributes<HTMLTextAreaElement>;
};

type InputProps = SingleLineProps | MultiLineProps;

export function Input({
  value,
  onChange,
  className = "",
  inputClassName = "",
  width,
  height,
  startIcon,
  multiline = false,
  ...rest
}: InputProps) {
  const style: React.CSSProperties = {
    ...(width ? { width } : {}),
    ...(height ? { height } : {}),
  };

  const containerClass = [
    "rounded-[10] bg-(--color-surface)",
    multiline ? "flex items-start" : "flex items-center",
    width ? "" : "w-full",
    startIcon ? "relative" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const inputClass = [
    "w-full text-sm text-(--color-ink) outline-none transition bg-transparent",
    "placeholder:text-(--color-muted) focus:border-(--color-accent) rounded-[10]",
    multiline ? "h-full px-3 py-2 resize-none" : "h-10 px-3",
    startIcon ? "pl-9" : "",
    inputClassName,
  ]
    .filter(Boolean)
    .join(" ");

  const { placeholder, ...passThrough } = rest as Record<string, unknown>;

  return (
    <label className={containerClass} style={style}>
      {startIcon && (
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-(--color-muted)">
          {startIcon}
        </span>
      )}
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder as string}
          className={inputClass}
          style={height ? { height: "100%" } : { minHeight: "80px" }}
          {...((passThrough || {}) as TextareaHTMLAttributes<HTMLTextAreaElement>)}
        />
      ) : (
        <input
          type={(rest as SingleLineProps).type || "text"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder as string}
          className={inputClass}
          {...((passThrough || {}) as InputHTMLAttributes<HTMLInputElement>)}
        />
      )}
    </label>
  );
}