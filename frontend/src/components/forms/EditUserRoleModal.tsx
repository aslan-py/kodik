"use client";

import { useEffect, useState } from "react";
import { FormModal } from "@/components/ui/FormModal/FormModal";
import { AuthUser, Permission } from "@/store/authSlice";
import { ROLE_OPTIONS } from "@/constants/roles";
import { useUpdateRoleUserMutation } from "@/api/usersApi";

type EditUserRoleModalProps = {
  user: AuthUser | null;
  onClose: () => void;
};

export function EditUserRoleModal({ user, onClose }: EditUserRoleModalProps) {
  const [role, setRole] = useState<Permission | "">("");
  const [error, setError] = useState("");

  const [updateRole, { isLoading }] = useUpdateRoleUserMutation();

  useEffect(() => {
    if (user) {
      setRole(user.role);
      setError("");
    }
  }, [user]);

  const handleSave = async () => {
    if (!user || !role) return;
    setError("");
    try {
      await updateRole({ id: user.id, role }).unwrap();
      onClose();
    } catch (err: unknown) {
      const message =
        err instanceof Object && "data" in err
          ? (err as { data: { message?: string } }).data?.message
          : "Ошибка обновления роли";
      setError(message ?? "Ошибка обновления роли");
    }
  };

  return (
    <FormModal
      isOpen={!!user}
      onClose={onClose}
      title="Изменение роли пользователя"
      subtitle={user ? `${user.full_name} · ${user.email}` : undefined}
      onSubmit={handleSave}
      loading={isLoading}
      error={error}
      height={320}
    >
      <select
        id="userRole"
        value={role}
        onChange={(e) => setRole(e.target.value as Permission)}
        className="w-full rounded-lg border border-(--color-border) px-3 py-2 text-sm"
      >
        {ROLE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FormModal>
  );
}