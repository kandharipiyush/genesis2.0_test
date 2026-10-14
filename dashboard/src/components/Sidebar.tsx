import React from "react";
import {
  Activity,
  History,
  Layers,
  BarChart2,
  ShieldAlert,
  Sliders,
  Sparkles,
} from "lucide-react";

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  activeVersion: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  activeVersion,
}) => {
  const navItems = [
    { id: "overview", label: "Dashboard Overview", icon: Activity },
    { id: "timeline", label: "Live Recovery Timeline", icon: History },
    { id: "registry", label: "Schema Explorer", icon: Layers },
    { id: "benchmarks", label: "Benchmark Suite", icon: BarChart2 },
    { id: "safety", label: "Safety & Analytics", icon: ShieldAlert },
    { id: "controls", label: "Gateway Controls", icon: Sliders },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <Sparkles size={18} />
        </div>
        <div>
          <h2 style={{ fontSize: "15px", fontWeight: "700", color: "var(--text-main)" }}>
            SchemaSurgeon
          </h2>
          <p style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: "500" }}>
            Control Center v1.0
          </p>
        </div>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              className={`nav-item ${isActive ? "active" : ""}`}
              onClick={() => onSelectTab(item.id)}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div>
          <span style={{ display: "block", color: "var(--text-muted)" }}>Active Tool Version</span>
          <span style={{ fontWeight: "700", color: "var(--blue-primary)", fontSize: "13px" }}>
            get_user: v{activeVersion}
          </span>
        </div>
        <div className="status-badge live">
          <span className="pulse-dot"></span>
          <span>Online</span>
        </div>
      </div>
    </aside>
  );
};
