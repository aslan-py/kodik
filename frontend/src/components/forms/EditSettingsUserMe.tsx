"use client";

import { useState, useEffect } from "react";
import { FormModal } from "@/components/ui/FormModal/FormModal";
import { Input } from "@/components/ui/Input/Input";
import { useAppSelector, useAppDispatch } from "@/hooks/storeHooks";
import { selectUser, setUser } from "@/store/authSlice";
import { useEditMeMutation } from "@/api/usersApi";

type SettingsModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
};

export default function EditSettingsUserMe({
  isOpen,
  onClose,
  onSuccess,
}: SettingsModalProps) {
  const user = useAppSelector(selectUser);
  const dispatch = useAppDispatch();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [telegram, setTelegram] = useState("");
  const [password, setPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [error, setError] = useState("");

  const [editMe, { isLoading }] = useEditMeMutation();

  useEffect(() => {
    if (isOpen && user) {
      setUsername(user.full_name ?? "");
      setEmail(user.email ?? "");
      setTelegram(user.telegram_id != null ? String(user.telegram_id) : "");
      setPassword("");
      setCurrentPassword("");
      setError("");
    }
  }, [isOpen, user]);

  const emailChanged = email !== user?.email;
  const passwordChanged = password.length > 0;
  const requiresCurrentPassword = emailChanged || passwordChanged;

  const handleSave = async () => {
    setError("");

    if (requiresCurrentPassword && !currentPassword) {
      setError("Введите текущий пароль, чтобы изменить email или пароль");
      return;
    }

    try {
      const body: Parameters<typeof editMe>[0] = {
        full_name: username,
        telegram_id: telegram ? Number(telegram) : null,
      };

      if (emailChanged) {
        body.email = email;
      }
      if (passwordChanged) {
        body.password = password;
      }
      if (requiresCurrentPassword) {
        body.current_password = currentPassword;
      }

      const result = await editMe(body).unwrap();
      dispatch(setUser({ user: result }));
      onClose();
      onSuccess?.(); // вызываем после успешного закрытия
    } catch (err: unknown) {
      const message =
        err instanceof Object && "data" in err
          ? (err as { data: { message?: string } }).data?.message
          : "Ошибка сохранения";
      setError(message ?? "Ошибка сохранения");
    }
  };

  return (
    <FormModal
      isOpen={isOpen}
      onClose={onClose}
      title="Настройки"
      subtitle="Учётная запись"
      onSubmit={handleSave}
      loading={isLoading}
      error={error}
      height={requiresCurrentPassword ? 530 : 410}
    >
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
        id="settings-password"
        label="Новый пароль (необязательно)"
        type="password"
        value={password}
        onChange={setPassword}
      />
      {requiresCurrentPassword && (
        <Input
          id="settings-current-password"
          label="Текущий пароль"
          type="password"
          value={currentPassword}
          onChange={setCurrentPassword}
        />
      )}
      <Input
        id="settings-telegram"
        label="Telegram ID"
        type="number"
        value={telegram}
        onChange={setTelegram}
      />
    </FormModal>
  );
}
