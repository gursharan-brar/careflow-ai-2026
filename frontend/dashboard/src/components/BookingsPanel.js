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
  // Client-side-only "arrived" marker — real queue linkage via appointments.visit_id
  // is a separate, deferred feature, so this just flags the row visually for now.
  const [arrivedIds, setArrivedIds] = useState(new Set());

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

  function markArrived(id) {
    setArrivedIds((prev) => new Set(prev).add(id));
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
      <div className="px-6 py-4 border-b border-gray-100">
        <h2 className="text-lg font-semibold text-c-navy">Today's Bookings</h2>
      </div>

      {loading ? (
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead className="bg-c-navy text-white">
              <tr>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Time</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Doctor</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Patient Name</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Status</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              <SkeletonRow />
              <SkeletonRow />
            </tbody>
          </table>
        </div>
      ) : bookings.length === 0 ? (
        <p className="px-6 py-8 text-sm text-gray-400">No bookings for today</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead className="bg-c-navy text-white">
              <tr>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Time</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Doctor</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Patient Name</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Status</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((booking) => {
                const hasArrived = arrivedIds.has(booking.id);
                return (
                  <tr key={booking.id} className="h-14 bg-white border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-4 font-medium text-c-navy">{formatSlotLabel(booking.slot_time)}</td>
                    <td className="px-4 text-gray-700">{booking.doctor_name}</td>
                    <td className="px-4 font-semibold text-gray-900">{booking.patient_name}</td>
                    <td className="px-4 text-sm">
                      {hasArrived ? (
                        <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold bg-c-routine-bg text-c-routine-text border border-green-200">
                          ARRIVED
                        </span>
                      ) : (
                        <span className="text-gray-500">Confirmed</span>
                      )}
                    </td>
                    <td className="px-4">
                      <div className="flex gap-1.5">
                        <button
                          type="button"
                          onClick={() => markArrived(booking.id)}
                          disabled={hasArrived}
                          className="h-7 px-2.5 rounded-md bg-c-teal text-white text-xs font-medium transition-colors hover:bg-c-teal-hover disabled:bg-c-teal/40 disabled:cursor-not-allowed"
                        >
                          Arrived
                        </button>
                        <button
                          type="button"
                          onClick={() => cancelBooking(booking.id)}
                          className="h-7 px-2.5 rounded-md bg-gray-100 text-gray-600 text-xs font-medium transition-colors hover:bg-gray-200"
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
