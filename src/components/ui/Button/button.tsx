"use client";
import { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./button.module.css";
import clsx from "clsx";

type ButtonSize = "small" | "medium" | "large" | "none";
type ButtonVariant = "primary" | "secondary" | "tertiary" | "badge";
type BadgeColor = "primary" | "secondary";
type ButtonJustify = "center" | "space-between" | "flex-start" | "flex-end";

type ButtonType = {
  size?: ButtonSize;
  variant?: ButtonVariant;
  badgeColor?: BadgeColor;
  justifyContent?: ButtonJustify;
  startIcon?: ReactNode;
  endIcon?: ReactNode;
  children?: React.ReactNode;
  fullWidth?: boolean;
  disabled?: boolean;
  loading?: boolean;
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  className?: string;
} & ButtonHTMLAttributes<HTMLButtonElement>;

export const Button = ({
  size = "small",
  variant = "primary",
  badgeColor = "primary",
  justifyContent = "center",
  startIcon,
  endIcon,
  children,
  fullWidth = false,
  onClick,
  className = "",
  disabled = false,
  loading = false,
  type = "button",
  ...props
}: ButtonType) => {
  const isDisabled = disabled || loading;

  const buttonClasses = clsx(
    styles.button,
    variant !== "badge" && styles[size],
    styles[variant],
    variant === "badge" && styles[`badge-${badgeColor}`],
    variant !== "badge" && styles[`justify-${justifyContent}`],
    fullWidth && styles.fullWidth,
    isDisabled && styles.disabled,
    loading && styles.loading,
    className,
  );

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (isDisabled) {
      event.preventDefault();
      return;
    }
    if (onClick) {
      onClick(event);
    }
  };

  return (
    <button
      type={type}
      className={buttonClasses}
      onClick={handleClick}
      disabled={isDisabled}
      {...props}
    >
      {loading ? (
        <span className={styles.spinner} />
      ) : (
        <>
          {startIcon && <span className={styles.startIcon}>{startIcon}</span>}

          {children && <span className={styles.content}>{children}</span>}

          {endIcon && <span className={styles.endIcon}>{endIcon}</span>}
        </>
      )}
    </button>
  );
};
