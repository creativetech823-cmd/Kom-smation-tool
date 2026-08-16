"use client";

import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/lib/utils";

export type ToastTone = "neutral" | "success" | "danger";
export type ToastState = { message: string; tone?: ToastTone } | null;

const toneClasses: Record<ToastTone, string> = {
  neutral: "border-[var(--border-strong)] bg-[var(--surface-3)] text-[var(--foreground)]",
  success: "border-[var(--success)]/30 bg-[var(--surface-3)] text-[var(--success)]",
  danger: "border-[var(--danger)]/30 bg-[var(--surface-3)] text-[var(--danger)]",
};

export function ToastHost({ toast }: { toast: ToastState }) {
  return (
    <div className="pointer-events-none fixed bottom-6 left-1/2 z-50 -translate-x-1/2">
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.96 }}
            transition={{ duration: 0.2 }}
            className={cn(
              "pointer-events-auto rounded-xl border px-4 py-2.5 text-[13px] font-medium shadow-[0_8px_24px_-8px_var(--shadow-color)]",
              toneClasses[toast.tone ?? "neutral"]
            )}
          >
            {toast.message}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
