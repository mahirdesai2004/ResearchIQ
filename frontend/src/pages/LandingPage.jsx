import { useState, useEffect } from 'react';
import SearchBar from '../components/SearchBar';
import StatsPanel from '../components/StatsPanel';
import BackgroundParticles from '../components/BackgroundParticles';
import { getSystemStats } from '../services/api';

export default function LandingPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadStats() {
      try {
        const data = await getSystemStats();
        setStats(data);
      } catch (error) {
        console.error("Failed to load system stats", error);
      } finally {
        setLoading(false);
      }
    }
    loadStats();
  }, []);

  return (
    <div className="relative min-h-[75vh]">
      <BackgroundParticles />
      <div className="flex flex-col items-center justify-center min-h-[75vh] w-full animate-fade-in relative z-10">
        <div className="w-full max-w-3xl text-center mb-10">
          <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-6 leading-tight">
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-500 via-rose-500 to-purple-600 animate-gradient-x">
              Explore Research Trends
            </span>
            <span className="block mt-2 text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-orange-500">with AI</span>
          </h1>
          <p className="text-lg text-slate-500 max-w-2xl mx-auto">
            Discover insights, track keywords, and analyze academic papers through an intelligent, minimalist interface.
          </p>
        </div>

        <div className="w-full max-w-3xl mb-16 px-4">
          <SearchBar sizes="large" />
        </div>

        <div className="w-full max-w-5xl mt-8">
          <StatsPanel stats={stats} loading={loading} />
        </div>
      </div>
    </div>
  );
}
