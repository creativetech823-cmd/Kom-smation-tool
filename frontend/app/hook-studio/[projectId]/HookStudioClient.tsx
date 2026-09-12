"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { HookStudioApp } from "@/components/hookstudio/HookStudioApp";
import { ApiError, getProject } from "@/lib/api";
import type { Project } from "@/lib/types";

// Deliberately does NOT call setActiveProject (unlike PipelineProjectClient) —
// a Hook Studio session must stay invisible to "/"'s resume-into-pipeline
// redirect, since it isn't a 7-stage pipeline session.
export function HookStudioClient({ projectId }: { projectId: string }) {
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
  }, [projectId]);

  if (loading) {
    return (
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 items-center justify-center px-6 py-10">
        <p className="text-[13px] text-[var(--muted)]">Loading your script studio…</p>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col items-center justify-center gap-3 px-6 py-10 text-center">
        <p className="text-[15px] font-semibold text-[var(--foreground)]">Project not found</p>
        <p className="max-w-md text-[13px] text-[var(--muted)]">{error}</p>
        <Link
          href="/hooks"
          className="mt-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-[12.5px] font-medium text-[var(--on-accent)] hover:brightness-110"
        >
          Back to Hooks Library
        </Link>
      </div>
    );
  }

  return <HookStudioApp projectId={projectId} initialProject={project} />;
}
