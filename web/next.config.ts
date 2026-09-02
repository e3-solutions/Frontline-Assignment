import type { NextConfig } from "next";

const nextConfig: NextConfig = {
   output: "standalone",
   async redirects() {
      return [
         {
            source: "/forms",
            destination: "/",
            permanent: false,
         },
      ];
   },
};

export default nextConfig;
