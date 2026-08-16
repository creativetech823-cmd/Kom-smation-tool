"use client";

import type { ReactNode } from "react";
import { ThemeProvider } from "@/lib/theme-context";
import { ToastProvider } from "@/components/shell/ToastProvider";
import { ProjectProvider } from "@/lib/project-context";
import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <ToastProvider>
        <ProjectProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            <div className="flex min-h-screen flex-1 flex-col">
              <TopBar />
              {children}
            </div>
          </div>
        </ProjectProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
