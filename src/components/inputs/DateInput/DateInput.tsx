"use client";

import { Input } from "@ui/Input";

type DateInputProps = {
  value: string;
  onChange: (value: string) => void;
  className?: string;
};

export function DateInput({ className = "", ...rest }: DateInputProps) {
  return <Input type="date" inputClassName="scheme-light" className={className} {...rest} />;
}