import { create, StateCreator } from 'zustand';

// Define the shape for a single flight leg in multi-city search
interface FlightLeg {
  origin: string;
  destination: string;
  date: string;
}

// Define the shape for passenger numbers
interface Passengers {
  adults: number;
  children: number;
  infants: number;
}

// 1. Define the interface for the store's state and actions
interface SearchStoreState {
  tripType: 'oneWay' | 'roundTrip' | 'multiCity';
  origin: string;
  destination: string;
  departureDate: string;
  returnDate: string;
  passengers: Passengers;
  multiCityLegs: FlightLeg[];
  setTripType: (type: 'oneWay' | 'roundTrip' | 'multiCity') => void;
  setField: (field: keyof Omit<SearchStoreState, 'passengers' | 'multiCityLegs'>, value: string) => void;
  setPassengers: (passengers: Partial<Passengers>) => void;
  addMultiCityLeg: () => void;
  updateMultiCityLeg: (index: number, leg: Partial<FlightLeg>) => void;
  removeMultiCityLeg: (index: number) => void;
}

// 2. Define the store creator
const searchStoreCreator: StateCreator<SearchStoreState> = (set, get) => ({
  // Initial State
  tripType: 'roundTrip',
  origin: 'MHD', // Mashhad
  destination: 'IST', // Istanbul
  departureDate: '',
  returnDate: '',
  passengers: { adults: 1, children: 0, infants: 0 },
  multiCityLegs: [{ origin: '', destination: '', date: '' }],

  // Actions
  setTripType: (type) => set({ tripType: type }),
  
  setField: (field, value) => set({ [field]: value } as any),

  setPassengers: (newPassengers) => set((state) => ({
    passengers: { ...state.passengers, ...newPassengers }
  })),

  addMultiCityLeg: () => set((state) => ({
    multiCityLegs: [...state.multiCityLegs, { origin: '', destination: '', date: '' }]
  })),

  updateMultiCityLeg: (index, leg) => set((state) => {
    const newLegs = [...state.multiCityLegs];
    newLegs[index] = { ...newLegs[index], ...leg };
    return { multiCityLegs: newLegs };
  }),

  removeMultiCityLeg: (index) => set((state) => ({
    multiCityLegs: state.multiCityLegs.filter((_, i) => i !== index)
  })),
});

// 3. Create the store
export const useSearchStore = create<SearchStoreState>(searchStoreCreator); 