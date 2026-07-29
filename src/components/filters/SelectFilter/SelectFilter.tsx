"use client";

import { Select, SelectItem } from "@/components/ui/Select";

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
  const selectedLabel = options.find((o) => o.value === value)?.label ?? "Все";

  return (
    <Select label={label} className={className} buttonContent={<span className="text-(--color-strong)">{selectedLabel} {label}</span>}>
      {(setOpen) => (
        <>
          <SelectItem active={!value} onClick={() => { onChange(""); setOpen(false); }}>
            Все {label}
          </SelectItem>
          {options.map((option) => (
            <SelectItem
              key={option.value}
              active={option.value === value}
              onClick={() => { onChange(option.value); setOpen(false); }}
            >
              {option.label}
            </SelectItem>
          ))}
        </>
      )}
    </Select>
  );
}