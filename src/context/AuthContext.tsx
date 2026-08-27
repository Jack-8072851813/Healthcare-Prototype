import React, { createContext, useContext, useState, useCallback } from 'react';
import { doctors } from '../data/doctors';

export type UserRole = 'admin' | 'doctor';

export interface AuthUser {
  username: string;
  role: UserRole;
  name: string;
  department?: string;
  doctorId?: string;
  loginId?: string;
}

interface AuthContextType {
  user: AuthUser | null;
  login: (username: string, password: string, role: UserRole) => { success: boolean; error?: string };
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  login: () => ({ success: false }),
  logout: () => {},
  isAuthenticated: false,
});

const CREDENTIALS: Record<string, { password: string; role: UserRole; name: string; department?: string; doctorLoginId?: string }> = {
  admin: { password: 'admin', role: 'admin', name: 'Administrator' },
  doc1: { password: 'doc1', role: 'doctor', name: 'Dr. Surendhar G', department: 'Cardiology', doctorLoginId: 'doc1' },
  doc2: { password: 'doc2', role: 'doctor', name: 'Dr. Dinesh Choudary', department: 'Orthopaedics', doctorLoginId: 'doc2' },
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const saved = sessionStorage.getItem('meridian_user');
    return saved ? JSON.parse(saved) : null;
  });

  const login = useCallback((username: string, password: string, role: UserRole): { success: boolean; error?: string } => {
    const cred = CREDENTIALS[username];
    if (!cred) return { success: false, error: 'Invalid username. Please check your credentials.' };
    if (cred.password !== password) return { success: false, error: 'Invalid password. Please try again.' };
    if (cred.role !== role) return { success: false, error: `This account does not have ${role} access.` };

    const doc = cred.doctorLoginId ? doctors.find(d => d.loginId === cred.doctorLoginId) : undefined;

    const authUser: AuthUser = {
      username,
      role: cred.role,
      name: cred.name,
      department: cred.department,
      doctorId: doc?.id,
      loginId: cred.doctorLoginId,
    };
    setUser(authUser);
    sessionStorage.setItem('meridian_user', JSON.stringify(authUser));
    return { success: true };
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
