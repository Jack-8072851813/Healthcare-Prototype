import React, { createContext, useContext, useState } from 'react';

export type DemoRole = 'admin' | 'billing' | 'bed-manager';

interface RoleContextType {
  demoRole: DemoRole;
  setDemoRole: (r: DemoRole) => void;
}

const RoleContext = createContext<RoleContextType>({
  demoRole: 'admin',
  setDemoRole: () => {},
});

export const RoleProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [demoRole, setDemoRole] = useState<DemoRole>('admin');
  return (
    <RoleContext.Provider value={{ demoRole, setDemoRole }}>
      {children}
    </RoleContext.Provider>
  );
};

export const useDemoRole = () => useContext(RoleContext);
