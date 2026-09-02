"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";

type Theme = "light" | "dark";

type ThemeContextValue = {
   theme: Theme;
   toggleTheme: () => void;
};

function updateFavicon(theme: Theme) {
   const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
   if (link) {
      link.href = theme === "light" ? "/favicon-light.webp" : "/favicon.webp";
   }
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
   const [theme, setTheme] = useState<Theme>("dark");

   useEffect(() => {
      const stored = localStorage.getItem("e3-theme") as Theme | null;
      if (stored === "light" || stored === "dark") {
         setTheme(stored);
         document.documentElement.dataset.theme = stored;
         updateFavicon(stored);
      }
   }, []);

   const toggleTheme = useCallback(() => {
      setTheme((current) => {
         const next = current === "dark" ? "light" : "dark";
         document.documentElement.dataset.theme = next;
         localStorage.setItem("e3-theme", next);
         updateFavicon(next);
         return next;
      });
   }, []);

   return (
      <ThemeContext.Provider value={{ theme, toggleTheme }}>
         {children}
      </ThemeContext.Provider>
   );
}

export function useTheme() {
   const context = useContext(ThemeContext);
   if (!context) {
      throw new Error("useTheme must be used within a ThemeProvider");
   }
   return context;
}
