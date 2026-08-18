"use client";

import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from "react";
import { Notification } from "./Notification";

type ToastType = "success" | "error";
type ToastPlacement = "global" | "inline";

type Toast = {
  id: number;
  type: ToastType;
  message: string;
  placement: ToastPlacement;
};

type ToastContextType = {
  showToast: (type: ToastType, message: string, options?: { placement?: ToastPlacement }) => void;
  toasts: Toast[];
};

const ToastContext = createContext<ToastContextType | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const showToast = useCallback(
    (type: ToastType, message: string, options?: { placement?: ToastPlacement }) => {
      const id = ++idRef.current;
      const placement = options?.placement ?? "global";
      setToasts((prev) => [...prev, { id, type, message, placement }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 3000);
    },
    [],
  );

  const globalToasts = toasts.filter((t) => t.placement === "global");

  return (
    <ToastContext.Provider value={{ showToast, toasts }}>
      {children}
      <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2">
        {globalToasts.map((toast) => (
          <Notification key={toast.id} type={toast.type}>
            {toast.message}
          </Notification>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

// Рендерит только "inline"-тосты — вставляется прямо в разметку формы,
export function ToastViewport({ className }: { className?: string }) {
  const { toasts } = useToast();
  const inlineToasts = toasts.filter((t) => t.placement === "inline");

  if (inlineToasts.length === 0) return null;

  return (
    <div className={className ?? "flex flex-col gap-2 mb-4"}>
      {inlineToasts.map((toast) => (
        <Notification key={toast.id} type={toast.type}>
          {toast.message}
        </Notification>
      ))}
    </div>
  );
}