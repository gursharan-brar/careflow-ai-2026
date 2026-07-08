import { useEffect, useState } from "react";
import Header from "./Header";
import Avatar from "./Avatar";

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
      <Header title="Doctors" subtitle="Manage who's on shift today" />

      <main className="max-w-[1500px] px-10 py-10 space-y-8">
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

        <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="px-7 py-5 border-b border-gray-100">
            <h2 className="text-xl font-bold text-c-navy">Shift Management</h2>
            <p className="text-base text-gray-500 mt-1">
              Mark who is working today. Only on-shift doctors appear as assignment options in the queue.
            </p>
          </div>

          <div className="p-7">
            {loading ? (
              <p className="text-base text-gray-400">Loading doctors...</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {doctors.map((doctor) => {
                  const isOnShift = doctor.status === "on_shift";
                  return (
                    <div
                      key={doctor.id}
                      className={`rounded-2xl border-2 p-6 transition-colors ${
                        isOnShift ? "border-c-teal bg-c-teal/5" : "border-gray-200 bg-white"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3.5">
                          <Avatar
                            name={doctor.name}
                            className={`w-14 h-14 text-base ${
                              isOnShift ? "bg-c-teal text-white" : "bg-gray-200 text-gray-600"
                            }`}
                          />
                          <h3 className="font-extrabold text-lg text-c-navy leading-tight">{doctor.name}</h3>
                        </div>
                      </div>
                      <span
                        className={`inline-block px-3 py-1.5 rounded-full text-sm font-bold tracking-wide mb-4 ${
                          isOnShift ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {isOnShift ? "ON SHIFT" : "OFF SHIFT"}
                      </span>
                      <p className={`text-base font-semibold mb-5 ${patientCountColor(doctor.active_patient_count)}`}>
                        {doctor.active_patient_count} patient{doctor.active_patient_count === 1 ? "" : "s"} today
                      </p>
                      <button
                        type="button"
                        onClick={() => toggleShift(doctor)}
                        className={`w-full h-12 rounded-xl text-base font-bold transition-colors ${
                          isOnShift
                            ? "bg-c-teal text-white hover:bg-c-teal-hover"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
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

        <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="px-7 py-5 border-b border-gray-100">
            <h2 className="text-xl font-bold text-c-navy">Roster Management</h2>
          </div>

          <div className="p-7 space-y-7">
            <form onSubmit={addDoctor} className="flex gap-3">
              <input
                type="text"
                value={newDoctorName}
                onChange={(e) => setNewDoctorName(e.target.value)}
                placeholder="New doctor name"
                maxLength={MAX_NAME_LENGTH}
                disabled={adding}
                className="flex-1 px-4 py-3 text-base border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-c-teal"
              />
              <button
                type="submit"
                disabled={adding || !newDoctorName.trim()}
                className="px-5 py-3 text-base font-bold rounded-xl bg-c-teal text-white hover:bg-c-teal-hover disabled:bg-c-teal/50 disabled:cursor-not-allowed"
              >
                Add Doctor
              </button>
            </form>

            {loading ? (
              <p className="text-base text-gray-400">Loading roster...</p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {doctors.map((doctor) => {
                  const hasActivePatients = doctor.active_patient_count > 0;
                  return (
                    <li key={doctor.id} className="flex items-center justify-between py-4">
                      <div>
                        <p className="font-semibold text-base text-gray-900">{doctor.name}</p>
                        <p className="text-sm text-gray-400 mt-0.5">
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
                        className="text-base font-semibold text-gray-500 hover:text-red-600 disabled:text-gray-300 disabled:cursor-not-allowed disabled:hover:text-gray-300"
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
