import { useAppDispatch, useAppSelector } from "@/hooks/storeHooks";
import { SelectItem, Select } from "../ui/Select";
import { setUser, selectUser } from "@/store/authSlice";
import type { AuthUser } from "@/store/authSlice";

const viewerUser: AuthUser = {
  id: "1",
  name: "Александр Матвеев",
  email: "alex@example.com",
  role: "Просмотрщик",
  permissions: [],
};

const adminUser: AuthUser = {
  id: "2",
  name: "Александр Матвеев",
  email: "alex@example.com",
  role: "Администратор",
  permissions: ["admin"],
};

function UserInfo({ name, role }: { name: string; role: string }) {
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("");
  return (
    <div className="grid w-full grid-cols-[auto_1fr] gap-x-2 rounded-md text-white">
      <span className="flex flex-none row-span-2 justify-center items-center h-8 w-8 text-sm bg-[#2B2F35] text-white rounded-full">
        {initials}
      </span>
      <p className="text-xs col-start-2 justify-self-start">{name}</p>
      <p className="text-[10px] col-start-2 justify-self-start">{role}</p>
    </div>
  );
}

export default function UserSidebarProfile() {
  const dispatch = useAppDispatch();
  const user = useAppSelector(selectUser);

  const currentUser = user ?? viewerUser;

  return (
    <div>
      <Select
        className="px-5"
        buttonClassName="hover:bg-zinc-800 py-2 px-2 cursor-pointer rounded-lg bg-[#222428]"
        buttonIconClassName=""
        direction="up"
        buttonContent={
          <UserInfo name={currentUser.name} role={currentUser.role} />
        }
      >
        {(setOpen) => (
          <>
            <SelectItem
              onClick={() => {
                dispatch(setUser(viewerUser));
                setOpen(false);
              }}
            >
              Просмотрщик
            </SelectItem>
            <SelectItem
              onClick={() => {
                dispatch(setUser(adminUser));
                setOpen(false);
              }}
            >
              Администратор
            </SelectItem>
          </>
        )}
      </Select>
    </div>
  );
}