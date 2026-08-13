"use client";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/hooks/useAuth";
import { checkUserAuth } from "@/store/authSlice";
import { useState } from "react";
import { useToast } from "../ui/Notification/toast";
import { useAppDispatch } from "@/hooks/storeHooks";

export function PendingForm() {
  const dispatch = useAppDispatch();
  const { showToast } = useToast();
  const [loading, setLoading] = useState(false);
  const { logout } = useAuth();

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const user = await dispatch(checkUserAuth()).unwrap();
      if (user.role === "pending") {
        showToast("error", "Роль пока не назначена. Попробуйте обновить позже");
      }
      // если роль сменилась — AuthGroupGuard сам среагирует и уведёт на /incidents,
      // отдельный тост здесь не нужен, иначе будет дублирование с редиректом
    } catch {
      showToast("error", "Не удалось обновить статус");
    } finally {
      setLoading(false);
    }
  };
  return (
    // ! поправить после обновления дизайна
    <div className="max-w-[500px]">
      <h1 className="text-3xl font-semibold mb-4">
        Доступ пока не предоставлен
      </h1>
      <div className="mb-8">
        <p className="text-[#41464D] text-[15px]">
          Администратор должен назначить вам роль.
        </p>
        <p className="text-[#41464D] text-[15px]">
          После этого доступ к разделам системы появится автоматически.
        </p>
      </div>
      <Button
        variant="primary"
        className="mb-3 h-9"
        fullWidth
        onClick={handleRefresh}
      >
        Обновить
      </Button>
      <Button
        className="h-9"
        fullWidth
        variant="secondary"
        onClick={() => {
          logout();
        }}
      >
        Выйти из аккаунта
      </Button>
    </div>
  );
}
