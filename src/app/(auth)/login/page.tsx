"use client";

import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox/Checkbox";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/hooks/useAuth";
import { useState } from "react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agree, setAgree] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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
    console.log('запрос');

    }
  };
  return (
    <div className="flex">
      <div className="flex h-full flex-col p-10 justify-between text-xl relative z-10 bg-(--color-light)">
        <div>
          Kodik+
          <span className="block text-(--color-secondary) text-xs">
            Конкурентная разведка
          </span>
        </div>
        <div className="max-w-md">
          <p className="text-3xl font-semibold mb-6">
            Вход в рабочее пространство
          </p>
          <span>{error}</span>
          <form className="" onSubmit={handleSubmit}>
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
              <Checkbox
                id="agree"
                checked={agree}
                onChange={setAgree}
                label="Запомнить меня"
                error=""
                className=""
              />

              <Button
                className="btn inline text-sm"
                size="none"
                variant="tertiary"
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
        </div>
        <p className="text-xs text-(--color-muted)">
          © 2026 Kodik. Все права защищены.
        </p>
      </div>
    </div>
  );
}
