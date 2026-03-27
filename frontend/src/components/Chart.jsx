import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';

export default function Chart({ data, title, dataKey = 'count', xAxisKey = 'year', color = '#000000', type = 'auto' }) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-6 flex items-center justify-center h-80 text-gray-400 shadow-sm text-sm">
        No data available for visualization
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
    <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm w-full">
      {title && (
        <h3 className="text-gray-900 font-semibold text-base mb-6 tracking-tight">
          {title}
        </h3>
      )}

      <div className="h-72 w-full -ml-2">
        <ResponsiveContainer width="100%" height="100%">
          {type === 'bar' || sortedData.length === 1 ? (
            <BarChart data={sortedData} margin={{ top: 10, right: 30, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
              <XAxis 
                dataKey={xAxisKey} 
                axisLine={{ stroke: '#e5e7eb', strokeWidth: 1 }}
                tickLine={false}
                tick={{ fill: '#6b7280', fontSize: 12, fontWeight: 500 }}
                tickMargin={12}
              />
              <YAxis 
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#6b7280', fontSize: 12, fontWeight: 500 }}
                tickMargin={12}
              />
              <Tooltip
                contentStyle={{ 
                  backgroundColor: '#111827',
                  borderRadius: '8px', 
                  border: '1px solid #374151', 
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                  padding: '8px 12px',
                  color: '#f9fafb',
                }}
                itemStyle={{ color: '#ffffff', fontWeight: 600, fontSize: '14px', paddingTop: '2px' }}
                labelStyle={{ color: '#9ca3af', marginBottom: '2px', fontSize: '12px', fontWeight: 500 }}
                cursor={{ fill: '#f3f4f6' }}
              />
              <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} barSize={40} />
            </BarChart>
          ) : (
            <AreaChart data={sortedData} margin={{ top: 10, right: 30, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="colorGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.1}/>
                  <stop offset="100%" stopColor={color} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
              <XAxis 
                dataKey={xAxisKey} 
                axisLine={{ stroke: '#e5e7eb', strokeWidth: 1 }}
                tickLine={false}
                tick={{ fill: '#6b7280', fontSize: 12, fontWeight: 500 }}
                tickMargin={12}
              />
              <YAxis 
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#6b7280', fontSize: 12, fontWeight: 500 }}
                tickMargin={12}
              />
              <Tooltip
                contentStyle={{ 
                  backgroundColor: '#111827',
                  borderRadius: '8px', 
                  border: '1px solid #374151', 
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                  padding: '8px 12px',
                  color: '#f9fafb',
                }}
                itemStyle={{ color: '#ffffff', fontWeight: 600, fontSize: '14px', paddingTop: '2px' }}
                labelStyle={{ color: '#9ca3af', marginBottom: '2px', fontSize: '12px', fontWeight: 500 }}
                cursor={{ stroke: '#d1d5db', strokeWidth: 1, strokeDasharray: '4 4' }}
                animationDuration={150}
              />
              <Area 
                type="monotone" 
                dataKey={dataKey} 
                stroke={color} 
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorGradient)"
                dot={{ r: 3, fill: '#ffffff', strokeWidth: 2, stroke: color }}
                activeDot={{ 
                  r: 5, 
                  strokeWidth: 2, 
                  fill: '#ffffff', 
                  stroke: color,
                }}
                animationDuration={500}
              />
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
