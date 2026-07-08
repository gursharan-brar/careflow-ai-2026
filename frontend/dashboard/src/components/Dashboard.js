import { useEffect, useState } from 'react';
import QueuePanel from './QueuePanel';
import HealthPanel from './HealthPanel';
import StatsBar from './StatsBar';
import BookingsPanel from './BookingsPanel';
import Header from './Header';

const API_URL = process.env.REACT_APP_API_URL;

export default function Dashboard() {
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState(null);
  const [onShiftDoctors, setOnShiftDoctors] = useState([]);
  const [doctorsLoading, setDoctorsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function fetchQueue() {
      try {
        const response = await fetch(`${API_URL}/api/queue`, { credentials: "include" });
        if (!response.ok) {
          throw new Error("Failed to fetch queue");
        }
        const data = await response.json();
        if (isMounted) {
          setQueue(data);
          setLastRefreshed(new Date());
        }
      } catch {
        // silently retry on next poll
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    async function fetchOnShiftDoctors() {
      try {
        const response = await fetch(`${API_URL}/api/doctors/on-shift`, { credentials: "include" });
        if (!response.ok) {
          throw new Error("Failed to fetch on-shift doctors");
        }
        const data = await response.json();
        if (isMounted) {
          setOnShiftDoctors(data);
        }
      } catch {
        // silently retry on next poll
      } finally {
        if (isMounted) {
          setDoctorsLoading(false);
        }
      }
    }

    fetchQueue();
    fetchOnShiftDoctors();
    const interval = setInterval(() => {
      fetchQueue();
      fetchOnShiftDoctors();
    }, 60000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  async function assignVisit(visitId, doctorId) {
    try {
      const response = await fetch(`${API_URL}/api/visits/${visitId}/assign`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ doctor_id: doctorId }),
      });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      setQueue((prev) =>
        prev.map((visit) =>
          visit.visit_id === visitId
            ? {
                ...visit,
                doctor_id: data.doctor_id,
                doctor_position: data.doctor_position,
                estimated_wait: data.estimated_wait,
                doctor_name: onShiftDoctors.find((d) => d.id === data.doctor_id)?.name || null,
              }
            : visit
        )
      );
    } catch {
      // next poll will reconcile state
    }
  }

  const rightSlot = (
    <div className="flex items-center gap-2.5 text-base text-gray-500 font-medium">
      <span className="relative flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 animate-pulse" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
      </span>
      {lastRefreshed
        ? `Last refreshed ${lastRefreshed.toLocaleTimeString()}`
        : "Refreshing..."}
    </div>
  );

  return (
    <div className="min-h-screen bg-c-bg">
      <Header title="Dashboard" subtitle="Live queue, today's bookings, and clinic activity" rightSlot={rightSlot} />

      <main className="max-w-[1500px] px-10 py-10 space-y-8">
        <StatsBar patients={queue} onShiftCount={doctorsLoading ? null : onShiftDoctors.length} />

        <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
          <QueuePanel
            queue={queue}
            loading={loading}
            setQueue={setQueue}
            onShiftDoctors={onShiftDoctors}
            doctorsLoading={doctorsLoading}
            onAssign={assignVisit}
          />
        </div>

        <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
          <BookingsPanel />
        </div>

        <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
          <HealthPanel />
        </div>
      </main>
    </div>
  );
}
