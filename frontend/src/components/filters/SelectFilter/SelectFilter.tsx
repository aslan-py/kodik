"use client";

import { Select } from "@/components/ui/Select/Select";
import { FilterOption } from "@/types/types";


type SelectFilterProps<T extends string> = {
  label: string;
  allLabel?: string;
  value: T | "";
  options: FilterOption<T>[];
  onChange: (value: T | "") => void;
  className?: string;
};

export function SelectFilter<T extends string>({
  label,
  allLabel = "Все",
  value,
  options,
  onChange,
  className = "",
}: SelectFilterProps<T>) {
  const allOption: FilterOption<T | ""> = { label: allLabel, value: "" };

  return (
    <Select<T | "">
      label={label}
      className={className}
      value={value}
      placeholder={allLabel}
      options={[allOption, ...options]}
      onChange={onChange}
    />
  );
}