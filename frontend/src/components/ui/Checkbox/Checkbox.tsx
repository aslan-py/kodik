"use client";

import { ChangeEvent } from "react";

import clsx from "clsx";

import styles from "./Checkbox.module.css";

type CheckboxProps = {
  id?: string;

  checked: boolean;

  onChange: (checked: boolean) => void;

  label?: string;

  description?: string;

  disabled?: boolean;

  error?: string;

  className?: string;
};

export function Checkbox({
  id = "checkbox",

  checked,

  onChange,

  label,

  description,

  disabled = false,

  error,

  className,
}: CheckboxProps) {
  const errorId = `${id}-error`;

  const descriptionId = `${id}-description`;

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.checked);
  };

  return (
    <div className={clsx(styles.wrapper, className)}>
      <label htmlFor={id} className={styles.label}>
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={handleChange}
          disabled={disabled}
          aria-invalid={!!error}
          aria-describedby={
            error ? errorId : description ? descriptionId : undefined
          }
          className={styles.input}
        />

        <span className={styles.box}>
          {checked && (
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M4 10.5L8 14.5L16 5.5" />
            </svg>
          )}
        </span>

        <span className={styles.content}>
          {label && <span className={styles.title}>{label}</span>}

          {description && (
            <span id={descriptionId} className={styles.description}>
              {description}
            </span>
          )}
        </span>
      </label>

      {error && (
        <p id={errorId} className={styles.error}>
          {error}
        </p>
      )}
    </div>
  );
}
