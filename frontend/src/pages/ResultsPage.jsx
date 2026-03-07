import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import SearchBar from '../components/SearchBar';
import PaperList from '../components/PaperList';
import Chart from '../components/Chart';
import { filterPapers, getKeywordTrend } from '../services/api';
import { Activity } from 'lucide-react';

export default function ResultsPage() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  
  const [papers, setPapers] = useState([]);
  const [loadingPapers, setLoadingPapers] = useState(true);
  
  const [trendData, setTrendData] = useState([]);
  const [loadingTrend, setLoadingTrend] = useState(true);

  useEffect(() => {
    async function fetchData() {
      if (!query) return;
      
      setLoadingPapers(true);
      setLoadingTrend(true);
      
      try {
        const [papersRes, trendRes] = await Promise.all([
          filterPapers({ keyword: query }),
          getKeywordTrend(query)
        ]);
        
        setPapers(papersRes.papers || []);
        
        // Convert trend dictionary to array for Recharts
        if (trendRes.yearly_counts) {
          const trendsArray = Object.entries(trendRes.yearly_counts).map(([year, count]) => ({
            year,
            count
          }));
          setTrendData(trendsArray);
        }
      } catch (err) {
        console.error("Error fetching results:", err);
      } finally {
        setLoadingPapers(false);
        setLoadingTrend(false);
      }
    }
    
    fetchData();
  }, [query]);

  return (
    <div className="w-full max-w-6xl mx-auto animate-fade-in">
      {/* Top Search Area */}
      <div className="mb-10 pb-6 border-b border-gray-200">
        <SearchBar initialQuery={query} sizes="small" className="!max-w-3xl !mx-0" />
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
                Search Results for "{query}"
              </h2>
              {!loadingPapers && (
                <span className="bg-blue-50 text-blue-700 text-sm font-medium px-3 py-1 rounded-full">
                  {papers.length} matches
                </span>
              )}
            </div>
            
            <PaperList 
              papers={papers} 
              loading={loadingPapers} 
              emptyMessage={`We couldn't find any papers matching "${query}". Try adjusting your keywords.`} 
            />
          </div>

          {/* Sidebar Area (Charts/Trends) */}
          <div className="lg:col-span-1 space-y-6">
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
                  Not enough data for chart
                </div>
              )}
            </div>
          </div>
          
        </div>
      )}
    </div>
  );
}
