"use client";

import Image from "next/image";
import { useTheme } from "@/src/contexts/ThemeContext";

type ThemedLogoProps = {
   width: number;
   height: number;
   className?: string;
   priority?: boolean;
};

export function ThemedLogo({ width, height, className, priority }: ThemedLogoProps) {
   const { theme } = useTheme();
   const src = theme === "light"
      ? "/designs/source/e3-logo-light-mode.svg"
      : "/designs/source/e3-logo.svg";

   return (
      <Image
         src={src}
         alt="E3 Group"
         width={width}
         height={height}
         priority={priority}
         className={className}
      />
   );
}
