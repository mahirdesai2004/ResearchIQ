import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';

export default function Chart({ data, title, dataKey = 'count', xAxisKey = 'year', color = '#3b82f6' }) {
  if (!data || data.length === 0) {
    return (
      <div className="glass-card p-6 flex items-center justify-center h-72 text-slate-400">
        No data available for chart
      </div>
    );
  }

  // Ensure data is sorted by year if it represents years
  const sortedData = [...data].sort((a, b) => {
    if (a[xAxisKey] < b[xAxisKey]) return -1;
    if (a[xAxisKey] > b[xAxisKey]) return 1;
    return 0;
  });

  return (
    <div className="glass-card p-6 w-full">
      {title && (
        <h3 className="text-slate-800 font-medium mb-6">{title}</h3>
      )}
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={sortedData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis 
              dataKey={xAxisKey} 
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#64748b', fontSize: 12 }}
              dy={10}
            />
            <YAxis 
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#64748b', fontSize: 12 }}
              dx={-10}
            />
            <Tooltip
              contentStyle={{ 
                borderRadius: '8px', 
                border: 'none', 
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
                padding: '12px'
              }}
              itemStyle={{ color: '#0f172a', fontWeight: 600 }}
              labelStyle={{ color: '#64748b', marginBottom: '4px' }}
            />
            <Line 
              type="monotone" 
              dataKey={dataKey} 
              stroke={color} 
              strokeWidth={3}
              dot={{ r: 4, fill: color, strokeWidth: 2, stroke: '#fff' }}
              activeDot={{ r: 6, strokeWidth: 0 }}
              animationDuration={1500}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
