import { useEffect, useState } from "react";
import Header from "./Header";

const API_URL = process.env.REACT_APP_API_URL;
const MAX_NAME_LENGTH = 100;

function patientCountColor(count) {
  if (count >= 5) {
    return "text-c-urgent-text";
  }
  if (count >= 3) {
    return "text-c-moderate-text";
  }
  return "text-c-routine-text";
}

export default function DoctorsPage() {
  const [doctors, setDoctors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [newDoctorName, setNewDoctorName] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function fetchDoctors() {
      try {
        const response = await fetch(`${API_URL}/api/doctors`, { credentials: "include" });
        if (!response.ok) {
          throw new Error("Failed to fetch doctors");
        }
        const data = await response.json();
        if (isMounted) {
          setDoctors(data);
        }
      } catch {
        // keep previous data; actions below will surface their own errors
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchDoctors();

    return () => {
      isMounted = false;
    };
  }, []);

  async function toggleShift(doctor) {
    const nextStatus = doctor.status === "on_shift" ? "off_shift" : "on_shift";
    setMessage(null);

    try {
      const response = await fetch(`${API_URL}/api/doctors/${doctor.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: nextStatus }),
      });
      const data = await response.json();

      if (!response.ok) {
        setMessage({ type: "error", text: data.error || "Could not update doctor status" });
        return;
      }

      setDoctors((prev) => prev.map((d) => (d.id === doctor.id ? data.doctor : d)));

      if (data.warning) {
        setMessage({ type: "warning", text: data.warning });
      }
    } catch {
      setMessage({ type: "error", text: "Could not reach the server. Please try again." });
    }
  }

  async function markInactive(doctor) {
    setMessage(null);

    try {
      const response = await fetch(`${API_URL}/api/doctors/${doctor.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: "inactive" }),
      });
      const data = await response.json();

      if (!response.ok) {
        setMessage({ type: "error", text: data.error || "Could not mark doctor inactive" });
        return;
      }

      setDoctors((prev) => prev.filter((d) => d.id !== doctor.id));
    } catch {
      setMessage({ type: "error", text: "Could not reach the server. Please try again." });
    }
  }

  async function addDoctor(e) {
    e.preventDefault();
    const name = newDoctorName.trim();
    if (!name || adding) {
      return;
    }

    setAdding(true);
    setMessage(null);

    try {
      const response = await fetch(`${API_URL}/api/doctors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ name }),
      });
      const data = await response.json();

      if (!response.ok) {
        setMessage({ type: "error", text: data.error || "Could not add doctor" });
        return;
      }

      setDoctors((prev) => [...prev, data]);
      setNewDoctorName("");
    } catch {
      setMessage({ type: "error", text: "Could not reach the server. Please try again." });
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="min-h-screen bg-c-bg">
      <Header />

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {message && (
          <div
            className={`text-sm rounded-xl px-4 py-3 border ${
              message.type === "error"
                ? "bg-red-50 border-red-200 text-red-700"
                : "bg-amber-50 border-amber-200 text-amber-800"
            }`}
          >
            {message.text}
          </div>
        )}

        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-c-navy">Shift Management</h2>
            <p className="text-sm text-gray-500 mt-1">
              Mark who is working today. Only on-shift doctors appear as assignment options in the queue.
            </p>
          </div>

          <div className="p-6">
            {loading ? (
              <p className="text-sm text-gray-400">Loading doctors...</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {doctors.map((doctor) => {
                  const isOnShift = doctor.status === "on_shift";
                  return (
                    <div
                      key={doctor.id}
                      className={`rounded-2xl border p-5 transition-colors ${
                        isOnShift ? "border-c-teal/30 bg-c-teal/5" : "border-gray-100 bg-white opacity-70"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className={`inline-block w-2 h-2 rounded-full ${
                            isOnShift ? "bg-emerald-500" : "bg-gray-300"
                          }`}
                        />
                        <h3 className="font-semibold text-c-navy">{doctor.name}</h3>
                      </div>
                      <p className={`text-sm mb-4 ${patientCountColor(doctor.active_patient_count)}`}>
                        {doctor.active_patient_count} patient{doctor.active_patient_count === 1 ? "" : "s"} today
                      </p>
                      <button
                        type="button"
                        onClick={() => toggleShift(doctor)}
                        className={`w-full h-10 rounded-lg text-sm font-medium transition-colors ${
                          isOnShift
                            ? "bg-c-teal text-white hover:bg-c-teal-hover"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                        }`}
                      >
                        {isOnShift ? "Mark Off Shift" : "Mark On Shift"}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-c-navy">Roster Management</h2>
          </div>

          <div className="p-6 space-y-6">
            <form onSubmit={addDoctor} className="flex gap-2">
              <input
                type="text"
                value={newDoctorName}
                onChange={(e) => setNewDoctorName(e.target.value)}
                placeholder="New doctor name"
                maxLength={MAX_NAME_LENGTH}
                disabled={adding}
                className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-c-teal"
              />
              <button
                type="submit"
                disabled={adding || !newDoctorName.trim()}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-c-teal text-white hover:bg-c-teal-hover disabled:bg-c-teal/50 disabled:cursor-not-allowed"
              >
                Add Doctor
              </button>
            </form>

            {loading ? (
              <p className="text-sm text-gray-400">Loading roster...</p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {doctors.map((doctor) => {
                  const hasActivePatients = doctor.active_patient_count > 0;
                  return (
                    <li key={doctor.id} className="flex items-center justify-between py-3">
                      <div>
                        <p className="font-medium text-gray-900">{doctor.name}</p>
                        <p className="text-xs text-gray-400">
                          {doctor.status === "on_shift" ? "On shift" : "Off shift"} ·{" "}
                          {doctor.active_patient_count} active patient{doctor.active_patient_count === 1 ? "" : "s"}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => markInactive(doctor)}
                        disabled={hasActivePatients}
                        title={
                          hasActivePatients
                            ? "Reassign this doctor's active patients before marking them inactive"
                            : undefined
                        }
                        className="text-sm font-medium text-gray-500 hover:text-red-600 disabled:text-gray-300 disabled:cursor-not-allowed disabled:hover:text-gray-300"
                      >
                        Mark Inactive
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
