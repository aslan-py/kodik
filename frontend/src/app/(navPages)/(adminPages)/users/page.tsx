"use client"
import UserTable from "@/components/tables/UserTable";
import TitlePage from "@/components/layout/TitlePage";

export default function AdminUsersPage() {
 
  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="Пользователи"
        text="Отделы и доступ сотрудников к рабочим данным Kodik+."
      />

      <UserTable />
    </div>
  );
}
