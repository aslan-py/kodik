// src/app/(navPages)/incidents/page.tsx
"use client";

import { useRouter } from "next/navigation";
import { useMemo } from "react";
import IncidentTable from "@/components/tables/IncidentTable";
import { useIncidentColumns } from "@/components/tables/columns/incidentColumns";
import TitlePage from "@/components/layout/TitlePage";
import { useTableFilters } from "@/hooks/useTableFilters";
import { FilterConfig } from "@/hooks/filters/types";
import { PRIORITY_OPTIONS } from "@/types/types";
import { useGetShowcasesQuery, GetShowcasesParams } from "@/api/showcaseApi";
import { useGetDepartmentsQuery } from "@/api/adminSourceApi";
import { buildApiParams } from "@/hooks/filters/buildApiParams";

// 1. Описываем конфигурацию фильтров
const INCIDENT_FILTERS: FilterConfig[] = [
  {
    type: "search",
    key: "search",
    label: "Событие, компания, источник...",
    paramName: "title",
  },
  {
    type: "period",
    key: "period",
    label: "Период",
    paramFrom: "published_from",
    paramTo: "published_to",
  },
  {
    type: "select",
    key: "priority",
    label: "Приоритет",
    allLabel: "Все приоритеты",
    options: PRIORITY_OPTIONS,
  },
  {
    type: "dict-select",
    key: "competitor",
    label: "Объект",
    allLabel: "Все объекты",
  },
  {
    type: "dict-select",
    key: "department",
    label: "Отдел",
    allLabel: "Все отделы",
  },
  {
    type: "dict-select",
    key: "region",
    label: "Регион",
    allLabel: "Все регионы",
  },
];

const metricsEvent = [
  { label: "событий", value: 248 },
  { label: "приоритет П1", value: 28 },
  { label: "приоритет П2", value: 120 },
];

export default function IncidentsPage() {
  const router = useRouter();
  const columns = useIncidentColumns();

  // 2. Загружаем опции для dict-select фильтров
  const { data: departments = [] } = useGetDepartmentsQuery();
  const departmentOptions = useMemo(
    () =>
      departments.map((d) => ({ label: d.name, value: String(d.name) })),
    [departments],
  );

  // 3. Хук фильтров
  const {
    filterValues,
    setFilter,
    searchQuery,
    setSearchQuery,
    debouncedSearch,
    dateFrom,
    setDateFrom,
    dateTo,
    setDateTo,
    filtersKey,
  } = useTableFilters(INCIDENT_FILTERS);

  // 4. Собираем параметры для API
  const apiParams = useMemo<GetShowcasesParams>(() => {
    const baseParams = buildApiParams(
      INCIDENT_FILTERS,
      filterValues,
      debouncedSearch,
      dateFrom,
      dateTo
    );
    return {
      limit: 50,
      offset: 0,
      ...baseParams,
    } as GetShowcasesParams;
  }, [debouncedSearch, filterValues, dateFrom, dateTo]);

  // 5. Загружаем данные
  const { data: incidents = [], isLoading } = useGetShowcasesQuery(apiParams as GetShowcasesParams);

  // 6. Опции для dict-select (конкуренты и регионы — из данных)
  const objectOptions = useMemo(() => {
    const values = [...new Set(incidents.map((i) => i.competitor))].filter(Boolean);
    return values.map((v) => ({ label: v, value: v }));
  }, [incidents]);

  const regionOptions = useMemo(() => {
    const values = [...new Set(incidents.map((i) => i.region))].filter(Boolean);
    return values.map((v) => ({ label: v, value: v }));
  }, [incidents]);

  const allDictOptions = useMemo(
    () => ({
      competitor: objectOptions,
      department: departmentOptions,
      region: regionOptions,
    }),
    [objectOptions, departmentOptions, regionOptions],
  );

  if (isLoading) {
    return <div className="py-8 text-sm text-muted">Загрузка...</div>;
  }

  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="События"
        text="Мониторинг событий и новостей по рынку и конкурентам."
        dataToday
        metrics={metricsEvent}
      />
      <IncidentTable
        columns={columns}
        data={incidents}
        onRowClick={(incident) => router.push(`/incidents/${incident.id}`)}
        configs={INCIDENT_FILTERS}
        filterValues={filterValues}
        onFilterChange={setFilter}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        dictOptions={allDictOptions}
        filtersKey={filtersKey}
        pageSize={50}
      />
    </div>
  );
}