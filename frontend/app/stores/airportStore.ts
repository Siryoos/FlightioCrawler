import { create, StateCreator } from 'zustand';
import { Airport } from '../components/AirportData';

// Utility function to apply filters and sorting
function applyFiltersAndSort(
  airports: Airport[], 
  searchTerm: string, 
  filterCountry: string, 
  sortBy: string
): Airport[] {
  let filtered = [...airports];

  // Apply search filter
  if (searchTerm.trim() !== '') {
    const term = searchTerm.toLowerCase();
    filtered = filtered.filter(a =>
      a.city.toLowerCase().includes(term) ||
      a.name.toLowerCase().includes(term) ||
      (a.iata && a.iata.toLowerCase().includes(term)) ||
      (a.icao && a.icao.toLowerCase().includes(term)) ||
      a.country.toLowerCase().includes(term)
    );
  }

  // Apply country filter
  if (filterCountry !== 'all' && filterCountry !== '') {
    filtered = filtered.filter(a => a.country === filterCountry);
  }

  // Apply sorting
  switch (sortBy) {
    case 'name':
      filtered.sort((a, b) => a.name.localeCompare(b.name));
      break;
    case 'city':
      filtered.sort((a, b) => a.city.localeCompare(b.city));
      break;
    case 'country':
      filtered.sort((a, b) => a.country.localeCompare(b.country));
      break;
    case 'iata':
      filtered.sort((a, b) => (a.iata || '').localeCompare(b.iata || ''));
      break;
    case 'passengers':
      filtered.sort((a, b) => (b.passengers || 0) - (a.passengers || 0));
      break;
    default:
      // Default to name sorting
      filtered.sort((a, b) => a.name.localeCompare(b.name));
  }

  return filtered;
}

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
    const { airports, filterCountry, sortBy } = get();
    const filtered = applyFiltersAndSort(airports, term, filterCountry, sortBy);
    set({ filteredAirports: filtered });
  },

  setFilterCountry: (country: string) => {
    set({ filterCountry: country });
    const { airports, searchTerm, sortBy } = get();
    const filtered = applyFiltersAndSort(airports, searchTerm, country, sortBy);
    set({ filteredAirports: filtered });
  },

  setSortBy: (criteria: string) => {
    set({ sortBy: criteria });
    const { airports, searchTerm, filterCountry } = get();
    const filtered = applyFiltersAndSort(airports, searchTerm, filterCountry, criteria);
    set({ filteredAirports: filtered });
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
      const { searchTerm, filterCountry, sortBy } = get();
      const filtered = applyFiltersAndSort(data, searchTerm, filterCountry, sortBy);
      set({ airports: data, filteredAirports: filtered, loading: false });
    } catch (err) {
      const error = err instanceof Error ? err.message : 'An unknown error occurred';
      set({ error, loading: false });
    }
  },
});

// Create the store
export const useAirportStore = create<AirportStoreState>(airportStoreCreator); 