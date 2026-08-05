import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/store/types";

export type Permission = "pending" | "viewer" | "analyst" | "admin";

export type AuthUser = {
  id: number;
  email: string;
  full_name: string;
  department_id: number;
  telegram_id?: number;
  role: Permission;
  is_active: boolean;
};

export type AuthState = {
  user: AuthUser | null;
  isAuthenticated: boolean;
  token: string | null;
  status: "idle" | "loading" | "succeeded" | "failed";
};

const initialState: AuthState = {
  user: null,
  token: null,
  isAuthenticated: false,
  status: "idle",
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setToken(state, action: PayloadAction<string>) {
      state.token = action.payload;
    },
    setUser(state, action: PayloadAction<{ user: AuthUser; token: string }>) {
      state.user = action.payload.user;
      state.token = action.payload.token;
      state.isAuthenticated = true;
      state.status = "succeeded";
    },

    clearUser(state) {
      state.user = null;
      state.isAuthenticated = false;
      state.token = null;
      state.status = "idle";
    },
    setStatus(state, action: PayloadAction<AuthState["status"]>) {
      state.status = action.payload;
    },
  },
});

export const { setUser, clearUser, setStatus, setToken } = authSlice.actions;
export const selectUser = (state: RootState) => state.auth.user;
export const selectToken = (state: RootState) => state.auth.token;
export const selectIsAuthenticated = (state: RootState) =>
  state.auth.isAuthenticated;
export const selectAuthStatus = (state: RootState) => state.auth.status;

export const selectHasPermission =
  (permission: Permission) =>
  (state: RootState): boolean =>
    state.auth.user?.role.includes(permission) ?? false;

export const authReducer = authSlice.reducer;
