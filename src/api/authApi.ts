// src/api/authApi.ts
import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type { AuthUser } from "@/store/authSlice";

type LoginRequest = { email: string; password: string };
type RegisterRequest = { name: string; email: string; password: string };

export const authApi = createApi({
  reducerPath: "authApi",
  baseQuery: fetchBaseQuery({
    baseUrl: "/api",
    credentials: "include", // httpOnly cookies
  }),
  endpoints: (builder) => ({
    // auth — регистрация и логин
    login: builder.mutation<{ user: AuthUser }, LoginRequest>({
      query: (body) => ({
        url: "/auth/login",
        method: "POST",
        body,
      }),
    }),

    register: builder.mutation<{ user: AuthUser }, RegisterRequest>({
      query: (body) => ({
        url: "/auth/register",
        method: "POST",
        body,
      }),
    }),

    // logout: builder.mutation<void, void>({
    //   query: () => ({
    //     url: "/auth/logout",
    //     method: "POST",
    //   }),
    // }),

    // users
    getMe: builder.query<{ user: AuthUser }, void>({
      query: () => "/users/me",
    }),
  }),
});

export const {
  useLoginMutation,
  useRegisterMutation,
//   useLogoutMutation,
  useGetMeQuery,
} = authApi;
