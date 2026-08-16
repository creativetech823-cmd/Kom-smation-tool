import type { ReactNode } from "react";
import { PipelineProjectClient } from "./PipelineProjectClient";

export default async function PipelineProjectLayout({
  params,
}: {
  children: ReactNode;
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <PipelineProjectClient projectId={projectId} />;
}
