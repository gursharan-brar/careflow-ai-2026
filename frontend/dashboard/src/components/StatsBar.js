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
    <div className="grid grid-cols-3 gap-4 mb-6">
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <p className="text-xs uppercase tracking-wide text-gray-500 font-medium mb-2">
          Active Patients
        </p>
        <p className="text-3xl font-bold text-c-navy">{activeCount}</p>
      </div>
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <p className="text-xs uppercase tracking-wide text-gray-500 font-medium mb-2">
          Average Wait
        </p>
        <p className="text-3xl font-bold text-c-navy">{avgWait === null ? "—" : `${avgWait} min`}</p>
      </div>
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <p className="text-xs uppercase tracking-wide text-gray-500 font-medium mb-2">
          Doctors On Shift
        </p>
        <p className="text-3xl font-bold text-c-navy">{onShiftCount === null ? "—" : onShiftCount}</p>
      </div>
    </div>
  );
}
