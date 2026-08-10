import { useCallback, useEffect, useMemo, useState } from "react";
import { useGetShowcasesQuery, GetShowcasesParams } from "@/api/showcaseApi";

function getDefaultDateRange(): { from: string; to: string } {
  const now = new Date();
  const from = new Date(now);
  from.setDate(from.getDate() - 29);
  return {
    from: from.toISOString().slice(0, 10),
    to: now.toISOString().slice(0, 10),
  };
}

const defaultRange = getDefaultDateRange();
const pageSize = 10;

export function useFilteredIncidents(baseParams?: Partial<GetShowcasesParams>) {
  const [searchQuery, setSearchQuery] = useState("");
  const [dateFrom, setDateFrom] = useState(defaultRange.from);
  const [dateTo, setDateTo] = useState(defaultRange.to);

  // TODO: поиск по источнику (media) — включить, когда в GetShowcasesParams
  // появится соответствующее поле на бэке (например, `media`)
  // const [sourceFilter, setSourceFilter] = useState("");

  const [priorityFilter, setPriorityFilter] = useState("");
  const [objectFilter, setObjectFilter] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [usePeriod, setUsePeriod] = useState(false);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(50);

  const filtersKey = `${searchQuery}-${dateFrom}-${dateTo}-${usePeriod}-${priorityFilter}-${objectFilter}-${departmentFilter}-${regionFilter}`;

  const params = useMemo<GetShowcasesParams>(() => {
    const p: GetShowcasesParams = {
      ...baseParams,
      limit,
      offset: (page - 1) * pageSize,
    };
    if (searchQuery.trim()) p.title = searchQuery.trim();
    if (usePeriod && dateFrom) p.published_from = dateFrom;
    if (usePeriod && dateTo) p.published_to = dateTo;
    // TODO: if (sourceFilter) p.media = sourceFilter; — когда появится в API
    if (priorityFilter) p.priority = priorityFilter;
    if (objectFilter) p.competitor = objectFilter;
    if (departmentFilter) p.department = departmentFilter;
    if (regionFilter) p.region = regionFilter;
    return p;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    page,
    limit,
    searchQuery,
    dateFrom,
    dateTo,
    usePeriod,
    priorityFilter,
    objectFilter,
    departmentFilter,
    regionFilter,
    baseParams,
  ]);

  const { data: incidents = [], isLoading } = useGetShowcasesQuery(params);

  const handleReachLastPage = useCallback(() => {
    setLimit((prev) => prev + 50);
  }, []);

  useEffect(() => {
    setPage(1);
  }, [filtersKey]);

  const getUniqueOptions = (field: "region" | "priority" | "competitor" | "department") => {
    const values = [...new Set(incidents.map((item) => item[field]))];
    return values.filter((v): v is string => v != null).map((value) => ({ label: value, value }));
  };

  // TODO: options для источника, когда появится поле media в ответе/фильтрах API
  // const sourceOptions = useMemo(() => getUniqueOptions("media"), [incidents]);

  const priorityOptions = useMemo(() => getUniqueOptions("priority"), [incidents]);
  const objectOptions = useMemo(() => getUniqueOptions("competitor"), [incidents]);
  const departmentOptions = useMemo(() => getUniqueOptions("department"), [incidents]);
  const regionOptions = useMemo(() => getUniqueOptions("region"), [incidents]);

  return {
    incidents, isLoading, pageSize, filtersKey, handleReachLastPage,
    searchQuery, setSearchQuery,
    dateFrom, setDateFrom, dateTo, setDateTo,
    // sourceFilter, setSourceFilter, sourceOptions, // TODO: включить с появлением поля в API
    priorityFilter, setPriorityFilter, priorityOptions,
    objectFilter, setObjectFilter, objectOptions,
    departmentFilter, setDepartmentFilter, departmentOptions,
    regionFilter, setRegionFilter, regionOptions,
    usePeriod, setUsePeriod,
  };
}