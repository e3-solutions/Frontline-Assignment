"use client";

import { useTheme } from "@/src/contexts/ThemeContext";

export function ThemeToggle() {
   const { theme, toggleTheme } = useTheme();
   const isDark = theme === "dark";

   return (
      <button
         type="button"
         role="switch"
         aria-checked={isDark}
         onClick={toggleTheme}
         className="relative h-8 w-[56px] shrink-0 cursor-pointer rounded-full transition-colors duration-300 bg-[color:var(--e3-surface-alt)] border border-[color:var(--e3-border-soft)]"
         aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
         title={`Switch to ${isDark ? "light" : "dark"} mode`}
      >
         {/* Sliding knob */}
         <span
            className="absolute top-1/2 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full bg-white shadow-md transition-all duration-300"
            style={{ left: isDark ? "4px" : "calc(100% - 28px)" }}
         >
            {isDark ? (
               <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="#334155" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
               </svg>
            ) : (
               <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="#f59e0b" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="4" />
                  <line x1="12" y1="2" x2="12" y2="5" />
                  <line x1="12" y1="19" x2="12" y2="22" />
                  <line x1="4.93" y1="4.93" x2="6.34" y2="6.34" />
                  <line x1="17.66" y1="17.66" x2="19.07" y2="19.07" />
                  <line x1="2" y1="12" x2="5" y2="12" />
                  <line x1="19" y1="12" x2="22" y2="12" />
                  <line x1="4.93" y1="19.07" x2="6.34" y2="17.66" />
                  <line x1="17.66" y1="6.34" x2="19.07" y2="4.93" />
               </svg>
            )}
         </span>
      </button>
   );
}
