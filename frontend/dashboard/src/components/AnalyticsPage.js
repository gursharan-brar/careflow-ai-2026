import { useEffect, useState } from "react";
import Header from "./Header";
import Shimmer from "./Shimmer";

const API_URL = process.env.REACT_APP_API_URL;

const ICONS = {
  visits: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
      <circle cx="9" cy="7" r="4"></circle>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
    </svg>
  ),
  wait: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9"></circle>
      <path d="M12 7v5l3 3"></path>
    </svg>
  ),
  walkin: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21V9"></path>
      <path d="M3 21h18"></path>
      <path d="M5 21V7a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v14"></path>
      <path d="M13 12h2"></path>
    </svg>
  ),
  booked: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2"></rect>
      <line x1="16" y1="2" x2="16" y2="6"></line>
      <line x1="8" y1="2" x2="8" y2="6"></line>
      <line x1="3" y1="10" x2="21" y2="10"></line>
    </svg>
  ),
  noShow: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9"></circle>
      <line x1="15" y1="9" x2="9" y2="15"></line>
      <line x1="9" y1="9" x2="15" y2="15"></line>
    </svg>
  ),
  completed: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9"></circle>
      <path d="M8.5 12.5l2.5 2.5 5-5"></path>
    </svg>
  ),
  summary: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2 4 5v6c0 5 3.5 9 8 11 4.5-2 8-6 8-11V5l-8-3z"></path>
      <line x1="12" y1="8" x2="12" y2="13"></line>
      <line x1="12" y1="16" x2="12" y2="16.01"></line>
    </svg>
  ),
};

function StatCard({ icon, iconClass, label, value }) {
  return (
    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-7 flex items-start gap-5">
      <div className={`w-16 h-16 rounded-2xl flex items-center justify-center shrink-0 ${iconClass}`}>
        <span className="[&>svg]:w-7 [&>svg]:h-7">{icon}</span>
      </div>
      <div className="min-w-0">
        <p className="text-sm uppercase tracking-wide text-gray-500 font-bold mb-2">{label}</p>
        <p className="text-4xl font-extrabold text-c-navy leading-none">{value}</p>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-7 space-y-3">
      <Shimmer className="h-5 w-1/2" />
      <Shimmer className="h-9 w-1/3" />
    </div>
  );
}

export default function AnalyticsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState(null);

  useEffect(() => {
    let isMounted = true;

    async function fetchAnalytics() {
      try {
        const response = await fetch(`${API_URL}/api/analytics/weekly`, { credentials: "include" });
        if (!response.ok) {
          throw new Error("Failed to fetch weekly analytics");
        }
        const result = await response.json();
        if (isMounted) {
          setData(result);
        }
      } catch {
        // keep previous data; nothing else to do for a read-only page
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchAnalytics();

    return () => {
      isMounted = false;
    };
  }, []);

  const stats = data?.stats || null;

  async function handleGenerateNow() {
    setGenerating(true);
    setGenerateError(null);

    try {
      const response = await fetch(`${API_URL}/api/analytics/weekly/recompute`, {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        setGenerateError(errorData.error || "Could not generate a new summary. Please try again.");
        return;
      }

      const result = await response.json();
      setData(result);
    } catch {
      setGenerateError("Could not reach the server. Please try again.");
    } finally {
      setGenerating(false);
    }
  }

  const rightSlot = (
    <button
      type="button"
      onClick={handleGenerateNow}
      disabled={generating}
      className="px-5 py-3 text-base font-bold rounded-xl bg-c-teal text-white hover:bg-c-teal-hover disabled:bg-c-teal/50 disabled:cursor-not-allowed"
    >
      {generating ? "Generating..." : "Generate Now"}
    </button>
  );

  return (
    <div className="min-h-screen bg-c-bg">
      <Header title="Analytics" subtitle="Weekly stats and an AI-written summary" rightSlot={rightSlot} />

      <main className="max-w-[1500px] px-10 py-10 space-y-8">
        {generateError && (
          <div className="text-sm rounded-xl px-4 py-3 border bg-red-50 border-red-200 text-red-700">
            {generateError}
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : !stats ? (
          <div className="bg-white rounded-3xl shadow-sm border border-gray-100 text-center py-14">
            <hr className="border-t border-c-teal/30 mb-6 mx-auto w-32" />
            <p className="text-gray-500 text-base">No analytics have been generated yet</p>
            <hr className="border-t border-c-teal/30 mt-6 mx-auto w-32" />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              <StatCard
                icon={ICONS.visits}
                iconClass="bg-c-teal/10 text-c-teal"
                label="Total Visits"
                value={stats.total_visits ?? 0}
              />
              <StatCard
                icon={ICONS.wait}
                iconClass="bg-amber-50 text-amber-600"
                label="Average Wait"
                value={stats.average_wait_minutes === null || stats.average_wait_minutes === undefined ? "—" : `${stats.average_wait_minutes} min`}
              />
              <StatCard
                icon={ICONS.walkin}
                iconClass="bg-c-navy/10 text-c-navy"
                label="Walk-Ins"
                value={stats.walkin_count ?? 0}
              />
              <StatCard
                icon={ICONS.booked}
                iconClass="bg-blue-50 text-blue-600"
                label="Booked Visits"
                value={stats.booked_count ?? 0}
              />
              <StatCard
                icon={ICONS.noShow}
                iconClass="bg-red-50 text-red-600"
                label="No-Shows"
                value={stats.no_show_count ?? 0}
              />
              <StatCard
                icon={ICONS.completed}
                iconClass="bg-emerald-50 text-emerald-600"
                label="Completed"
                value={stats.completed_count ?? 0}
              />
            </div>

            {stats.visits_per_doctor && stats.visits_per_doctor.length > 0 && (
              <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="px-7 py-5 border-b border-gray-100">
                  <h2 className="text-xl font-bold text-c-navy">Visits per Doctor</h2>
                  <p className="text-sm text-gray-500 mt-1">
                    {stats.window_start} to {stats.window_end}
                  </p>
                </div>
                <ul className="divide-y divide-gray-100">
                  {stats.visits_per_doctor.map((entry) => (
                    <li key={entry.doctor_name} className="flex items-center justify-between px-7 py-4">
                      <span className="text-base font-semibold text-gray-900">{entry.doctor_name}</span>
                      <span className="text-base text-gray-500">
                        {entry.count} visit{entry.count === 1 ? "" : "s"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
              <div className="flex items-center justify-between px-7 py-5 border-b border-gray-100">
                <div className="flex items-center gap-3">
                  <span className="w-10 h-10 rounded-xl bg-c-teal/10 text-c-teal flex items-center justify-center">
                    {ICONS.summary}
                  </span>
                  <h2 className="text-xl font-bold text-c-navy">Weekly Summary</h2>
                </div>
                {data?.generated_at && (
                  <span className="text-sm text-gray-400 font-medium">
                    Generated {new Date(data.generated_at).toLocaleString()}
                  </span>
                )}
              </div>
              <div className="p-7">
                <p className="text-base text-gray-600 leading-relaxed">{data?.summary}</p>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
