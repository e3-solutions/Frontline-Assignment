import React, { useState, useEffect, useRef } from "react";

// Phone number formatting functions from original form.js
const phoneFormatters: { [key: string]: (value: string) => string } = {
   "+1": (value: string) => {
      // US/Canada format: (555) 123-4567
      if (value.length <= 3) return `(${value}`;
      if (value.length <= 6) return `(${value.substring(0, 3)}) ${value.substring(3)}`;
      return `(${value.substring(0, 3)}) ${value.substring(3, 6)}-${value.substring(6, 10)}`;
   },
   "+44": (value: string) => {
      // UK format: 20 1234 5678
      if (value.length <= 2) return value;
      if (value.length <= 6) return `${value.substring(0, 2)} ${value.substring(2)}`;
      return `${value.substring(0, 2)} ${value.substring(2, 6)} ${value.substring(6, 10)}`;
   },
   "+49": (value: string) => {
      // Germany format: 151 12345678
      if (value.length <= 3) return value;
      return `${value.substring(0, 3)} ${value.substring(3)}`;
   },
   "+33": (value: string) => {
      // France format: 6 12 34 56 78
      const parts = [];
      for (let i = 0; i < value.length; i += 2) {
         if (i === 0) {
            parts.push(value.substring(i, i + 1));
            i--;
         } else {
            parts.push(value.substring(i, i + 2));
         }
      }
      return parts.join(" ");
   },
   // Default formatter for other countries
   default: (value: string) => value,
};

interface PhoneInputProps {
   label: string;
   name: string;
   value?: string;
   countryCode?: string;
   required?: boolean;
   hint?: string;
   onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
   onCountryCodeChange?: (countryCode: string) => void;
}

// Complete country codes list from original form.js
const COUNTRY_CODES = [
   {
      name: "United States",
      code: "+1",
      iso: "US",
      placeholder: "(555) 123-4567",
   },
   { name: "Canada", code: "+1", iso: "CA", placeholder: "(555) 123-4567" },
   {
      name: "United Kingdom",
      code: "+44",
      iso: "GB",
      placeholder: "20 1234 5678",
   },
   { name: "Australia", code: "+61", iso: "AU", placeholder: "412 345 678" },
   { name: "Germany", code: "+49", iso: "DE", placeholder: "151 12345678" },
   { name: "France", code: "+33", iso: "FR", placeholder: "6 12 34 56 78" },
   { name: "Spain", code: "+34", iso: "ES", placeholder: "612 34 56 78" },
   { name: "Italy", code: "+39", iso: "IT", placeholder: "312 345 6789" },
   { name: "Mexico", code: "+52", iso: "MX", placeholder: "55 1234 5678" },
   { name: "Brazil", code: "+55", iso: "BR", placeholder: "11 91234-5678" },
   { name: "Argentina", code: "+54", iso: "AR", placeholder: "11 1234-5678" },
   { name: "Japan", code: "+81", iso: "JP", placeholder: "90-1234-5678" },
   { name: "China", code: "+86", iso: "CN", placeholder: "138 0013 8000" },
   { name: "India", code: "+91", iso: "IN", placeholder: "98765 43210" },
   { name: "Russia", code: "+7", iso: "RU", placeholder: "912 345-67-89" },
   { name: "South Korea", code: "+82", iso: "KR", placeholder: "10-1234-5678" },
   { name: "Netherlands", code: "+31", iso: "NL", placeholder: "6 12345678" },
   { name: "Belgium", code: "+32", iso: "BE", placeholder: "470 12 34 56" },
   { name: "Sweden", code: "+46", iso: "SE", placeholder: "70-123 45 67" },
   { name: "Norway", code: "+47", iso: "NO", placeholder: "412 34 567" },
   { name: "Denmark", code: "+45", iso: "DK", placeholder: "20 12 34 56" },
   { name: "Finland", code: "+358", iso: "FI", placeholder: "41 2345678" },
   { name: "Poland", code: "+48", iso: "PL", placeholder: "512 345 678" },
   { name: "Switzerland", code: "+41", iso: "CH", placeholder: "78 123 45 67" },
];

const DEFAULT_COUNTRY = COUNTRY_CODES[0];

const findCountryByCode = (countryCode?: string) =>
   COUNTRY_CODES.find((country) => country.code === countryCode) ?? DEFAULT_COUNTRY;

const PhoneInput: React.FC<PhoneInputProps> = ({
   label,
   name,
   value = "",
   countryCode,
   required = false,
   hint,
   onChange,
   onCountryCodeChange,
}) => {
   const [selectedCountry, setSelectedCountry] = useState(findCountryByCode(countryCode));
   const [isDropdownOpen, setIsDropdownOpen] = useState(false);
   const [searchTerm, setSearchTerm] = useState("");
   const inputRef = useRef<HTMLInputElement>(null);
   const containerRef = useRef<HTMLDivElement>(null);

   const emitChange = (nextValue: string) => {
      onChange?.({
         target: { name, value: nextValue },
      } as React.ChangeEvent<HTMLInputElement>);
   };

   // Close dropdown when clicking outside
   useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
         if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
            setIsDropdownOpen(false);
            setSearchTerm("");
         }
      };

      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
   }, []);

   useEffect(() => {
      setSelectedCountry(findCountryByCode(countryCode));
   }, [countryCode]);

   // Close all dropdowns before opening this one
   const closeAllDropdowns = () => {
      const allContainers = document.querySelectorAll(".phone-input-wrapper");
      allContainers.forEach((container) => {
         container.classList.remove("dropdown-open");
      });
   };

   const toggleDropdown = () => {
      closeAllDropdowns();
      if (!isDropdownOpen) {
         setIsDropdownOpen(true);
         setSearchTerm("");
         if (containerRef.current) {
            containerRef.current.classList.add("dropdown-open");
         }
      } else {
         setIsDropdownOpen(false);
         if (containerRef.current) {
            containerRef.current.classList.remove("dropdown-open");
         }
      }
   };

   // Format phone number based on country
   const formatPhoneNumber = (inputValue: string, countryCode: string) => {
      const value = inputValue.replace(/\D/g, ""); // Remove non-digits
      const formatter = phoneFormatters[countryCode] || phoneFormatters["default"];
      return formatter(value);
   };

   const handleCountrySelect = (country: (typeof COUNTRY_CODES)[0]) => {
      setSelectedCountry(country);
      setIsDropdownOpen(false);
      setSearchTerm("");
      onCountryCodeChange?.(country.code);

      // Reformat existing phone number with new country format
      if (value) {
         const cleanValue = value.replace(/\D/g, "");
         const formattedValue = formatPhoneNumber(cleanValue, country.code);
         emitChange(formattedValue);
      } else if (!onChange && inputRef.current) {
         inputRef.current.value = "";
      }

      if (containerRef.current) {
         containerRef.current.classList.remove("dropdown-open");
      }
   };

   const handlePhoneInput = (e: React.ChangeEvent<HTMLInputElement>) => {
      const inputValue = e.target.value;
      const formattedValue = formatPhoneNumber(inputValue, selectedCountry.code);

      if (!onChange && inputRef.current) {
         inputRef.current.value = formattedValue;
      }
      emitChange(formattedValue);
   };

   const handlePhonePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
      e.preventDefault();
      const pastedText = e.clipboardData.getData("text");
      const formattedValue = formatPhoneNumber(pastedText, selectedCountry.code);

      if (!onChange && inputRef.current) {
         inputRef.current.value = formattedValue;
      }
      emitChange(formattedValue);
   };

   const handlePhoneKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
      const char = e.key;
      // Only allow numbers, backspace, delete, and arrow keys
      if (
         !/[0-9]/.test(char) &&
         !["Backspace", "Delete", "ArrowLeft", "ArrowRight", "Tab"].includes(char)
      ) {
         e.preventDefault();
      }
   };

   const filteredCountries = COUNTRY_CODES.filter(
      (country) =>
         country.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
         country.code.includes(searchTerm) ||
         country.iso.toLowerCase().includes(searchTerm.toLowerCase())
   );

   return (
      <div className="form-group relative z-10 mb-4 flex min-w-[200px] flex-col justify-center overflow-visible">
         <label htmlFor={name} className="e3-field-label">
            {label}
            {hint && (
               <span className="ml-1 font-normal text-[color:var(--e3-text-soft)]">{hint}</span>
            )}
         </label>

         <div
            ref={containerRef}
            className={`phone-input-wrapper relative flex w-full min-w-0 items-stretch overflow-visible rounded-2xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] transition-all duration-200 hover:border-[color:var(--e3-border-strong)] focus-within:border-[color:var(--e3-border-strong)] focus-within:ring-2 focus-within:ring-[color:var(--e3-brand-accent)]/25 ${
               isDropdownOpen ? "dropdown-open z-[1001]" : ""
            }`}
         >
            {/* Country Code Select Button */}
            <button
               type="button"
               onClick={toggleDropdown}
               className="country-code-select relative flex w-[120px] min-w-[100px] flex-shrink-0 cursor-pointer items-center justify-between whitespace-nowrap border-none bg-transparent px-3 py-2.5 text-base text-[color:var(--e3-text-muted)] transition-all rounded-l-2xl hover:bg-[color:var(--e3-surface-alt)] focus:bg-[color:var(--e3-surface-alt)] focus:outline-none sm:w-[140px]"
            >
               <div className="flex items-center gap-1.5">
                  <span className="country-iso inline-block w-6 rounded bg-[color:var(--e3-surface-alt)] px-1.5 py-0.5 text-center text-xs font-semibold text-[color:var(--e3-text-strong)] e3-font-mono">
                     {selectedCountry.iso}
                  </span>
                  <span className="country-code text-sm font-medium text-[color:var(--e3-text-strong)] e3-font-mono">
                     {selectedCountry.code}
                  </span>
               </div>

               <span
                  className={`dropdown-arrow text-xs text-[color:var(--e3-text-soft)] transition-transform duration-200 ${
                     isDropdownOpen ? "rotate-180" : ""
                  }`}
               >
                  ▼
               </span>
            </button>

            {/* Phone Number Input */}
            <input
               type="tel"
               id={name}
               name={name}
               ref={inputRef}
               value={value}
               placeholder={selectedCountry.placeholder}
               required={required}
               onChange={handlePhoneInput}
               onPaste={handlePhonePaste}
               onKeyDown={handlePhoneKeyPress}
               className="phone-input min-w-0 flex-1 border-none bg-transparent px-3 py-2.5 text-base text-[color:var(--e3-text-strong)] placeholder:text-[color:var(--e3-text-soft)] outline-none e3-font-body focus:shadow-none"
            />

            {/* Country Code Dropdown */}
            {isDropdownOpen && (
               <div className="country-code-dropdown scrollbar-custom absolute left-0 right-0 top-[calc(100%+8px)] z-[9999] max-h-[300px] w-full min-w-[280px] overflow-y-auto rounded-2xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface)] shadow-[0_24px_60px_rgba(4,2,10,0.42)] sm:min-w-[320px]">
                  <input
                     type="text"
                     value={searchTerm}
                     onChange={(e) => setSearchTerm(e.target.value)}
                     placeholder="Search country..."
                     className="country-search sticky top-0 z-10 box-border w-full border-b border-[color:var(--e3-border-subtle)] bg-[color:var(--e3-surface)] px-4 py-2.5 text-base text-[color:var(--e3-text-strong)] placeholder:text-[color:var(--e3-text-soft)] outline-none e3-font-body"
                  />

                  <div className="country-options max-h-[250px] overflow-x-hidden overflow-y-auto">
                     {filteredCountries.map((country, index) => (
                        <div
                           key={`${country.code}-${country.iso}-${index}`}
                           onClick={() => handleCountrySelect(country)}
                           className={`country-option flex cursor-pointer items-center gap-3 px-4 py-2.5 text-base transition-colors hover:bg-[color:var(--e3-surface-soft)] ${
                              selectedCountry.code === country.code &&
                              selectedCountry.iso === country.iso
                                 ? "selected bg-[color:var(--e3-surface-alt)] text-[color:var(--e3-brand-lavender)]"
                                 : ""
                           }`}
                        >
                           <span className="country-iso inline-block w-6 rounded bg-[color:var(--e3-surface-alt)] px-1.5 py-0.5 text-center text-xs font-semibold text-[color:var(--e3-text-strong)] e3-font-mono">
                              {country.iso}
                           </span>
                           <span className="country-name flex-1 text-[color:var(--e3-text-muted)] e3-font-body">
                              {country.name}
                           </span>
                           <span className="country-code whitespace-nowrap text-sm text-[color:var(--e3-text-soft)] e3-font-mono">
                              {country.code}
                           </span>
                        </div>
                     ))}
                  </div>
               </div>
            )}
         </div>

         <input type="hidden" name={`${name}_country_code`} value={selectedCountry.code} />
      </div>
   );
};

export default PhoneInput;
