import React, { createContext, useContext, useState, useCallback } from 'react';

export type UserRole = 'admin' | 'doctor';

export interface AuthUser {
  username: string;
  role: UserRole;
  name: string;
  department?: string;
  doctorId?: string;
  loginId?: string;
  token?: string;
}

interface AuthContextType {
  user: AuthUser | null;
  login: (username: string, password: string, role: UserRole) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  login: async () => ({ success: false }),
  logout: () => {},
  isAuthenticated: false,
});

const BASE_URL = 'http://localhost:8000';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const saved = sessionStorage.getItem('meridian_user');
    return saved ? JSON.parse(saved) : null;
  });

  const login = useCallback(async (username: string, password: string, role: UserRole): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch(`${BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password, role }),
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        return { success: false, error: data.detail || 'Authentication failed' };
      }
      
      if (data.success && data.token) {
        const authUser: AuthUser = {
          ...data.user,
          token: data.token,
        };
        setUser(authUser);
        sessionStorage.setItem('meridian_user', JSON.stringify(authUser));
        return { success: true };
      }
      
      return { success: false, error: 'Invalid server response structure' };
    } catch (e) {
      console.error('Login error:', e);
      return { success: false, error: 'Server unreachable. Please verify backend service status.' };
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    sessionStorage.removeItem('meridian_user');
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
