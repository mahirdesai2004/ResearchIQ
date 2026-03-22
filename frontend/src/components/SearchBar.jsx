import { useState } from 'react';
import { Search, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function SearchBar({ initialQuery = '', className = '', sizes = 'large' }) {
  const [query, setQuery] = useState(initialQuery);
  const navigate = useNavigate();

  const handleSearch = (e) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/results?q=${encodeURIComponent(query.trim())}`);
    }
  };

  const isLarge = sizes === 'large';

  return (
    <form 
      onSubmit={handleSearch} 
      className={`relative w-full max-w-2xl mx-auto group ${className}`}
    >
      <div 
        className={`flex items-center bg-white border border-gray-200 rounded-lg shadow-sm transition-all duration-150 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-500/10 ${
          isLarge ? 'p-2.5' : 'p-1.5'
        }`}
      >
        <div className={`px-4 text-slate-400 ${isLarge ? '' : 'scale-90'}`}>
          <Search size={22} strokeWidth={2.5} />
        </div>
        
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search research topics (e.g., AI, Quantum Computing)"
          className={`flex-1 bg-transparent border-none outline-none font-medium text-slate-900 placeholder-slate-500 w-full ${
            isLarge ? 'text-lg py-3.5 pl-2' : 'text-base py-2 pl-1'
          }`}
        />
        
        <button
          type="submit"
          disabled={!query.trim()}
          className={`ml-2 bg-slate-900 hover:bg-slate-800 text-white rounded-md transition-colors duration-150 disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed cursor-pointer flex items-center justify-center ${
            isLarge ? 'h-[50px] w-14' : 'h-10 w-10 shrink-0'
          }`}
        >
          <ArrowRight size={20} />
        </button>
      </div>
    </form>
  );
}
