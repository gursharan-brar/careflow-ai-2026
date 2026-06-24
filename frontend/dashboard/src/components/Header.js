import { Link, useLocation } from 'react-router-dom';

const NAV_LINKS = [
  { to: '/', label: 'Dashboard' },
  { to: '/doctors', label: 'Doctors' },
];

export default function Header({ rightSlot }) {
  const location = useLocation();

  return (
    <header className="bg-c-navy text-white shadow-md px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-8">
          <div>
            <h1 className="text-xl font-bold text-white">CareFlow AI</h1>
            <p className="text-sm text-white/80">Calgary Walk-In Clinic Platform</p>
          </div>
          <nav className="flex items-center gap-4">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={`text-sm font-medium transition-colors ${
                  location.pathname === link.to ? 'text-white' : 'text-white/70 hover:text-white'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        {rightSlot}
      </div>
    </header>
  );
}
