"use client";
import TitlePage from "@/components/layout/TitlePage";
import TabsNav from "@/components/ui/Tabs/tabs";
const tabs = [
  { path: "/filtring/common", label: "Исключенные домены" },
  { path: "/filtring/competitors", label: "Стоп-правила" },
];
export default function AdminFiltringPage({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="Фильтрация"
        text="Конкуренты, источники и триггеры, доступные для правил мониторинга."
      />
      <TabsNav tabs={tabs}></TabsNav>
      <div>{children}</div>
    </div>
  );
}
