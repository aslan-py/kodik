import { useEffect, useState } from "react";
import { useAppSelector } from "@/hooks/storeHooks";
import { SelectItem, Select } from "../ui/Select";
import { selectUser } from "@/store/authSlice";
import type { Permission } from "@/store/authSlice";
import EditSettingsUserMe from "@/components/forms/EditSettingsUserMe";
import { useAuth } from "@/hooks/useAuth";
import { getInitials } from "@/helpers/user";

const ROLE_LABELS: Record<Permission, string> = {
  pending: "На рассмотрении",
  viewer: "Просмотрщик",
  analyst: "Аналитик",
  admin: "Администратор",
};

function UserInfo({ name, role }: { name: string; role: string }) {
  return (
    <div className="grid w-full grid-cols-[auto_1fr] gap-x-2 rounded-md text-white">
      <span className="flex flex-none row-span-2 justify-center items-center h-8 w-8 text-sm bg-[#2B2F35] text-white rounded-full">
        {getInitials(name)}
      </span>
      <p className="text-xs col-start-2 justify-self-start">{name}</p>
      <p className="text-[10px] col-start-2 justify-self-start">{role}</p>
    </div>
  );
}

export default function UserSidebarProfile() {
  const user = useAppSelector(selectUser);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const { logout } = useAuth();

  useEffect(() => {
    setMounted(true);
  }, []);

  const currentUser = mounted ? user : null;
  return (
    <div>
      <Select
        className="px-5"
        buttonClassName="hover:bg-zinc-800 py-2 px-2 cursor-pointer rounded-lg bg-[#222428]"
        buttonIconClassName=""
        direction="up"
        buttonContent={
          <UserInfo name={currentUser?.full_name ?? ""} role={currentUser ? ROLE_LABELS[currentUser.role] : ""} />
        }
      >
        {(setOpen) => (
          <>
            <SelectItem
              onClick={() => {
                setSettingsOpen(true);
                setOpen(false);
              }}
            >
              Настройки
            </SelectItem>
            <SelectItem
              onClick={() => {
                logout();
                setOpen(false);
              }}
            >
              Выйти
            </SelectItem>
          </>
        )}
      </Select>

      <EditSettingsUserMe
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  );
}