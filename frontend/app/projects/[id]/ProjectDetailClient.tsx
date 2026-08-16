"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  deleteProject,
  getProject,
  listAssets,
  updateAsset,
  updateProject,
} from "@/lib/api";
import type { ContentAsset, ContentAssetType, Project } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/library/EmptyState";
import { ContentAssetCard } from "@/components/library/ContentAssetCard";
import { ScriptAssetCard } from "@/components/library/ScriptAssetCard";
import { useActiveProject } from "@/lib/project-context";
import { useToast } from "@/components/shell/ToastProvider";

const TABS: { key: ContentAssetType | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "script", label: "Scripts" },
  { key: "image", label: "Images" },
  { key: "video", label: "Videos" },
  { key: "voiceover", label: "Voiceovers" },
  { key: "render", label: "Renders" },
];

export function ProjectDetailClient({ projectId }: { projectId: string }) {
  const router = useRouter();
  const { showToast } = useToast();
  const { activeProjectId, setActiveProject } = useActiveProject();
  const [project, setProject] = useState<Project | null>(null);
  const [assets, setAssets] = useState<ContentAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<ContentAssetType | "all">("all");

  const refresh = useCallback(() => {
    setLoading(true);
    return Promise.all([getProject(projectId), listAssets({ project_id: projectId })])
      .then(([p, a]) => {
        setProject(p);
        setAssets(a);
      })
      .catch(() => showToast("Couldn't load this project.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  function handleToggleFavorite(id: string, next: boolean) {
    setAssets((prev) => prev.map((a) => (a.id === id ? { ...a, is_favorite: next } : a)));
    void updateAsset(id, { is_favorite: next }).catch(() => {});
  }

  async function handleArchive() {
    if (!project) return;
    const next = project.status === "archived" ? "active" : "archived";
    try {
      const updated = await updateProject(project.id, { status: next });
      setProject(updated);
      showToast(next === "archived" ? "Project archived" : "Project restored", "success");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't update project.", "danger");
    }
  }

  async function handleDelete() {
    if (!project) return;
    if (!window.confirm(`Delete "${project.name}"? Its assets will remain in your Content Library.`)) return;
    try {
      await deleteProject(project.id);
      if (activeProjectId === project.id) setActiveProject(null);
      showToast("Project deleted", "success");
      router.push("/projects");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't delete project.", "danger");
    }
  }

  const filtered = tab === "all" ? assets : assets.filter((a) => a.asset_type === tab);
  const isActive = activeProjectId === projectId;

  if (loading && !project) {
    return (
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
        <p className="text-[13px] text-[var(--muted)]">Loading project…</p>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
        <EmptyState title="Project not found" message="This project may have been deleted." />
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
      <Card>
        <CardBody className="flex flex-col gap-3 pt-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-[19px] font-semibold tracking-tight text-[var(--foreground)]">{project.name}</h1>
                {project.status === "archived" && <Badge tone="warning">Archived</Badge>}
                {isActive && <Badge tone="accent">Active</Badge>}
              </div>
              {project.product_category && (
                <span className="mt-1 inline-block rounded-full bg-[var(--accent-soft)] px-2.5 py-1 text-[11px] font-medium text-[var(--accent)]">
                  {project.product_category}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant={isActive ? "secondary" : "primary"}
                onClick={() => setActiveProject(isActive ? null : project.id, isActive ? null : project.name)}
              >
                {isActive ? "Unset Active" : "Set as Active Project"}
              </Button>
              <Button size="sm" variant="secondary" onClick={handleArchive}>
                {project.status === "archived" ? "Restore" : "Archive"}
              </Button>
              <Button size="sm" variant="danger" onClick={handleDelete}>
                Delete
              </Button>
            </div>
          </div>
          {project.description && <p className="text-[13px] leading-relaxed text-[var(--muted)]">{project.description}</p>}
          <p className="text-[11.5px] text-[var(--muted)]">
            {assets.length} asset{assets.length === 1 ? "" : "s"} · Created{" "}
            {new Date(project.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
          </p>
        </CardBody>
      </Card>

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

      {filtered.length === 0 ? (
        <EmptyState
          title="Your content will appear here"
          message="Generate a script, image, or video from the Content Pipeline while this project is active."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((asset) =>
            asset.asset_type === "script" ? (
              <ScriptAssetCard key={asset.id} asset={asset} onToggleFavorite={handleToggleFavorite} />
            ) : (
              <ContentAssetCard key={asset.id} asset={asset} onToggleFavorite={handleToggleFavorite} />
            )
          )}
        </div>
      )}
    </div>
  );
}
