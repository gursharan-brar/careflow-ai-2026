import { useEffect, useState } from "react";
import Shimmer from "./Shimmer";

const API_URL = process.env.REACT_APP_API_URL;

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function formatSlotLabel(slotTime) {
  const [h, m] = slotTime.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const hour12 = h % 12 || 12;
  return `${hour12}:${m.toString().padStart(2, "0")} ${period}`;
}

function SkeletonRow() {
  return (
    <tr className="h-14 border-b border-gray-100">
      <td className="px-4"><Shimmer className="h-4 w-16" /></td>
      <td className="px-4"><Shimmer className="h-4 w-28" /></td>
      <td className="px-4"><Shimmer className="h-4 w-28" /></td>
      <td className="px-4"><Shimmer className="h-4 w-20" /></td>
      <td className="px-4"><Shimmer className="h-4 w-24" /></td>
    </tr>
  );
}

export default function BookingsPanel() {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [arrivingId, setArrivingId] = useState(null);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    let isMounted = true;

    async function fetchBookings() {
      try {
        const response = await fetch(`${API_URL}/api/appointments?date=${todayIso()}`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Failed to fetch bookings");
        }
        const data = await response.json();
        if (isMounted) {
          setBookings(data);
        }
      } catch {
        // silently retry on next poll
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchBookings();
    const interval = setInterval(fetchBookings, 60000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Arrived moves the patient straight into their booked doctor's queue lane,
  // tagged with the original slot time so they sort ahead of walk-ins —
  // see POST /api/appointments/<id>/arrive. This is a real, committed action
  // (not a local-only marker), so the row disappears from this list on success.
  async function markArrived(id) {
    setMessage(null);
    setArrivingId(id);
    try {
      const response = await fetch(`${API_URL}/api/appointments/${id}/arrive`, {
        method: "POST",
        credentials: "include",
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setMessage({ type: "error", text: data.error || "Could not check in this patient." });
        return;
      }

      setBookings((prev) => prev.filter((b) => b.id !== id));
    } catch {
      setMessage({ type: "error", text: "Could not reach the server. Please try again." });
    } finally {
      setArrivingId(null);
    }
  }

  async function cancelBooking(id) {
    try {
      const response = await fetch(`${API_URL}/api/appointments/${id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: "cancelled" }),
      });
      if (!response.ok) {
        return;
      }
      setBookings((prev) => prev.filter((b) => b.id !== id));
    } catch {
      // next poll will reconcile state
    }
  }

  return (
    <div className="text-c-text">
      <div className="px-7 py-5 border-b border-gray-100 flex items-center gap-3">
        <span className="w-10 h-10 rounded-xl bg-c-teal/10 text-c-teal flex items-center justify-center">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2"></rect>
            <line x1="16" y1="2" x2="16" y2="6"></line>
            <line x1="8" y1="2" x2="8" y2="6"></line>
            <line x1="3" y1="10" x2="21" y2="10"></line>
          </svg>
        </span>
        <h2 className="text-xl font-bold text-c-navy">Today's Bookings</h2>
      </div>

      {message && (
        <div className="px-7 pt-4 text-base text-red-700 bg-red-50 border-b border-red-100 py-3">
          {message.text}
        </div>
      )}

      {loading ? (
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead className="bg-c-navy text-white">
              <tr>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Time</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Doctor</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Patient Name</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Status</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Actions</th>
              </tr>
            </thead>
            <tbody>
              <SkeletonRow />
              <SkeletonRow />
            </tbody>
          </table>
        </div>
      ) : bookings.length === 0 ? (
        <p className="px-7 py-10 text-base text-gray-400">No bookings for today</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead className="bg-c-navy text-white">
              <tr>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Time</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Doctor</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Patient Name</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Status</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((booking) => {
                const isArriving = arrivingId === booking.id;
                return (
                  <tr key={booking.id} className="h-16 bg-white border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-5 font-bold text-base text-c-navy">{formatSlotLabel(booking.slot_time)}</td>
                    <td className="px-5 text-base text-gray-700">{booking.doctor_name}</td>
                    <td className="px-5 font-bold text-base text-gray-900">{booking.patient_name}</td>
                    <td className="px-5 text-base">
                      <span className="text-gray-500">Confirmed</span>
                    </td>
                    <td className="px-5">
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => markArrived(booking.id)}
                          disabled={isArriving}
                          className="h-9 px-3.5 rounded-lg bg-c-teal text-white text-sm font-semibold transition-colors hover:bg-c-teal-hover disabled:bg-c-teal/40 disabled:cursor-not-allowed"
                        >
                          {isArriving ? "Checking in…" : "Arrived"}
                        </button>
                        <button
                          type="button"
                          onClick={() => cancelBooking(booking.id)}
                          disabled={isArriving}
                          className="h-9 px-3.5 rounded-lg bg-gray-100 text-gray-600 text-sm font-semibold transition-colors hover:bg-gray-200 disabled:cursor-not-allowed"
                        >
                          Cancel
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
