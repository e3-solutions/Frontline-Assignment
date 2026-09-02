export type Coordinates = { lat: number; lng: number };

const cache = new Map<string, Coordinates | null>();

// Add a helper to wait for a short duration to respect Nominatim's 1 req/sec limit
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function geocodeLocation(query: string, signal?: AbortSignal): Promise<Coordinates | null> {
   if (!query) return null;

   const cacheKey = query.toLowerCase().trim();
   if (cache.has(cacheKey)) {
      return cache.get(cacheKey) || null;
   }

   try {
      const response = await fetch(
         `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=1`,
         {
            headers: {
               "User-Agent": "E3Solutions-NegDashboard/1.0",
            },
            signal,
         }
      );

      if (!response.ok) {
         throw new Error("Geocoding failed");
      }

      const data = await response.json();
      if (data && data.length > 0) {
         const coords = {
            lat: parseFloat(data[0].lat),
            lng: parseFloat(data[0].lon),
         };
         cache.set(cacheKey, coords);
         return coords;
      }

      // Fallback: If exact full address fails, fallback to just City, State/ZIP 
      // by taking the last two parts of the comma-separated address.
      const parts = query.split(",");
      if (parts.length > 1) {
         const fallbackQuery = parts.slice(-2).join(",").trim();
         
         if (fallbackQuery && fallbackQuery !== query) {
            // Delay 1s to respect Nominatim's 1 request per second usage policy
            await delay(1000);
            
            const fallbackResponse = await fetch(
               `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(fallbackQuery)}&format=json&limit=1`,
               {
                  headers: {
                     "User-Agent": "E3Solutions-NegDashboard/1.0",
                  },
                  signal,
               }
            );

            if (fallbackResponse.ok) {
               const fallbackData = await fallbackResponse.json();
               if (fallbackData && fallbackData.length > 0) {
                  const coords = {
                     lat: parseFloat(fallbackData[0].lat),
                     lng: parseFloat(fallbackData[0].lon),
                  };
                  cache.set(cacheKey, coords);
                  return coords;
               }
            }
         }
      }

      cache.set(cacheKey, null);
      return null;
   } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
         return null;
      }
      console.error("Geocoding error:", error);
      return null;
   }
}
