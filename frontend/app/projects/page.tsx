"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createProject, listProjects, logHistoryEvent, ApiError } from "@/lib/api";
import type { Project } from "@/lib/types";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Label, Textarea } from "@/components/ui/Field";
import { EmptyState } from "@/components/library/EmptyState";
import { useToast } from "@/components/shell/ToastProvider";

export default function ProjectsPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");

  const refresh = useCallback(() => {
    setLoading(true);
    return listProjects()
      .then(setProjects)
      .catch(() => showToast("Couldn't load projects.", "danger"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  async function handleCreate() {
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      const project = await createProject({ name: name.trim(), description, product_category: category });
      void logHistoryEvent({
        event_type: "created_project",
        summary: `Created project — ${project.name}`,
        project_id: project.id,
      });
      showToast("Project created", "success");
      router.push(`/projects/${project.id}`);
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Couldn't create project.", "danger");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-[20px] font-semibold tracking-tight text-[var(--foreground)]">Projects</h1>
          <p className="mt-1 text-[13px] text-[var(--muted)]">
            Campaigns and workspaces that group scripts, images, videos, voiceovers and renders together.
          </p>
        </div>
        <Button onClick={() => setCreating((c) => !c)}>{creating ? "Cancel" : "New Project"}</Button>
      </div>

      {creating && (
        <Card>
          <CardBody className="pt-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label>Project name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="GreenLeaf Herbal Tea" />
              </div>
              <div>
                <Label>Product category</Label>
                <Input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Wellness" />
              </div>
              <div className="sm:col-span-2">
                <Label>Description</Label>
                <Textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  placeholder="What is this campaign about?"
                />
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <Button onClick={handleCreate} loading={submitting} disabled={!name.trim()}>
                Create Project
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {loading ? (
        <p className="text-[13px] text-[var(--muted)]">Loading projects…</p>
      ) : projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          message="Create your first content project."
          actionLabel="New Project"
          onAction={() => setCreating(true)}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Card key={project.id} className="flex flex-col">
              <CardBody className="flex flex-1 flex-col gap-2 pt-6">
                <p className="text-[14px] font-semibold text-[var(--foreground)]">{project.name}</p>
                {project.product_category && (
                  <span className="w-fit rounded-full bg-[var(--accent-soft)] px-2.5 py-1 text-[11px] font-medium text-[var(--accent)]">
                    {project.product_category}
                  </span>
                )}
                {project.description && (
                  <p className="line-clamp-2 text-[12.5px] leading-relaxed text-[var(--muted)]">
                    {project.description}
                  </p>
                )}
                <p className="text-[11.5px] text-[var(--muted)]">
                  {project.asset_count} asset{project.asset_count === 1 ? "" : "s"} · Updated{" "}
                  {new Date(project.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                </p>
                <div className="mt-auto pt-3">
                  <Button size="sm" variant="secondary" onClick={() => router.push(`/projects/${project.id}`)}>
                    Open
                  </Button>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
