import { Database, CalendarRange, BookOpenCheck } from 'lucide-react';

export default function StatsPanel({ stats, loading }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm animate-pulse">
            <div className="h-10 w-10 bg-slate-200 rounded-lg mb-4"></div>
            <div className="h-6 w-24 bg-slate-200 rounded mb-2"></div>
            <div className="h-4 w-32 bg-slate-100 rounded"></div>
          </div>
        ))}
      </div>
    );
  }

  if (!stats) return null;

  // Derive year range from year_distribution if earliest/latest not provided
  const yearDist = stats.year_distribution || {};
  const years = Object.keys(yearDist).map(Number).filter(y => !isNaN(y));
  const earliestYear = stats.earliest_year || (years.length > 0 ? Math.min(...years) : null);
  const latestYear = stats.latest_year || (years.length > 0 ? Math.max(...years) : null);

  const statItems = [
    {
      title: 'Academic Database Index',
      value: 'Live API Cascade',
      subtitle: `${stats.total_papers || 0} papers indexed in local cache`,
      icon: <Database size={20} className="text-blue-600" />,
      bg: 'bg-blue-50'
    },
    {
      title: 'Coverage Range',
      value: earliestYear && latestYear ? `${earliestYear} - ${latestYear}` : '1990 - 2026',
      subtitle: 'Global peer-reviewed registries',
      icon: <CalendarRange size={20} className="text-indigo-600" />,
      bg: 'bg-indigo-50'
    },
    {
      title: 'Sources & Intelligence',
      value: 'arXiv · S2 · OpenAlex',
      subtitle: 'BM25 + LinUCB RL Recommender',
      icon: <BookOpenCheck size={20} className="text-emerald-600" />,
      bg: 'bg-emerald-50'
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      {statItems.map((item, idx) => (
        <div key={idx} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm hover:border-gray-300 hover:shadow transition-all duration-150 cursor-pointer">
          <div className="flex items-center gap-4 mb-3">
            <div className={`${item.bg} p-2.5 rounded-lg border border-gray-100`}>
              {item.icon}
            </div>
            <h3 className="text-gray-500 font-semibold text-xs tracking-wide uppercase">{item.title}</h3>
          </div>
          <p className="text-xl font-bold text-gray-900 leading-snug">{item.value}</p>
          {item.subtitle && (
            <p className="text-xs text-slate-400 mt-1 font-medium">{item.subtitle}</p>
          )}
        </div>
      ))}
    </div>
  );
}
