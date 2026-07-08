import { useEffect, useState } from "react";
import Header from "./Header";
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

// Same colors already used for these five statuses on the patient-facing
// status.html page — reused here so a status reads identically everywhere.
const STATUS_BADGES = {
  checked_in: "bg-blue-100 text-blue-700 border-blue-200",
  called: "bg-amber-100 text-amber-800 border-amber-200",
  in_progress: "bg-purple-100 text-purple-700 border-purple-200",
  completed: "bg-c-routine-bg text-c-routine-text border-green-200",
  no_show: "bg-c-urgent-bg text-c-urgent-text border-red-200",
};

const STATUS_FILTER_OPTIONS = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "no_show", label: "No Show" },
];

const PER_PAGE = 20;
const SEARCH_DEBOUNCE_MS = 400;

function PriorityBadge({ priority }) {
  const config = PRIORITY_BADGES[priority] || PRIORITY_FALLBACK;
  return (
    <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold border whitespace-nowrap ${config.className}`}>
      {config.label}
    </span>
  );
}

function StatusBadge({ status }) {
  const className = STATUS_BADGES[status] || "bg-c-null-bg text-c-null-text border-gray-200";
  return (
    <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold border whitespace-nowrap ${className}`}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function formatDateTime(isoString) {
  if (!isoString) {
    return "—";
  }
  return new Date(isoString).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatSlotLabel(slotTime) {
  if (!slotTime) {
    return "—";
  }
  const [h, m] = slotTime.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const hour12 = h % 12 || 12;
  return `${hour12}:${m.toString().padStart(2, "0")} ${period}`;
}

function waitDisplay(visit) {
  if (visit.status === "completed" || visit.status === "no_show") {
    return visit.actual_wait !== null && visit.actual_wait !== undefined ? `${visit.actual_wait} min` : "—";
  }
  return visit.estimated_wait !== null && visit.estimated_wait !== undefined ? `${visit.estimated_wait} min` : "—";
}

function SkeletonRow() {
  return (
    <tr className="h-16 border-b border-gray-100">
      <td className="px-5"><Shimmer className="h-4 w-32" /></td>
      <td className="px-5"><Shimmer className="h-4 w-24" /></td>
      <td className="px-5"><Shimmer className="h-4 w-20" /></td>
      <td className="px-5"><Shimmer className="h-4 w-20" /></td>
      <td className="px-5"><Shimmer className="h-4 w-24" /></td>
      <td className="px-5"><Shimmer className="h-4 w-28" /></td>
      <td className="px-5"><Shimmer className="h-4 w-16" /></td>
    </tr>
  );
}

function TriageIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 2h6l1 4H8l1-4z"></path>
      <path d="M6 6h12v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6z"></path>
      <line x1="9" y1="11" x2="15" y2="11"></line>
      <line x1="9" y1="15" x2="15" y2="15"></line>
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
    </svg>
  );
}

function RowIndicators({ visit }) {
  if (!visit.has_triage && !visit.has_chat) {
    return null;
  }
  return (
    <div className="flex items-center gap-2 text-c-teal">
      {visit.has_triage && (
        <span title="Triage completed">
          <TriageIcon />
        </span>
      )}
      {visit.has_chat && (
        <span title="Has chat history">
          <ChatIcon />
        </span>
      )}
    </div>
  );
}

function PatientsList({ onSelectVisit }) {
  const [visits, setVisits] = useState([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, per_page: PER_PAGE, pages: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [doctorId, setDoctorId] = useState("");
  const [page, setPage] = useState(1);

  const [doctors, setDoctors] = useState([]);

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
        // doctor filter simply stays empty; not fatal to the page
      }
    }
    fetchDoctors();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [searchInput]);

  useEffect(() => {
    let isMounted = true;

    async function fetchPatients() {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.set("page", String(page));
        params.set("per_page", String(PER_PAGE));
        if (status !== "all") {
          params.set("status", status);
        }
        if (dateFrom) {
          params.set("date_from", dateFrom);
        }
        if (dateTo) {
          params.set("date_to", dateTo);
        }
        if (doctorId) {
          params.set("doctor_id", doctorId);
        }
        if (debouncedSearch) {
          params.set("search", debouncedSearch);
        }

        const response = await fetch(`${API_URL}/api/patients?${params.toString()}`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Failed to fetch patients");
        }
        const data = await response.json();
        if (isMounted) {
          setVisits(data.visits);
          setMeta({ total: data.total, page: data.page, per_page: data.per_page, pages: data.pages });
        }
      } catch {
        if (isMounted) {
          setError("Could not load patients. Please try again.");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchPatients();

    return () => {
      isMounted = false;
    };
  }, [page, status, dateFrom, dateTo, doctorId, debouncedSearch]);

  function clearFilters() {
    setSearchInput("");
    setDebouncedSearch("");
    setStatus("all");
    setDateFrom("");
    setDateTo("");
    setDoctorId("");
    setPage(1);
  }

  return (
    <div className="text-c-text">
      <div className="px-7 py-5 border-b border-gray-100 flex flex-wrap items-center gap-4">
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search by patient name"
          maxLength={100}
          className="flex-1 min-w-[200px] px-4 py-2.5 text-base border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-c-teal"
        />

        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2.5 text-base border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-c-teal"
        >
          {STATUS_FILTER_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        <input
          type="date"
          value={dateFrom}
          onChange={(e) => {
            setDateFrom(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2.5 text-base border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-c-teal"
        />
        <span className="text-gray-400">to</span>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => {
            setDateTo(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2.5 text-base border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-c-teal"
        />

        <select
          value={doctorId}
          onChange={(e) => {
            setDoctorId(e.target.value);
            setPage(1);
          }}
          className="px-3 py-2.5 text-base border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-c-teal"
        >
          <option value="">All Doctors</option>
          {doctors.map((doc) => (
            <option key={doc.id} value={doc.id}>
              {doc.name}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={clearFilters}
          className="px-4 py-2.5 text-base font-semibold text-gray-500 hover:text-c-teal transition-colors"
        >
          Clear Filters
        </button>
      </div>

      {error ? (
        <div className="px-7 py-14 text-center">
          <p className="text-base text-red-600 mb-4">{error}</p>
          <button
            type="button"
            onClick={() => setPage((p) => p)}
            className="px-4 py-2 text-base font-semibold rounded-xl bg-c-teal text-white hover:bg-c-teal-hover"
          >
            Retry
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead className="bg-c-navy text-white">
              <tr>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Patient Name</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Visit Type</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Priority</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Status</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Doctor</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Check-in</th>
                <th className="text-left px-5 py-4 text-sm uppercase tracking-wide font-bold">Wait</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <>
                  <SkeletonRow />
                  <SkeletonRow />
                  <SkeletonRow />
                  <SkeletonRow />
                </>
              ) : visits.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-7 py-14 text-center text-base text-gray-400">
                    No patients found matching your filters.
                  </td>
                </tr>
              ) : (
                visits.map((visit) => (
                  <tr
                    key={visit.id}
                    onClick={() => onSelectVisit(visit.id)}
                    className="h-16 border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                  >
                    <td className="px-5">
                      <div className="flex items-center gap-2.5">
                        <span className="font-bold text-base text-gray-900">{visit.name}</span>
                        <RowIndicators visit={visit} />
                      </div>
                    </td>
                    <td className="px-5 text-base text-gray-600">
                      {VISIT_TYPE_LABELS[visit.visit_type] || visit.visit_type}
                    </td>
                    <td className="px-5">
                      <PriorityBadge priority={visit.priority_level} />
                    </td>
                    <td className="px-5">
                      <StatusBadge status={visit.status} />
                    </td>
                    <td className="px-5 text-base text-gray-600">{visit.doctor_name || "Unassigned"}</td>
                    <td className="px-5 text-base text-gray-500">{formatDateTime(visit.created_at)}</td>
                    <td className="px-5 text-base text-gray-500">{waitDisplay(visit)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {!error && !loading && visits.length > 0 && (
        <div className="flex items-center justify-between px-7 py-5 border-t border-gray-100">
          <p className="text-sm text-gray-400">{meta.total} total patients</p>
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={meta.page <= 1}
              className="px-4 py-2 text-base font-semibold rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-base text-gray-600">
              Page {meta.page} of {meta.pages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(meta.pages, p + 1))}
              disabled={meta.page >= meta.pages}
              className="px-4 py-2 text-base font-semibold rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function TriageSection({ detail }) {
  if (!detail.triage_summary && !detail.triage_answers) {
    return null;
  }
  const hasFlag = detail.flag_reason && detail.flag_reason.toLowerCase() !== "none" && detail.flag_reason.trim() !== "";

  return (
    <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
      <div className="px-7 py-5 border-b border-gray-100">
        <h2 className="text-xl font-bold text-c-navy">Triage</h2>
      </div>
      <div className="p-7 space-y-5">
        <div className="flex items-center gap-3">
          <PriorityBadge priority={detail.priority_level} />
          <p className="text-base text-gray-700">{detail.triage_summary || "Not yet triaged"}</p>
        </div>

        {hasFlag && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-base text-amber-800">
            <span className="font-bold">Flag: </span>
            {detail.flag_reason}
          </div>
        )}

        <div>
          <p className="text-sm uppercase tracking-wide text-gray-500 font-bold mb-3">Triage Answers</p>
          {detail.triage_answers && detail.triage_answers.length > 0 ? (
            <ul className="space-y-3">
              {detail.triage_answers.map((qa, i) => (
                <li key={i} className="text-base">
                  <p className="font-semibold text-gray-800">Q: {qa.question}</p>
                  <p className="text-gray-600">A: {qa.answer}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-base text-gray-400">Triage answers were not recorded for this visit.</p>
          )}
        </div>
      </div>
    </div>
  );
}

const AUDIT_EVENT_LABELS = {
  status_change: "Status Change",
  triage_completed: "Triage Completed",
  record_exported: "Record Exported",
};

function AuditTrailSection({ auditTrail }) {
  return (
    <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
      <div className="px-7 py-5 border-b border-gray-100">
        <h2 className="text-xl font-bold text-c-navy">Visit Audit Trail</h2>
      </div>
      <div className="p-7">
        {auditTrail.length === 0 ? (
          <p className="text-base text-gray-400">No audit events recorded.</p>
        ) : (
          <ol className="space-y-4">
            {auditTrail.map((entry, i) => (
              <li key={i} className="flex items-start gap-4 text-base">
                <span className="text-gray-400 whitespace-nowrap">{formatDateTime(entry.timestamp)}</span>
                <span className="text-gray-700">
                  <span className="font-semibold">
                    {AUDIT_EVENT_LABELS[entry.event_type] || entry.event_type}
                  </span>
                  {": "}
                  {STATUS_LABELS[entry.old_status] || entry.old_status} →{" "}
                  {STATUS_LABELS[entry.new_status] || entry.new_status}
                  <span className="text-gray-400"> (actor: {entry.actor})</span>
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

function ChatHistorySection({ chatLog }) {
  if (!chatLog || chatLog.length === 0) {
    return null;
  }
  return (
    <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
      <div className="px-7 py-5 border-b border-gray-100">
        <h2 className="text-xl font-bold text-c-navy">Chat History</h2>
      </div>
      <div className="p-7 space-y-3">
        {chatLog.map((turn, i) => (
          <div key={i} className="text-base">
            <span className={`font-bold ${turn.role === "user" ? "text-c-navy" : "text-c-teal"}`}>
              {turn.role === "user" ? "Patient" : "CareFlow AI"}
            </span>
            <span className="text-gray-400 text-sm ml-2">{formatDateTime(turn.created_at)}</span>
            <p className="text-gray-700 whitespace-pre-wrap">{turn.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function AppointmentSection({ appointment }) {
  if (!appointment) {
    return null;
  }
  return (
    <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
      <div className="px-7 py-5 border-b border-gray-100">
        <h2 className="text-xl font-bold text-c-navy">Appointment Details</h2>
      </div>
      <div className="p-7 text-base text-gray-700 space-y-1">
        <p>
          <span className="font-semibold">Slot:</span> {appointment.slot_date} {formatSlotLabel(appointment.slot_time)}
        </p>
        <p>
          <span className="font-semibold">Booking Status:</span> {appointment.status}
        </p>
      </div>
    </div>
  );
}

function PatientDetail({ visitId, onBack }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function fetchDetail() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${API_URL}/api/patients/${visitId}`, { credentials: "include" });
        if (!response.ok) {
          throw new Error("Failed to fetch visit detail");
        }
        const data = await response.json();
        if (isMounted) {
          setDetail(data);
        }
      } catch {
        if (isMounted) {
          setError("Could not load this patient's record. Please try again.");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchDetail();

    return () => {
      isMounted = false;
    };
  }, [visitId]);

  async function handleExport() {
    setExporting(true);
    try {
      const response = await fetch(`${API_URL}/api/patients/export/${visitId}`, { credentials: "include" });
      if (!response.ok) {
        return;
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `visit-${visitId.slice(0, 8)}.txt`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      // export failure is non-critical; the visit data is still visible on screen
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-2 text-base font-semibold text-c-teal hover:text-c-teal-hover"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
        Back to Patients
      </button>

      {loading ? (
        <div className="bg-white rounded-3xl shadow-lg border border-gray-100 p-7 space-y-4">
          <Shimmer className="h-6 w-1/3" />
          <Shimmer className="h-4 w-1/2" />
          <Shimmer className="h-4 w-2/3" />
        </div>
      ) : error ? (
        <div className="bg-white rounded-3xl shadow-lg border border-gray-100 p-7 text-center">
          <p className="text-base text-red-600">{error}</p>
        </div>
      ) : detail ? (
        <>
          <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
            <div className="p-7 space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <h2 className="text-2xl font-extrabold text-c-navy">{detail.name}</h2>
                  <p className="text-base text-gray-500 mt-1">
                    {VISIT_TYPE_LABELS[detail.visit_type] || detail.visit_type} · Checked in {formatDateTime(detail.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <PriorityBadge priority={detail.priority_level} />
                  <StatusBadge status={detail.status} />
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
                <div>
                  <p className="text-sm uppercase tracking-wide text-gray-500 font-bold mb-1">Doctor</p>
                  <p className="text-base text-gray-800">{detail.doctor_name || "Unassigned"}</p>
                </div>
                <div>
                  <p className="text-sm uppercase tracking-wide text-gray-500 font-bold mb-1">Estimated Wait</p>
                  <p className="text-base text-gray-800">
                    {detail.estimated_wait !== null && detail.estimated_wait !== undefined ? `${detail.estimated_wait} min` : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-sm uppercase tracking-wide text-gray-500 font-bold mb-1">Actual Wait</p>
                  <p className="text-base text-gray-800">
                    {detail.actual_wait !== null && detail.actual_wait !== undefined ? `${detail.actual_wait} min` : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-sm uppercase tracking-wide text-gray-500 font-bold mb-1">Contact</p>
                  <p className="text-base text-gray-800 truncate">{detail.email}</p>
                  <p className="text-base text-gray-500">{detail.phone}</p>
                </div>
              </div>
            </div>
          </div>

          <TriageSection detail={detail} />
          <AuditTrailSection auditTrail={detail.audit_trail} />
          <ChatHistorySection chatLog={detail.chat_log} />
          <AppointmentSection appointment={detail.appointment} />

          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleExport}
              disabled={exporting}
              className="px-5 py-3 text-base font-bold rounded-xl bg-c-teal text-white hover:bg-c-teal-hover disabled:bg-c-teal/50 disabled:cursor-not-allowed"
            >
              {exporting ? "Preparing…" : "Download Visit Summary"}
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

export default function PatientsPage() {
  const [selectedVisitId, setSelectedVisitId] = useState(null);

  // PatientsList stays mounted at all times (just hidden via CSS) rather than
  // being conditionally rendered, so its filter/search/page state survives a
  // trip into the detail view and back — the list looks exactly as the staff
  // member left it, per the "Back returns with filters intact" requirement.
  return (
    <div className="min-h-screen bg-c-bg">
      <Header title="Patients" subtitle="Search and review every patient visit, active or historical" />

      <main className="max-w-[1500px] px-10 py-10 space-y-8">
        <div className={selectedVisitId ? "hidden" : ""}>
          <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
            <PatientsList onSelectVisit={setSelectedVisitId} />
          </div>
        </div>

        {selectedVisitId && (
          <PatientDetail visitId={selectedVisitId} onBack={() => setSelectedVisitId(null)} />
        )}
      </main>
    </div>
  );
}
