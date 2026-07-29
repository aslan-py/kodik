"use client";

import { Input } from "@ui/Input";

type TextInputProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  width?: string;
  height?: string;
  multiline?: boolean;
};

export function TextInput(props: TextInputProps) {
  return <Input {...props} />;
}