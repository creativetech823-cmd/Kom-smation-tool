"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PipelineApp } from "@/components/pipeline/PipelineApp";
import { useActiveProject } from "@/lib/project-context";
import { ApiError, getProject } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const { activeProjectId, setActiveProject } = useActiveProject();
  // "checking" briefly gates the very first render so a stale active-project
  // pointer never flashes a fresh pipeline before the redirect fires.
  const [phase, setPhase] = useState<"checking" | "fresh">("checking");

  useEffect(() => {
    let cancelled = false;
    if (!activeProjectId) {
      // useActiveProject itself resolves from localStorage one tick after
      // mount — undefined-vs-null here would misfire, so wait for its own
      // effect to have run at least once before deciding there's nothing to resume.
      const timer = setTimeout(() => {
        if (!cancelled) setPhase("fresh");
      }, 0);
      return () => {
        cancelled = true;
        clearTimeout(timer);
      };
    }
    getProject(activeProjectId)
      .then((project) => {
        if (cancelled) return;
        const stage = project.pipeline_stage || "product";
        router.replace(`/pipeline/${project.id}/${stage}`);
      })
      .catch((e) => {
        if (cancelled) return;
        // The remembered project is gone or unreachable — fall back to a
        // fresh session rather than getting stuck on a loading screen.
        if (e instanceof ApiError && e.status === 404) {
          // The project this pointer refers to no longer exists (deleted,
          // or from a previous DB) — clear it so it isn't re-requested (and
          // 404s again) on every future visit to this page.
          setActiveProject(null);
        }
        setPhase("fresh");
      });
    return () => {
      cancelled = true;
    };
    // setActiveProject is a new function identity on every ProjectProvider
    // render (not memoized) — including it here would re-fire this effect
    // (and re-request the same project) on unrelated parent re-renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProjectId, router]);

  if (phase === "checking") {
    return (
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 items-center justify-center px-6 py-10">
        <p className="text-[13px] text-[var(--muted)]">Restoring your project…</p>
      </div>
    );
  }

  return <PipelineApp projectId={null} initialProject={null} />;
}
