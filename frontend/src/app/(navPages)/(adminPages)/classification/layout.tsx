"use client";
import TitlePage from "@/components/layout/TitlePage";
import TabsNav from "@/components/ui/Tabs/tabs";
const tabs = [
  { path: "/classification/common", label: "Категории" },
  { path: "/classification/competitors", label: "Типы событий" },
];
export default function AdminClassificationPage({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="Классификация"
        text="Конкуренты, источники и триггеры, доступные для правил мониторинга."
      />
      <TabsNav tabs={tabs}></TabsNav>
      <div>{children}</div>
    </div>
  );
}
