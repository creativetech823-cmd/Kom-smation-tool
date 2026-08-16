import { Card, CardHeader, CardBody } from "@/components/ui/Card";

export default function SettingsPage() {
  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
      <div>
        <h1 className="text-[20px] font-semibold tracking-tight text-[var(--foreground)]">Settings</h1>
        <p className="mt-1 text-[13px] text-[var(--muted)]">Workspace preferences and account info.</p>
      </div>

      <Card>
        <CardHeader title="Workspace" subtitle="Your current Content Factory workspace" />
        <CardBody className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-[13px] font-semibold text-[var(--on-accent)]">
            CF
          </div>
          <div>
            <p className="text-[13.5px] font-medium text-[var(--foreground)]">Creator</p>
            <p className="text-[12px] text-[var(--muted)]">Free workspace · Single-user mode</p>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="About" subtitle="What powers this pipeline" />
        <CardBody className="space-y-1.5 text-[13px] text-[var(--muted)]">
          <p>Content Factory generates scripts, storyboard images, voiceovers and rendered ads from a single product input, and now automatically organizes everything you create into Projects, a searchable Content Library, and Favorites.</p>
        </CardBody>
      </Card>
    </div>
  );
}
