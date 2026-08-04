"use client";

import {
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";

import { createPortal } from "react-dom";

import styles from "./modal.module.css";

type ModalProps = {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
};

export function Modal({
  isOpen,
  onClose,
  children,
}: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div ref={overlayRef} className={styles.overlay}>
      {children}
    </div>,
    document.body,
  );
}