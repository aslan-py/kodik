"use client";

import { Icon } from "@ui/Icon/Icon";
import { Input } from "@ui/Input";

type SearchInputProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
};

export function SearchInput({
  value,
  onChange,
  placeholder = "Поиск...",
  className = "",
}: SearchInputProps) {
  return (
    <Input
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className={className}
      startIcon={<Icon name="search" />}
    />
  );
}