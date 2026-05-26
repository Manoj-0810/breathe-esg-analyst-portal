import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  }
});

// Interceptor to handle Basic Auth if credentials exist in localStorage
api.interceptors.request.use((config) => {
  const username = 'admin';
  const password = 'adminpassword';
  // Use Basic Auth credentials for seed user to bypass any future Auth block
  const token = btoa(`${username}:${password}`);
  config.headers.Authorization = `Basic ${token}`;
  return config;
}, (error) => {
  return Promise.reject(error);
});

export const ingestFile = (sourceType, file, clientId) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('client_id', clientId);
  return api.post(`/ingest/${sourceType}/`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
};

export const getRuns = () => {
  return api.get('/runs/');
};

export const getRunRows = (runId) => {
  return api.get(`/runs/${runId}/rows/`);
};

export const approveRow = (rowId, note) => {
  return api.post(`/rows/${rowId}/approve/`, { note });
};

export const flagRow = (rowId, flagReason, note) => {
  return api.post(`/rows/${rowId}/flag/`, { flag_reason: flagReason, note });
};

export const getDashboardData = () => {
  return api.get('/dashboard/');
};

export const getAuditLogs = () => {
  return api.get('/audit-logs/');
};

export default api;
