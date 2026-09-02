"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { geocodeLocation, type Coordinates } from "@/src/utils/geocode";

const createCustomIcon = (colorHex: string) => {
   if (typeof window === "undefined") return undefined as any;
   return L.divIcon({
      className: "custom-map-blip",
      html: `<div style="width: 14px; height: 14px; background-color: ${colorHex}; border: 2px solid white; border-radius: 50%; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
      iconSize: [14, 14],
      iconAnchor: [7, 7],
   });
};

const originIcon = createCustomIcon("#f43f5e"); // rose-500
const destIcon = createCustomIcon("#10b981"); // emerald-500

function MapBoundsFitter({ bounds }: { bounds: L.LatLngBounds }) {
   const map = useMap();
   useEffect(() => {
      if (bounds.isValid()) {
         map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
      }
   }, [map, bounds]);
   return null;
}

type LoadMapProps = {
   origin: string | null;
   destination: string | null;
};

export default function LoadMap({ origin, destination }: LoadMapProps) {
   const [originCoords, setOriginCoords] = useState<Coordinates | null>(null);
   const [destCoords, setDestCoords] = useState<Coordinates | null>(null);
   const [isLoading, setIsLoading] = useState(true);

   useEffect(() => {
      const controller = new AbortController();
      setIsLoading(true);

      async function fetchCoords() {
         const [orig, dest] = await Promise.all([
            origin ? geocodeLocation(origin, controller.signal) : Promise.resolve(null),
            destination ? geocodeLocation(destination, controller.signal) : Promise.resolve(null),
         ]);

         if (!controller.signal.aborted) {
            setOriginCoords(orig);
            setDestCoords(dest);
            setIsLoading(false);
         }
      }

      fetchCoords();

      return () => {
         controller.abort();
      };
   }, [origin, destination]);

   if (isLoading) {
      return (
         <div className="flex h-48 w-full items-center justify-center rounded-xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)]">
            <p className="text-sm text-[color:var(--e3-text-muted)] e3-font-mono animate-pulse">Loading map...</p>
         </div>
      );
   }

   if (!originCoords && !destCoords) {
      return (
         <div className="flex h-48 w-full items-center justify-center rounded-xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)]">
            <p className="text-sm text-[color:var(--e3-text-muted)] e3-font-body">Map data unavailable.</p>
         </div>
      );
   }

   // Default to geographic center of USA if only one coord is available
   const center: [number, number] = originCoords
      ? [originCoords.lat, originCoords.lng]
      : destCoords
      ? [destCoords.lat, destCoords.lng]
      : [39.8283, -98.5795];

   const bounds = new L.LatLngBounds([]);
   if (originCoords) bounds.extend([originCoords.lat, originCoords.lng]);
   if (destCoords) bounds.extend([destCoords.lat, destCoords.lng]);

   const polylinePositions: [number, number][] = [];
   if (originCoords) polylinePositions.push([originCoords.lat, originCoords.lng]);
   if (destCoords) polylinePositions.push([destCoords.lat, destCoords.lng]);

   return (
      <div className="h-48 w-full overflow-hidden rounded-xl border border-[color:var(--e3-border-soft)] z-0 relative">
         <MapContainer center={center} zoom={4} scrollWheelZoom={false} className="h-full w-full">
            <TileLayer
               attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
               url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            />
            {originCoords && <Marker position={[originCoords.lat, originCoords.lng]} icon={originIcon} title="Origin" />}
            {destCoords && <Marker position={[destCoords.lat, destCoords.lng]} icon={destIcon} title="Destination" />}
            {polylinePositions.length === 2 && (
               <Polyline positions={polylinePositions} color="var(--e3-brand-lavender, #8b5cf6)" weight={3} dashArray="5, 10" />
            )}
            {bounds.isValid() && <MapBoundsFitter bounds={bounds} />}
         </MapContainer>
      </div>
   );
}
