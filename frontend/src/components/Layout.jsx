import { Outlet, Link } from 'react-router-dom';
import { BookOpen } from 'lucide-react';

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 w-full">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-2 rounded-xl text-white shadow-md shadow-purple-200 group-hover:shadow-lg group-hover:shadow-purple-300 group-hover:-translate-y-0.5 transition-all duration-300">
              <BookOpen size={22} strokeWidth={2.5} />
            </div>
            <span className="font-extrabold text-2xl tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600">
              ResearchIQ
            </span>
          </Link>
          <div className="text-sm font-medium text-slate-500">
            Explorer
          </div>
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
