// src/components/ui/Notification/toast.tsx
"use client";

import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from "react";
import { Notification } from "./Notification";

type Toast = {
  id: number;
  type: "success" | "error";
  message: string;
};

type ToastContextType = {
  showToast: (type: "success" | "error", message: string) => void;
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

  const showToast = useCallback((type: "success" | "error", message: string) => {
    const id = ++idRef.current;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2">
        {toasts.map((toast) => (
          <Notification key={toast.id} type={toast.type}>
            {toast.message}
          </Notification>
        ))}
      </div>
    </ToastContext.Provider>
  );
}