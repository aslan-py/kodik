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
  full_name: string;
  department_id: number;
  telegram_id?: number;
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

    logout: builder.mutation<void, void>({
      query: () => ({
        url: "/auth/logout",
        method: "POST",
      }),
    }),

    // users
    getMe: builder.query<{ user: AuthUser }, void>({
      query: () => "/users/me",
    }),
    getAllUsers: builder.query<{ user: AuthUser[] }, void>({
      query: () => "/users",
    }),
    updateRoleUser: builder.mutation<AuthUser, { id: string; role: Permission }>({
      query: ({ id, role }) => ({
        url: `/users/${id}/role`,
        method: "PATCH",
        body: { role },
      }),
    }),
  }),
});

export const {
  useLoginMutation,
  useRegisterMutation,
  useLogoutMutation,
  useGetMeQuery,
  useGetAllUsersQuery,
  useUpdateRoleUserMutation,
} = authApi;
