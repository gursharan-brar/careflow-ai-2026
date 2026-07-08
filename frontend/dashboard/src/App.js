import { useEffect, useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import DoctorsPage from './components/DoctorsPage';
import PatientsPage from './components/PatientsPage';
import StaffChatWidget from './components/StaffChatWidget';
import Sidebar from './components/Sidebar';

const API_URL = process.env.REACT_APP_API_URL;

function App() {
  const [authChecked, setAuthChecked] = useState(false);
  const [staffName, setStaffName] = useState(null);

  useEffect(() => {
    let isMounted = true;

    async function checkSession() {
      try {
        const response = await fetch(`${API_URL}/api/session`, { credentials: "include" });
        const data = await response.json();
        if (!isMounted) {
          return;
        }
        if (!data.authenticated) {
          window.location.href = `${API_URL}/login`;
          return;
        }
        setStaffName(data.display_name || null);
        setAuthChecked(true);
      } catch {
        window.location.href = `${API_URL}/login`;
      }
    }

    checkSession();

    return () => {
      isMounted = false;
    };
  }, []);

  async function handleLogout() {
    try {
      await fetch(`${API_URL}/api/logout`, { method: "POST", credentials: "include" });
    } catch {
      // proceed to login regardless
    }
    window.location.href = `${API_URL}/login`;
  }

  if (!authChecked) {
    return null;
  }

  return (
    <div className="flex min-h-screen bg-c-bg">
      <Sidebar staffName={staffName} onLogout={handleLogout} />

      <div className="flex-1 min-w-0">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/doctors" element={<DoctorsPage />} />
          <Route path="/patients" element={<PatientsPage />} />
        </Routes>
      </div>

      <StaffChatWidget />
    </div>
  );
}

export default App;
