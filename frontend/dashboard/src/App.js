import { useEffect, useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import DoctorsPage from './components/DoctorsPage';
import StaffChatWidget from './components/StaffChatWidget';

const API_URL = process.env.REACT_APP_API_URL;

function App() {
  const [authChecked, setAuthChecked] = useState(false);

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

  if (!authChecked) {
    return null;
  }

  return (
    <>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/doctors" element={<DoctorsPage />} />
      </Routes>

      <StaffChatWidget />
    </>
  );
}

export default App;
