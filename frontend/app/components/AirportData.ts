export interface Airport {
  iata: string;
  icao: string;
  name: string;
  city: string;
  country: string;
  type?: string;
  passengers?: number;
}

let cache: Airport[] | null = null;

export const POPULAR_AIRPORTS = [
  'THR','IKA','MHD','SYZ','IFN','TBZ','AWZ','KIH','RAS','KER','KSH','BND',
  'DXB','IST','DOH','JED','RUH','SAW','AUH','CAI','KWI','MCT','BAH','AMM',
  'AYT','ESB','BEY','TLV','BGW','EBL','LCA'
];

export async function loadAirports(): Promise<Airport[]> {
  if (cache) return cache;
  const res = await fetch('/airports');
  const data = await res.json();
  cache = data.airports || [];
  return cache;
}

export function searchAirports(list: Airport[], query: string): Airport[] {
  const term = query.toLowerCase();
  return list.filter(a =>
    a.city.toLowerCase().includes(term) ||
    a.name.toLowerCase().includes(term) ||
    (a.iata && a.iata.toLowerCase().includes(term)) ||
    (a.icao && a.icao.toLowerCase().includes(term)) ||
    a.country.toLowerCase().includes(term)
  );
}

export function getAirportByCode(list: Airport[], code: string): Airport | undefined {
  const c = code.toLowerCase();
  return list.find(a => a.iata?.toLowerCase() === c || a.icao?.toLowerCase() === c);
}

export function getAirportsByCountry(list: Airport[], country: string): Airport[] {
  return list.filter(a => a.country === country);
}

export function getTopAirportsByPassengers(list: Airport[], limit: number): Airport[] {
  return list
    .filter(a => a.passengers && a.passengers > 0)
    .sort((a, b) => (b.passengers || 0) - (a.passengers || 0))
    .slice(0, limit);
}
