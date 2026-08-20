import { Link, useLocation } from "react-router-dom";
import { initialsFor } from "./Avatar";

const NAV_ITEMS = [
  {
    to: "/",
    label: "Dashboard",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="9" rx="1.5"></rect>
        <rect x="14" y="3" width="7" height="5" rx="1.5"></rect>
        <rect x="14" y="12" width="7" height="9" rx="1.5"></rect>
        <rect x="3" y="16" width="7" height="5" rx="1.5"></rect>
      </svg>
    ),
  },
  {
    to: "/doctors",
    label: "Doctors",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 3v4a2 2 0 0 0 2 2h0a2 2 0 0 0 2-2V3"></path>
        <path d="M8 3a2 2 0 0 0-2 2v5a5 5 0 0 0 10 0V5a2 2 0 0 0-2-2"></path>
        <path d="M18 10v2a6 6 0 0 1-12 0v-2"></path>
        <circle cx="19" cy="16" r="2.5"></circle>
      </svg>
    ),
  },
  {
    to: "/patients",
    label: "Patients",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
        <circle cx="9" cy="7" r="4"></circle>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
        <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
      </svg>
    ),
  },
  {
    to: "/analytics",
    label: "Analytics",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="18" y1="20" x2="18" y2="10"></line>
        <line x1="12" y1="20" x2="12" y2="4"></line>
        <line x1="6" y1="20" x2="6" y2="14"></line>
      </svg>
    ),
  },
];

export default function Sidebar({ staffName, onLogout }) {
  const location = useLocation();

  return (
    <aside className="w-72 shrink-0 bg-c-navy-deep text-white min-h-screen flex flex-col sticky top-0 self-start h-screen">
      <div className="px-7 py-8 flex items-center gap-3">
        <img src="/logo.svg" alt="CareFlow AI logo" className="w-9 h-9 rounded-full shrink-0 shadow-md" />
        <div className="leading-tight">
          <p className="font-extrabold text-xl tracking-tight">CareFlow AI</p>
          <p className="text-xs text-white/50 font-medium">Clinic Operations</p>
        </div>
      </div>

      <nav className="flex-1 px-4 mt-3 space-y-2">
        {NAV_ITEMS.map((item) => {
          const active = location.pathname === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`flex items-center gap-3.5 px-4 py-3.5 rounded-xl text-base font-semibold transition-colors ${
                active ? "bg-c-teal text-white shadow-md" : "text-white/65 hover:bg-white/[0.08] hover:text-white"
              }`}
            >
              <span className="[&>svg]:w-5 [&>svg]:h-5">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-4 pb-7 pt-4 border-t border-white/10">
        <div className="flex items-center gap-3.5 px-2 py-2">
          <div className="w-10 h-10 rounded-full bg-c-teal/25 text-white flex items-center justify-center text-sm font-bold shrink-0">
            {initialsFor(staffName)}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-base font-bold truncate">{staffName || "Staff"}</p>
            <button
              type="button"
              onClick={onLogout}
              className="text-sm text-white/50 hover:text-white transition-colors font-medium"
            >
              Log out
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}
