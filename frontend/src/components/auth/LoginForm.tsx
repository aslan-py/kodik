"use client";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/hooks/useAuth";
import { ResetPassword } from "@/components/auth/ResetPassword";
import { useState } from "react";
import Link from "next/link";
import { ToastViewport } from "../ui/Notification/toast";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginForm() {
  const [email, setEmail] = useState("admin123@example.com");
  const [password, setPassword] = useState("12345Admin");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [touched, setTouched] = useState<{ email: boolean; password: boolean }>({
    email: false,
    password: false,
  });

  const { login } = useAuth();

  const emailError = email && !EMAIL_REGEX.test(email) ? "Введите корректный email" : "";
  const passwordError =
    password && password.length < 8
      ? "Пароль должен быть не меньше 8 символов"
      : password && !/[A-ZА-ЯЁ]/.test(password)
        ? "Пароль должен содержать заглавную букву"
        : "";
  const showEmailError = touched.email ? (emailError ? emailError : "") : "";
  const showPasswordError = touched.password ? (passwordError ? passwordError : "") : "";
  const isValid = !emailError && !passwordError && !!email && !!password;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: unknown) {
      const message =
        err instanceof Object && "data" in err
          ? (err as { data: { message?: string } }).data?.message
          : "Ошибка входа";
      setError(message ?? "Ошибка входа");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-110">
      <p className="text-3xl font-semibold mb-6">Вход в рабочее пространство</p>
      <ToastViewport />
      <form autoComplete="off" className="" onSubmit={handleSubmit}>
        <Input
          id="emailLogin"
          type={"email"}
          label="Рабочий email"
          value={email}
          placeholder="you@company.com"
          onChange={setEmail}
          error={showEmailError}
          inputProps={{ onBlur: () => setTouched((t) => ({ ...t, email: true })) }}
          className="mb-6"
        />
        <Input
          id="passwordLogin"
          type={"password"}
          value={password}
          label="Пароль"
          placeholder="Введите пароль"
          onChange={setPassword}
          error={showPasswordError}
          inputProps={{ onBlur: () => setTouched((t) => ({ ...t, password: true })) }}
          className="mb-6"
        />
        <div className="flex justify-end items-center mb-6">
          {/* <Checkbox
            id="agree"
            checked={agree}
            onChange={setAgree}
            label="Запомнить меня"
            error=""
            className=""
          /> */}

          <Button
            className="btn inline text-sm"
            size="none"
            variant="tertiary"
            onClick={() => setShowReset(true)}
          >
            Забыли пароль?
          </Button>
        </div>
        <Button
          loading={loading}
          disabled={!isValid}
          className="btn inline h-9 text-sm font-medium"
          fullWidth
          variant="primary"
          type="submit"
        >
          Войти
        </Button>
        <div className="text-[13px] mt-6 flex justify-center gap-1">
        <p className="text-(--color-secondary)">Нет аккаунта?</p>
        <Link
          href="/registration"
          className="text-(--color-accent)"
        >
          Зарегистрироваться
        </Link>
        </div>
      </form>
      <ResetPassword isOpen={showReset} onClose={() => setShowReset(false)} />
    </div>
  );
}
