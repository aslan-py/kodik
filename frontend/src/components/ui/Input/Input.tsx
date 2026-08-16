"use client";

import { ReactNode, InputHTMLAttributes, TextareaHTMLAttributes } from "react";
import clsx from "clsx";
import styles from "./input.module.css";

type InputProps = {
  id: string;

  value: string;
  onChange: (value: string) => void;

  label?: string;
  placeholder?: string;

  type?: "text" | "email" | "password" | "number" | "search";

  multiline?: boolean;

  width?: string;
  height?: string;

  disabled?: boolean;
  readOnly?: boolean;

  onClick?: () => void;

  error?: string;

  startIcon?: ReactNode;
  endIcon?: ReactNode;

  className?: string;
  inputClassName?: string;

  inputProps?: InputHTMLAttributes<HTMLInputElement>;
  textareaProps?: TextareaHTMLAttributes<HTMLTextAreaElement>;
};

export function Input({
  id,

  value,
  onChange,

  label,
  placeholder,

  type = "text",
  readOnly,

  multiline = false,

  width,
  height,

  disabled,

  error,

  startIcon,
  endIcon,

  className,
  inputClassName,
  onClick,
  inputProps,
  textareaProps,
}: InputProps) {
  const wrapperStyle: React.CSSProperties = {
    ...(width && { width }),
  };

  const controlStyle: React.CSSProperties = {
    ...(height && { height }),
  };

  const containerClass = clsx(styles.field, className);

  const controlClass = clsx(
    styles.container,
    multiline ? styles.containerMulti : styles.containerSingle,
    startIcon && styles.containerWithIcon,
    endIcon && styles.containerWithEndIcon,
  );

  const inputClass = clsx(
    styles.input,
    multiline ? styles.inputMulti : styles.inputSingle,
    startIcon && styles.inputWithIcon,
    endIcon && styles.inputWithEndIcon,
    inputClassName,
  );

  return (
    <div className={containerClass} style={wrapperStyle}>
      {label && (
        <label htmlFor={id} className={styles.label}>
          {label}
        </label>
      )}

      <div className={controlClass} style={controlStyle}>
        {startIcon && <span className={styles.icon}>{startIcon}</span>}

        {multiline ? (
          <textarea
            id={id}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            readOnly={readOnly}
            aria-invalid={!!error}
            aria-describedby={error ? `${id}-error` : undefined}
            className={inputClass}
            {...textareaProps}
          />
        ) : (
          <input
            id={id}
            type={type}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            readOnly={readOnly}
            onClick={onClick}
            aria-invalid={!!error}
            aria-describedby={error ? `${id}-error` : undefined}
            className={`${inputClass} ${error ? styles.errorInput : ''}`}
            {...inputProps}
          />
        )}

        {endIcon && <span className={styles.endIcon}>{endIcon}</span>}
      </div>

      {error && (
        <p id={`${id}-error`} className={styles.error}>
          {error}
        </p>
      )}
    </div>
  );
}
