"use client";

import { useEffect, useMemo, useState } from "react";
import Button from "@ui/Button/button";
import { PeriodSelector } from "@/components/filters/PeriodSelector/PeriodSelector";
import { SearchInput } from "@/components/filters/SearchInput/SearchInput";
import { SelectFilter } from "@/components/filters/SelectFilter/SelectFilter";
import { Table, TableColumn } from "@ui/Table/Table";
import { Icon } from "@ui/Icon/Icon";
import { IncidentItem } from "@/types/types";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { loadIncidents } from "@/store/incidentsSlice";

function useIncidentColumns(onOpen: (item: IncidentItem) => void): TableColumn<IncidentItem>[] {
    return [
    {
        key: "data", header: "дата", width: "80px",
        className: "font-medium",
        render: (item: IncidentItem) => {
            const [day, month] = item.data.split(".").map(Number);
            const monthNames = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"];
            return (
                <span className="block whitespace-nowrap">
                    {day} {monthNames[month - 1]}
                </span>
            );
        },
    },
    {
        key: "incident", header: "событие", className: "",
        render: (item: IncidentItem) => (
            <>
                <span className="block text-(--color-ink) font-medium">
                    {item.incident}
                </span>
                
                {/* ! времено */}
                <span className="inline-block text-(--color-muted) py-1 text-xs">
                    {item.type} • {item.category}
                </span>
            </>
        ),
    },
    { key: "object", header: "объект",
          render: (item: IncidentItem) => (
            <>
                <span className="block text-(--color-strong)">
                    {item.object}
                </span>
            </>
        ),
     },
    { key: "source", header: "источник",
         render: (item: IncidentItem) => (
            <>
                <span className="block text-(--color-secondary)">
                    {item.source}
                </span>
            </>
        ),
    },
    {
        key: "priority", header: "приоритет",
        render: (item: IncidentItem) => {
            const priorityMap: Record<string, string> = {
                "П1": "var(--color-priority-high)",
                "П2": "var(--color-priority-medium)",
                "П3": "var(--color-priority-low)",
            };
            return (
                <span className="inline-flex items-center gap-2">
                    <span
                        className="inline-block h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: priorityMap[item.priority] ?? "var(--color-status-neutral)" }}
                    />
                    {item.priority}
                </span>
            );
        },
    },
    { key: "index", header: "медиаиндекс" },
    {
        key: "tonality", header: "тональность",
        render: (item: IncidentItem) => {
            const colorMap: Record<string, string> = {
                "Позитивная": "var(--color-status-positive)",
                "Нейтральная": "var(--color-status-neutral)",
                "Негативная": "var(--color-status-negative)",
            };
            return (
                <span className="inline-flex items-center gap-2">
                    <span
                        className="inline-block h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: colorMap[item.tonality] ?? "var(--color-status-neutral)" }}
                    />
                    {item.tonality}
                </span>
            );
        },
    },
    {
        key: "button", header: "",
        render: (item: IncidentItem) => (
            <Button variant="link" onClick={() => onOpen(item)} endIcon={<Icon name="link" />} className="hover:text-(--color-accent)">Открыть</Button>
        ),
    },
];
}

// <SelectFilter
function getUniqueOptions(items: IncidentItem[], field: keyof Pick<IncidentItem, "source" | "priority" | "object">) {
    const values = [...new Set(items.map((item) => item[field]))];

    return values.map((value) => ({ label: value, value }));
}

function getDefaultDateRange(): { from: string; to: string } {
    const now = new Date();
    const from = new Date(now);
    from.setDate(from.getDate() - 6);
    const toStr = now.toISOString().slice(0, 10);
    const fromStr = from.toISOString().slice(0, 10);
    return { from: fromStr, to: toStr };
}

const defaultRange = getDefaultDateRange();

type IncidentTableProps = {
  onOpen: (item: IncidentItem) => void;
};

export default function IncidentTable({ onOpen }: IncidentTableProps) {
    const dispatch = useAppDispatch();
    const { items: incidents, loading } = useAppSelector((state) => state.incidents);
    const [searchQuery, setSearchQuery] = useState("");
    const [dateFrom, setDateFrom] = useState(defaultRange.from);
    const [dateTo, setDateTo] = useState(defaultRange.to);
    const [sourceFilter, setSourceFilter] = useState("");
    const [priorityFilter, setPriorityFilter] = useState("");
    const [objectFilter, setObjectFilter] = useState("");

    useEffect(() => {
        dispatch(loadIncidents());
    }, []);
    
    const columns = useMemo(() => useIncidentColumns(onOpen), []);

    const sourceOptions = useMemo(
        () => getUniqueOptions(incidents, "source"),
        [incidents]
    );

    const priorityOptions = useMemo(
        () => getUniqueOptions(incidents, "priority"),
        [incidents]
    );

    const objectOptions = useMemo(
        () => getUniqueOptions(incidents, "object"),
        [incidents]
    );

    function parseDate(d: string): Date {
        // data — DD.MM.YYYY, dateFrom/dateTo — YYYY-MM-DD
        if (d.includes(".")) {
            const [day, month, year] = d.split(" ")[0].split(".").map(Number);
            return new Date(year, month - 1, day);
        }
        return new Date(d + "T00:00:00");
    }

    const filteredIncidents = useMemo(
        () => incidents
            .filter((item) => {
                const q = searchQuery.toLowerCase().trim();
                const matchesSearch = !q
                    || item.incident.toLowerCase().includes(q)
                    || item.object.toLowerCase().includes(q)
                    || item.source.toLowerCase().includes(q);
                const matchesSource = !sourceFilter || item.source === sourceFilter;
                const matchesPriority = !priorityFilter || item.priority === priorityFilter;
                const matchesObject = !objectFilter || item.object === objectFilter;

                const itemDate = parseDate(item.data);
                const matchesDateFrom = !dateFrom || itemDate >= parseDate(dateFrom);
                const matchesDateTo = !dateTo || itemDate <= new Date(parseDate(dateTo).getTime() + 86400000);

                return matchesSearch && matchesSource && matchesPriority && matchesObject && matchesDateFrom && matchesDateTo;
            })
            .sort((a, b) => {
                const [aDay, aMonth, aYear] = a.data.split(".").map(Number);
                const [bDay, bMonth, bYear] = b.data.split(".").map(Number);
                const aTs = new Date(aYear, aMonth - 1, aDay).getTime();
                const bTs = new Date(bYear, bMonth - 1, bDay).getTime();
                return bTs - aTs; // сначала новые
            }),
        [incidents, searchQuery, sourceFilter, priorityFilter, objectFilter, dateFrom, dateTo]
    );

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <span className="text-(--color-muted)">Загрузка событий...</span>
            </div>
        );
    }

    return (
        <>
            <div className="mb-4 grid grid-cols-[1fr_1fr_auto] gap-x-6 gap-y-4 items-end">
                <div className="flex items-end gap-4 max-w-110">
                    <SearchInput
                        value={searchQuery}
                        onChange={setSearchQuery}
                        placeholder="Событие, компания, источник..."
                    />
                </div>
                <div />
                <PeriodSelector
                    dateFrom={dateFrom}
                    dateTo={dateTo}
                    onDateFromChange={setDateFrom}
                    onDateToChange={setDateTo}
                />
                <div className="flex items-end gap-4">
                    <SelectFilter
                        label="Источник"
                        value={sourceFilter}
                        options={sourceOptions}
                        onChange={setSourceFilter}
                        className="w-full max-w-51"
                    />
                    <SelectFilter
                        label="Приоритет"
                        value={priorityFilter}
                        options={priorityOptions}
                        onChange={setPriorityFilter}
                        className="w-full max-w-51"
                    />
                </div>
                <SelectFilter
                    label="Объект"
                    value={objectFilter}
                    options={objectOptions}
                    onChange={setObjectFilter}
                    className="w-full max-w-51"
                />
                <div />
            </div>
            <Table
                key={`${searchQuery}-${dateFrom}-${dateTo}-${sourceFilter}-${priorityFilter}-${objectFilter}`}
                data={filteredIncidents}
                columns={columns}
                pageSize={10}
            />
        </>
    );
}
