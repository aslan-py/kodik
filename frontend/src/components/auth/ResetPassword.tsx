"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal/Modal";
import {
  useRequestPasswordResetMutation,
  useConfirmPasswordResetMutation,
} from "@/api/authApi";
import { useToast } from "@/components/ui/Notification/toast";

type ResetPasswordProps = {
  isOpen: boolean;
  onClose: () => void;
};

export function ResetPassword({ isOpen, onClose }: ResetPasswordProps) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const [requestCode, { isLoading: isRequesting }] =
    useRequestPasswordResetMutation();
  const [confirmReset, { isLoading: isConfirming }] = useConfirmPasswordResetMutation();

  const { showToast } = useToast();

  const handleRequestCode = async () => {
    setError("");
    if (!email.trim()) {
      setError("Введите email");
      return;
    }
    try {
      await requestCode({ email: email.trim() }).unwrap();
      setCodeSent(true);
      showToast("success", "Код отправлен на указанную почту");
    } catch {
      setError("Не удалось отправить код. Проверьте email");
    }
  };

  const handleConfirm = async () => {
    setError("");
    if (!code.trim() || !newPassword) {
      setError("Введите код и новый пароль");
      return;
    }
    try {
      await confirmReset({
        email: email.trim(),
        code: code.trim(),
        new_password: newPassword,
      }).unwrap();
      setSuccess(true);
      setCodeSent(false);
      setCode("");
      setNewPassword("");
    } catch {
      setError("Не удалось сменить пароль. Проверьте код");
    }
  };

  return (
    <Modal isOpen={isOpen || success} onClose={success ? () => setSuccess(false) : onClose}>
      {success ? (
        <div className="m-auto w-full max-w-100 rounded-xl bg-white p-8 text-center shadow-lg">
          <p className="text-lg font-medium text-(--color-ink)">
            Пароль успешно изменён
          </p>
          <Button
            className="btn mt-6 h-9 text-sm font-medium"
            fullWidth
            variant="primary"
            onClick={() => {
              setSuccess(false);
              onClose();
            }}
          >
            Ок
          </Button>
        </div>
      ) : (
        <div className="m-auto w-full max-w-100 rounded-xl bg-white p-8 text-center shadow-lg">
          <p className="text-xl font-semibold mb-6 text-(--color-ink)">
            Сброс пароля
          </p>

          <Input
          id="resetEmail"
          type="email"
          label="Email"
          value={email}
          placeholder="you@company.com"
          onChange={setEmail}
          error=""
          className="mb-4"
        />

        {!codeSent ? (
          <Button
            loading={isRequesting}
            className="btn inline h-9 text-sm font-medium"
            fullWidth
            variant="primary"
            onClick={handleRequestCode}
          >
            Запросить код
          </Button>
        ) : (
          <>
            <Input
              id="resetCode"
              type="text"
              label="Код из письма"
              value={code}
              placeholder="Введите код"
              onChange={setCode}
              error=""
              className="mb-4"
            />
            <Input
              id="resetNewPassword"
              type="password"
              label="Новый пароль"
              value={newPassword}
              placeholder="Введите новый пароль"
              onChange={setNewPassword}
              error=""
              className="mb-4"
            />
            <Button
              disabled={!codeSent}
              loading={isConfirming}
              className="btn inline h-9 text-sm font-medium"
              fullWidth
              variant="primary"
              onClick={handleConfirm}
            >
              Назначить новый пароль
            </Button>
          </>
        )}

        {error && <p className="mt-4 text-sm text-(--color-status-negative)">{error}</p>}
      </div>
      )}
    </Modal>
  );
}