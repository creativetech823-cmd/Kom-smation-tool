"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PipelineApp } from "@/components/pipeline/PipelineApp";
import { useActiveProject } from "@/lib/project-context";
import { ApiError, getProject } from "@/lib/api";
import type { Project } from "@/lib/types";

/** Lives in a layout (not a page) on purpose — Next.js preserves layout
 * state across navigation between sibling [stage] segments, so selecting a
 * story angle and generating a script no longer remounts the whole pipeline
 * (which used to re-fetch the project mid-flight and show stale/missing
 * data — see the Story-page-after-Generate-Script regression). */
export function PipelineProjectClient({ projectId }: { projectId: string }) {
  const { setActiveProject } = useActiveProject();
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getProject(projectId)
      .then((p) => {
        if (cancelled) return;
        setProject(p);
        setActiveProject(p.id, p.name);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(
          e instanceof ApiError && e.status === 404
            ? "This project doesn't exist or may have been deleted."
            : "Couldn't load this project — check your connection and try again."
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  if (loading) {
    return (
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 items-center justify-center px-6 py-10">
        <p className="text-[13px] text-[var(--muted)]">Restoring your project…</p>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col items-center justify-center gap-3 px-6 py-10 text-center">
        <p className="text-[15px] font-semibold text-[var(--foreground)]">Project not found</p>
        <p className="max-w-md text-[13px] text-[var(--muted)]">{error}</p>
        <Link
          href="/"
          className="mt-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-[12.5px] font-medium text-[var(--on-accent)] hover:brightness-110"
        >
          Start a new project
        </Link>
      </div>
    );
  }

  return <PipelineApp projectId={projectId} initialProject={project} />;
}
