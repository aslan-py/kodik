"use client";

import { useLazyGetMeQuery } from "@/api/authApi";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/hooks/useAuth";
import { useState } from "react";

export default function LoginPage() {
  const [email, setEmail] = useState("user@example.com");
  const [full_name, setFullName] = useState("string");
  const [password, setPassword] = useState("Spassword1");
  const [department_id, setDepartment] = useState("0");
  const [telegram, setTelegram] = useState("0");
  const [errorForm, setError] = useState("");
  const [loadingForm, setLoading] = useState(false);

  const [trigger, { data, error, isLoading }] = useLazyGetMeQuery();
  const { register } = useAuth();



  const handleClickTest = async () => {
    try {
      const result = await trigger().unwrap();
      console.log("✅ Успех:", result.user);
      alert(`Привет, ${result.user.full_name}!`);
    } catch (err) {
      console.error("❌ Ошибка:", err);
      alert("Ошибка запроса. Смотри консоль.");
    }
  };


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register({
        email,
        full_name,
        password,
        department_id: Number(department_id),
        telegram_id: 0,
      });
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
    <div className="flex min-h-full items-center justify-center p-6 bg-(--color-light)">
      <div className="flex flex-col gap-8 w-full max-w-md text-xl relative z-10 ">
        <div>
          Kodik+
          <span className="block text-(--color-secondary) text-xs">
            Конкурентная разведка
          </span>
        </div>

        <div>
          <p className="text-3xl font-semibold mb-6">Регистрация</p>

          <form onSubmit={handleSubmit}>
            <Input
              id="emailRegistration"
              type={"email"}
              label="Рабочий email"
              value={email}
              placeholder="you@company.com"
              onChange={setEmail}
              error=""
              className="mb-6"
            />
            <Input
              id="fullnameRegistration"
              type={"text"}
              label="Ваше ФИО"
              value={full_name}
              placeholder="ФИО"
              onChange={setFullName}
              error=""
              className="mb-6"
            />
            <Input
              id="passwordRegistration"
              type={"password"}
              value={password}
              label="Пароль"
              placeholder="Введите пароль"
              onChange={setPassword}
              error=""
              className="mb-6"
            />

            <Input
              id="departmentRegistration"
              type={"number"}
              value={department_id}
              label="Отдел"
              placeholder="Введите отдел"
              onChange={setDepartment}
              error=""
              className="mb-6"
            />
            <Input
              id="TelegramRegistration"
              type={"text"}
              value={telegram}
              label="Telegram (необязательно)"
              placeholder="Telegram id"
              onChange={setTelegram}
              error=""
              className="mb-6"
            />
            <div className="flex justify-between items-center mb-6"></div>
            <Button
              className="btn inline h-9 text-sm font-medium"
              fullWidth
              variant="primary"
              type="submit"
            >
              Войти
            </Button>
          </form>
            <Button
              className="btn inline h-9 text-sm font-medium"
              fullWidth
              variant="primary"
              onClick={handleClickTest}
            >
              тест getMe
            </Button>
        </div>
        <p className="text-xs text-(--color-muted)">
          © 2026 Kodik. Все права защищены.
        </p>
      </div>
    </div>
  );
}
