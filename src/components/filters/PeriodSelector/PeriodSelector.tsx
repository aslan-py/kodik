"use client";

import { useMemo, useState } from "react";
import { formatDate, formatShort } from "@helpers/date";
import { Select, SelectItem } from "@/components/ui/Select";

type PeriodOption = "today" | "7days" | "30days" | "thisMonth" | "lastMonth" | "custom";

type PeriodSelectorProps = {
  dateFrom: string;
  dateTo: string;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
};

const periodOptions: { value: PeriodOption; label: string }[] = [
  { value: "today", label: "Сегодня" },
  { value: "7days", label: "7 дней" },
  { value: "30days", label: "30 дней" },
  { value: "thisMonth", label: "Этот месяц" },
  { value: "lastMonth", label: "Прошлый месяц" },
  { value: "custom", label: "Произвольный период" },
];

export function PeriodSelector({
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
}: PeriodSelectorProps) {
  const currentPeriod = useMemo((): PeriodOption => {
    if (!dateFrom && !dateTo) return "custom";

    const now = new Date();
    const today = formatDate(now);

    if (dateFrom === today && dateTo === today) return "today";

    const sevenDaysAgo = new Date(now);
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 6);
    if (dateFrom === formatDate(sevenDaysAgo) && dateTo === today) return "7days";

    const thirtyDaysAgo = new Date(now);
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 29);
    if (dateFrom === formatDate(thirtyDaysAgo) && dateTo === today) return "30days";

    const thisMonthStart = new Date(now.getFullYear(), now.getMonth(), 1);
    if (dateFrom === formatDate(thisMonthStart) && dateTo === today) return "thisMonth";

    const lastMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const lastMonthEnd = new Date(now.getFullYear(), now.getMonth(), 0);
    if (dateFrom === formatDate(lastMonthStart) && dateTo === formatDate(lastMonthEnd))
      return "lastMonth";

    return "custom";
  }, [dateFrom, dateTo]);

  const handlePeriodChange = (value: string) => {
    const period = value as PeriodOption;
    const now = new Date();

    switch (period) {
      case "today": {
        const d = formatDate(now);
        onDateFromChange(d);
        onDateToChange(d);
        break;
      }
      case "7days": {
        const from = new Date(now);
        from.setDate(from.getDate() - 6);
        onDateFromChange(formatDate(from));
        onDateToChange(formatDate(now));
        break;
      }
      case "30days": {
        const from = new Date(now);
        from.setDate(from.getDate() - 29);
        onDateFromChange(formatDate(from));
        onDateToChange(formatDate(now));
        break;
      }
      case "thisMonth": {
        const from = new Date(now.getFullYear(), now.getMonth(), 1);
        onDateFromChange(formatDate(from));
        onDateToChange(formatDate(now));
        break;
      }
      case "lastMonth": {
        const from = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        const to = new Date(now.getFullYear(), now.getMonth(), 0);
        onDateFromChange(formatDate(from));
        onDateToChange(formatDate(to));
        break;
      }
      case "custom":
        onDateFromChange("");
        onDateToChange("");
        break;
    }
  };

  const dateLabel = useMemo(() => {
    if (!dateFrom && !dateTo) return "";

    const from = dateFrom ? new Date(dateFrom + "T00:00:00") : null;
    const to = dateTo ? new Date(dateTo + "T00:00:00") : null;

    if (currentPeriod === "today" && to) {
      return formatShort(to);
    }

    if (from && to) {
      return `${formatShort(from)} – ${formatShort(to)}`;
    }

    return "";
  }, [dateFrom, dateTo, currentPeriod]);

  return (
    <Select
      label="Период"
      className="min-w-55"
      buttonClassName="min-w-55"
      buttonContent={
        <span className="text-(--color-ink) font-medium">{dateLabel}</span>
      }
    >
      {(setOpen) => (
        <>
          {periodOptions.map((opt) =>
            opt.value === "custom" ? (
              <div key="custom">
                <SelectItem
                  active={opt.value === currentPeriod}
                  onClick={() => {
                    handlePeriodChange(opt.value);
                    setOpen(false);
                  }}
                >
                  {opt.label}
                </SelectItem>
                {currentPeriod === "custom" && (
                  <div className="flex gap-2 border-t border-zinc-100 px-3 py-2">
                    <label className="flex flex-col gap-1 text-xs ">
                      <span>С</span>
                      <input
                        type="date"
                        value={dateFrom}
                        onChange={(e) => onDateFromChange(e.target.value)}
                        className="rounded-xl border border-zinc-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-zinc-900"
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-zinc-500">
                      <span>По</span>
                      <input
                        type="date"
                        value={dateTo}
                        onChange={(e) => onDateToChange(e.target.value)}
                        className="rounded-xl border border-zinc-300 bg-white px-3 py-2 text-sm  outline-none transition focus:border-zinc-900"
                      />
                    </label>
                  </div>
                )}
              </div>
            ) : (
              <SelectItem
                key={opt.value}
                active={opt.value === currentPeriod}
                onClick={() => {
                  handlePeriodChange(opt.value);
                  setOpen(false);
                }}
              >
                {opt.label}
              </SelectItem>
            )
          )}
        </>
      )}
    </Select>
  );
}