import { Database, CalendarRange, BookOpenCheck } from 'lucide-react';

export default function StatsPanel({ stats, loading }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {[1, 2, 3].map((i) => (
          <div key={i} className="glass-card p-5 animate-pulse">
            <div className="h-10 w-10 bg-slate-200 rounded-lg mb-4"></div>
            <div className="h-6 w-24 bg-slate-200 rounded mb-2"></div>
            <div className="h-4 w-32 bg-slate-100 rounded"></div>
          </div>
        ))}
      </div>
    );
  }

  if (!stats) return null;

  const statItems = [
    {
      title: 'Total Papers',
      value: stats.total_papers || 0,
      icon: <Database size={20} className="text-blue-600" />,
      bg: 'bg-blue-50'
    },
    {
      title: 'Coverage Range',
      value: stats.earliest_year && stats.latest_year ? `${stats.earliest_year} - ${stats.latest_year}` : 'N/A',
      icon: <CalendarRange size={20} className="text-indigo-600" />,
      bg: 'bg-indigo-50'
    },
    {
      title: 'Analyzed Content',
      value: 'Abstracts & Titles',
      icon: <BookOpenCheck size={20} className="text-emerald-600" />,
      bg: 'bg-emerald-50'
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      {statItems.map((item, idx) => (
        <div key={idx} className="glass-card p-5 hover:shadow-md transition-shadow">
          <div className="flex items-center gap-4 mb-3">
            <div className={`${item.bg} p-2.5 rounded-xl`}>
              {item.icon}
            </div>
            <h3 className="text-slate-500 font-medium text-sm tracking-wide uppercase">{item.title}</h3>
          </div>
          <p className="text-2xl font-bold text-slate-800">{item.value}</p>
        </div>
      ))}
    </div>
  );
}
