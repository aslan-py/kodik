"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/Button/button";
import { Input } from "@/components/ui/Input/Input";
import { Icon } from "@/components/ui/Icon";

type SettingsModalProps = {
  isOpen: boolean;
  onClose: () => void;
};

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [username, setUsername] = useState("Александр Матвеев");
  const [email, setEmail] = useState("alex@example.com");
  const [telegram, setTelegram] = useState("@alex_matveev");

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (!isOpen) return;
    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen || typeof document === "undefined") return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] bg-black/50 flex items-center justify-center"
      onClick={onClose}
    >
      <div
        className="relative flex flex-col bg-white rounded-xl shadow-xl"
        style={{ width: 560, height: 410 }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Кнопка закрыть */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 flex items-center justify-center w-8 h-8 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <Icon name="close" className="text-gray-500" />
        </button>

        {/* Контент с паддингами 24px по бокам */}
        <div className="flex flex-col flex-1 px-6 pb-4 pt-5">
          {/* Title */}
          <h2 className="text-xl font-semibold text-(--color-ink) mb-6">
            Настройки
          </h2>

          {/* Учётная запись */}
          <p className="text-xs font-medium text-(--color-secondary) uppercase tracking-wider mb-4">
            Учётная запись
          </p>

          {/* Поля формы */}
          <div className="flex flex-col gap-3 flex-1">
            <Input
              id="settings-username"
              label="Имя пользователя"
              value={username}
              onChange={setUsername}
            />
            <Input
              id="settings-email"
              label="Рабочий email"
              type="email"
              value={email}
              onChange={setEmail}
            />
            <Input
              id="settings-telegram"
              label="Telegram ID"
              value={telegram}
              onChange={setTelegram}
            />
          </div>

          {/* Кнопка сохранить */}
          <Button
            variant="primary"
            size="medium"
            fullWidth
            className="mt-auto"
            onClick={() => {
              // TODO: сохранить изменения
              onClose();
            }}
          >
            Сохранить изменения
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
