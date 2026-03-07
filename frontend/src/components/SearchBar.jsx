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
        className={`flex items-center bg-white border border-gray-200 rounded-2xl shadow-sm transition-all duration-300 focus-within:ring-4 focus-within:ring-blue-100 focus-within:border-blue-500 hover:shadow-md ${
          isLarge ? 'p-2' : 'p-1.5'
        }`}
      >
        <div className={`px-4 text-gray-400 group-focus-within:text-blue-500 transition-colors ${isLarge ? '' : 'scale-90'}`}>
          <Search size={22} strokeWidth={2.5} />
        </div>
        
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search research topics (e.g., AI, Quantum Computing)"
          className={`flex-1 bg-transparent border-none outline-none font-medium text-slate-900 placeholder-slate-400 w-full ${
            isLarge ? 'text-lg py-3' : 'text-base py-2'
          }`}
        />
        
        <button
          type="submit"
          disabled={!query.trim()}
          className={`ml-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-colors disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed flex items-center justify-center ${
            isLarge ? 'h-12 w-12' : 'h-10 w-10 shrink-0'
          }`}
        >
          <ArrowRight size={20} />
        </button>
      </div>
    </form>
  );
}
