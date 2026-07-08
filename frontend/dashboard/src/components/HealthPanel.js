import { useEffect, useState } from "react";
import Shimmer from "./Shimmer";

const API_URL = process.env.REACT_APP_API_URL;
const REFRESH_INTERVAL = 12 * 60 * 60 * 1000;
const TICK_INTERVAL = 60 * 1000;

function formatRelativeTime(isoString, now) {
  if (!isoString) {
    return null;
  }

  const diffMinutes = Math.floor((now - new Date(isoString).getTime()) / 60000);

  if (diffMinutes < 1) {
    return "just now";
  }
  if (diffMinutes < 60) {
    return `${diffMinutes} minute${diffMinutes === 1 ? "" : "s"} ago`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
  }

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
}

function SkeletonCard() {
  return (
    <div className="border border-gray-100 rounded-2xl p-5 space-y-3">
      <Shimmer className="h-5 w-3/4" />
      <Shimmer className="h-4 w-full" />
      <Shimmer className="h-4 w-2/3" />
      <Shimmer className="h-3 w-1/3" />
    </div>
  );
}

export default function HealthPanel() {
  const [entries, setEntries] = useState([]);
  const [fetchedAt, setFetchedAt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    let isMounted = true;

    async function fetchHealthFeed() {
      try {
        const response = await fetch(`${API_URL}/api/health-feed`, { credentials: "include" });
        if (!response.ok) {
          throw new Error("Failed to fetch health feed");
        }
        const data = await response.json();
        if (isMounted) {
          setEntries(data.entries || []);
          setFetchedAt(data.fetched_at || null);
        }
      } catch {
        // keep previous data; will retry on next refresh
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchHealthFeed();
    const interval = setInterval(fetchHealthFeed, REFRESH_INTERVAL);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), TICK_INTERVAL);
    return () => clearInterval(tick);
  }, []);

  const relativeTime = formatRelativeTime(fetchedAt, now);

  return (
    <div className="bg-white text-c-text">
      <div className="flex items-center justify-between px-7 py-5 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <span className="w-10 h-10 rounded-xl bg-c-teal/10 text-c-teal flex items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2 4 5v6c0 5 3.5 9 8 11 4.5-2 8-6 8-11V5l-8-3z"></path>
              <line x1="12" y1="8" x2="12" y2="13"></line>
              <line x1="12" y1="16" x2="12" y2="16.01"></line>
            </svg>
          </span>
          <h2 className="text-xl font-bold text-c-navy">Health Advisories</h2>
        </div>
        <span className="text-sm text-gray-400 font-medium">
          {loading ? "—" : relativeTime ? `Last updated ${relativeTime}` : "Never updated"}
        </span>
      </div>

      <div className="p-7">
        {loading ? (
          <div className="grid gap-5 grid-cols-1 sm:grid-cols-2">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-14">
            <hr className="border-t border-c-teal/30 mb-6 mx-auto w-32" />
            <p className="text-gray-500 text-base">No health advisories available</p>
            <hr className="border-t border-c-teal/30 mt-6 mx-auto w-32" />
          </div>
        ) : (
          <div className="grid gap-5 grid-cols-1 sm:grid-cols-2">
            {entries.map((entry, index) => (
              <div key={index} className="bg-white border border-gray-100 rounded-2xl p-6">
                <h3 className="font-bold text-lg text-c-navy mb-2.5">{entry.title}</h3>
                <p className="text-base text-gray-600 mb-4">{entry.summary}</p>
                <p className="text-sm text-gray-400">
                  {entry.source}
                  {entry.date ? ` · ${entry.date}` : ""}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
