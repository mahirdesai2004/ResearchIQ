import { FileText, Calendar, ExternalLink, FileDown, Users, Tag, HelpCircle, Activity, Sparkles, Brain, GitBranch } from 'lucide-react';

export default function PaperList({ papers, loading, mode = 'deep dive', emptyMessage = 'No papers found.', onAnalyze }) {
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

  const renderPaper = (paper, isCard = false) => {
    const paperYear = paper.year || 'Unknown Year';
    const paperAbstract = paper.abstract || '';
    const paperTitle = paper.title || 'Untitled';
    const paperAuthors = paper.authors || [];
    const paperScore = paper.score;
    const matchedKeywords = paper.matched_keywords || [];
    const paperArxivUrl = paper.id ? `https://arxiv.org/abs/${paper.id}` : '';
    const paperPdfUrl = paper.id ? `https://arxiv.org/pdf/${paper.id}` : '';

    const shortAbstract = paperAbstract.length > 200 && isCard
      ? paperAbstract.substring(0, 200) + '...' 
      : paperAbstract;

    return (
      <div key={paper.id || paperTitle} className={`bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:border-gray-300 hover:shadow transition-all duration-150 ${isCard ? 'flex flex-col h-full' : 'mb-4'}`}>
        <div className="flex items-start justify-between gap-3 mb-3">
          <h3 className="text-lg font-semibold text-gray-900 leading-tight">
            {paperTitle}
          </h3>
          {paperScore > 0 && (
            <div className="flex-shrink-0 bg-blue-50 text-blue-700 text-xs font-medium px-2.5 py-1 rounded flex items-center gap-1.5" title="Confidence Score">
              <Activity size={12} />
              {Math.round(paperScore)}% Match
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 text-sm text-gray-500 mb-3">
          <span className="flex items-center gap-1"><Calendar size={14} /> {paperYear}</span>
          {paperAuthors.length > 0 && (
            <span className="flex items-center gap-1 text-xs truncate max-w-xs">
              <Users size={12} /> {paperAuthors.slice(0, 2).join(', ')}{paperAuthors.length > 2 ? ' et al.' : ''}
            </span>
          )}
        </div>

        {matchedKeywords.length > 0 && (
          <div className="mb-4 bg-gray-50 border border-gray-200 rounded-lg p-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-700 mb-2">
               <HelpCircle size={14} /> Why this paper?
            </div>
            <div className="flex flex-wrap gap-1.5 pt-1">
              <span className="text-xs text-gray-500 mr-1 flex items-center">Matched:</span>
              {matchedKeywords.map((kw, i) => (
                <span key={i} className="inline-flex items-center gap-1 bg-white border border-gray-200 text-gray-700 text-[10px] font-medium px-2 py-0.5 rounded transition-colors hover:bg-gray-50 cursor-pointer">
                  <Tag size={10} /> {kw}
                </span>
              ))}
            </div>
            {paper.llm_reason && (
              <p className="mt-2 text-xs text-emerald-800 italic leading-relaxed">
                {paper.llm_reason}
              </p>
            )}
          </div>
        )}

        <div className="relative flex-grow">
           <div className="absolute -left-2 top-0 bottom-0 w-0.5 bg-slate-100"></div>
           <p className="text-slate-600 leading-relaxed text-sm pl-3">
             {shortAbstract || 'No abstract available.'}
           </p>
        </div>

        <div className="flex items-center gap-3 mt-5 pt-4 border-t border-gray-100">
          {/* Paper links */}
          <div className="flex gap-3">
            {paperArxivUrl && (
              <a href={paperArxivUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors">
                <ExternalLink size={14} /> arXiv
              </a>
            )}
            {paperPdfUrl && (
              <a href={paperPdfUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-gray-500 hover:text-gray-800 transition-colors">
                <FileDown size={14} /> PDF
              </a>
            )}
          </div>
          
          {/* AI Action Buttons */}
          {onAnalyze && paper.id && (
            <div className="flex gap-2 ml-auto">
              <button
                onClick={() => onAnalyze(paper)}
                className="inline-flex items-center gap-1 text-xs font-medium bg-amber-50 text-amber-700 hover:bg-amber-100 px-2.5 py-1.5 rounded-lg transition-colors cursor-pointer"
                title="Explain Simply"
              >
                <Brain size={12} /> Explain
              </button>
            </div>
          )}
        </div>
      </div>
    );
  };

  // --- RENDERING BASED ON PURPOSE ---

  // Quick Overview -> Grid of cards
  if (mode === 'quick overview') {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4">
        {papers.map((paper, i) => renderPaper(paper, true))}
      </div>
    );
  }

  // Literature Review -> Grouped by year
  if (mode === 'literature review') {
    // Group papers
    const byYear = {};
    papers.forEach(p => {
      const y = p.year || 'Unknown';
      if (!byYear[y]) byYear[y] = [];
      byYear[y].append ? byYear[y].push(p) : byYear[y].push(p);
    });
    
    return (
      <div className="space-y-8">
        {Object.keys(byYear).sort((a,b) => b - a).map(year => (
          <div key={year} className="relative">
            <div className="sticky top-0 bg-slate-50 border-y border-slate-200 py-2 px-4 mb-4 z-10 flex items-center gap-2 text-slate-800 font-bold rounded shadow-sm">
              <Calendar size={18} className="text-blue-500" /> year {year}
            </div>
            <div className="space-y-4 pl-4 border-l-2 border-slate-100 ml-4">
              {byYear[year].map((p, i) => renderPaper(p, false))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Default: Deep Dive -> List
  return (
    <div className="space-y-5">
      {papers.map((paper, i) => renderPaper(paper, false))}
    </div>
  );
}
