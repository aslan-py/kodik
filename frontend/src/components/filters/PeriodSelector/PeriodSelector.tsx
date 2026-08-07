"use client";

import { useMemo, useState } from "react";
import { formatDate, formatShort } from "@helpers/date";
import { Select, SelectItem } from "@/components/ui/Select";

type PeriodOption =
  | "today"
  | "7days"
  | "30days"
  | "thisMonth"
  | "lastMonth"
  | "custom";

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

function getPresetRange(
  period: Exclude<PeriodOption, "custom">,
  now: Date,
): { from: string; to: string } {
  const today = formatDate(now);

  switch (period) {
    case "today":
      return { from: today, to: today };

    case "7days": {
      const from = new Date(now);
      from.setDate(from.getDate() - 6);
      return { from: formatDate(from), to: today };
    }

    case "30days": {
      const from = new Date(now);
      from.setDate(from.getDate() - 29);
      return { from: formatDate(from), to: today };
    }

    case "thisMonth": {
      const from = new Date(now.getFullYear(), now.getMonth(), 1);
      return { from: formatDate(from), to: today };
    }

    case "lastMonth": {
      const from = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const to = new Date(now.getFullYear(), now.getMonth(), 0);
      return { from: formatDate(from), to: formatDate(to) };
    }
  }
}

const PRESET_ORDER: Exclude<PeriodOption, "custom">[] = [
  "today",
  "7days",
  "30days",
  "thisMonth",
  "lastMonth",
];

export function PeriodSelector({
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
}: PeriodSelectorProps) {
  const [isCustom, setIsCustom] = useState(false);

  const currentPeriod = useMemo((): PeriodOption => {
    if (isCustom) return "custom";
    if (!dateFrom && !dateTo) return "custom";

    const now = new Date();
    const matched = PRESET_ORDER.find((preset) => {
      const range = getPresetRange(preset, now);
      return dateFrom === range.from && dateTo === range.to;
    });

    return matched ?? "custom";
  }, [dateFrom, dateTo, isCustom]);

  const handlePeriodChange = (value: PeriodOption) => {
    if (value === "custom") {
      setIsCustom(true);
      const range = getPresetRange("thisMonth", new Date());
      onDateFromChange(range.from);
      onDateToChange(range.to);
      return;
    }

    setIsCustom(false);
    const range = getPresetRange(value, new Date());
    onDateFromChange(range.from);
    onDateToChange(range.to);
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
          {periodOptions.map((opt) => (
            <div key={opt.value}>
              <SelectItem
                active={opt.value === currentPeriod}
                onClick={() => {
                  handlePeriodChange(opt.value);
                  // "Произвольный период" не закрывает дропдаун — под ним
                  // сразу должны появиться поля ввода дат
                  if (opt.value !== "custom") setOpen(false);
                }}
              >
                {opt.label}
              </SelectItem>

              {opt.value === "custom" && currentPeriod === "custom" && (
                <div className="flex items-center gap-1.5 border-t border-zinc-100 px-3 py-2">
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => onDateFromChange(e.target.value)}
                    className="date-input min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-xs outline-none transition focus:border-zinc-900"
                  />
                  <span className="text-xs text-zinc-400">—</span>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => onDateToChange(e.target.value)}
                    className="date-input min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-xs outline-none transition focus:border-zinc-900"
                  />
                </div>
              )}
            </div>
          ))}
        </>
      )}
    </Select>
  );
}