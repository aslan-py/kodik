// src/api/adminSourceApi.ts
import { baseApi } from "./baseApi";

export type Department = {
  id: number;
  name: string;
  note: string;
  is_active: boolean;
};

export type GetDepartmentsParams = {
  is_active?: boolean | null;
  q?: string | null;
  limit?: number;
  offset?: number;
};

export type DepartmentPayload = {
  name: string;
  note: string;
};

export type Category = {
  id: number;
  name: string;
  note: string;
  is_active: boolean;
};

export type GetCategoriesParams = {
  is_active?: boolean | null;
  q?: string | null;
  limit?: number;
  offset?: number;
};

export type CategoryPayload = {
  name: string;
  note: string;
};

export const adminSourceApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getDepartments: builder.query<Department[], GetDepartmentsParams | void>({
      query: (params) => {
        const sp = new URLSearchParams();
        if (params?.is_active != null)
          sp.set("is_active", String(params.is_active));
        if (params?.q) sp.set("q", params.q);
        if (params?.limit != null) sp.set("limit", String(params.limit));
        if (params?.offset != null) sp.set("offset", String(params.offset));
        const qs = sp.toString();
        return qs ? `/departments?${qs}` : "/departments";
      },
      providesTags: (result) =>
        result
          ? [
              ...result.map(({ id }) => ({ type: "Department" as const, id })),
              { type: "Department" as const, id: "LIST" },
            ]
          : [{ type: "Department" as const, id: "LIST" }],
    }),
    getDepartmentById: builder.query<Department, number>({
      query: (id) => `/departments/${id}`,
      providesTags: (result, error, id) => [{ type: "Department", id }],
    }),
    createDepartment: builder.mutation<Department, DepartmentPayload>({
      query: (body) => ({
        url: "/departments",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "Department", id: "LIST" }],
    }),
    updateDepartment: builder.mutation<
      Department,
      { id: number; body: Partial<DepartmentPayload> }
    >({
      query: ({ id, body }) => ({
        url: `/departments/${id}`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: "Department", id },
        { type: "Department", id: "LIST" },
      ],
    }),
    deleteDepartment: builder.mutation<void, number>({
      query: (id) => ({
        url: `/departments/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: (result, error, id) => [
        { type: "Department", id },
        { type: "Department", id: "LIST" },
      ],
    }),

    getCategories: builder.query<Category[], GetCategoriesParams | void>({
      query: (params) => {
        const sp = new URLSearchParams();
        if (params?.is_active != null)
          sp.set("is_active", String(params.is_active));
        if (params?.q) sp.set("q", params.q);
        if (params?.limit != null) sp.set("limit", String(params.limit));
        if (params?.offset != null) sp.set("offset", String(params.offset));
        const qs = sp.toString();
        return qs ? `/categories?${qs}` : "/categories";
      },
      providesTags: (result) =>
        result
          ? [
              ...result.map(({ id }) => ({ type: "Category" as const, id })),
              { type: "Category" as const, id: "LIST" },
            ]
          : [{ type: "Category" as const, id: "LIST" }],
    }),
    getCategoryById: builder.query<Category, number>({
      query: (id) => `/categories/${id}`,
      providesTags: (result, error, id) => [{ type: "Category", id }],
    }),
    createCategory: builder.mutation<Category, CategoryPayload>({
      query: (body) => ({
        url: "/categories",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "Category", id: "LIST" }],
    }),
    updateCategory: builder.mutation<
      Category,
      { id: number; body: Partial<CategoryPayload> }
    >({
      query: ({ id, body }) => ({
        url: `/categories/${id}`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: "Category", id },
        { type: "Category", id: "LIST" },
      ],
    }),
    deleteCategory: builder.mutation<void, number>({
      query: (id) => ({
        url: `/categories/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: (result, error, id) => [
        { type: "Category", id },
        { type: "Category", id: "LIST" },
      ],
    }),
  }),
});

export const {
  useGetDepartmentsQuery,
  useGetDepartmentByIdQuery,
  useCreateDepartmentMutation,
  useUpdateDepartmentMutation,
  useDeleteDepartmentMutation,
  useGetCategoriesQuery,
  useGetCategoryByIdQuery,
  useCreateCategoryMutation,
  useUpdateCategoryMutation,
  useDeleteCategoryMutation,
} = adminSourceApi;