// src/api/baseApi.ts
import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { clearUser } from "@/store/authSlice";
import { RootState } from "@/store";

const baseQuery = fetchBaseQuery({
  // http://127.0.0.1:8000/auth/register
  baseUrl: "http://127.0.0.1:8000",
  // baseUrl: "/api",
  // baseUrl: process.env.NEXT_PUBLIC_API_URL,
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.token;
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return headers;
  },
});

const baseQueryWithAuth: typeof baseQuery = async (args, api, extraOptions) => {
  // 1. Выполняем оригинальный запрос
  const result = await baseQuery(args, api, extraOptions);

  // 2. Если сервер вернул 401 — токен недействителен
  if (result.error?.status === 401) {
    // 3. Разлогиниваем пользователя
    api.dispatch(clearUser());
    // 4. Редирект на страницу логина
    window.location.href = "/login";
  }
  // 5. Возвращаем результат (успех или другую ошибку)
  return result;
};

export const baseApi = createApi({
  reducerPath: "baseApi",
  baseQuery: baseQueryWithAuth,
  tagTypes: ["Showcases"],
  endpoints: () => ({}), // injectEndpoints в дочерних API
});
