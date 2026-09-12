import { HookStudioClient } from "./HookStudioClient";

export default async function HookStudioPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <HookStudioClient projectId={projectId} />;
}
