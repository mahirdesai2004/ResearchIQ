import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

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

// Chat with papers (LangChain-powered)
export const chatQuery = async (query, papers, session_id = 'default') => {
  const response = await api.post('/chat/query', {
    query,
    papers: papers.slice(0, 10),
    session_id
  });
  return response.data;
};

// Paper-level analysis (explain)
export const analyzePaper = async (paper_id) => {
  const response = await api.post('/paper/analyze', {
    paper_id: String(paper_id)
  });
  return response.data;
};

// Recommender System & RL Interaction API
export const logUserInteraction = async (sessionId, paperId, action, topic = '') => {
  try {
    const response = await api.post('/user/interact', {
      session_id: sessionId,
      paper_id: String(paperId),
      action,
      topic
    });
    return response.data;
  } catch (err) {
    console.warn('Interaction logging error (non-fatal):', err);
    return null;
  }
};

export const getPersonalizedRecommendations = async (sessionId, topic = '', limit = 6, useAgents = false) => {
  const response = await api.get('/recommend/for-you', {
    params: {
      session_id: sessionId,
      topic: topic || undefined,
      limit,
      use_agents: useAgents
    }
  });
  return response.data;
};

export const getUserHistory = async (sessionId) => {
  const response = await api.get('/user/history', {
    params: { session_id: sessionId }
  });
  return response.data;
};

export default api;
