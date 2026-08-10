"use client";

import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox/Checkbox";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/hooks/useAuth";
import { ResetPassword } from "@/components/auth/ResetPassword";
import { useState } from "react";

export default function LoginForm() {
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("12345Admin");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showReset, setShowReset] = useState(false);

  const { login } = useAuth();

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
      <span>{error}</span>
      <form autoComplete="off" className="" onSubmit={handleSubmit}>
        <Input
          id="emailLogin"
          type={"email"}
          label="Рабочий email"
          value={email}
          placeholder="you@company.com"
          onChange={setEmail}
          error=""
          className="mb-6"
        />
        <Input
          id="passwordLogin"
          type={"password"}
          value={password}
          label="Пароль"
          placeholder="Введите пароль"
          onChange={setPassword}
          error=""
          className="mb-6"
        />
        <div className="flex justify-between items-center mb-6">
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
          className="btn inline h-9 text-sm font-medium"
          fullWidth
          variant="primary"
          type="submit"
        >
          Войти
        </Button>
      </form>
      {/* <Modal isOpen={success} onClose={() => setSuccess(false)}>
        <div className="m-auto max-w-100 rounded-xl bg-white p-8 text-center shadow-lg">
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
      </Modal> */}

      <ResetPassword isOpen={showReset} onClose={() => setShowReset(false)} />
    </div>
  );
}
