export default function Header({ title, subtitle, rightSlot }) {
  return (
    <header className="bg-white border-b border-gray-100 px-10 py-7">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-c-navy tracking-tight">{title}</h1>
          {subtitle && <p className="text-base text-gray-500 mt-1">{subtitle}</p>}
        </div>
        {rightSlot}
      </div>
    </header>
  );
}
