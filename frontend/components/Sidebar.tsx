import React from "react";

type SidebarItem = {
  key: string;
  label: string;
  description?: string;
  icon: React.ReactNode;
  badge?: string;
};

type SidebarProps = {
  selectedView: string;
  onSelect: (view: string) => void;
};

const navItems: SidebarItem[] = [
  {
    key: "dashboard",
    label: "Dashboard",
    description: "Overview & signals",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M5 12h6V5H5v7Zm0 7h6v-5H5v5Zm8 0h6v-7h-6v7Zm0-16v5h6V3h-6Z"
          fill="currentColor"
          opacity="0.88"
        />
      </svg>
    ),
  },
  {
    key: "frames",
    label: "Frames",
    description: "Active review",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M5 4h14a1 1 0 0 1 1 1v10.5a1 1 0 0 1-1 1H8.83L5.4 19.42A1 1 0 0 1 4 18.67V5a1 1 0 0 1 1-1Zm4 8h6a1 1 0 1 0 0-2H9a1 1 0 0 0 0 2Zm0-3h6a1 1 0 1 0 0-2H9a1 1 0 0 0 0 2Z"
          fill="currentColor"
          opacity="0.9"
        />
      </svg>
    ),
    badge: "Live",
  },
  {
    key: "tasks",
    label: "Tasks",
    description: "Assignments & QA",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M8.7 12.7a1 1 0 0 1-1.4-1.4l2-2a1 1 0 0 1 1.45-.05l.08.08L14 12l3.3-3.3a1 1 0 0 1 1.5 1.3l-.08.1-4 4a1 1 0 0 1-1.32.08l-.1-.08L11 13l-2.3 2.3Z"
          fill="currentColor"
          opacity="0.9"
        />
        <path
          d="M8 3h8a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm0 2v14h8V5H8Z"
          fill="currentColor"
          opacity="0.88"
        />
      </svg>
    ),
  },
  {
    key: "settings",
    label: "Settings",
    description: "Admin & configs",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M12 9.5A2.5 2.5 0 1 0 12 14a2.5 2.5 0 0 0 0-5Zm0-2a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9Z"
          fill="currentColor"
          opacity="0.9"
        />
        <path
          d="M4.93 4.93a1 1 0 0 1 1.41 0l1.06 1.06 1.46-.34a1 1 0 0 1 1.21.76l.06.24.34 1.46 1.46.34a1 1 0 0 1 .76 1.21l-.06.24-.34 1.46.34 1.46a1 1 0 0 1-.76 1.21l-.24.06-1.46.34-.34 1.46a1 1 0 0 1-1.21.76l-.24-.06-1.46-.34-1.06 1.06a1 1 0 0 1-1.41-1.41l1.06-1.06-.34-1.46a1 1 0 0 1 .76-1.21l.24-.06 1.46-.34.34-1.46a1 1 0 0 1 1.21-.76l.24.06 1.46.34 1.06-1.06a1 1 0 0 1 1.41 1.41L14.4 9.6l1.46.34a1 1 0 0 1 .76 1.21l-.06.24-.34 1.46 1.06 1.06a1 1 0 0 1-1.41 1.41l-1.06-1.06-1.46.34a1 1 0 0 1-1.21-.76l-.06-.24-.34-1.46-1.46-.34a1 1 0 0 1-.76-1.21l.06-.24.34-1.46-1.06-1.06a1 1 0 0 1 0-1.41Z"
          fill="currentColor"
          opacity="0.88"
        />
      </svg>
    ),
  },
  {
    key: "models",
    label: "Models",
    description: "Pipelines",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M7 4h10a1 1 0 0 1 .96.74l2 8a1 1 0 0 1-.97 1.26H16v2a2 2 0 0 1-2 2h-1.17l.58 1.45a1 1 0 1 1-1.82.7L10.17 18H10a2 2 0 0 1-2-2v-2H4.01a1 1 0 0 1-.97-1.26l2-8A1 1 0 0 1 7 4Zm9.12 2H7.88l-1.5 6h11.24l-1.5-6ZM10 14v2h4v-2h-4Z"
          fill="currentColor"
          opacity="0.9"
        />
      </svg>
    ),
  },
  {
    key: "support",
    label: "Support",
    description: "Help center",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M12 3a8 8 0 0 1 8 8c0 3.1-1.79 5.77-4.37 7.04l-1.02 1.8a1 1 0 0 1-1.75-.06l-.05-.12-.58-1.74a8.03 8.03 0 0 1-8.23-9.38A8 8 0 0 1 12 3Zm0 2a6 6 0 0 0-1 11.9l.54.1.43 1.29.58-1.03a1 1 0 0 1 .52-.44l.16-.04A6 6 0 1 0 12 5Zm0 8a1 1 0 1 1 0 2 1 1 0 0 1 0-2Zm0-6a2.5 2.5 0 0 1 2.5 2.5 1 1 0 1 1-2 0 .5.5 0 0 0-.5-.5 1.5 1.5 0 0 0-1.5 1.5 1 1 0 0 1-2 0A3.5 3.5 0 0 1 12 7Z"
          fill="currentColor"
          opacity="0.9"
        />
      </svg>
    ),
  },
];

export function Sidebar({ selectedView, onSelect }: SidebarProps) {
  return (
    <aside className="app-sidebar" aria-label="Primary navigation">
      <div className="app-sidebar__header">
        <div className="app-sidebar__mark" aria-hidden="true">
          <span>MT</span>
        </div>
        <div>
          <p className="app-sidebar__title">Movietag</p>
          <p className="app-sidebar__subtitle">Operations</p>
        </div>
      </div>

      <nav aria-label="Views" className="app-sidebar__nav" role="tablist">
        {navItems.map((item) => {
          const isActive = selectedView === item.key;
          return (
            <button
              key={item.key}
              type="button"
              className={`app-sidebar__item ${isActive ? "is-active" : ""}`}
              onClick={() => onSelect(item.key)}
              role="tab"
              aria-selected={isActive}
            >
              <span className="app-sidebar__icon">{item.icon}</span>
              <span className="app-sidebar__text">
                <span className="app-sidebar__label">{item.label}</span>
                {item.description ? <span className="app-sidebar__hint">{item.description}</span> : null}
              </span>
              {item.badge ? <span className="app-sidebar__badge">{item.badge}</span> : null}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
