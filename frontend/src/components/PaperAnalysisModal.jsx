import { useState, useEffect } from 'react';
import { X, Loader2, Brain, AlertCircle } from 'lucide-react';
import { analyzePaper } from '../services/api';

export default function PaperAnalysisModal({ paper, onClose }) {
  const [explanation, setExplanation] = useState("");
  const [gaps, setGaps] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!paper) return;
    fetchAnalysis();
  }, [paper]);

  const fetchAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await analyzePaper(paper.id);
      const resultText = res.result || "";
      
      // Split the response to separate Explanation from Research Gaps
      const parts = resultText.split("Research Gap:");
      
      let expText = parts[0]?.replace("Explanation:", "").trim();
      setExplanation(expText || "No explanation provided.");
      
      if (parts[1]) {
        const parsedGaps = parts[1]
          .split("-")
          .map(g => g.trim())
          .filter(Boolean);
        setGaps(parsedGaps);
      } else {
        setGaps([]);
      }
    } catch (err) {
      setError('Failed to generate analysis.');
    } finally {
      setLoading(false);
    }
  };

  if (!paper) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-start justify-between gap-4 bg-gray-50/50">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 leading-tight pr-8">{paper.title}</h3>
            <p className="text-sm text-gray-500 mt-1">{paper.year} · AI Paper Analysis</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors cursor-pointer flex-shrink-0 mt-1 bg-white rounded-full p-1 shadow-sm border border-gray-100">
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto flex-1">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400">
              <Loader2 size={36} className="animate-spin mb-4 text-amber-500" />
              <p className="text-sm font-medium text-gray-600">Analyzing paper for non-technical readers...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 text-red-400">
              <AlertCircle size={32} className="mb-3" />
              <p className="text-sm">{error}</p>
            </div>
          ) : (
            <div className="space-y-8 animate-in fade-in duration-300">
              {/* Explanation Section */}
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <div className="p-1.5 bg-amber-100 text-amber-700 rounded-md">
                    <Brain size={18} />
                  </div>
                  <h4 className="text-md font-semibold text-gray-900">Simple Explanation</h4>
                </div>
                <div className="bg-gray-50 rounded-xl p-5 border border-gray-100">
                  <p className="text-gray-700 leading-relaxed whitespace-pre-line text-sm md:text-base">
                    {explanation}
                  </p>
                </div>
              </section>

              {/* Research Gaps Section */}
              {gaps.length > 0 && (
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="p-1.5 bg-red-100 text-red-700 rounded-md">
                      <AlertCircle size={18} />
                    </div>
                    <h4 className="text-md font-semibold text-gray-900">Identified Research Gaps</h4>
                  </div>
                  <ul className="space-y-3">
                    {gaps.map((gap, i) => (
                      <li key={i} className="flex gap-3 bg-white border border-gray-100 p-4 rounded-xl shadow-sm">
                        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-red-50 text-red-600 flex items-center justify-center text-xs font-bold leading-none mt-0.5">
                          {i + 1}
                        </span>
                        <p className="text-sm text-gray-700 leading-relaxed">
                          {gap}
                        </p>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
