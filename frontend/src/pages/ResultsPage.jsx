import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import SearchBar from '../components/SearchBar';
import PaperList from '../components/PaperList';
import Chart from '../components/Chart';
import ChatPanel from '../components/ChatPanel';
import PaperAnalysisModal from '../components/PaperAnalysisModal';
import BackgroundParticles from '../components/BackgroundParticles';
import { 
  researchQuery, 
  getKeywordTrend, 
  getLiteratureReview, 
  getTrendExplanation, 
  getGapDetection,
  getAnalysis
} from '../services/api';
import { 
  Activity, 
  SlidersHorizontal, 
  BookOpen, 
  Lightbulb, 
  Target, 
  Download,
  AlertCircle,
  Loader2,
  ThumbsUp,
  ThumbsDown
} from 'lucide-react';

export default function ResultsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  
  const [papers, setPapers] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loadingPapers, setLoadingPapers] = useState(true);
  
  const [trendData, setTrendData] = useState([]);
  const [loadingTrend, setLoadingTrend] = useState(true);
  
  // Dashboard Intelligence State
  const [analysisSummary, setAnalysisSummary] = useState(null);
  const [analyzingSummary, setAnalyzingSummary] = useState(false);
  
  const [reviewData, setReviewData] = useState(null);
  const [loadingReview, setLoadingReview] = useState(true);
  
  const [gapData, setGapData] = useState(null);
  const [loadingGaps, setLoadingGaps] = useState(true);
  
  const [trendExplanation, setTrendExplanation] = useState(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);

  // User controls
  const [purpose, setPurpose] = useState('deep dive');
  const [numPapers, setNumPapers] = useState(20);

  // Paper analysis modal
  const [analysisPaper, setAnalysisPaper] = useState(null);

  // LLM gap sentences from analysis
  const [gapSentences, setGapSentences] = useState([]);

  const handleAnalyzePaper = (paper) => {
    setAnalysisPaper(paper);
  };

  const handleSearchTrigger = () => {
    // If the query is essentially the same, just re-fetch the data.
    // We do this by artificially triggering the effect (handled by states changing if any, but since query doesn't change, we just refetch)
    // Actually, setting searchParams will trigger a re-render and if query is same, nothing happens.
    // We will just force a fetch by calling the same logic inside useEffect manually, but the cleanest way is a trigger state.
    setSearchTrigger(prev => prev + 1);
  };

  const [searchTrigger, setSearchTrigger] = useState(0);

  useEffect(() => {
    async function fetchData() {
      if (!query) return;
      
      setLoadingPapers(true);
      setLoadingTrend(true);
      setLoadingReview(true);
      setLoadingGaps(true);
      
      setPapers([]);
      setTrendExplanation(null);
      
      // 1. Fetch main papers via /research/query
      let fetchedPapers = [];
      try {
        const res = await researchQuery({
          topic: query,
          purpose: purpose,
          num_papers: numPapers,
        });
        
        fetchedPapers = res.papers || [];
        setPapers(fetchedPapers);
        setTotalCount(res.count || 0);
        
        // Step 2 of Async: If we have papers, start deep analysis
        if (fetchedPapers.length > 0) {
          setAnalyzingSummary(true);
          const pIds = fetchedPapers.slice(0, 10).map(p => p.id);
          // Wait 1 second mostly for UX smoothness then fire the heavyweight LLM analysis
          setTimeout(() => {
            getAnalysis(query, purpose, pIds)
              .then(analysisRes => {
                setAnalysisSummary(analysisRes.summary);
                if (analysisRes.gaps && Array.isArray(analysisRes.gaps)) {
                  setGapSentences(analysisRes.gaps);
                }
              })
              .catch(err => {
                console.error("Analysis summary failed:", err);
                setAnalysisSummary("Analysis could not be generated.");
              })
              .finally(() => setAnalyzingSummary(false));
          }, 1000);
        } else {
          setAnalysisSummary(null);
          setGapSentences([]);
        }
      } catch (err) {
        console.error("Error fetching research query:", err);
      } finally {
        setLoadingPapers(false);
      }
      
      // 2. Fetch keyword trend
      try {
        const trendRes = await getKeywordTrend(query);
        if (Array.isArray(trendRes) && trendRes.length >= 3) {
          // It's already an array of {year, count} formatted properly
          setTrendData(trendRes.map(item => ({...item, year: String(item.year)})));
        } else {
          // Empty or contains {"message": "Not enough data"}
          setTrendData([]);
        }
      } catch (err) {
        console.error("Error fetching trend:", err);
        setTrendData([]);
      } finally {
        setLoadingTrend(false);
      }

      // 3. Fetch Literature Review
      try {
        const reviewRes = await getLiteratureReview(query);
        setReviewData(reviewRes);
      } catch (err) {
        console.error("Error fetching review:", err);
        setReviewData(null);
      } finally {
        setLoadingReview(false);
      }

      // 4. Fetch Gap Detection
      try {
        const gapRes = await getGapDetection(query);
        setGapData(gapRes);
      } catch (err) {
        console.error("Error fetching gaps:", err);
        setGapData(null);
      } finally {
        setLoadingGaps(false);
      }
    }
    
    fetchData();
  }, [query, searchTrigger]);

  const handleChartClick = async (event) => {
    if (event && event.activeLabel) {
      setLoadingExplanation(true);
      try {
        // Find explanation for the specific keyword
        const expRes = await getTrendExplanation(query);
        setTrendExplanation(expRes.explanation);
      } catch (err) {
        setTrendExplanation("Could not load explanation.");
      } finally {
        setLoadingExplanation(false);
      }
    }
  };

  const handleGapClick = (keyword) => {
    setSearchParams({ q: keyword });
  };

  const triggerCSVDownload = async (url, filename) => {
    try {
      const res = await fetch(url);
      const data = await res.json();
      
      if (!data || data.length === 0) {
        alert("No data available to export");
        return;
      }

      const headers = Object.keys(data[0]);
      const csvContent = [
        headers.join(','),
        ...data.map(row => 
          headers.map(header => {
            let val = row[header];
            if (val === null || val === undefined) val = "";
            val = String(val).replace(/"/g, '""');
            if (val.includes(',') || val.includes('"') || val.includes('\n')) {
              val = `"${val}"`;
            }
            return val;
          }).join(',')
        )
      ].join('\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement("a");
      const objUrl = URL.createObjectURL(blob);
      link.href = objUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (e) {
      console.error(e);
      alert("Failed to download CSV");
    }
  };

  // gapChartData is removed since gaps are now full sentences rendered directly

  return (
    <div className="relative min-h-screen w-full font-sans">
      <BackgroundParticles />
      <div className="w-full max-w-7xl mx-auto animate-fade-in p-4 xl:p-0 mb-10 relative z-10">
      
      {/* Top Search & Controls Area */}
      <div className="mb-8 pt-6 pb-6 border-b border-orange-100">
        <h1 className="text-3xl md:text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-orange-500 via-rose-500 to-purple-600 animate-gradient-x tracking-tight mb-2">
          Research Dashboard
        </h1>
        <p className="text-slate-500 text-sm font-medium mb-6">
          Contextualized from a diverse global corpus of <span className="text-orange-600 font-bold">~200M+ publications</span>
        </p>
        
        <div className="flex flex-col lg:flex-row gap-6 items-start lg:items-center">
          <div className="flex-1 w-full lg:max-w-xl">
            <SearchBar initialQuery={query} sizes="medium" className="!m-0" />
          </div>
          
          <div className="flex flex-wrap items-center gap-4 bg-gray-50 p-2.5 rounded-lg border border-gray-200">
            <div className="flex items-center gap-2 px-2">
              <SlidersHorizontal size={16} className="text-gray-500" />
              <span className="text-sm font-medium text-gray-700">Purpose:</span>
            </div>
            <select
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              className="text-sm font-medium border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-700 focus:ring-2 focus:ring-orange-100 focus:border-orange-500 outline-none transition-colors cursor-pointer"
            >
              <option value="deep dive">Deep Dive</option>
              <option value="literature review">Literature Review</option>
              <option value="quick overview">Quick Overview</option>
            </select>

            <div className="flex items-center gap-2 ml-2">
              <span className="text-sm font-medium text-gray-700">Papers:</span>
            </div>
            <select
              value={numPapers}
              onChange={(e) => setNumPapers(Number(e.target.value))}
              className="text-sm font-medium border border-gray-300 rounded-md px-3 py-1.5 bg-white text-gray-700 focus:ring-2 focus:ring-orange-100 focus:border-orange-500 outline-none transition-colors cursor-pointer"
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
            
            <button 
              onClick={handleSearchTrigger}
              className="ml-auto lg:ml-4 bg-gradient-to-r from-orange-500 to-rose-500 hover:from-orange-600 hover:to-rose-600 text-white font-medium py-1.5 px-6 rounded-md transition-all duration-300 shadow-md hover:shadow-lg hover:-translate-y-0.5 cursor-pointer"
            >
              Analyze
            </button>
          </div>
        </div>
      </div>

      {!query ? (
        <div className="text-center py-32 text-slate-500 text-lg flex flex-col items-center">
          <SearchIcon size={48} className="text-slate-300 mb-4" />
          <p>Please enter a domain or topic to generate your dashboard.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Column (8 cols): Literature Review & Top Papers */}
          <div className="lg:col-span-8 space-y-8">
            
            {/* SECTION 1: LLM Executive Summary */}
            {analyzingSummary || analysisSummary ? (
              <div className="glass-card p-6 mb-8 animate-slide-up">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 bg-orange-50 rounded text-orange-600">
                    <Activity size={20} className={analyzingSummary ? "animate-spin" : ""} />
                  </div>
                  <h2 className="text-lg font-bold text-gray-900 tracking-tight">
                    {analyzingSummary ? "Analyzing research trends..." : "Executive Summary"}
                  </h2>
                </div>
                {analyzingSummary ? (
                  <div className="space-y-3 animate-pulse">
                    <div className="h-4 bg-orange-200/50 rounded w-full"></div>
                    <div className="h-4 bg-orange-200/50 rounded w-5/6"></div>
                    <div className="h-4 bg-orange-200/50 rounded w-3/4"></div>
                  </div>
                ) : (
                  <div>
                    <p className="text-gray-700 leading-relaxed text-sm mb-4">
                      {analysisSummary}
                    </p>
                    <div className="flex items-center gap-3 border-t border-orange-100 pt-3">
                      <span className="text-xs text-gray-500 font-medium">Was this AI summary helpful?</span>
                      <button className="text-gray-400 hover:text-emerald-500 transition-colors" title="Train Model"><ThumbsUp size={16}/></button>
                      <button className="text-gray-400 hover:text-rose-500 transition-colors" title="Train Model"><ThumbsDown size={16}/></button>
                    </div>
                  </div>
                )}
              </div>
            ) : null}

            {/* SECTION 4: Top Papers */}
            <div>
              <div className="flex items-center justify-between mb-4 mt-2">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 tracking-tight">
                  Top Papers <span className="bg-gray-100 text-gray-700 text-xs font-medium px-2 py-0.5 rounded">{totalCount}</span>
                </h2>
              </div>
              <PaperList 
                papers={papers} 
                loading={loadingPapers} 
                mode={purpose}
                emptyMessage="No relevant papers found for this strict query domain."
                onAnalyze={handleAnalyzePaper}
              />
            </div>
          </div>

          {/* Right Column (4 cols): Trends, Gaps, Export */}
          <div className="lg:col-span-4 space-y-8">
            
            {/* SECTION 5: Export Data Panel */}
            <div className="glass-card p-6 animate-slide-up delay-100">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-rose-50 rounded text-rose-600">
                  <Target size={20} />
                </div>
                <h2 className="text-lg font-bold text-gray-900 tracking-tight">Export Data</h2>
              </div>
              <p className="text-gray-500 text-sm mb-6 leading-relaxed">
                Download structured datasets to use in tools like Tableau or Excel for deeper analysis, custom dashboards, and reporting.
              </p>
              
              <div className="space-y-3">
                <button 
                  onClick={() => triggerCSVDownload(`http://127.0.0.1:8000/export/tableau-data?domain=${encodeURIComponent(query)}`, "researchIQ_papers.csv")}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-slate-800 to-slate-900 text-white hover:from-slate-700 hover:to-slate-800 py-2.5 px-4 rounded-md font-medium transition-all duration-300 hover:shadow-lg cursor-pointer shadow-sm hover:-translate-y-0.5"
                >
                  <Download size={16} />
                  Raw Data (All Papers)
                </button>
                <button
                  onClick={() => triggerCSVDownload(`http://127.0.0.1:8000/export/tableau-aggregates`, "researchIQ_aggregates.csv")}
                  className="w-full flex items-center justify-center gap-2 bg-white text-gray-700 border border-gray-300 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200 py-2 px-4 rounded-md font-medium transition-all duration-300 cursor-pointer shadow-sm hover:-translate-y-0.5"
                >
                  <Download size={16} />
                  Processed Data (Trends & Counts)
                </button>
              </div>
            </div>

            {/* SECTION 2: Analytics Visualizations */}
            <div className="glass-card p-6 animate-slide-up delay-200">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-purple-50 rounded text-purple-600">
                  <Activity size={20} />
                </div>
                <h3 className="text-lg font-bold text-gray-900 tracking-tight">Data Analytics</h3>
              </div>
              <p className="text-sm text-gray-500 mb-6">Explore publication trends and data sources</p>
              
              <div className="space-y-8">
                {/* Chart 1: Trend */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-3">Publication Trend</h4>
                  {loadingTrend ? (
                    <div className="h-48 w-full bg-purple-50/50 animate-pulse rounded-xl"></div>
                  ) : trendData.length > 0 ? (
                    <div>
                      <Chart 
                        data={trendData} 
                        dataKey="count" 
                        xAxisKey="year" 
                        color="#a855f7" 
                        onClick={handleChartClick}
                      />
                      {loadingExplanation ? (
                        <div className="text-sm text-purple-400 mt-4 animate-pulse">Analyzing trend spike...</div>
                      ) : trendExplanation ? (
                        <div className="mt-4 p-3 bg-purple-50 border border-purple-100 rounded-lg text-sm text-purple-800 animate-slide-up">
                          <strong>Insight:</strong> {trendExplanation}
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="h-24 flex items-center justify-center text-sm text-purple-400/70 bg-purple-50/50 border border-dashed border-purple-200 rounded-xl">
                      Trend Timeline unavailable for this corpus
                    </div>
                  )}
                </div>

                {/* Chart 2: Top Research Gaps Addressed (Sentence Form) */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-3">Top Research Gaps Addressed</h4>
                  {gapData?.gaps?.length > 0 ? (
                    <div className="flex flex-col gap-3">
                      {gapData.gaps.map((gapStr, idx) => (
                        <div key={idx} className="bg-orange-50/50 p-3 rounded-xl border border-orange-100 text-sm text-slate-700 flex items-start gap-2 shadow-sm">
                          <Target className="w-4 h-4 text-orange-500 mt-0.5 shrink-0" />
                          <p>{gapStr}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="h-24 flex items-center justify-center text-sm text-orange-400/70 bg-orange-50/50 border border-dashed border-orange-200 rounded-xl">
                      Gap frequency metrics unavailable
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* SECTION 3: Research Gaps (LLM Sentences) */}
            <div className="glass-card p-6 animate-slide-up delay-300 mb-8 lg:mb-0">
              <div className="flex items-center gap-3 mb-4">
                 <div className="p-2 bg-emerald-50 rounded text-emerald-600">
                  <Lightbulb size={20} />
                </div>
                <h3 className="text-lg font-bold text-gray-900 tracking-tight">Research Gaps</h3>
              </div>
              <p className="text-sm text-gray-500 mb-4">
                AI-identified gaps and underexplored areas in this domain.
              </p>
              
              {gapSentences.length > 0 ? (
                <ul className="space-y-3">
                  {gapSentences.map((gap, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700 leading-relaxed">
                      <span className="flex-shrink-0 w-5 h-5 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center text-[10px] font-bold mt-0.5">{i + 1}</span>
                      {gap}
                    </li>
                  ))}
                </ul>
              ) : loadingGaps ? (
                <div className="space-y-2 animate-pulse">
                  {[1,2,3].map(n => <div key={n} className="h-4 bg-slate-100 rounded w-full" />)}
                </div>
              ) : gapData?.gaps?.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {gapData.gaps.map((g, i) => (
                    <button 
                      key={i} 
                      onClick={() => handleGapClick(g.keyword)}
                      className="group flex items-center gap-2 bg-white border border-gray-200 hover:border-gray-300 text-gray-700 text-xs px-3 py-1.5 rounded transition-colors duration-150 cursor-pointer"
                    >
                      <span>{g.keyword}</span>
                      <span className="bg-gray-100 text-gray-600 text-[10px] font-medium px-1.5 py-0.5 rounded group-hover:bg-gray-200 transition-colors">
                        {g.count}
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="h-24 flex items-center justify-center text-sm text-emerald-500/70 bg-emerald-50/50 border border-dashed border-emerald-200 rounded-xl">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    No significant gaps identified
                  </div>
                </div>
              )}
            </div>

          </div>
          
        </div>
      )}

      {/* Chat Panel */}
      {query && <ChatPanel papers={papers} topic={query} />}

      {/* Paper Analysis Modal */}
      {analysisPaper && (
        <PaperAnalysisModal
          paper={analysisPaper}
          onClose={() => setAnalysisPaper(null)}
        />
      )}
      </div>
    </div>
  );
}

// Just adding a quick fallback icon since imported lucide-react might not have SearchIcon mapped exactly to 'SearchIcon' usually it's `Search`
function SearchIcon(props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={props.size||24} height={props.size||24} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={props.className}>
      <circle cx="11" cy="11" r="8"></circle>
      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
    </svg>
  );
}
