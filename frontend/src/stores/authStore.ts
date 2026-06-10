import { create } from 'zustand';

interface AuthState {
  token: string | null;
  user: { id: string; email: string; tenant_id: string; roles: string[] } | null;
  setAuth: (token: string, user: any) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('access_token'),
  user: null,
  setAuth: (token, user) => {
    localStorage.setItem('access_token', token);
    set({ token, user });
  },
  logout: () => {
    localStorage.removeItem('access_token');
    set({ token: null, user: null });
  },
}));
