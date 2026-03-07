import { FileText, Calendar } from 'lucide-react';

export default function PaperList({ papers, loading, emptyMessage = 'No papers found.' }) {
  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="glass-card p-6 animate-pulse">
            <div className="h-6 w-3/4 bg-slate-200 rounded mb-3"></div>
            <div className="h-4 w-24 bg-slate-100 rounded mb-4"></div>
            <div className="space-y-2">
              <div className="h-4 bg-slate-100 rounded"></div>
              <div className="h-4 bg-slate-100 rounded w-5/6"></div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!papers || papers.length === 0) {
    return (
      <div className="bg-white border border-gray-100 rounded-xl p-12 text-center text-slate-500 shadow-sm">
        <FileText size={48} className="mx-auto text-slate-300 mb-4" />
        <p className="text-lg">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {papers.map((paper, idx) => (
        <div key={idx} className="glass-card p-6 hover:-translate-y-0.5 transition-transform duration-200">
          <h3 className="text-lg font-semibold text-slate-900 mb-2 leading-tight">
            {paper.title}
          </h3>
          <div className="flex items-center gap-2 text-sm text-slate-400 font-medium mb-4">
            <Calendar size={14} />
            <span>{paper.published_year || 'Unknown Year'}</span>
          </div>
          <p className="text-slate-600 leading-relaxed text-sm line-clamp-3">
            {paper.summary || paper.abstract || 'No summary available.'}
          </p>
        </div>
      ))}
    </div>
  );
}
