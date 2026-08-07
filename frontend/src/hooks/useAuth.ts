"use client";

import { useCallback, useRef } from "react";
import {
  RegisterRequest,
  useRegisterMutation,
  useLogoutMutation,
  useLoginMutation,
} from "@/api/authApi";
import { useRouter } from "next/navigation";
import { useAppSelector, useAppDispatch } from "@/hooks/storeHooks";
import {
  selectUser,
  selectIsAuthenticated,
  selectAuthStatus,
  hasAccess,
  checkUserAuth,
  logout as logoutAction,
  type Permission,
} from "@/store/authSlice";
import { useToast } from "@/components/ui/Notification/toast";
import { setAccessToken, clearAccessToken } from "@/helpers/cookies";

export function usePermission(requiredRoles?: Permission[]) {
  const role = useAppSelector(selectUser)?.role;
  return hasAccess(role, requiredRoles);
}

export function useAuth() {
  const { showToast } = useToast();
  const dispatch = useAppDispatch();
  const router = useRouter();
  const user = useAppSelector(selectUser);
  const isAuthenticated = useAppSelector(selectIsAuthenticated);
  const status = useAppSelector(selectAuthStatus);

  const [loginMutation] = useLoginMutation();
  const [registerMutation] = useRegisterMutation();
  const [logoutMutation] = useLogoutMutation();
  
  const login = useCallback(
    async (email: string, password: string) => {
      try {
        const result = await loginMutation({ email, password }).unwrap();
        setAccessToken(result.access_token);

        await dispatch(checkUserAuth()).unwrap();

        showToast("success", "Вход выполнен успешно");
        router.replace("/"); // дальше сама "/" решит: incidents или уведомление
      } catch {
        clearAccessToken();
        dispatch(logoutAction());
        showToast("error", "Ошибка входа. Проверьте email и пароль");
      }
    },
    [loginMutation, dispatch, router, showToast],
  );

  const register = useCallback(
    async (data: RegisterRequest) => {
      try {
        await registerMutation(data).unwrap();
        showToast("success", "Регистрация прошла успешно");
      } catch (err) {
        const errStatus = (err as { status?: number })?.status;

        if (errStatus === 409) {
          showToast(
            "error",
            "Email или telegram_id уже заняты другим пользователем",
          );
        } else if (errStatus === 422) {
          showToast(
            "error",
            "Пароль должен быть не короче 8 символов и иметь заглавную букву",
          );
        } else {
          showToast("error", "Ошибка регистрации. Попробуйте снова");
        }
      }
    },
    [registerMutation, showToast],
  );

  const isLoggingOutRef = useRef(false);

  const logout = useCallback(async () => {
    if (isLoggingOutRef.current) return;
    isLoggingOutRef.current = true;

    let serverLogoutSucceeded = false;
    try {
      await logoutMutation().unwrap();
      serverLogoutSucceeded = true;
    } catch {
      // сервер недоступен — локальную сессию всё равно очищаем
    } finally {
      clearAccessToken();
      dispatch(logoutAction());

      if (serverLogoutSucceeded) {
        showToast("success", "Вы вышли из системы");
      }

      router.replace("/login");
      isLoggingOutRef.current = false;
    }
  }, [logoutMutation, dispatch, router, showToast]);

  return { user, isAuthenticated, status, login, logout, register };
}
