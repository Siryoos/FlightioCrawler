import { create, StateCreator } from 'zustand';
import { Airport } from '../components/AirportData'; // Assuming Airport type is exported from here

// 1. Define the interface for the store's state and actions
interface AirportStoreState {
  airports: Airport[];
  filteredAirports: Airport[];
  searchTerm: string;
  filterCountry: string;
  sortBy: string;
  loading: boolean;
  error: string | null;

  setSearchTerm: (term: string) => void;
  setFilterCountry: (country: string) => void;
  setSortBy: (criteria: string) => void;
  fetchAirports: () => Promise<void>;
}

// Define the store creator with proper types
const airportStoreCreator: StateCreator<AirportStoreState> = (set, get) => ({
  // Initial State
  airports: [],
  filteredAirports: [],
  searchTerm: '',
  filterCountry: 'all',
  sortBy: 'name',
  loading: false,
  error: null,

  // Actions
  setSearchTerm: (term: string) => {
    set({ searchTerm: term });
    // TODO: Implement filtering logic here
  },

  setFilterCountry: (country: string) => {
    set({ filterCountry: country });
    // TODO: Implement filtering logic here
  },

  setSortBy: (criteria: string) => {
    set({ sortBy: criteria });
    // TODO: Implement sorting logic here
  },

  fetchAirports: async () => {
    set({ loading: true, error: null });
    try {
      // In a real app, you'd fetch from an API
      // For now, we'll simulate with a static import or a placeholder
      const response = await fetch('/api/airports'); // Placeholder API endpoint
      if (!response.ok) {
        throw new Error('Failed to fetch airports');
      }
      const data: Airport[] = await response.json();
      set({ airports: data, filteredAirports: data, loading: false });
    } catch (err) {
      const error = err instanceof Error ? err.message : 'An unknown error occurred';
      set({ error, loading: false });
    }
  },
});

// Create the store
export const useAirportStore = create<AirportStoreState>(airportStoreCreator); 