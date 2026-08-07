"use client";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal/Modal";
import { useAuth } from "@/hooks/useAuth";
import { useState } from "react";

export default function RegisterForm() {
  const [email, setEmail] = useState("user@example.com");
  const [full_name, setFullName] = useState("string");
  const [password, setPassword] = useState("string");
  const [department_id, setDepartment] = useState("");
  const [telegram, setTelegram] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const { register } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register({
        email,
        password,
        full_name: full_name ? full_name : null,
        department_id: department_id ? Number(department_id) : null,
        telegram_id: telegram ? Number(telegram) : null,
      });
      setSuccess(true);
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
      <p className="text-3xl font-semibold mb-6">Регистрация</p>
      <form autoComplete="off" onSubmit={handleSubmit}>
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
          loading={loading}
        >
          Войти
        </Button>
      </form>
      <Modal isOpen={success} onClose={() => setSuccess(false)}>
        <div
          className="m-auto max-w-100 rounded-xl bg-white p-8 text-center shadow-lg"
        >
          <p className="text-lg font-medium text-(--color-ink)">
            Регистрация прошла успешно, обратитесь к администратору для доступа
            к сервису
          </p>
          <Button
            className="btn mt-6 h-9 text-sm font-medium"
            fullWidth
            variant="primary"
            onClick={() => setSuccess(false)}
          >
            Ок
          </Button>
        </div>
      </Modal>
    </div>
  );
}
