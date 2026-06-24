export default function Shimmer({ className }) {
  return (
    <div
      className={`rounded bg-gray-200 bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 bg-[length:1000px_100%] animate-shimmer ${className}`}
    />
  );
}
