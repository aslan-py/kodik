"use client";

import { useState } from "react";
import { Input } from "../Input";

type InlineCommentProps = {
  label?: string;
  placeholder?: string;
  height?: string;
};

export function InlineComment({
  label = "Комментарий аналитика",
  placeholder = "Введите комментарий...",
  height,
}: InlineCommentProps) {
  const [show, setShow] = useState(false);
  const [value, setValue] = useState("");

  if (!show) {
    return (
      <button
        type="button"
        onClick={() => setShow(true)}
        className="text-(--color-accent) text-sm cursor-pointer bg-transparent border-none p-0 text-left"
      >
        + {label}
      </button>
    );
  }

  return (
    <div>
      <p className="text-(--color-secondary) mb-2">{label}</p>
      <Input
        id="comment"
        multiline
        height={height}
        inputClassName="py-3"
        value={value}
        onChange={setValue}
        placeholder={placeholder}
      />
    </div>
  );
}