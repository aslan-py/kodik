// src/api/authApi.ts
import type { AuthUser, Permission } from "@/store/authSlice";
import { baseApi } from "./baseApi";

type LoginRequest = {
  email: string;
  password: string;
};

type LoginResponse = {
  access_token: string;
  token_type: "bearer";
};
type RegisterResponse = {
  user: AuthUser;
};
export type RegisterRequest = {
  email: string;
  password: string;
  full_name: string | null;
  department_id: number | null;
  telegram_id?: number | null;
};

export const authApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // auth — регистрация и логин
    login: builder.mutation<LoginResponse, LoginRequest>({
      query: (body) => ({
        url: "/auth/login",
        method: "POST",
        body,
      }),
    }),

    register: builder.mutation<RegisterResponse, RegisterRequest>({
      query: (body) => ({
        url: "/auth/register",
        method: "POST",
        body,
      }),
    }),

    logout: builder.mutation<{ detail: string }, void>({
      query: () => ({
        url: "/auth/logout",
        method: "POST",
      }),
    }),
  }),
});

export const { useLoginMutation, useRegisterMutation, useLogoutMutation } =
  authApi;
