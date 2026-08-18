// src/api/authApi.ts
import type { AuthUser, Permission } from "@/store/authSlice";
import { baseApi } from "./baseApi";

type EditMeRequest = {
  email?: string;
  password?: string;
  full_name?: string;
  department_id?: number | null;
  telegram_id?: number | null;
  current_password?: string;
};
type GetAllUsersParams = {
  id?: number | null;
  full_name?: string;
  email?: string;
  department_id?: number;
};

export const usersApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getMe: builder.query<AuthUser, void>({
      query: () => "/users/me",
    }),
    editMe: builder.mutation<AuthUser, EditMeRequest>({
      query: (body) => ({
        url: `/users/me`,
        method: "PATCH",
        body,
      }),
    }),

    updateRoleUser: builder.mutation<
      AuthUser,
      { id: number; role: Permission }
    >({
      query: ({ id, role }) => ({
        url: `/users/${id}/role`,
        method: "PATCH",
        body: { role },
      }),
      invalidatesTags: ["Users"],
    }),
    getAllUsers: builder.query<AuthUser[], GetAllUsersParams | void>({
      query: (params) => {
        const searchParams = new URLSearchParams();
        if (params?.full_name) searchParams.set("full_name", params.full_name);
        if (params?.email) searchParams.set("email", params.email);
        if (params?.department_id != null)
          searchParams.set("department_id", String(params.department_id));
        if (params?.id != null) searchParams.set("id", String(params.id));

        const qs = searchParams.toString();
        return qs ? `/users?${qs}` : "/users";
      },
      providesTags: ["Users"],
    }),
  }),
});

export const { useGetMeQuery, useEditMeMutation, useGetAllUsersQuery, useUpdateRoleUserMutation } =
  usersApi;
