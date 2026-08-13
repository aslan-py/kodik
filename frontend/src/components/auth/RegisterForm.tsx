"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select/Select";
import { useAuth } from "@/hooks/useAuth";

import Link from "next/link";
import { NotificationModal } from "../modal/NotificationModal";
import { ToastViewport } from "../ui/Notification/toast";
import type { FilterOption } from "@/types/types";
import { useDepartmentOptions } from "@/hooks/useDepartament";
import { useRouter } from 'next/navigation'

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const NAME_REGEX = /^[А-Яа-яЁё\s-]+$/;
const DIGITS_REGEX = /^\d+$/;

export default function RegisterForm() {
  const [email, setEmail] = useState("");
  const [full_name, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [department_id, setDepartment] = useState("");
  const [telegram, setTelegram] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [touched, setTouched] = useState({
    email: false,
    name: false,
    password: false,
    confirm: false,
    telegram: false,
  });

  const { register } = useAuth();
  const router = useRouter()

  const departmentOptions = useDepartmentOptions();
  const departmentSelectOptions: FilterOption<string>[] = useMemo(
    () =>
      departmentOptions.map((o) => ({
        label: o.label,
        value: String(o.value),
      })),
    [departmentOptions],
  );

  const emailError =
    email && !EMAIL_REGEX.test(email) ? "Введите корректный email" : "";
  const nameError =
    full_name &&
    (full_name.trim().length < 2 || !NAME_REGEX.test(full_name.trim()))
      ? "Имя должно содержать минимум 2 символа и только русские буквы"
      : "";
  const passwordError =
    password && password.length < 8
      ? "Пароль должен быть не меньше 8 символов"
      : password && !/[A-ZА-ЯЁ]/.test(password)
        ? "Пароль должен содержать заглавную букву"
        : "";
  const confirmError =
    confirmPassword && confirmPassword !== password
      ? "Пароли не совпадают"
      : "";
  const telegramError =
    telegram && !DIGITS_REGEX.test(telegram)
      ? "Telegram id должен быть числом"
      : "";

  const showEmailError = touched.email ? emailError : "";
  const showNameError = touched.name ? nameError : "";
  const showPasswordError = touched.password ? passwordError : "";
  const showConfirmError = touched.confirm ? confirmError : "";
  const showTelegramError = touched.telegram ? telegramError : "";

  const isValid =
    !emailError &&
    !nameError &&
    !passwordError &&
    !confirmError &&
    !telegramError &&
    !!email &&
    !!full_name.trim() &&
    !!password &&
    !!confirmPassword;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const ok = await register({
      email,
      password,
      full_name: full_name ? full_name : null,
      department_id: department_id ? Number(department_id) : null,
      telegram_id: telegram ? Number(telegram) : null,
    });
    setSuccess(ok);
    setLoading(false);
  };

  return (
    <div className="w-full max-w-110">
      <p className="text-3xl font-semibold mb-6">Регистрация</p>
      <ToastViewport />
      <form autoComplete="off" onSubmit={handleSubmit}>
        <Input
          id="emailRegistration"
          type={"email"}
          label="Рабочий email"
          value={email}
          placeholder="you@company.com"
          onChange={setEmail}
          error={showEmailError}
          inputProps={{
            onBlur: () => setTouched((t) => ({ ...t, email: true })),
          }}
          className="mb-6"
        />
        <Input
          id="fullnameRegistration"
          type={"text"}
          label="Ваше ФИО"
          value={full_name}
          placeholder="ФИО"
          onChange={setFullName}
          error={showNameError}
          inputProps={{
            onBlur: () => setTouched((t) => ({ ...t, name: true })),
          }}
          className="mb-6"
        />
        <Input
          id="passwordRegistration"
          type={"password"}
          value={password}
          label="Пароль"
          placeholder="Введите пароль"
          onChange={setPassword}
          error={showPasswordError}
          inputProps={{
            onBlur: () => setTouched((t) => ({ ...t, password: true })),
          }}
          className="mb-6"
        />
        <Input
          id="confirmPasswordRegistration"
          type={"password"}
          value={confirmPassword}
          label="Подтвердите пароль"
          placeholder="Повторите пароль"
          onChange={setConfirmPassword}
          error={showConfirmError}
          inputProps={{
            onBlur: () => setTouched((t) => ({ ...t, confirm: true })),
          }}
          className="mb-6"
        />
        <p className="text-[12px] text-(--color-muted)">Отдел</p>
        <Select
          label=""
          placeholder="Выберите отдел"
          value={department_id}
          onChange={setDepartment}
          options={departmentSelectOptions}
          className="mb-6 bg-(--color-surface) h-10.5 px-4 py-2 rounded-[10px]"

        />
        <Input
          id="TelegramRegistration"
          type={"text"}
          value={telegram}
          label="Telegram (необязательно)"
          placeholder="Telegram id"
          onChange={setTelegram}
          error={showTelegramError}
          inputProps={{
            onBlur: () => setTouched((t) => ({ ...t, telegram: true })),
          }}
          className="mb-6"
        />
        <div className="flex justify-between items-center mb-6"></div>
        <Button
          className="btn inline h-9 text-sm font-medium"
          fullWidth
          variant="primary"
          type="submit"
          loading={loading}
          disabled={!isValid}
        >
          Зарегистрироваться
        </Button>
        <div className="text-[13px] mt-6 flex justify-center gap-1">
          <p className="text-(--color-secondary)">Уже есть аккаунт?</p>
          <Link href="/login" className="text-(--color-accent)">
            Войти
          </Link>
        </div>
      </form>
      <NotificationModal
        isOpen={success}
        onClose={() => setSuccess(false)}
        title="Регистрация прошла успешно"
        text="Обратитесь к администратору — он откроет доступ к сервису после проверки заявки."
        buttonText="Понятно"
        onButtonClick={() => router.push("/login")}
      />
    </div>
  );
}