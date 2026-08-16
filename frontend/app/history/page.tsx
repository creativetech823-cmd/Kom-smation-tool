"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listHistory } from "@/lib/api";
import type { HistoryEvent, HistoryEventType } from "@/lib/types";
import { EmptyState } from "@/components/library/EmptyState";
import { useToast } from "@/components/shell/ToastProvider";

const EVENT_LABEL: Record<HistoryEventType, string> = {
  created_project: "Created project",
  generated_script: "Generated script",
  generated_image: "Generated image",
  generated_video: "Generated video",
  generated_voiceover: "Generated voiceover",
  used_template: "Used template",
  used_hook: "Used hook",
  edited_script: "Edited script",
  exported_video: "Exported video",
  deleted_content: "Deleted content",
  restored_content: "Restored content",
};

const EVENT_ICON: Record<HistoryEventType, string> = {
  created_project: "📁",
  generated_script: "📝",
  generated_image: "🖼️",
  generated_video: "🎬",
  generated_voiceover: "🎙️",
  used_template: "🧩",
  used_hook: "🪝",
  edited_script: "✏️",
  exported_video: "⬇️",
  deleted_content: "🗑️",
  restored_content: "♻️",
};

function dayLabel(date: Date): string {
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  if (sameDay(date, today)) return "Today";
  if (sameDay(date, yesterday)) return "Yesterday";
  return date.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });
}

export default function HistoryPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [events, setEvents] = useState<HistoryEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listHistory({ limit: 300 })
      .then(setEvents)
      .catch(() => showToast("Couldn't load history.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleClick(event: HistoryEvent) {
    if (event.asset_id) {
      router.push(`/library?highlight=${event.asset_id}`);
    } else if (event.project_id) {
      router.push(`/projects/${event.project_id}`);
    }
  }

  const groups = new Map<string, HistoryEvent[]>();
  for (const event of events) {
    const date = new Date(event.created_at);
    const key = dayLabel(date);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(event);
  }

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
      <div>
        <h1 className="text-[20px] font-semibold tracking-tight text-[var(--foreground)]">History</h1>
        <p className="mt-1 text-[13px] text-[var(--muted)]">A record of actions you&apos;ve taken, not just what you&apos;ve created.</p>
      </div>

      {loading ? (
        <p className="text-[13px] text-[var(--muted)]">Loading history…</p>
      ) : events.length === 0 ? (
        <EmptyState title="Nothing here yet" message="Actions like generating a script or creating a project will show up here." />
      ) : (
        <div className="flex flex-col gap-8">
          {Array.from(groups.entries()).map(([label, items]) => (
            <div key={label} className="flex flex-col gap-2">
              <h2 className="text-[13px] font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</h2>
              <div className="flex flex-col divide-y divide-[var(--border)] overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
                {items.map((event) => {
                  const clickable = Boolean(event.asset_id || event.project_id);
                  const time = new Date(event.created_at).toLocaleTimeString(undefined, {
                    hour: "numeric",
                    minute: "2-digit",
                  });
                  return (
                    <button
                      key={event.id}
                      type="button"
                      disabled={!clickable}
                      onClick={() => handleClick(event)}
                      className={`flex items-center gap-3 px-4 py-3 text-left transition-colors ${
                        clickable ? "hover:bg-[var(--foreground)]/[0.04]" : "cursor-default"
                      }`}
                    >
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--surface-2)] text-[14px]">
                        {EVENT_ICON[event.event_type]}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-medium text-[var(--foreground)]">
                          {event.summary || EVENT_LABEL[event.event_type]}
                        </p>
                        <p className="truncate text-[11.5px] text-[var(--muted)]">
                          {event.project_name ?? EVENT_LABEL[event.event_type]}
                        </p>
                      </div>
                      <span className="shrink-0 text-[11.5px] text-[var(--muted)]">{time}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
