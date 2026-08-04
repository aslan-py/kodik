"use client";

import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox/Checkbox";
import { Input } from "@/components/ui/Input";
import { useState } from "react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agree, setAgree] = useState(false);

  return (
    <div className="flex">
      <div className="flex flex-col pt-16 pb-16 pl-24 pr-46 justify-between text-xl relative z-10 bg-(--color-light)">
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

          <form className="w-110" action="" method="post">
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

              <Button className="btn inline text-sm" size="none" variant="tertiary">
                Забыли пароль?
              </Button>
            </div>
            <Button  className="btn inline h-9 text-sm font-medium" fullWidth variant="primary" type="submit">
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

