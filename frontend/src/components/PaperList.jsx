import { FileText, Calendar, ExternalLink, FileDown, Users } from 'lucide-react';

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
      {papers.map((paper, idx) => {
        // Handle both old JSON format and new DB format
        const paperYear = paper.year || paper.published_year || 'Unknown Year';
        const paperAbstract = paper.abstract || '';
        const paperTitle = paper.title || 'Untitled';
        const paperAuthors = paper.authors || [];
        const paperSource = paper.source || '';
        const paperSummary = paper.summary || '';
        const paperArxivUrl = paper.arxiv_url || (paper.id ? `https://arxiv.org/abs/${paper.id}` : '');
        const paperPdfUrl = paper.pdf_url || (paper.id ? `https://arxiv.org/pdf/${paper.id}` : '');
        
        // Shorten abstract for display
        const shortAbstract = paperAbstract.length > 300 
          ? paperAbstract.substring(0, 300) + '...' 
          : paperAbstract;

        return (
          <div key={paper.id || idx} className="glass-card p-6 hover:-translate-y-0.5 transition-transform duration-200">
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-lg font-semibold text-slate-900 mb-2 leading-tight flex-1">
                {paperTitle}
              </h3>
              <div className="flex flex-col gap-2 flex-shrink-0">
                {paperArxivUrl && (
                  <a
                    href={paperArxivUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-full transition-colors"
                    title="View on arXiv"
                  >
                    <ExternalLink size={12} />
                    Abstract
                  </a>
                )}
                {paperPdfUrl && (
                  <a
                    href={paperPdfUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-600 hover:text-emerald-800 bg-emerald-50 hover:bg-emerald-100 px-3 py-1.5 rounded-full transition-colors"
                    title="View PDF"
                  >
                    <FileDown size={12} />
                    PDF
                  </a>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 text-sm text-slate-400 font-medium mb-3">
              <Calendar size={14} />
              <span>{paperYear}</span>
              {paperSource && (
                <span className="bg-slate-100 text-slate-500 text-xs px-2 py-0.5 rounded-full ml-2 uppercase tracking-wider">
                  {paperSource}
                </span>
              )}
            </div>

            {/* Authors */}
            {paperAuthors.length > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-3 flex-wrap">
                <Users size={12} />
                <span>{paperAuthors.slice(0, 4).join(', ')}{paperAuthors.length > 4 ? ` +${paperAuthors.length - 4} more` : ''}</span>
              </div>
            )}

            {/* AI Summary */}
            {paperSummary && paperSummary !== 'Summary not available.' && (
              <div className="bg-gradient-to-br from-indigo-50/50 via-blue-50/50 to-slate-50/50 border border-blue-100/50 rounded-xl p-4 mb-4 shadow-sm border-l-4 border-l-blue-500">
                <div className="flex items-center gap-2 mb-2 text-blue-700">
                  <div className="bg-blue-500 p-1 rounded-md text-white">
                    <FileText size={12} />
                  </div>
                  <span className="text-xs font-bold uppercase tracking-widest">AI Research Insight</span>
                </div>
                <p className="text-sm text-slate-700 leading-relaxed italic">
                  {paperSummary.startsWith('AI Analysis:') ? paperSummary.replace('AI Analysis:', '').trim() : paperSummary}
                </p>
              </div>
            )}

            {/* Abstract */}
            <div className="relative">
               <div className="absolute -left-3 top-0 bottom-0 w-0.5 bg-slate-100"></div>
               <p className="text-slate-500 leading-relaxed text-sm pl-2">
                 {shortAbstract || 'No abstract available.'}
               </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
