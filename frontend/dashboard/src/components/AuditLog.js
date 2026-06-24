import { useEffect, useState } from "react";
import Shimmer from "./Shimmer";
import { STATUS_LABELS } from "../constants";

const API_URL = process.env.REACT_APP_API_URL;

const EVENT_TYPE_LABELS = {
  status_change: "Status Change",
  triage_completed: "Triage Completed",
};

const PAGE_SIZE = 15;

// Conservative, narrowly-scoped heuristic for hiding dev/QA noise: every synthetic
// name used during testing contains the standalone word "test" ("Rapid Test 20",
// "Cap Consistency Test 8", "Queue Tool Test", etc.). A real patient is very unlikely
// to be named literally "test" as a whole word, so this is a low-risk way to keep the
// log scannable without touching the underlying data. Hidden entries are never
// discarded — just not rendered, and the count is shown so the filter is visible
// rather than a silent black box.
const TEST_DATA_PATTERN = /\btest\b/i;

function isTestEntry(entry) {
  return TEST_DATA_PATTERN.test(entry.patient_name || "");
}

function formatTimestamp(isoString) {
  return new Date(isoString).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function SkeletonRow() {
  return (
    <tr className="h-14 border-b border-gray-100">
      <td className="px-4"><Shimmer className="h-4 w-32" /></td>
      <td className="px-4"><Shimmer className="h-4 w-28" /></td>
      <td className="px-4"><Shimmer className="h-4 w-32" /></td>
      <td className="px-4"><Shimmer className="h-4 w-20" /></td>
      <td className="px-4"><Shimmer className="h-4 w-20" /></td>
    </tr>
  );
}

export default function AuditLog() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  useEffect(() => {
    let isMounted = true;

    async function fetchAuditLog() {
      try {
        const response = await fetch(`${API_URL}/api/audit`, { credentials: "include" });
        if (!response.ok) {
          throw new Error("Failed to fetch audit log");
        }
        const data = await response.json();
        if (isMounted) {
          setEntries(data);
        }
      } catch {
        // silently retry on next poll
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchAuditLog();
    const interval = setInterval(fetchAuditLog, 60000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const realEntries = entries.filter((entry) => !isTestEntry(entry));
  const hiddenTestCount = entries.length - realEntries.length;
  const visibleEntries = realEntries.slice(0, visibleCount);
  const hasMore = visibleCount < realEntries.length;

  return (
    <div className="bg-white text-c-text">
      <div className="px-6 py-4 border-b border-gray-100">
        <h2 className="text-lg font-semibold text-c-navy">Audit Log</h2>
      </div>

      {loading ? (
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse">
            <thead className="bg-c-navy text-white">
              <tr>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Timestamp</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Patient Name</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Event Type</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Old Status</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">New Status</th>
              </tr>
            </thead>
            <tbody>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </tbody>
          </table>
        </div>
      ) : realEntries.length === 0 ? (
        <div className="text-center py-16 px-4">
          <hr className="border-t border-c-teal/30 mb-6 mx-auto w-32" />
          <p className="text-gray-500 text-sm">No audit entries yet</p>
          {hiddenTestCount > 0 && (
            <p className="text-gray-400 text-xs mt-2">
              ({hiddenTestCount} test {hiddenTestCount === 1 ? "entry" : "entries"} hidden)
            </p>
          )}
          <hr className="border-t border-c-teal/30 mt-6 mx-auto w-32" />
        </div>
      ) : (
        <>
          {hiddenTestCount > 0 && (
            <p className="px-6 pt-3 text-xs text-gray-400">
              {hiddenTestCount} test {hiddenTestCount === 1 ? "entry" : "entries"} hidden
            </p>
          )}
          <div className="overflow-x-auto max-h-[70vh] overflow-y-auto">
          <table className="min-w-full border-collapse">
            <thead className="sticky top-0 bg-c-navy text-white z-10">
              <tr>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Timestamp</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Patient Name</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Event Type</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">Old Status</th>
                <th className="text-left px-4 py-3 text-xs uppercase tracking-wide font-medium">New Status</th>
              </tr>
            </thead>
            <tbody>
              {visibleEntries.map((entry) => (
                <tr key={entry.id} className="h-14 bg-white border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 text-sm text-gray-500">{formatTimestamp(entry.timestamp)}</td>
                  <td className="px-4 font-semibold text-gray-900">{entry.patient_name}</td>
                  <td className="px-4 text-sm text-gray-600">
                    {EVENT_TYPE_LABELS[entry.event_type] || entry.event_type}
                  </td>
                  <td className="px-4 text-sm text-gray-600">
                    {STATUS_LABELS[entry.old_status] || entry.old_status}
                  </td>
                  <td className="px-4 text-sm text-gray-600">
                    {STATUS_LABELS[entry.new_status] || entry.new_status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          {hasMore && (
            <div className="flex justify-center py-3 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}
                className="text-sm font-medium text-c-teal hover:text-c-teal-hover"
              >
                Load more ({realEntries.length - visibleEntries.length} remaining)
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
