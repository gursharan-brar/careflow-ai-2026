import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Shimmer from "./Shimmer";
import { STATUS_LABELS } from "../constants";

const API_URL = process.env.REACT_APP_API_URL;

const VISIT_TYPE_LABELS = {
  gp_consult: "GP Consult",
  prescription_renewal: "Prescription Renewal",
  injury: "Injury",
  general: "General",
};

const PRIORITY_BADGES = {
  urgent: { label: "URGENT", className: "bg-c-urgent-bg text-c-urgent-text border-red-200" },
  moderate: { label: "MODERATE", className: "bg-c-moderate-bg text-c-moderate-text border-amber-200" },
  routine: { label: "ROUTINE", className: "bg-c-routine-bg text-c-routine-text border-green-200" },
};

const PRIORITY_FALLBACK = { label: "PENDING", className: "bg-c-null-bg text-c-null-text border-gray-200" };

const PRIORITY_CARD_ACCENT = {
  urgent: "border-l-4 border-l-red-500 bg-red-50/50",
  moderate: "border-l-4 border-l-amber-400 bg-amber-50/40",
  routine: "border-l-4 border-l-emerald-400",
};

const PRIORITY_CARD_ACCENT_FALLBACK = "border-l-4 border-l-transparent";

// Wait time itself is a second, independent signal — a routine patient who has been
// waiting a long time still deserves attention. Thresholds are rough operational
// judgment calls: under 30 min reads as fine, 30-59 as worth watching, 60+ as a
// real problem regardless of triage priority.
function getWaitClassName(minutes) {
  if (minutes === null || minutes === undefined) {
    return "text-gray-400";
  }
  if (minutes >= 60) {
    return "text-c-urgent-text font-semibold";
  }
  if (minutes >= 30) {
    return "text-c-moderate-text font-semibold";
  }
  return "text-gray-500";
}

// Same thresholds as the Doctors page's per-doctor patient count — a lane
// reads as fine at 0-2, worth watching at 3-4, overloaded at 5+.
function laneIndicatorClassName(count) {
  if (count >= 5) {
    return "bg-red-500";
  }
  if (count >= 3) {
    return "bg-amber-400";
  }
  return "bg-emerald-400";
}

const VALID_TRANSITIONS = {
  checked_in: ["called", "no_show"],
  called: ["in_progress", "no_show"],
  in_progress: ["completed", "no_show"],
  completed: [],
  no_show: [],
};

const STATUS_BUTTON_LABELS = {
  called: "Called",
  in_progress: "In Progress",
  completed: "Completed",
  no_show: "No Show",
};

function PriorityBadge({ priority }) {
  const config = PRIORITY_BADGES[priority] || PRIORITY_FALLBACK;
  return (
    <span
      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold border whitespace-nowrap ${config.className}`}
    >
      {config.label}
    </span>
  );
}

function SkeletonBlock() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 p-6">
      {[0, 1, 2].map((i) => (
        <div key={i} className="border border-gray-100 rounded-xl p-4 space-y-3">
          <Shimmer className="h-4 w-1/2" />
          <Shimmer className="h-16 w-full" />
          <Shimmer className="h-16 w-full" />
        </div>
      ))}
    </div>
  );
}

function PatientActionButtons({ visit, onUpdateStatus }) {
  const transitions = VALID_TRANSITIONS[visit.status] || [];
  if (transitions.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {transitions.map((targetStatus) => (
        <button
          key={targetStatus}
          type="button"
          onClick={() => onUpdateStatus(visit.visit_id, targetStatus)}
          className="h-7 px-2.5 rounded-md bg-c-teal text-white text-xs font-medium transition-colors hover:bg-c-teal-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-c-teal focus-visible:ring-offset-1"
        >
          {STATUS_BUTTON_LABELS[targetStatus]}
        </button>
      ))}
    </div>
  );
}

function DoctorLane({ lane, isDragOver, onDragOver, onDragLeave, onDrop, onDragStart, onUpdateStatus }) {
  return (
    <div
      onDragOver={(e) => onDragOver(e, lane.doctorId)}
      onDragLeave={onDragLeave}
      onDrop={(e) => onDrop(e, lane.doctorId)}
      className={`rounded-xl border flex flex-col transition-colors ${
        isDragOver ? "border-c-teal bg-c-teal/5" : "border-gray-100"
      }`}
    >
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`inline-block w-2 h-2 rounded-full ${laneIndicatorClassName(lane.patients.length)}`} />
          <h3 className="font-semibold text-c-navy text-sm">{lane.doctorName}</h3>
        </div>
        <span className="text-xs text-gray-500">
          {lane.patients.length} patient{lane.patients.length === 1 ? "" : "s"}
        </span>
      </div>

      {!lane.isOnShift && (
        <div className="px-4 py-2 bg-amber-50 border-b border-amber-100 text-xs text-amber-700">
          {lane.doctorName} is now off shift — patients still assigned.
        </div>
      )}

      <div className="p-3 space-y-2 flex-1">
        {lane.patients.length === 0 ? (
          <p className="text-xs text-gray-400 px-1 py-2">No patients assigned yet</p>
        ) : (
          lane.patients.map((visit) => (
            <div
              key={visit.visit_id}
              draggable
              data-visit-id={visit.visit_id}
              onDragStart={(e) => onDragStart(e, visit.visit_id)}
              className={`rounded-lg border border-gray-100 p-3 cursor-grab active:cursor-grabbing hover:border-gray-200 ${
                PRIORITY_CARD_ACCENT[visit.priority_level] || PRIORITY_CARD_ACCENT_FALLBACK
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-c-navy">#{visit.doctor_position}</span>
                <PriorityBadge priority={visit.priority_level} />
              </div>
              <p className="font-semibold text-gray-900 text-sm">{visit.name}</p>
              <p className="text-xs text-gray-500">
                {VISIT_TYPE_LABELS[visit.visit_type] || visit.visit_type} · {STATUS_LABELS[visit.status] || visit.status}
                {" · "}
                <span className={getWaitClassName(visit.estimated_wait)}>{visit.estimated_wait} min</span>
              </p>
              <PatientActionButtons visit={visit} onUpdateStatus={onUpdateStatus} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function QueuePanel({ queue, loading, setQueue, onShiftDoctors, doctorsLoading, onAssign }) {
  const [toast, setToast] = useState(null);
  const toastTimeoutRef = useRef(null);
  const [dragOverTarget, setDragOverTarget] = useState(null);

  useEffect(() => {
    return () => {
      if (toastTimeoutRef.current) {
        clearTimeout(toastTimeoutRef.current);
      }
    };
  }, []);

  function showToast(message) {
    setToast(message);
    if (toastTimeoutRef.current) {
      clearTimeout(toastTimeoutRef.current);
    }
    toastTimeoutRef.current = setTimeout(() => setToast(null), 2000);
  }

  async function updateStatus(visitId, newStatus) {
    try {
      const response = await fetch(`${API_URL}/api/visit/${visitId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: newStatus }),
      });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      setQueue((prev) => {
        if (newStatus === "completed" || newStatus === "no_show") {
          return prev.filter((visit) => visit.visit_id !== visitId);
        }
        return prev.map((visit) =>
          visit.visit_id === visitId ? { ...visit, status: data.status } : visit
        );
      });
      showToast("Status updated");
    } catch {
      // next poll will reconcile state
    }
  }

  function handleDragStart(e, visitId) {
    e.dataTransfer.setData("text/plain", visitId);
    e.dataTransfer.effectAllowed = "move";
  }

  function handleDragOver(e, target) {
    e.preventDefault();
    if (dragOverTarget !== target) {
      setDragOverTarget(target);
    }
  }

  function handleDragLeave() {
    setDragOverTarget(null);
  }

  function handleDrop(e, doctorId) {
    e.preventDefault();
    setDragOverTarget(null);
    const visitId = e.dataTransfer.getData("text/plain");
    if (visitId) {
      onAssign(visitId, doctorId);
    }
  }

  if (loading || doctorsLoading) {
    return (
      <div className="text-c-text">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-c-navy">Live Queue</h2>
        </div>
        <SkeletonBlock />
      </div>
    );
  }

  const unassigned = queue.filter((visit) => visit.doctor_id === null);

  const patientsByDoctor = {};
  queue.forEach((visit) => {
    if (visit.doctor_id !== null) {
      if (!patientsByDoctor[visit.doctor_id]) {
        patientsByDoctor[visit.doctor_id] = [];
      }
      patientsByDoctor[visit.doctor_id].push(visit);
    }
  });
  Object.values(patientsByDoctor).forEach((list) =>
    list.sort((a, b) => (a.doctor_position || 0) - (b.doctor_position || 0))
  );

  const onShiftIds = new Set(onShiftDoctors.map((d) => d.id));
  const allLaneDoctorIds = new Set([
    ...onShiftDoctors.map((d) => d.id),
    ...Object.keys(patientsByDoctor).map(Number),
  ]);

  const lanes = Array.from(allLaneDoctorIds)
    .sort((a, b) => a - b)
    .map((doctorId) => {
      const onShiftDoctor = onShiftDoctors.find((d) => d.id === doctorId);
      const patients = patientsByDoctor[doctorId] || [];
      return {
        doctorId,
        doctorName: onShiftDoctor ? onShiftDoctor.name : patients[0]?.doctor_name || `Doctor ${doctorId}`,
        patients,
        isOnShift: onShiftIds.has(doctorId),
      };
    });

  const onShiftLanes = lanes.filter((lane) => lane.isOnShift);
  const ghostLanes = lanes.filter((lane) => !lane.isOnShift);

  return (
    <div className="text-c-text">
      <div className="px-6 py-4 border-b border-gray-100">
        <h2 className="text-lg font-semibold text-c-navy">Live Queue</h2>
      </div>

      <div className="p-6 space-y-6">
        <div
          onDragOver={(e) => handleDragOver(e, "unassigned")}
          onDragLeave={handleDragLeave}
          onDrop={(e) => handleDrop(e, null)}
          className={`rounded-xl border transition-colors ${
            dragOverTarget === "unassigned" ? "border-c-teal bg-c-teal/5" : "border-gray-100"
          }`}
        >
          <div className="px-4 py-3">
            <h3
              className={`text-sm font-semibold ${
                unassigned.length > 0 ? "text-amber-700" : "text-gray-400"
              }`}
            >
              Unassigned Patients ({unassigned.length})
            </h3>
          </div>

          {unassigned.length === 0 ? (
            <p className="px-4 pb-4 text-sm text-gray-400">All patients assigned</p>
          ) : (
            <div className="overflow-x-auto pb-2">
              <table className="min-w-full border-collapse">
                <thead>
                  <tr className="text-xs uppercase tracking-wide text-gray-500">
                    <th className="text-left px-4 py-2 font-medium">Position</th>
                    <th className="text-left px-4 py-2 font-medium">Patient Name</th>
                    <th className="text-left px-4 py-2 font-medium">Visit Type</th>
                    <th className="text-left px-4 py-2 font-medium">Priority</th>
                    <th className="text-left px-4 py-2 font-medium">Status</th>
                    <th className="text-left px-4 py-2 font-medium">Wait</th>
                    <th className="text-left px-4 py-2 font-medium">Assign To</th>
                  </tr>
                </thead>
                <tbody>
                  {unassigned.map((visit) => (
                    <tr
                      key={visit.visit_id}
                      draggable
                      data-visit-id={visit.visit_id}
                      onDragStart={(e) => handleDragStart(e, visit.visit_id)}
                      className="h-12 border-t border-gray-100 hover:bg-gray-50 cursor-grab active:cursor-grabbing"
                    >
                      <td className="px-4 font-medium text-c-navy">{visit.queue_position}</td>
                      <td className="px-4 font-semibold text-gray-900">{visit.name}</td>
                      <td className="px-4 text-gray-500">
                        {VISIT_TYPE_LABELS[visit.visit_type] || visit.visit_type}
                      </td>
                      <td className="px-4">
                        <PriorityBadge priority={visit.priority_level} />
                      </td>
                      <td className="px-4 text-gray-500">{STATUS_LABELS[visit.status] || visit.status}</td>
                      <td className="px-4 text-amber-600 text-sm font-medium whitespace-nowrap">
                        Awaiting assignment
                      </td>
                      <td className="px-4">
                        <select
                          defaultValue=""
                          onChange={(e) => {
                            if (e.target.value) {
                              onAssign(visit.visit_id, Number(e.target.value));
                            }
                          }}
                          disabled={onShiftDoctors.length === 0}
                          className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-c-teal disabled:bg-gray-50 disabled:cursor-not-allowed"
                        >
                          <option value="" disabled>
                            Assign a doctor...
                          </option>
                          {onShiftDoctors.map((doc) => (
                            <option key={doc.id} value={doc.id}>
                              {doc.name}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {onShiftDoctors.length === 0 ? (
          <div className="text-center py-10 px-4 border border-dashed border-gray-200 rounded-xl">
            <p className="text-gray-500 text-sm mb-2">No doctors on shift yet.</p>
            <Link to="/doctors" className="text-c-teal text-sm font-medium hover:underline">
              Go to the Doctors page to mark who is working today.
            </Link>
          </div>
        ) : (
          <div
            className={`grid gap-4 grid-cols-1 sm:grid-cols-2 ${
              onShiftLanes.length > 2 ? "lg:grid-cols-3" : ""
            }`}
          >
            {onShiftLanes.map((lane) => (
              <DoctorLane
                key={lane.doctorId}
                lane={lane}
                isDragOver={dragOverTarget === lane.doctorId}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onDragStart={handleDragStart}
                onUpdateStatus={updateStatus}
              />
            ))}
          </div>
        )}

        {ghostLanes.length > 0 && (
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
            {ghostLanes.map((lane) => (
              <DoctorLane
                key={lane.doctorId}
                lane={lane}
                isDragOver={dragOverTarget === lane.doctorId}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onDragStart={handleDragStart}
                onUpdateStatus={updateStatus}
              />
            ))}
          </div>
        )}
      </div>

      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-4 right-4 bg-white shadow-xl rounded-xl border border-gray-100 px-4 py-3 text-sm font-medium text-gray-700 animate-fade-out"
        >
          {toast}
        </div>
      )}
    </div>
  );
}
