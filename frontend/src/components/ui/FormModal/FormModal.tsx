"use client";

import type { ReactNode } from "react";
import { Modal } from "@/components/ui/Modal/Modal";
import { Icon } from "@/components/ui/Icon";
import { Button } from "@/components/ui/Button/button";

type FormModalProps = {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  submitLabel?: string;
  onSubmit?: () => void;
  loading?: boolean;
  error?: string;
  width?: number;
  height?: number;
};

export function FormModal({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  submitLabel = "Сохранить изменения",
  onSubmit,
  loading,
  error,
  width = 560,
}: FormModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <div
        className="relative m-auto flex flex-col bg-white rounded-xl shadow-xl"
        style={{ width }}
      >
        <button
          onClick={onClose}
          className="absolute top-5 right-5 flex items-center justify-center w-8 h-8 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <Icon name="close" className="text-gray-500" />
        </button>

        <div className="flex flex-col flex-1 px-6 pb-4 pt-5">
          <h2 className="text-xl font-semibold text-(--color-ink) mb-6">
            {title}
          </h2>

          {subtitle && (
            <p className="text-xs font-medium text-(--color-secondary) uppercase tracking-wider mb-4">
              {subtitle}
            </p>
          )}

          <div className="flex flex-col gap-3 flex-1">{children}</div>

          {error && (
            <p className="mt-2 text-sm text-(--color-error)">{error}</p>
          )}

          {onSubmit && (
            <Button
              variant="primary"
              size="medium"
              fullWidth
              className="mt-3"
              loading={loading}
              onClick={onSubmit}
            >
              {submitLabel}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}