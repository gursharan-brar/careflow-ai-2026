export function initialsFor(name) {
  if (!name) {
    return "?";
  }
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

export default function Avatar({ name, className }) {
  return (
    <div className={`shrink-0 rounded-full flex items-center justify-center font-semibold ${className}`}>
      {initialsFor(name)}
    </div>
  );
}
