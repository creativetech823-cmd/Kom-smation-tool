// Intentionally empty — all rendering happens in the parent layout
// (app/pipeline/[projectId]/layout.tsx), which stays mounted across
// navigation between sibling [stage] segments. PipelineApp reads the
// current stage reactively via useParams(). A page.tsx is still required
// here purely so this segment is a navigable route.
export default function PipelineStagePage() {
  return null;
}
