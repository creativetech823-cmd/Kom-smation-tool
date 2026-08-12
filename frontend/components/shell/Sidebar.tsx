"use client";

import { type ReactNode, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/lib/utils";

type SidebarItem = { key: string; label: string; icon: ReactNode; active?: boolean; comingSoon?: boolean };

export function Sidebar({ onToast }: { onToast: (message: string) => void }) {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    // Deferred to after mount, not a lazy useState initializer: the server has no
    // access to localStorage, so reading it during the initial client render would
    // mismatch the server-rendered HTML and trigger a hydration error.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCollapsed(window.localStorage.getItem("cf:sidebar-collapsed") === "1");
  }, []);

  function toggle() {
    setCollapsed((c) => {
      const next = !c;
      window.localStorage.setItem("cf:sidebar-collapsed", next ? "1" : "0");
      return next;
    });
  }

  const items: SidebarItem[] = [
    { key: "pipeline", label: "Content Pipeline", icon: <IconPipeline />, active: true },
    { key: "projects", label: "Projects", icon: <IconProjects />, comingSoon: true },
    { key: "templates", label: "Templates", icon: <IconTemplates />, comingSoon: true },
    { key: "history", label: "History", icon: <IconHistory />, comingSoon: true },
    { key: "library", label: "Content Library", icon: <IconLibrary />, comingSoon: true },
  ];
  const bottomItems: SidebarItem[] = [
    { key: "settings", label: "Settings", icon: <IconSettings />, comingSoon: true },
    { key: "help", label: "Help", icon: <IconHelp />, comingSoon: true },
  ];

  function handleClick(item: SidebarItem) {
    if (item.comingSoon) onToast(`${item.label} — coming soon`);
  }

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 220 }}
      transition={{ duration: 0.25, ease: "easeInOut" }}
      className="sticky top-0 flex h-screen shrink-0 flex-col overflow-hidden border-r border-[var(--border)] bg-[var(--surface)]/60 py-4 backdrop-blur-xl"
    >
      <div className="flex items-center px-3">
        {!collapsed && (
          <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
            Workspace
          </span>
        )}
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="ml-auto flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[var(--muted)] transition-colors hover:bg-white/[0.06] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          <IconChevron collapsed={collapsed} />
        </button>
      </div>

      <nav className="mt-4 flex flex-1 flex-col gap-1 px-2">
        {items.map((item) => (
          <SidebarButton key={item.key} item={item} collapsed={collapsed} onClick={() => handleClick(item)} />
        ))}
        <div className="my-2 h-px bg-[var(--border)]" />
        {bottomItems.map((item) => (
          <SidebarButton key={item.key} item={item} collapsed={collapsed} onClick={() => handleClick(item)} />
        ))}
      </nav>

      <div className="mt-auto flex items-center gap-2.5 border-t border-[var(--border)] px-3 pt-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[var(--accent)] to-[var(--accent-2)] text-[12px] font-semibold text-white">
          CF
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="min-w-0">
              <p className="truncate text-[13px] font-medium text-[var(--foreground)]">Creator</p>
              <p className="truncate text-[11px] text-[var(--muted)]">Free workspace</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.aside>
  );
}

function SidebarButton({
  item,
  collapsed,
  onClick,
}: {
  item: SidebarItem;
  collapsed: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={collapsed ? item.label : undefined}
      className={cn(
        "flex items-center gap-3 rounded-xl px-2.5 py-2 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
        item.active
          ? "bg-[var(--accent-soft)] text-[var(--accent)]"
          : "text-[var(--muted)] hover:bg-white/[0.05] hover:text-[var(--foreground)]"
      )}
    >
      <span className="flex h-5 w-5 shrink-0 items-center justify-center">{item.icon}</span>
      <AnimatePresence>
        {!collapsed && (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="truncate"
          >
            {item.label}
          </motion.span>
        )}
      </AnimatePresence>
      {!collapsed && item.comingSoon && (
        <span className="ml-auto shrink-0 rounded-full bg-white/[0.06] px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-[var(--muted)]">
          Soon
        </span>
      )}
    </button>
  );
}

function IconChevron({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      style={{ transform: collapsed ? "rotate(180deg)" : undefined, transition: "transform .2s" }}
    >
      <path d="M15 6l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconPipeline() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M12 2l9 5v10l-9 5-9-5V7l9-5z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M3 7l9 5 9-5M12 12v10" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

function IconProjects() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path
        d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconTemplates() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="13" y="3" width="8" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="13" y="12" width="8" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function IconHistory() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 7v5l3.5 2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconLibrary() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M4 4h6v16H4a1 1 0 01-1-1V5a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M14 4h6a1 1 0 011 1v14a1 1 0 01-1 1h-6V4z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconHelp() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M9.5 9.5a2.5 2.5 0 114 2c-.7.6-1.5 1-1.5 2.2"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M12 17.5v.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
