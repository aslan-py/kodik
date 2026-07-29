"use client";
import { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";
import styles from "./button.module.css";
import clsx from "clsx";
type ButtonSize = "small" | "medium" | "large";
type ButtonVariant =
  | "primary"
  | "secondary"
  | "link"
  | "badge"

type BadgeColor = "accent" | "gray";

type ButtonType = {
  size?: ButtonSize;
  variant?: ButtonVariant;
  badgeColor?: BadgeColor;
  startIcon?: ReactNode;
  endIcon?: ReactNode;
  children?: React.ReactNode;
  fullWidth?: boolean;
  disabled?: boolean;
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  className?: string;
} & ButtonHTMLAttributes<HTMLButtonElement>;

export const Button = ({
  size = "small",
  variant = "primary",
  badgeColor = "accent",
  startIcon,
  endIcon,
  children,
  fullWidth = false,
  onClick,
  className = "",
  disabled = false,
  type = "button",
  color,
  ...props
}: ButtonType) => {
  const buttonClasses = clsx(
    styles.button,
    variant !== "badge" && styles[size],
    styles[variant],
    variant === "badge" && styles[`badge-${badgeColor}`],
    fullWidth && styles.fullWidth,
    disabled && styles.disabled,
    color && styles.customColor,
    className,
  );

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (disabled) {
      event.preventDefault();
      return;
    }
    // обработчик
    if (onClick) {
      onClick(event);
    }
  };

  const customStyle: CSSProperties = {};

  if (color) {
    customStyle.backgroundColor = color;
    customStyle.borderColor = "black";
  }
  return (
    <button
      type={type}
      className={buttonClasses}
      onClick={handleClick}
      disabled={disabled}
      style={customStyle}
      {...props}
    >
      {startIcon && <span className={styles.startIcon}>{startIcon}</span>}
      {children && <span className={styles.content}>{children}</span>}
      {endIcon && <span className={styles.endIcon}>{endIcon}</span>}
    </button>
  );
};

export default Button;
