import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { get, hasSession, login as apiLogin, logout as apiLogout, setCompany } from "./api";

export interface Company {
  id: number;
  code: string;
  name: string;
  country: string;
  currency: string;
  permissions: string[];
  disabled_modules: string[];
}

export interface Me {
  id: number;
  email: string;
  full_name: string;
  is_superadmin: boolean;
  companies: Company[];
}

interface SessionValue {
  me: Me | null;
  company: Company | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  selectCompany: (id: number) => void;
  can: (perm: string) => boolean;
  moduleOn: (module: string) => boolean;
}

const Ctx = createContext<SessionValue | null>(null);
const COMPANY_KEY = "erp.company";

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [company, setCompanyState] = useState<Company | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const profile = await get<Me>("/auth/me");
    setMe(profile);
    let stored: number | null = null;
    try {
      stored = Number(localStorage.getItem(COMPANY_KEY)) || null;
    } catch {
      stored = null;
    }
    const chosen = profile.companies.find((c) => c.id === stored) ?? profile.companies[0] ?? null;
    setCompany(chosen?.id ?? null);
    setCompanyState(chosen);
  }, []);

  useEffect(() => {
    (hasSession() ? load() : Promise.resolve()).catch(() => setMe(null)).finally(() => setLoading(false));
  }, [load]);

  const value: SessionValue = {
    me,
    company,
    loading,
    login: async (email, password) => {
      await apiLogin(email, password);
      await load();
    },
    logout: async () => {
      await apiLogout();
      setMe(null);
      setCompanyState(null);
    },
    selectCompany: (id) => {
      const c = me?.companies.find((x) => x.id === id) ?? null;
      setCompany(c?.id ?? null);
      setCompanyState(c);
      try {
        localStorage.setItem(COMPANY_KEY, String(id));
      } catch {
        /* almacenamiento no disponible: se ignora */
      }
    },
    can: (perm) => !!company?.permissions.includes(perm),
    moduleOn: (m) => !company?.disabled_modules.includes(m),
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession fuera de SessionProvider");
  return v;
}
