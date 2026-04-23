import React, { useState } from "react";
import { NavLink, useNavigate, Outlet, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  LayoutDashboard, Receipt, Sparkles, PieChart, Gift, CreditCard, Settings, LogOut, Menu, X,
} from "lucide-react";

const nav = [
  { to: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/app/expenses", label: "Expenses", icon: Receipt, testid: "nav-expenses" },
  { to: "/app/insights", label: "Insights", icon: Sparkles, testid: "nav-insights" },
  { to: "/app/portfolio", label: "Portfolio", icon: PieChart, testid: "nav-portfolio" },
  { to: "/app/offers", label: "Offers", icon: Gift, testid: "nav-offers" },
  { to: "/app/subscription", label: "Pricing", icon: CreditCard, testid: "nav-subscription" },
  { to: "/app/settings", label: "Settings", icon: Settings, testid: "nav-settings" },
];

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const handleLogout = () => { logout(); navigate("/"); };

  return (
    <div className="min-h-screen flex text-[color:var(--text-primary)]" style={{ background: "var(--bg-main)" }}>
      {/* Sidebar */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 w-64 border-r transform transition-transform md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
        style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
        data-testid="sidebar"
      >
        <div className="px-6 py-6 flex items-center justify-between">
          <Link to="/app/dashboard" className="flex items-center gap-2" data-testid="sidebar-logo">
            <div className="w-8 h-8 rounded-md grid place-items-center font-bold text-white" style={{ background: "var(--brand)" }}>₹</div>
            <span className="font-display text-lg font-bold tracking-tight">FinSight</span>
          </Link>
          <button className="md:hidden" onClick={() => setOpen(false)} data-testid="sidebar-close"><X size={18} /></button>
        </div>
        <nav className="px-3 space-y-1">
          {nav.map((n) => {
            const Icon = n.icon;
            return (
              <NavLink
                key={n.to}
                to={n.to}
                data-testid={n.testid}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                    isActive
                      ? "bg-[rgba(255,85,0,0.12)] text-white border border-[rgba(255,85,0,0.3)]"
                      : "text-[color:var(--text-secondary)] hover:text-white hover:bg-[color:var(--bg-surface-hover)]"
                  }`
                }
              >
                <Icon size={18} />
                <span>{n.label}</span>
              </NavLink>
            );
          })}
        </nav>
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t" style={{ borderColor: "var(--border)" }}>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-full grid place-items-center font-semibold" style={{ background: "var(--bg-surface-hover)" }}>
              {(user?.name || "U").charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate" data-testid="sidebar-username">{user?.name}</div>
              <div className="text-xs text-[color:var(--text-muted)] truncate">{user?.email}</div>
            </div>
          </div>
          <button onClick={handleLogout} data-testid="logout-btn"
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-[color:var(--text-secondary)] hover:text-white hover:bg-[color:var(--bg-surface-hover)]">
            <LogOut size={16} /> Logout
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0">
        <header className="sticky top-0 z-30 glass-header px-6 py-4 flex items-center justify-between md:hidden">
          <button onClick={() => setOpen(true)} data-testid="sidebar-open"><Menu size={20} /></button>
          <span className="font-display font-bold">FinSight</span>
          <div style={{ width: 20 }} />
        </header>
        <main className="p-6 md:p-10 max-w-[1400px] mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
