"use client";

import { Select } from "@/components/ui/Select";

type Option = {
  label: string;
  value: string;
};

type SelectFilterProps = {
  label?: string;
  /** Подпись для варианта "показать всё", например «Все статусы». Если не передана, используется «Все». */
  allLabel?: string;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  className?: string;
};

export function SelectFilter({
  label,
  allLabel = "Все",
  value,
  options,
  onChange,
  className = "",
}: SelectFilterProps) {
  const allOption: Option = { label: allLabel, value: "" };

  return (
    <Select
      label={label}
      className={className}
      value={value}
      placeholder={allLabel}
      options={[allOption, ...options]}
      onChange={onChange}
    />
  );
}