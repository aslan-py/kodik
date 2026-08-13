"use client";
import TitleAdminPage from "@/components/layout/TitleAdminPage";
import TitlePage from "@/components/layout/TitlePage";
import TabsNav from "@/components/ui/Tabs/tabs";
const tabs = [
  { path: "/monitoring/common", label: "Правила мониторинга" },
  { path: "/monitoring/competitors", label: "Конкуренты" },
  { path: "/monitoring/sources", label: "Источники" },
  { path: "/monitoring/triggers", label: "Тригеры" },
];
export default function AdminMonitoringPage({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col p-8">
      <TitleAdminPage
        title="Мониторинг"
        text="Конкуренты, источники и триггеры, доступные для правил мониторинга."
      />
      <TabsNav tabs={tabs}></TabsNav>
      <div>{children}</div>
    </div>
  );
}
