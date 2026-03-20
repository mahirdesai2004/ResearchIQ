import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Context-aware research query (main search endpoint)
export const researchQuery = async ({ topic, purpose = 'deep dive', num_papers = 20 }) => {
  const response = await api.post('/research/query', {
    topic,
    purpose,
    num_papers,
  });
  return response.data;
};

export const getSystemStats = async () => {
  const response = await api.get('/system/stats');
  return response.data;
};

export const getKeywordTrend = async (keyword) => {
  const response = await api.get('/analytics/keyword-trend', {
    params: { keyword }
  });
  return response.data;
};

export const getYearlyCount = async () => {
  const response = await api.get('/analytics/yearly-count');
  return response.data;
};

export const searchArxivPapers = async (query, max_results = 20) => {
  const response = await api.get('/papers/arxiv', {
    params: { query, max_results }
  });
  return response.data;
};

// Intelligence Endpoints
export const getAnalysis = async (topic, purpose, paper_ids) => {
  const response = await api.post('/analytics/analysis', {
    topic,
    purpose,
    paper_ids
  });
  return response.data;
};

export const getLiteratureReview = async (domain) => {
  const response = await api.get('/analytics/literature-review', {
    params: { domain }
  });
  return response.data;
};

export const getTrendExplanation = async (keyword) => {
  const response = await api.get('/analytics/trend-explanation', {
    params: { keyword }
  });
  return response.data;
};

export const getGapDetection = async (domain) => {
  const response = await api.get('/analytics/gap-detection', {
    params: { domain }
  });
  return response.data;
};

export default api;
