"use client";

import { useState } from "react";

type SearchField = "loadId" | "origin" | "destination";

type SearchBarProps = {
   onSearch: (query: string, field: SearchField) => void;
   placeholder?: string;
   defaultField?: SearchField;
};

const FIELD_OPTIONS: { value: SearchField; label: string }[] = [
   { value: "loadId", label: "Load ID" },
   { value: "origin", label: "Origin" },
   { value: "destination", label: "Destination" },
];

export function SearchBar({
   onSearch,
   placeholder = "Search...",
   defaultField = "loadId",
}: SearchBarProps) {
   const [query, setQuery] = useState("");
   const [field, setField] = useState<SearchField>(defaultField);

   const handleSearch = (searchQuery: string, searchField: SearchField) => {
      onSearch(searchQuery, searchField);
   };

   const handleQueryChange = (value: string) => {
      setQuery(value);
      handleSearch(value, field);
   };

   const handleFieldChange = (newField: SearchField) => {
      setField(newField);
      handleSearch(query, newField);
   };

   const handleClear = () => {
      setQuery("");
      handleSearch("", field);
   };

   return (
      <div className="flex w-full items-center gap-2">
         {/* Search Input */}
         <div className="relative flex-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
               <svg
                  className="h-5 w-5 text-slate-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
               >
                  <path
                     strokeLinecap="round"
                     strokeLinejoin="round"
                     strokeWidth={2}
                     d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
               </svg>
            </div>
            <input
               type="text"
               value={query}
               onChange={(e) => handleQueryChange(e.target.value)}
               placeholder={placeholder}
               className="block w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-11 pr-10 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
            />
            {query && (
               <button
                  onClick={handleClear}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600 transition-colors"
                  aria-label="Clear search"
               >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                     <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                     />
                  </svg>
               </button>
            )}
         </div>

         {/* Field Selector */}
         <div className="relative">
            <select
               value={field}
               onChange={(e) => handleFieldChange(e.target.value as SearchField)}
               className="block cursor-pointer appearance-none rounded-lg border border-slate-200 bg-white py-2.5 pl-3.5 pr-10 text-sm text-slate-900 transition-colors hover:border-slate-300 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
            >
               {FIELD_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                     {option.label}
                  </option>
               ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
               <svg
                  className="h-4 w-4 text-slate-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
               >
                  <path
                     strokeLinecap="round"
                     strokeLinejoin="round"
                     strokeWidth={2}
                     d="M19 9l-7 7-7-7"
                  />
               </svg>
            </div>
         </div>
      </div>
   );
}
