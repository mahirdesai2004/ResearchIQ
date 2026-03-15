import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import SearchBar from '../components/SearchBar';
import PaperList from '../components/PaperList';
import Chart from '../components/Chart';
import { researchQuery, getKeywordTrend } from '../services/api';
import { Activity, SlidersHorizontal } from 'lucide-react';

export default function ResultsPage() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  
  const [papers, setPapers] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loadingPapers, setLoadingPapers] = useState(true);
  
  const [trendData, setTrendData] = useState([]);
  const [loadingTrend, setLoadingTrend] = useState(true);

  // User controls
  const [purpose, setPurpose] = useState('deep dive');
  const [numPapers, setNumPapers] = useState(20);

  // Related keywords from deep dive
  const [relatedKeywords, setRelatedKeywords] = useState([]);

  useEffect(() => {
    async function fetchData() {
      if (!query) return;
      
      setLoadingPapers(true);
      setLoadingTrend(true);
      setPapers([]);
      setRelatedKeywords([]);
      
      // Fetch papers via /research/query
      try {
        const res = await researchQuery({
          topic: query,
          purpose: purpose,
          num_papers: numPapers,
        });
        
        setPapers(res.papers || []);
        setTotalCount(res.count || 0);
        
        if (res.related_keywords) {
          setRelatedKeywords(res.related_keywords);
        }
      } catch (err) {
        console.error("Error fetching research query:", err);
        setPapers([]);
        setTotalCount(0);
      } finally {
        setLoadingPapers(false);
      }
      
      // Fetch keyword trend separately
      try {
        const trendRes = await getKeywordTrend(query);
        if (trendRes.yearly_counts) {
          const trendsArray = Object.entries(trendRes.yearly_counts).map(([year, count]) => ({
            year: String(year),
            count
          }));
          setTrendData(trendsArray);
        } else {
          setTrendData([]);
        }
      } catch (err) {
        console.error("Error fetching trend:", err);
        setTrendData([]);
      } finally {
        setLoadingTrend(false);
      }
    }
    
    fetchData();
  }, [query, purpose, numPapers]);

  return (
    <div className="w-full max-w-6xl mx-auto animate-fade-in">
      {/* Top Search Area */}
      <div className="mb-6 pb-6 border-b border-gray-200">
        <SearchBar initialQuery={query} sizes="small" className="!max-w-3xl !mx-0" />
      </div>

      {/* Controls Bar */}
      <div className="mb-8 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={16} className="text-slate-400" />
          <span className="text-sm font-medium text-slate-500">Purpose:</span>
        </div>
        <select
          value={purpose}
          onChange={(e) => setPurpose(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-slate-700 focus:ring-2 focus:ring-blue-100 focus:border-blue-500 outline-none"
        >
          <option value="deep dive">Deep Dive</option>
          <option value="literature review">Literature Review</option>
          <option value="quick overview">Quick Overview</option>
        </select>

        <div className="flex items-center gap-2 ml-2">
          <span className="text-sm font-medium text-slate-500">Papers:</span>
        </div>
        <select
          value={numPapers}
          onChange={(e) => setNumPapers(Number(e.target.value))}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-slate-700 focus:ring-2 focus:ring-blue-100 focus:border-blue-500 outline-none"
        >
          <option value={10}>10</option>
          <option value={20}>20</option>
          <option value={50}>50</option>
        </select>
      </div>

      {!query ? (
        <div className="text-center py-20 text-slate-500 text-lg">
          Please enter a search term to view results.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Main Content Area (Papers) */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-semibold text-slate-900">
                Results for "{query}"
              </h2>
              {!loadingPapers && (
                <span className="bg-blue-50 text-blue-700 text-sm font-medium px-3 py-1 rounded-full">
                  {totalCount} matches
                </span>
              )}
            </div>
            
            <PaperList 
              papers={papers} 
              loading={loadingPapers} 
              emptyMessage="No results found. Try another query." 
            />
          </div>

          {/* Sidebar Area */}
          <div className="lg:col-span-1 space-y-6">
            {/* Keyword Trend Chart */}
            <div className="bg-slate-50 border border-gray-200 rounded-xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <Activity size={20} className="text-blue-600" />
                <h3 className="font-semibold text-slate-800">Keyword Trend</h3>
              </div>
              <p className="text-sm text-slate-500 mb-6">
                Publication frequency over time for this topic.
              </p>
              
              {loadingTrend ? (
                <div className="h-48 w-full bg-slate-200 animate-pulse rounded-lg"></div>
              ) : trendData.length > 0 ? (
                <Chart 
                  data={trendData} 
                  dataKey="count" 
                  xAxisKey="year" 
                  color="#3b82f6" 
                />
              ) : (
                <div className="h-48 flex items-center justify-center text-sm text-slate-400 bg-white border border-gray-100 rounded-lg">
                  Not enough data for trend
                </div>
              )}
            </div>

            {/* Related Keywords (from deep dive) */}
            {relatedKeywords.length > 0 && (
              <div className="bg-slate-50 border border-gray-200 rounded-xl p-6">
                <h3 className="font-semibold text-slate-800 mb-3">Related Keywords</h3>
                <div className="flex flex-wrap gap-2">
                  {relatedKeywords.map((kw, i) => (
                    <span key={i} className="bg-blue-50 text-blue-700 text-xs font-medium px-2.5 py-1 rounded-full">
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
          
        </div>
      )}
    </div>
  );
}
