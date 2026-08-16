"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, duplicateTemplate, listTemplates, logHistoryEvent, updateTemplate } from "@/lib/api";
import type { Template, TemplateKind } from "@/lib/types";
import { EmptyState } from "@/components/library/EmptyState";
import { TemplateCard } from "@/components/library/TemplateCard";
import { useActiveProject } from "@/lib/project-context";
import { useToast } from "@/components/shell/ToastProvider";
import { ACTIVE_TEMPLATE_KEY } from "@/lib/constants";

const TABS: { key: TemplateKind | "mine"; label: string }[] = [
  { key: "static", label: "Static Templates" },
  { key: "video", label: "Video Templates" },
  { key: "mine", label: "My Templates" },
];

export default function TemplatesPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const { activeProjectId } = useActiveProject();
  const [tab, setTab] = useState<TemplateKind | "mine">("static");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    const params = tab === "mine" ? { mine: true } : { kind: tab };
    listTemplates(params)
      .then(setTemplates)
      .catch(() => showToast("Couldn't load templates.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  function handleToggleFavorite(id: string, next: boolean) {
    setTemplates((prev) => prev.map((t) => (t.id === id ? { ...t, is_favorite: next } : t)));
    void updateTemplate(id, { is_favorite: next }).catch(() => {});
  }

  async function handleDuplicate(template: Template) {
    try {
      const copy = await duplicateTemplate(template.id);
      showToast(`Saved as "${copy.name}" in My Templates`, "success");
      if (tab === "mine") setTemplates((prev) => [copy, ...prev]);
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't duplicate that template.", "danger");
    }
  }

  function handleUse(template: Template) {
    window.localStorage.setItem(
      ACTIVE_TEMPLATE_KEY,
      JSON.stringify({ id: template.id, name: template.name, category: template.category })
    );
    void logHistoryEvent({
      event_type: "used_template",
      summary: `Used template — ${template.name}`,
      project_id: activeProjectId ?? undefined,
    });
    showToast(`Using "${template.name}" in the pipeline`, "success");
    router.push("/");
  }

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
      <div>
        <h1 className="text-[20px] font-semibold tracking-tight text-[var(--foreground)]">Templates</h1>
        <p className="mt-1 text-[13px] text-[var(--muted)]">
          Official starting points for static and video creatives, plus templates you&apos;ve saved.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`rounded-full border px-3.5 py-1.5 text-[12.5px] font-medium transition-colors ${
              tab === t.key
                ? "border-[var(--accent)]/40 bg-[var(--accent-soft)] text-[var(--accent)]"
                : "border-[var(--border-strong)] text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-[13px] text-[var(--muted)]">Loading templates…</p>
      ) : templates.length === 0 ? (
        <EmptyState
          title={tab === "mine" ? "No saved templates yet" : "No templates found"}
          message={
            tab === "mine"
              ? "Duplicate an official template to start customizing your own."
              : "Try another tab."
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => (
            <TemplateCard
              key={template.id}
              template={template}
              onToggleFavorite={handleToggleFavorite}
              onUse={handleUse}
              onDuplicate={handleDuplicate}
            />
          ))}
        </div>
      )}
    </div>
  );
}
