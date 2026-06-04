// ====== Auth Types ======
export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface LoginForm {
  username: string;
  password: string;
}

export interface RegisterForm {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

// ====== Scene Types ======
export interface Scene {
  id: number;
  name: string;
  description: string | null;
  filename: string;
  file_size: number;
  file_format: string;
  num_gaussians: number | null;
  scene_scale: number | null;
  has_sh: boolean;
  sh_degree: number;
  status: string;
  owner_id: number;
  is_public: boolean;
  view_count: number;
  created_at: string;
  updated_at: string;
}

export interface SceneList {
  total: number;
  items: Scene[];
}

export interface SceneUploadForm {
  name: string;
  description?: string;
  is_public: boolean;
  file: File;
}

// ====== System Types ======
export interface SystemInfo {
  name: string;
  version: string;
  demo_mode: boolean;
  features: string[];
  supported_formats: string[];
}

export interface SystemStats {
  total_users: number;
  total_scenes: number;
  total_views: number;
  storage_used: number;
}
