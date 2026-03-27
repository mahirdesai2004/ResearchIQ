import { Outlet, Link } from 'react-router-dom';
import { BookOpen } from 'lucide-react';

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <header className="bg-white/80 backdrop-blur-sm border-b border-orange-100 w-full z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 group">
            <div className="bg-slate-900 p-1.5 rounded-lg text-white">
              <BookOpen size={20} strokeWidth={2} />
            </div>
            <span className="font-bold text-xl tracking-tight text-slate-900">
              ResearchIQ
            </span>
          </Link>
          <nav className="flex items-center gap-6">
            <Link to="/" className="text-sm font-medium text-slate-500 hover:text-slate-900 transition-colors cursor-pointer">
              Explorer
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      <footer className="bg-white border-t border-gray-200 py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 flex justify-between items-center text-sm text-slate-500">
          <p>© {new Date().getFullYear()} ResearchIQ</p>
          <p>AI-Powered Research Analytics</p>
        </div>
      </footer>
    </div>
  );
}
