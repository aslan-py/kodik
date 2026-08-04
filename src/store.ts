// src/store.ts
import { configureStore } from "@reduxjs/toolkit";
import { authApi } from "@/api/authApi";
import { baseApi } from "@api/baseApi";
import { fakeApi } from "@/api/fakeApi"; // пока мок
import { authReducer } from "@/store/authSlice";

export const store = configureStore({
  reducer: {
    [authApi.reducerPath]: authApi.reducer,
    [baseApi.reducerPath]: baseApi.reducer,
    [fakeApi.reducerPath]: fakeApi.reducer, // удалить, когда перейдёте на реальное API
    auth: authReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware()
      .concat(authApi.middleware)
      .concat(baseApi.middleware)
      .concat(fakeApi.middleware),
});

export type { RootState } from "@/store/types";
export type AppDispatch = typeof store.dispatch;