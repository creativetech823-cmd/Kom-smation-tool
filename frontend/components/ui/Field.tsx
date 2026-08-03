"use client";

import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const baseInputClasses =
  "w-full rounded-xl border border-[var(--border-strong)] bg-[var(--surface-2)] px-3.5 py-2.5 text-[14px] text-[var(--foreground)] placeholder:text-[var(--muted)] outline-none transition-colors focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/25";

export function Label({ children }: { children: React.ReactNode }) {
  return (
    <label className="mb-1.5 block text-[13px] font-medium text-[var(--muted)]">
      {children}
    </label>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(baseInputClasses, props.className)} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn(baseInputClasses, "resize-none", props.className)} />;
}
