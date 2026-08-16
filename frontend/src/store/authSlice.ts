import {
  createAsyncThunk,
  createSlice,
  type PayloadAction,
} from "@reduxjs/toolkit";
import type { RootState } from "@/store/types";
import { getAccessToken } from "@/helpers/cookies";
import { usersApi } from "@/api/usersApi";

export type Permission = "pending" | "viewer" | "analyst" | "admin";

export function hasAccess(
  role: Permission | undefined,
  requiredRoles?: Permission[],
): boolean {
  if (!role) return false;
  if (!requiredRoles || requiredRoles.length === 0) {
    return role !== "pending"; // ← без requiredRoles pending исключён
  }
  return requiredRoles.includes(role);
}

export type AuthUser = {
  id: number;
  email: string;
  full_name: string;
  department_id: number;
  telegram_id?: number;
  role: Permission;
  is_active: boolean;
};

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export type AuthState = {
  user: AuthUser | null;
  status: AuthStatus;
};

const initialState: AuthState = {
  user: null,
  status: "loading",
};

export const checkUserAuth = createAsyncThunk(
  "auth/checkUserAuth",
  async (_, thunkAPI) => {
    const token = getAccessToken();
    if (!token) {
      return thunkAPI.rejectWithValue("no token");
    }

    try {
      const user = await thunkAPI
        .dispatch(
          usersApi.endpoints.getMe.initiate(undefined, {
            forceRefetch: true,
          }),
        )
        .unwrap();
      return user;
    } catch {
      return thunkAPI.rejectWithValue("Unauthorized");
    }
  },
);

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setUser(state, action: PayloadAction<{ user: AuthUser }>) {
      state.user = action.payload.user;
      state.status = "authenticated";
    },
    logout(state) {
      state.user = null;
      state.status = "unauthenticated";
    },
  },
  // компоненты вызывают useAuth().logout(). Только сам useAuth и глобальные non-React обработчики (401-interceptor в baseApi) имеют право дергать dispatch(logoutAction()) напрямую — потому что только они знают весь контекст (нужен ли toast, нужен ли редирект, был ли это явный клик или принудительный логаут по истечении сессии) и корректно его обрабатывают. Никогда не делайте dispatch(logoutAction()) прямо из компонента в обход useAuth — это оставит cookie на месте и не уведомит бэкенд, ровно то расхождение, которое useAuth.logout существует, чтобы предотвратить.
  extraReducers: (builder) => {
    builder
      .addCase(checkUserAuth.pending, (state) => {
        state.status = "loading";
      })
      .addCase(checkUserAuth.fulfilled, (state, action) => {
        state.user = action.payload;
        state.status = "authenticated"; // pending тоже authenticated теперь
      })
      .addCase(checkUserAuth.rejected, (state) => {
        state.user = null;
        state.status = "unauthenticated";
      });
  },
});

export const { setUser, logout } = authSlice.actions;

export const selectUser = (state: RootState) => state.auth.user;
export const selectAuthStatus = (state: RootState) => state.auth.status;
export const selectIsAuthenticated = (state: RootState) =>
  state.auth.status === "authenticated";

export const authReducer = authSlice.reducer;
