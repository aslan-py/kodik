import { combineReducers } from "@reduxjs/toolkit";
import { baseApi } from "@/api/baseApi";
import { authReducer } from "./authSlice";

export const rootReducer = combineReducers({
  [baseApi.reducerPath]: baseApi.reducer,
  auth: authReducer,
});

export type RootState = ReturnType<typeof rootReducer>;
