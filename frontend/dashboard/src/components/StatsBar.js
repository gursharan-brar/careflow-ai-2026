const ICONS = {
  patients: (
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
  doctors: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 3v4a2 2 0 0 0 2 2h0a2 2 0 0 0 2-2V3"></path>
      <path d="M8 3a2 2 0 0 0-2 2v5a5 5 0 0 0 10 0V5a2 2 0 0 0-2-2"></path>
      <path d="M18 10v2a6 6 0 0 1-12 0v-2"></path>
      <circle cx="19" cy="16" r="2.5"></circle>
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

export default function StatsBar({ patients, onShiftCount }) {
  const activeCount = patients.length;
  const assignedWithWait = patients.filter(
    (visit) => visit.estimated_wait !== null && visit.estimated_wait !== undefined
  );
  const avgWait =
    assignedWithWait.length === 0
      ? null
      : Math.round(
          assignedWithWait.reduce((sum, visit) => sum + visit.estimated_wait, 0) / assignedWithWait.length
        );

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
      <StatCard
        icon={ICONS.patients}
        iconClass="bg-c-teal/10 text-c-teal"
        label="Active Patients"
        value={activeCount}
      />
      <StatCard
        icon={ICONS.wait}
        iconClass="bg-amber-50 text-amber-600"
        label="Average Wait"
        value={avgWait === null ? "—" : `${avgWait} min`}
      />
      <StatCard
        icon={ICONS.doctors}
        iconClass="bg-c-navy/10 text-c-navy"
        label="Doctors On Shift"
        value={onShiftCount === null ? "—" : onShiftCount}
      />
    </div>
  );
}
