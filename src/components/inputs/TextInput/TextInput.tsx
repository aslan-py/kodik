"use client";

import { Input } from "@/components/ui/Input";

type TextInputProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  inputClassName?: string;
  width?: string;
  height?: string;
  multiline?: boolean;
};

export function TextInput({ inputClassName, ...props }: TextInputProps) {
  return <Input inputClassName={inputClassName} {...props} />;
}