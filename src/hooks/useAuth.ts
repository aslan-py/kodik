// src/hooks/useAuth.ts
"use client";

import { useCallback } from "react";
import { authApi, RegisterRequest, useRegisterMutation } from "@/api/authApi";
import { useRouter } from "next/navigation";
import { useAppSelector, useAppDispatch } from "@/hooks/storeHooks";
import {
  selectUser,
  selectIsAuthenticated,
  selectAuthStatus,
  selectHasPermission,
  setUser,
  clearUser,
  type Permission,
  setToken,
} from "@/store/authSlice";

import { useLoginMutation } from "@api/authApi";
import { useToast } from "@/components/ui/Notification/toast";

export function usePermission(permission: Permission) {
  return useAppSelector(selectHasPermission(permission));
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

const login = useCallback(
  async (email: string, password: string) => {
    try {
      const result = await loginMutation({ email, password }).unwrap();
      dispatch(setToken(result.access_token));

      const userResult = await dispatch(
        authApi.endpoints.getMe.initiate(undefined),
      ).unwrap();

      dispatch(setUser({ user: userResult.user, token: result.access_token }));
      showToast("success", "Вход выполнен успешно");
      router.replace("/incidents");
    } catch {
      showToast("error", "Ошибка входа. Проверьте email и пароль");
    }
  },
  [loginMutation, dispatch, router, showToast],
);

const register = useCallback(
  async (data: RegisterRequest) => {
    console.log(data)
    try {
      await registerMutation(data).unwrap();
      showToast("success", "Регистрация прошла успешно");
      // router.push("/login");
    } catch {
      showToast("error", "Ошибка регистрации. Попробуйте снова");
    }
  },
  [registerMutation, showToast],
);


  const logout = useCallback(async () => {
    dispatch(clearUser());
    router.replace("/login");
  }, [dispatch, router]);

  return {
    user,
    isAuthenticated,
    status,
    login,
    logout,
    register,
  };
}
