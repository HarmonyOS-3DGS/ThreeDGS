import axios, { AxiosError } from 'axios';
import type { 
  Token, LoginForm, RegisterForm, 
  Scene, SceneList, SystemInfo, SystemStats 
} from './types';

const API_BASE_URL = '/api/v1';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - clear and redirect
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ====== Auth API ======
export const authApi = {
  login: async (data: LoginForm): Promise<Token> => {
    const formData = new URLSearchParams();
    formData.append('username', data.username);
    formData.append('password', data.password);
    
    const response = await api.post<Token>('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
  },

  register: async (data: RegisterForm) => {
    const response = await api.post('/auth/register', data);
    return response.data;
  },

  getMe: async (): Promise<{ id: number; username: string; email: string; full_name: string | null; role: string; is_active: boolean; created_at: string }> => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

// ====== Scene API ======
export const sceneApi = {
  list: async (mineOnly = false): Promise<SceneList> => {
    const response = await api.get('/scenes', { params: { mine_only: mineOnly } });
    return response.data;
  },

  get: async (id: number): Promise<Scene> => {
    const response = await api.get(`/scenes/${id}`);
    return response.data;
  },

  upload: async (formData: FormData): Promise<Scene> => {
    const response = await api.post('/scenes', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  update: async (id: number, data: { name?: string; description?: string; is_public?: boolean }): Promise<Scene> => {
    const response = await api.put(`/scenes/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/scenes/${id}`);
  },

  getDownloadUrl: (id: number): string => `${API_BASE_URL}/scenes/${id}/download`,
  
  getRawUrl: (id: number): string => `${API_BASE_URL}/scenes/${id}/raw`,
};

// ====== System API ======
export const systemApi = {
  getInfo: async (): Promise<SystemInfo> => {
    const response = await api.get('/system/info');
    return response.data;
  },

  getStats: async (): Promise<SystemStats> => {
    const response = await api.get('/system/stats');
    return response.data;
  },

  healthCheck: async () => {
    const response = await api.get('/system/health');
    return response.data;
  },
};

export default api;
