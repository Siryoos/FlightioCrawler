import { create, StateCreator } from 'zustand';

// Define the shape of site information
export interface SiteInfo {
  name: string;
  url: string;
  status: 'active' | 'inactive' | 'maintenance';
  lastCrawled?: string;
  averageSuccessRate?: number;
}

// Define the shape for detailed site data
export interface SiteDetail {
    name: string;
    // ... other detailed properties
    crawledData: any[]; 
}

// 1. Define the interface for the store's state and actions
interface SiteStoreState {
  sites: Record<string, SiteInfo>;
  currentSiteData: SiteDetail | null;
  loading: boolean;
  error: string | null;

  fetchSites: () => Promise<void>;
  fetchSiteDetails: (siteId: string) => Promise<void>;
  toggleSiteStatus: (siteId: string) => Promise<void>;
}

// 2. Define the store creator with proper types
const siteStoreCreator: StateCreator<SiteStoreState> = (set, get) => ({
  // Initial State
  sites: {},
  currentSiteData: null,
  loading: false,
  error: null,

  // Actions
  fetchSites: async () => {
    set({ loading: true, error: null });
    try {
      const response = await fetch('/api/sites'); // Placeholder API
      if (!response.ok) throw new Error('Failed to fetch sites');
      const data: Record<string, SiteInfo> = await response.json();
      set({ sites: data, loading: false });
    } catch (err) {
      const error = err instanceof Error ? err.message : 'An unknown error occurred';
      set({ error, loading: false });
    }
  },

  fetchSiteDetails: async (siteId: string) => {
    set({ loading: true, error: null });
    try {
      const response = await fetch(`/api/sites/${siteId}`); // Placeholder API
      if (!response.ok) throw new Error(`Failed to fetch details for ${siteId}`);
      const data: SiteDetail = await response.json();
      set({ currentSiteData: data, loading: false });
    } catch (err) {
      const error = err instanceof Error ? err.message : 'An unknown error occurred';
      set({ error, loading: false });
    }
  },

  toggleSiteStatus: async (siteId: string) => {
    const currentStatus = get().sites[siteId]?.status;
    if (!currentStatus) return;

    const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
    const endpoint = newStatus === 'active' ? 'enable' : 'disable';

    try {
      // Optimistic update
      set(state => ({
        sites: {
          ...state.sites,
          [siteId]: { ...state.sites[siteId], status: newStatus },
        },
      }));

      const response = await fetch(`/api/v1/sites/${siteId}/${endpoint}`, { method: 'POST' });
      if (!response.ok) {
        throw new Error('Failed to toggle site status');
      }
    } catch (err) {
      // Rollback on failure
      set(state => ({
        sites: {
          ...state.sites,
          [siteId]: { ...state.sites[siteId], status: currentStatus },
        },
      }));
      // Optionally handle the error display
    }
  }
});

// 3. Create the store
export const useSiteStore = create<SiteStoreState>(siteStoreCreator); 