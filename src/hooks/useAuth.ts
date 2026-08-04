// src/hooks/useAuth.ts
"use client";

import { useCallback } from "react";
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
} from "@/store/authSlice";

import { useLoginMutation } from "@api/authApi";

export function usePermission(permission: Permission) {
  return useAppSelector(selectHasPermission(permission));
}

export function useAuth() {
  const dispatch = useAppDispatch();
  const router = useRouter();
  const user = useAppSelector(selectUser);
  const isAuthenticated = useAppSelector(selectIsAuthenticated);
  const status = useAppSelector(selectAuthStatus);

  const [loginMutation] = useLoginMutation();

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await loginMutation({ email, password }).unwrap();
      dispatch(setUser(result.user));
      router.replace("/incidents");
    },
    [loginMutation, dispatch, router],
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
    hasPermission: (permission: Permission) =>
      user?.permissions.includes(permission) ?? false,
  };
}