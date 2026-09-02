/**
 * Fuzzy string matching utility
 *
 * Implements a simple but effective fuzzy search algorithm that:
 * - Ignores case
 * - Handles partial matches
 * - Scores results by relevance
 */

/**
 * Calculate similarity score between two strings
 * Returns a score between 0 and 1 (1 being exact match)
 */
function calculateSimilarity(str1: string, str2: string): number {
   const s1 = str1.toLowerCase();
   const s2 = str2.toLowerCase();

   // Exact match
   if (s1 === s2) return 1;

   // If search query is contained in the string, score based on position and length
   if (s1.includes(s2)) {
      const startIndex = s1.indexOf(s2);
      // Boost score if query is at the beginning
      if (startIndex === 0) {
         return 0.95;
      }
      // Still high score for contains, but lower than starts-with
      return 0.75;
   }

   // If the string is contained in the query (user typed more than exists)
   if (s2.includes(s1)) {
      return 0.7;
   }

   // Calculate character match ratio (stricter than before)
   let matches = 0;
   const searchChars = s2.split("");
   const s1Chars = s1.split("");

   for (const char of searchChars) {
      const index = s1Chars.indexOf(char);
      if (index !== -1) {
         matches++;
         s1Chars.splice(index, 1); // Remove matched char to avoid double counting
      }
   }

   // Only count if we have a high match ratio
   const ratio = matches / s2.length;
   return ratio > 0.7 ? ratio * 0.6 : 0; // Scale down fuzzy matches
}

/**
 * Fuzzy search through an array of items
 *
 * @param items - Array of items to search
 * @param query - Search query string
 * @param getSearchableValue - Function to extract searchable string from item
 * @param threshold - Minimum similarity score (0-1) to include in results
 * @returns Filtered and sorted array of items
 */
export function fuzzySearch<T>(
   items: T[],
   query: string,
   getSearchableValue: (item: T) => string | undefined | null,
   threshold: number = 0.5 // Increased from 0.3 to be stricter
): T[] {
   if (!query.trim()) {
      return items;
   }

   const queryLower = query.toLowerCase().trim();

   // Score each item
   const scored = items
      .map((item) => {
         const value = getSearchableValue(item);
         if (!value) return { item, score: 0 };

         const valueLower = value.toLowerCase();

         // Exact match gets highest score
         if (valueLower === queryLower) {
            return { item, score: 1 };
         }

         // Boost score for starts-with matches
         if (valueLower.startsWith(queryLower)) {
            return { item, score: 0.95 };
         }

         // Boost score for word-start matches
         const words = valueLower.split(/\s+/);
         const wordMatch = words.some((word) => word.startsWith(queryLower));
         if (wordMatch) {
            return { item, score: 0.85 };
         }

         const score = calculateSimilarity(valueLower, queryLower);
         return { item, score };
      })
      .filter(({ score }) => score >= threshold)
      .sort((a, b) => b.score - a.score);

   return scored.map(({ item }) => item);
}

/**
 * Multi-field fuzzy search
 * Searches across multiple fields and returns best matches
 *
 * @param items - Array of items to search
 * @param query - Search query string
 * @param getSearchableValues - Function to extract array of searchable strings from item
 * @param threshold - Minimum similarity score (0-1) to include in results
 * @returns Filtered and sorted array of items
 */
export function fuzzySearchMultiField<T>(
   items: T[],
   query: string,
   getSearchableValues: (item: T) => (string | undefined | null)[],
   threshold: number = 0.5 // Increased from 0.3 to be stricter
): T[] {
   if (!query.trim()) {
      return items;
   }

   const queryLower = query.toLowerCase().trim();

   // Score each item across all fields, take highest score
   const scored = items
      .map((item) => {
         const values = getSearchableValues(item).filter((v): v is string => Boolean(v));

         if (values.length === 0) return { item, score: 0 };

         const scores = values.map((value) => {
            const valueLower = value.toLowerCase();

            // Exact match gets highest score
            if (valueLower === queryLower) {
               return 1;
            }

            if (valueLower.startsWith(queryLower)) {
               return 0.95;
            }

            const words = valueLower.split(/\s+/);
            const wordMatch = words.some((word) => word.startsWith(queryLower));
            if (wordMatch) {
               return 0.85;
            }

            return calculateSimilarity(valueLower, queryLower);
         });

         return { item, score: Math.max(...scores) };
      })
      .filter(({ score }) => score >= threshold)
      .sort((a, b) => b.score - a.score);

   return scored.map(({ item }) => item);
}
