"use client";

import { useMemo, useState } from "react";
import { formatDate, formatShort, parseISODate } from "@helpers/date";
import { Select, SelectItem } from "@/components/ui/Select";
import { DateTimePicker } from "@/components/ui/DatePicker/DatePicker";

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

    const from = parseISODate(dateFrom);
    const to = parseISODate(dateTo);

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
                  <DateTimePicker
                    value={parseISODate(dateFrom)}
                    onChange={(d) => onDateFromChange(formatDate(d))}
                    withTime={false}
                  />
                  <span className="text-xs text-zinc-400">—</span>
                  <DateTimePicker
                    value={parseISODate(dateTo)}
                    onChange={(d) => onDateToChange(formatDate(d))}
                    withTime={false}
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
