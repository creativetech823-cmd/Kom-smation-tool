"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const ACTIVE_PROJECT_ID_KEY = "cf:active-project-id";
const ACTIVE_PROJECT_NAME_KEY = "cf:active-project-name";

type ProjectContextValue = {
  activeProjectId: string | null;
  activeProjectName: string | null;
  setActiveProject: (id: string | null, name?: string | null) => void;
};

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [activeProjectName, setActiveProjectName] = useState<string | null>(null);

  useEffect(() => {
    // Deferred to after mount — the server has no access to localStorage, so
    // reading it during the initial client render would mismatch the
    // server-rendered HTML and trigger a hydration error.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActiveProjectId(window.localStorage.getItem(ACTIVE_PROJECT_ID_KEY));
    setActiveProjectName(window.localStorage.getItem(ACTIVE_PROJECT_NAME_KEY));
  }, []);

  function setActiveProject(id: string | null, name?: string | null) {
    setActiveProjectId(id);
    setActiveProjectName(name ?? null);
    if (id) {
      window.localStorage.setItem(ACTIVE_PROJECT_ID_KEY, id);
    } else {
      window.localStorage.removeItem(ACTIVE_PROJECT_ID_KEY);
    }
    if (name) {
      window.localStorage.setItem(ACTIVE_PROJECT_NAME_KEY, name);
    } else {
      window.localStorage.removeItem(ACTIVE_PROJECT_NAME_KEY);
    }
  }

  return (
    <ProjectContext.Provider value={{ activeProjectId, activeProjectName, setActiveProject }}>
      {children}
    </ProjectContext.Provider>
  );
}

export function useActiveProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useActiveProject must be used within a ProjectProvider");
  return ctx;
}
