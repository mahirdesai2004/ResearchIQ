import { useState, useEffect } from 'react';
import { Sparkles, Compass, Bookmark, ExternalLink, FileDown, Activity, ChevronRight, RefreshCw, ThumbsDown } from 'lucide-react';
import { getPersonalizedRecommendations, logUserInteraction } from '../services/api';

export default function RecommendedFeed({ currentTopic = '', onAnalyze }) {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all'); // 'all', 'exploit', 'explore'
  const [feedbackGiven, setFeedbackGiven] = useState({});

  const getSessionId = () => {
    let s = localStorage.getItem('researchiq_session_id');
    if (!s) {
      s = 'session_' + Math.random().toString(36).substring(2, 9);
      localStorage.setItem('researchiq_session_id', s);
    }
    return s;
  };

  const loadRecommendations = async () => {
    setLoading(true);
    try {
      const sId = getSessionId();
      const res = await getPersonalizedRecommendations(sId, currentTopic, 10, false);
      setRecommendations(res.recommendations || []);
    } catch (err) {
      console.warn('Failed to fetch personalized recommendations:', err);
      setRecommendations([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRecommendations();
  }, [currentTopic]);

  const handleAction = async (paper, action) => {
    const sId = getSessionId();
    setFeedbackGiven(prev => ({ ...prev, [paper.id]: action }));
    await logUserInteraction(sId, paper.id, action, currentTopic);
    // Reload after a short delay so the LinUCB update reflects in order
    setTimeout(loadRecommendations, 600);
  };

  const filteredRecs = recommendations.filter(p => {
    if (activeTab === 'exploit') return p.rec_type === 'exploitation';
    if (activeTab === 'explore') return p.rec_type === 'exploration';
    return true;
  });

  return (
    <div className="glass-card p-6 border-purple-100 bg-gradient-to-br from-white via-purple-50/20 to-orange-50/20 rounded-2xl shadow-sm mb-8 animate-slide-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 border-b border-purple-100/60 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-gradient-to-br from-purple-600 to-indigo-600 rounded-lg text-white shadow-sm">
              <Sparkles size={18} />
            </div>
            <h2 className="text-lg font-bold text-gray-900 tracking-tight">
              Recommended for You
            </h2>
            <span className="bg-purple-100 text-purple-700 text-[11px] font-semibold px-2 py-0.5 rounded-full border border-purple-200">
              LinUCB RL Agent
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Adapts in real-time as you save, read, and explore research papers
          </p>
        </div>

        {/* Tab Controls + Refresh */}
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <div className="flex bg-slate-100 p-0.5 rounded-lg text-xs font-medium text-slate-600 border border-slate-200">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-2.5 py-1 rounded-md transition-colors ${activeTab === 'all' ? 'bg-white text-slate-900 shadow-xs font-semibold' : 'hover:text-slate-900'}`}
            >
              All
            </button>
            <button
              onClick={() => setActiveTab('exploit')}
              className={`px-2.5 py-1 rounded-md transition-colors flex items-center gap-1 ${activeTab === 'exploit' ? 'bg-white text-emerald-800 shadow-xs font-semibold' : 'hover:text-slate-900'}`}
              title="Exploitation: Matches your saved preference topics"
            >
              🎯 Matched
            </button>
            <button
              onClick={() => setActiveTab('explore')}
              className={`px-2.5 py-1 rounded-md transition-colors flex items-center gap-1 ${activeTab === 'explore' ? 'bg-white text-purple-800 shadow-xs font-semibold' : 'hover:text-slate-900'}`}
              title="Exploration: Novel papers from adjacent fields"
            >
              🔭 Novel
            </button>
          </div>

          <button
            onClick={loadRecommendations}
            className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
            title="Refresh Recommendations"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="p-4 bg-white/70 rounded-xl border border-slate-100 animate-pulse space-y-2">
              <div className="h-4 bg-slate-200 rounded w-3/4"></div>
              <div className="h-3 bg-slate-100 rounded w-1/2"></div>
              <div className="h-3 bg-slate-100 rounded w-full"></div>
            </div>
          ))}
        </div>
      ) : filteredRecs.length === 0 ? (
        <div className="text-center py-8 text-xs text-slate-400">
          No recommendations under this filter. Save or interact with papers to train your agent.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {filteredRecs.map(paper => {
            const isExploit = paper.rec_type === 'exploitation';
            const feedback = feedbackGiven[paper.id];

            return (
              <div
                key={paper.id}
                className="bg-white/90 backdrop-blur-xs border border-slate-200/80 hover:border-purple-300 hover:shadow-md transition-all duration-200 rounded-xl p-4 flex flex-col justify-between"
              >
                <div>
                  {/* Badge & UCB score */}
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span
                      className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                        isExploit
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-purple-50 text-purple-700 border-purple-200'
                      }`}
                    >
                      {isExploit ? '🎯 Focus Match' : '🔭 Serendipity Pick'}
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono" title="Upper Confidence Bound Score">
                      UCB {paper.ucb_score?.toFixed(2) || '0.00'}
                    </span>
                  </div>

                  {/* Title */}
                  <h3 className="text-sm font-bold text-slate-900 leading-snug line-clamp-2 hover:text-purple-700 transition-colors">
                    {paper.title}
                  </h3>

                  {/* Rationale */}
                  <p className="text-[11px] text-slate-500 mt-1 italic line-clamp-1">
                    {paper.rec_reason}
                  </p>

                  {/* Abstract Snippet */}
                  {paper.abstract && (
                    <p className="text-xs text-slate-600 mt-2 line-clamp-2 leading-relaxed">
                      {paper.abstract}
                    </p>
                  )}
                </div>

                {/* Footer Controls */}
                <div className="flex items-center justify-between gap-2 mt-3 pt-3 border-t border-slate-100 text-xs">
                  <div className="flex items-center gap-2 text-slate-400">
                    <span>{paper.year}</span>
                    {paper.citation_count > 0 && <span>• {paper.citation_count} cites</span>}
                  </div>

                  <div className="flex items-center gap-1.5">
                    {paper.pdf_url && (
                      <a
                        href={paper.pdf_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={() => handleAction(paper, 'pdf_click')}
                        className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-orange-600 hover:bg-orange-50 rounded-md transition-colors"
                      >
                        <FileDown size={11} /> PDF
                      </a>
                    )}

                    <button
                      onClick={() => handleAction(paper, 'bookmark')}
                      className={`inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded-md transition-colors border cursor-pointer ${
                        feedback === 'bookmark'
                          ? 'bg-amber-100 text-amber-800 border-amber-300'
                          : 'bg-slate-50 text-slate-600 hover:bg-amber-50 hover:text-amber-700 border-slate-200'
                      }`}
                      title="Save to your reading list (+5 reward)"
                    >
                      <Bookmark size={11} />
                      {feedback === 'bookmark' ? 'Saved' : 'Save'}
                    </button>

                    <button
                      onClick={() => handleAction(paper, 'dismiss')}
                      className={`p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors border border-slate-200 cursor-pointer ${
                        feedback === 'dismiss' ? 'text-rose-600 bg-rose-50' : ''
                      }`}
                      title="Not relevant (-3 penalty)"
                    >
                      <ThumbsDown size={11} />
                    </button>

                    {onAnalyze && (
                      <button
                        onClick={() => onAnalyze(paper)}
                        className="px-2 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
                      >
                        Explain
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
