import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000'; // Make sure the FastAPI runs on 8000

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const getSystemStats = async () => {
  const response = await api.get('/system/stats');
  return response.data;
};

export const getYearlyCount = async () => {
  const response = await api.get('/analytics/yearly-count');
  return response.data;
};

export const getKeywordTrend = async (keyword) => {
  const response = await api.get('/analytics/keyword-trend', {
    params: { keyword }
  });
  return response.data;
};

export const getRecentPapers = async (limit = 10) => {
  const response = await api.get('/analytics/recent-papers', {
    params: { limit }
  });
  return response.data;
};

export const filterPapers = async ({ year, keyword }) => {
  const params = {};
  if (year) params.year = year;
  if (keyword) params.keyword = keyword;
  
  const response = await api.get('/analytics/filter', { params });
  return response.data;
};

export const getSummaries = async () => {
  const response = await api.get('/analytics/summaries');
  return response.data;
};

export const searchArxivPapers = async (query, max_results = 5) => {
  const response = await api.get('/papers/arxiv', {
    params: { query, max_results }
  });
  return response.data;
};

export default api;
