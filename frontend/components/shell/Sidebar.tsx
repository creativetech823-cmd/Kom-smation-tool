"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { listAyushProducts } from "@/lib/api";
import { PRODUCT_CATEGORIES, type AyushProduct } from "@/lib/types";
import { cn } from "@/lib/utils";

type SidebarItem = { key: string; label: string; href: string; icon: ReactNode };
type SidebarGroup = { label: string; items: SidebarItem[] };

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  // Session-persisted (component never unmounts across client-side nav) —
  // starts expanded so a fresh session sees the catalog immediately.
  const [treeOpen, setTreeOpen] = useState(true);
  const [openCategories, setOpenCategories] = useState<Set<string>>(
    () => new Set(PRODUCT_CATEGORIES.map((c) => c.value))
  );
  const [ayushProducts, setAyushProducts] = useState<AyushProduct[] | null>(null);
  const [ayushProductsFailed, setAyushProductsFailed] = useState(false);
  const [retryTick, setRetryTick] = useState(0);
  // Caps the automatic retry to once per failure streak — never hammers a
  // genuinely-down backend, just smooths over a one-off blip (e.g. the dev
  // server mid-restart from `uvicorn --reload`) without the user noticing.
  const autoRetriedRef = useRef(false);

  useEffect(() => {
    // Deferred to after mount, not a lazy useState initializer: the server has no
    // access to localStorage, so reading it during the initial client render would
    // mismatch the server-rendered HTML and trigger a hydration error.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCollapsed(window.localStorage.getItem("cf:sidebar-collapsed") === "1");
  }, []);

  useEffect(() => {
    // Refetch on every navigation so a product created/archived elsewhere
    // (the Add Product page, archiving from the detail page) is reflected
    // here without needing a global event bus — this is a small catalog, so
    // a GET per navigation is cheap.
    //
    // A transient failure (e.g. the dev backend mid-restart from
    // `uvicorn --reload`, or a brief network blip) must never be silently
    // treated as "this category genuinely has zero products" — that used to
    // collapse a failed fetch straight to an empty array, which rendered
    // identically to "No products yet" with no way to recover short of
    // navigating to a different route and back. Now it's a distinct,
    // honest "couldn't load" state with a one-click retry, and only ever
    // falls back to an empty list if a PRIOR successful fetch actually
    // returned one (a real, confirmed "no products" case).
    let cancelled = false;
    listAyushProducts()
      .then((products) => {
        if (cancelled) return;
        setAyushProducts(products);
        setAyushProductsFailed(false);
        autoRetriedRef.current = false; // a real success resets the retry budget for next time
      })
      .catch(() => {
        if (cancelled) return;
        setAyushProductsFailed(true);
        // A transient blip (classic case: this dev backend restarts on every
        // file save) is usually gone within a second — one silent, automatic
        // retry recovers from that without the user ever seeing an error.
        if (!autoRetriedRef.current) {
          autoRetriedRef.current = true;
          setTimeout(() => {
            if (!cancelled) setRetryTick((t) => t + 1);
          }, 1500);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [pathname, retryTick]);

  function retryAyushProducts() {
    autoRetriedRef.current = false;
    setRetryTick((t) => t + 1);
  }

  function toggleCategory(value: string) {
    setOpenCategories((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  function toggle() {
    setCollapsed((c) => {
      const next = !c;
      window.localStorage.setItem("cf:sidebar-collapsed", next ? "1" : "0");
      return next;
    });
  }

  const groups: SidebarGroup[] = [
    {
      label: "Create",
      items: [{ key: "pipeline", label: "Content Pipeline", href: "/", icon: <IconPipeline /> }],
    },
    {
      label: "Library",
      items: [
        { key: "projects", label: "Projects", href: "/projects", icon: <IconProjects /> },
        { key: "templates", label: "Templates", href: "/templates", icon: <IconTemplates /> },
        { key: "hooks", label: "Hooks", href: "/hooks", icon: <IconHooks /> },
        { key: "library", label: "Content Library", href: "/library", icon: <IconLibrary /> },
        { key: "favorites", label: "Favorites", href: "/favorites", icon: <IconFavorites /> },
      ],
    },
    {
      label: "Activity",
      items: [{ key: "history", label: "History", href: "/history", icon: <IconHistory /> }],
    },
  ];
  const bottomItems: SidebarItem[] = [
    { key: "settings", label: "Settings", href: "/settings", icon: <IconSettings /> },
    { key: "help", label: "Help", href: "/help", icon: <IconHelp /> },
  ];

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 220 }}
      transition={{ duration: 0.25, ease: "easeInOut" }}
      className="sticky top-0 flex h-screen shrink-0 flex-col overflow-hidden border-r border-[var(--border)] bg-[var(--surface)] py-4"
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
          className="ml-auto flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[var(--muted)] transition-colors hover:bg-[var(--foreground)]/[0.06] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          <IconChevron collapsed={collapsed} />
        </button>
      </div>

      <nav className="mt-4 flex flex-1 flex-col gap-4 overflow-y-auto px-2">
        {groups.map((group) => (
          <div key={group.label} className="flex flex-col gap-1">
            {!collapsed && (
              <p className="px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]/70">
                {group.label}
              </p>
            )}
            {group.items.map((item) => (
              <SidebarButton key={item.key} item={item} collapsed={collapsed} active={isActive(item.href)} />
            ))}
            {group.label === "Library" && (
              <AyushProductTree
                collapsed={collapsed}
                pathname={pathname}
                treeOpen={treeOpen}
                setTreeOpen={setTreeOpen}
                openCategories={openCategories}
                toggleCategory={toggleCategory}
                products={ayushProducts}
                failed={ayushProductsFailed}
                onRetry={retryAyushProducts}
              />
            )}
          </div>
        ))}

        <div className="mt-auto flex flex-col gap-1">
          <div className="mb-2 h-px bg-[var(--border)]" />
          {bottomItems.map((item) => (
            <SidebarButton key={item.key} item={item} collapsed={collapsed} active={isActive(item.href)} />
          ))}
        </div>
      </nav>

      <div className="mt-3 flex items-center gap-2.5 border-t border-[var(--border)] px-3 pt-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-[12px] font-semibold text-[var(--on-accent)]">
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

function AyushProductTree({
  collapsed,
  pathname,
  treeOpen,
  setTreeOpen,
  openCategories,
  toggleCategory,
  products,
  failed,
  onRetry,
}: {
  collapsed: boolean;
  pathname: string;
  treeOpen: boolean;
  setTreeOpen: (fn: (v: boolean) => boolean) => void;
  openCategories: Set<string>;
  toggleCategory: (value: string) => void;
  products: AyushProduct[] | null;
  failed: boolean;
  onRetry: () => void;
}) {
  if (collapsed) {
    // Icon-only mode: a single nav item to the flat list page, matching how
    // every other sidebar entry behaves when collapsed — the tree itself
    // only makes sense expanded.
    return (
      <SidebarButton
        item={{ key: "ayush-products", label: "AyushWellness Products", href: "/ayush-products", icon: <IconAyushProducts /> }}
        collapsed={collapsed}
        active={pathname.startsWith("/ayush-products")}
      />
    );
  }

  // Defensive, ID-keyed dedup — the product's stable id is the identity,
  // never its display name. Guards the render even if the API ever returned
  // the same row twice; the actual fix for duplicate DATA is server-side
  // (normalized product_url matching in POST /product-library/products).
  const byId = new Map<string, AyushProduct>();
  for (const p of products ?? []) {
    if (!byId.has(p.id)) byId.set(p.id, p);
  }

  const byCategory = new Map<string, AyushProduct[]>();
  for (const p of byId.values()) {
    const list = byCategory.get(p.category);
    if (list) list.push(p);
    else byCategory.set(p.category, [p]);
  }

  return (
    <div className="flex flex-col gap-0.5">
      <button
        type="button"
        onClick={() => setTreeOpen((v) => !v)}
        className={cn(
          "flex items-center gap-2 rounded-xl px-2.5 py-2 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
          pathname.startsWith("/ayush-products")
            ? "bg-[var(--accent-soft)] text-[var(--accent)]"
            : "text-[var(--muted)] hover:bg-[var(--foreground)]/[0.05] hover:text-[var(--foreground)]"
        )}
      >
        <span className="flex h-5 w-5 shrink-0 items-center justify-center">
          <IconAyushProducts />
        </span>
        <span className="flex-1 truncate text-left">AyushWellness Products</span>
        <IconCaret open={treeOpen} />
      </button>

      {treeOpen && (
        <div className="ml-2.5 flex flex-col gap-0.5 border-l border-[var(--border)] pl-2.5">
          {PRODUCT_CATEGORIES.map((cat) => {
            const catProducts = byCategory.get(cat.value) ?? [];
            const open = openCategories.has(cat.value);
            return (
              <div key={cat.value} className="flex flex-col gap-0.5">
                <button
                  type="button"
                  onClick={() => toggleCategory(cat.value)}
                  className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[12.5px] font-medium text-[var(--muted)] transition-colors hover:bg-[var(--foreground)]/[0.05] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
                  title={cat.description}
                >
                  <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                    {cat.value === "nutraceuticals" ? <IconCapsule /> : <IconLeaf />}
                  </span>
                  <span className="flex-1 truncate text-left">{cat.label}</span>
                  <IconCaret open={open} small />
                </button>

                {open && (
                  <div className="ml-2 flex max-h-[260px] flex-col gap-0.5 overflow-y-auto border-l border-[var(--border)] pl-2.5">
                    {products === null && failed ? (
                      <button
                        type="button"
                        onClick={onRetry}
                        className="px-2 py-1 text-left text-[11.5px] text-[var(--danger)] hover:underline"
                      >
                        Couldn&apos;t load — retry
                      </button>
                    ) : products === null ? (
                      <p className="px-2 py-1 text-[11.5px] text-[var(--muted)]">Loading…</p>
                    ) : catProducts.length === 0 ? (
                      <p className="px-2 py-1 text-[11.5px] text-[var(--muted)]">No products yet</p>
                    ) : (
                      catProducts.map((p) => {
                        const href = `/ayush-products/${p.id}`;
                        const active = pathname === href;
                        const fullName = p.display_name || p.name;
                        return (
                          <Link
                            key={p.id}
                            href={href}
                            title={fullName}
                            aria-label={fullName}
                            className={cn(
                              "block rounded-lg px-2 py-1.5 text-[12.5px] leading-[1.35] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
                              active
                                ? "bg-[var(--accent-soft)] font-medium text-[var(--accent)]"
                                : "text-[var(--muted)] hover:bg-[var(--foreground)]/[0.05] hover:text-[var(--foreground)]"
                            )}
                          >
                            <span className="line-clamp-2 break-words">{fullName}</span>
                          </Link>
                        );
                      })
                    )}
                    <Link
                      href={`/ayush-products/new?category=${encodeURIComponent(cat.value)}`}
                      className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[12.5px] font-medium text-[var(--accent)] transition-colors hover:bg-[var(--accent-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
                    >
                      <IconPlus />
                      Add Product
                    </Link>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function IconCaret({ open, small }: { open: boolean; small?: boolean }) {
  const size = small ? 10 : 12;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className="shrink-0"
      style={{ transform: open ? "rotate(90deg)" : undefined, transition: "transform .15s" }}
    >
      <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}

function IconLeaf() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path
        d="M5 19c8-1 13-6 14-14-8 1-13 6-14 14z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="M5 19c1-4 3.5-8 8-10.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function IconCapsule() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <rect
        x="3.5"
        y="8.5"
        width="17"
        height="7"
        rx="3.5"
        transform="rotate(-35 12 12)"
        stroke="currentColor"
        strokeWidth="1.8"
      />
      <path d="M9.5 9.5l5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function SidebarButton({ item, collapsed, active }: { item: SidebarItem; collapsed: boolean; active: boolean }) {
  return (
    <Link
      href={item.href}
      title={collapsed ? item.label : undefined}
      className={cn(
        "flex items-center gap-3 rounded-xl px-2.5 py-2 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
        active
          ? "bg-[var(--accent-soft)] text-[var(--accent)]"
          : "text-[var(--muted)] hover:bg-[var(--foreground)]/[0.05] hover:text-[var(--foreground)]"
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
    </Link>
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

function IconHooks() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path
        d="M9 3v9a5 5 0 0010 0v-2"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="9" cy="3" r="2" stroke="currentColor" strokeWidth="1.8" />
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

function IconAyushProducts() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 3l2.2 4.6L19 8.3l-3.5 3.3.8 4.8L12 14.2l-4.3 2.2.8-4.8L5 8.3l4.8-.7L12 3z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M6 20h12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function IconFavorites() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 20s-7.5-4.6-9.5-9.1C1.3 7.6 3 4.5 6.2 4.1c1.9-.2 3.6.8 4.8 2.3 1.2-1.5 2.9-2.5 4.8-2.3 3.2.4 4.9 3.5 3.7 6.8C19.5 15.4 12 20 12 20z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
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
