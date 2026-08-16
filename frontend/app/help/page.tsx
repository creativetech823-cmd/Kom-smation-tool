import { Card, CardHeader, CardBody } from "@/components/ui/Card";

const FAQS: { q: string; a: string }[] = [
  {
    q: "Where does generated content go?",
    a: "Every script, image, video, voiceover and render you generate in the Content Pipeline is saved automatically to Content Library — no manual save step needed. If a project is set active, it's also attached to that project.",
  },
  {
    q: "How do I reuse a hook in a script?",
    a: "In the Script step of the pipeline, click \"Choose Hook\" to browse the Hooks Library and pick one. It's used as the opening line the next time you generate the script.",
  },
  {
    q: "What's the difference between Content Library and History?",
    a: "Content Library answers \"what have I created\" — the actual assets. History answers \"what actions have I taken\" — a timeline of events, some of which link back to the content they produced.",
  },
  {
    q: "How do Favorites work?",
    a: "Click the heart icon on any script, hook, image, video, voiceover or template. It's a flag on the existing item, not a copy — unfavoriting removes it from Favorites without deleting the original.",
  },
  {
    q: "Can I use an official template as a starting point for my own?",
    a: "Yes — click Duplicate on any official template in Templates to save an editable copy under My Templates.",
  },
];

export default function HelpPage() {
  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-6 py-10 lg:px-10 xl:px-12">
      <div>
        <h1 className="text-[20px] font-semibold tracking-tight text-[var(--foreground)]">Help</h1>
        <p className="mt-1 text-[13px] text-[var(--muted)]">Answers to common questions about the pipeline and content management.</p>
      </div>

      <Card>
        <CardHeader title="Frequently asked" />
        <CardBody>
          <div className="divide-y divide-[var(--border)]">
            {FAQS.map((faq) => (
              <div key={faq.q} className="py-3.5 first:pt-0 last:pb-0">
                <p className="text-[13.5px] font-medium text-[var(--foreground)]">{faq.q}</p>
                <p className="mt-1 text-[13px] leading-relaxed text-[var(--muted)]">{faq.a}</p>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
