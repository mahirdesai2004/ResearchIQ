import PaperList from './PaperList';

export default function RecentPapers({ papers, loading }) {
  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-slate-800 tracking-tight">Recent Discovery</h2>
        {!loading && papers?.length > 0 && (
          <span className="text-sm text-slate-500 bg-slate-100 px-3 py-1 rounded-full font-medium">
            {papers.length} papers
          </span>
        )}
      </div>
      
      <PaperList papers={papers} loading={loading} emptyMessage="No recent papers available." />
    </div>
  );
}
