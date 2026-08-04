"use client";

import { Select } from "@/components/ui/Select";

type Option = {
  label: string;
  value: string;
};

type TableSelectProps = {
  label?: string;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  className?: string;
};

export function SelectFilter({
  label,
  value,
  options,
  onChange,
  className = "",
}: TableSelectProps) {
  const allOption = { label: `Все ${label}`, value: "" };

  return (
    <Select
      label={label}
      className={className}
      value={value}
      placeholder={`Все ${label}`}
      options={[allOption, ...options]}
      onChange={onChange}
    />
  );
}