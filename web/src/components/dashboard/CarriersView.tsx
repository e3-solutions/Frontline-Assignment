"use client";

import { useDeferredValue, useMemo, useState } from "react";

import {
   Input,
   MailIcon,
   PhoneIcon,
   SearchIcon,
   SpacedTable,
   SpacedTableBody,
   SpacedTableCell,
   SpacedTableHead,
   SpacedTableHeader,
   SpacedTableRow,
   StatusChip,
   TableEmptyState,
   formatConsoleDateTime,
   formatCurrency,
} from "@e3-solutions/ui";
import type { CallRecord, EmailRecord, LoadRecord } from "@/src/types/dashboard";
import { fuzzySearch } from "@/src/utils/search";

type CarrierRecord = {
   name: string;
   phone: string;
   email: string;
   totalCalls: number;
   totalEmails: number;
   agreements: number;
   bids: number;
   avgPrice: number;
   lastActive: string;
   loadIds: string[];
};

function aggregateCarriers(calls: CallRecord[], loads: LoadRecord[], emails: EmailRecord[]): CarrierRecord[] {
   const carrierMap = new Map<string, CarrierRecord>();
   const allNegotiations = loads.flatMap((load) =>
      load.negotiations.map((n) => ({ ...n, loadId: load.loadId }))
   );

   const makeCarrier = (key: string): CarrierRecord => ({
      name: "",
      phone: "",
      email: "",
      totalCalls: 0,
      totalEmails: 0,
      agreements: 0,
      bids: 0,
      avgPrice: 0,
      lastActive: "",
      loadIds: [],
   });

   // Group by caller phone number from calls
   for (const call of calls) {
      const key = call.callerNumber;
      const carrier = carrierMap.get(key) ?? makeCarrier(key);
      carrier.phone = key;
      carrier.totalCalls++;
      if (!carrier.lastActive || new Date(call.initiatedAt) > new Date(carrier.lastActive)) {
         carrier.lastActive = call.initiatedAt;
      }
      if (!carrier.loadIds.includes(call.loadId)) {
         carrier.loadIds.push(call.loadId);
      }
      carrierMap.set(key, carrier);
   }

   // Build a map from callId -> callerNumber so we can link negotiations to carriers
   const callIdToPhone = new Map<string, string>();
   for (const call of calls) {
      callIdToPhone.set(call.id, call.callerNumber);
   }

   // Enrich with call negotiation data — match via callId, not phone number
   for (const neg of allNegotiations) {
      const phone = neg.callId ? callIdToPhone.get(neg.callId) : null;
      if (!phone) continue;

      const carrier = carrierMap.get(phone);
      if (!carrier) continue;

      if (neg.carrierContactName && !carrier.name) {
         carrier.name = neg.carrierContactName;
      }
      if (neg.aboveMax) {
         carrier.bids++;
      } else if (neg.agreedPrice && neg.agreedPrice > 0) {
         carrier.agreements++;
      }
   }

   // Add email carriers — try to match by name, otherwise create new entry
   for (const em of emails) {
      const emailKey = em.carrierEmail;
      // Check if this email carrier already exists (by matching name from negotiation)
      let matched = false;
      if (em.negotiation?.carrierContactPhone) {
         for (const [, carrier] of carrierMap) {
            if (carrier.phone && (carrier.phone.includes(em.negotiation.carrierContactPhone) || em.negotiation.carrierContactPhone.includes(carrier.phone.replace(/\D/g, "")))) {
               carrier.totalEmails++;
               carrier.email = emailKey;
               if (em.negotiation.carrierContactName && !carrier.name) {
                  carrier.name = em.negotiation.carrierContactName;
               }
               if (em.loadId && !carrier.loadIds.includes(em.loadId)) {
                  carrier.loadIds.push(em.loadId);
               }
               if (!carrier.lastActive || new Date(em.updatedAt) > new Date(carrier.lastActive)) {
                  carrier.lastActive = em.updatedAt;
               }
               if (em.negotiation.aboveMax) {
                  carrier.bids++;
               } else if (em.negotiation.agreedPrice != null && em.negotiation.agreedPrice > 0) {
                  carrier.agreements++;
               }
               matched = true;
               break;
            }
         }
      }

      if (!matched) {
         const carrier = carrierMap.get(emailKey) ?? makeCarrier(emailKey);
         carrier.email = emailKey;
         carrier.totalEmails++;
         if (em.negotiation?.carrierContactName) {
            carrier.name = em.negotiation.carrierContactName;
         }
         if (em.negotiation?.carrierContactPhone) {
            carrier.phone = em.negotiation.carrierContactPhone;
         }
         if (em.loadId && !carrier.loadIds.includes(em.loadId)) {
            carrier.loadIds.push(em.loadId);
         }
         if (!carrier.lastActive || new Date(em.updatedAt) > new Date(carrier.lastActive)) {
            carrier.lastActive = em.updatedAt;
         }
         if (em.negotiation) {
            if (em.negotiation.aboveMax) {
               carrier.bids++;
            } else if (em.negotiation.agreedPrice != null && em.negotiation.agreedPrice > 0) {
               carrier.agreements++;
            }
         }
         carrierMap.set(emailKey, carrier);
      }
   }

   // Calculate avg price from all sources — use callId matching for calls
   for (const [key, carrier] of carrierMap) {
      const callPrices = allNegotiations
         .filter((n) => n.agreedPrice && n.agreedPrice > 0 && n.callId && callIdToPhone.get(n.callId) === key)
         .map((n) => n.agreedPrice!);
      const emailPrices = emails
         .filter((e) => e.carrierEmail === carrier.email && e.negotiation?.agreedPrice && e.negotiation.agreedPrice > 0)
         .map((e) => e.negotiation!.agreedPrice!);
      const allPrices = [...callPrices, ...emailPrices];
      carrier.avgPrice = allPrices.length > 0 ? allPrices.reduce((a, b) => a + b, 0) / allPrices.length : 0;
   }

   return Array.from(carrierMap.values()).sort((a, b) => (b.totalCalls + b.totalEmails) - (a.totalCalls + a.totalEmails));
}

type CarriersViewProps = {
   calls: CallRecord[];
   loads: LoadRecord[];
   emails: EmailRecord[];
};

export function CarriersView({ calls, loads, emails }: CarriersViewProps) {
   const [query, setQuery] = useState("");
   const deferredQuery = useDeferredValue(query);

   const carriers = useMemo(() => aggregateCarriers(calls, loads, emails), [calls, loads, emails]);

   const filtered = useMemo(() => {
      if (!deferredQuery.trim()) return carriers;
      return fuzzySearch(carriers, deferredQuery, (c) => `${c.name} ${c.phone}`);
   }, [carriers, deferredQuery]);

   return (
      <div className="space-y-6">
         <header className="flex items-start justify-between">
            <div>
               <h1 className="text-3xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                  Carriers
               </h1>
               <p className="mt-1 text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                  {carriers.length} unique carriers from calls &amp; emails
               </p>
            </div>
         </header>

         <div className="max-w-md">
            <Input
               value={query}
               onChange={(e) => setQuery(e.target.value)}
               placeholder="Search by name or phone..."
               iconLeft={<SearchIcon className="h-4 w-4" />}
            />
         </div>

         {filtered.length === 0 ? (
            <TableEmptyState
               title={carriers.length === 0 ? "No carriers found" : "No carriers match your search"}
               description={carriers.length === 0 ? "Carriers will appear here after calls are received." : "Try a different search term."}
            />
         ) : (
            <div className="rounded-[22px] border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface)] p-4">
               <SpacedTable spacing="sm">
                  <SpacedTableHeader>
                     <tr>
                        <SpacedTableHead className="w-[22%]">Carrier</SpacedTableHead>
                        <SpacedTableHead className="w-[18%]">Contact</SpacedTableHead>
                        <SpacedTableHead className="w-[12%]">Activity</SpacedTableHead>
                        <SpacedTableHead className="w-[10%]">Agreements</SpacedTableHead>
                        <SpacedTableHead className="w-[10%]">Bids</SpacedTableHead>
                        <SpacedTableHead className="w-[12%]">Avg Price</SpacedTableHead>
                        <SpacedTableHead className="w-[16%]">Last Active</SpacedTableHead>
                     </tr>
                  </SpacedTableHeader>
                  <SpacedTableBody>
                     {filtered.map((carrier) => (
                        <SpacedTableRow key={carrier.phone || carrier.email || carrier.name}>
                           <SpacedTableCell position="first" className="pl-3">
                              <p className="text-sm font-medium text-[color:var(--e3-text-strong)] e3-font-body">
                                 {carrier.name || "Unknown"}
                              </p>
                              <p className="text-xs text-[color:var(--e3-text-soft)] e3-font-mono">
                                 {carrier.loadIds.length} load{carrier.loadIds.length !== 1 ? "s" : ""}
                              </p>
                           </SpacedTableCell>
                           <SpacedTableCell>
                              <div className="min-w-0">
                                 {carrier.phone && (
                                    <p className="truncate text-sm text-[color:var(--e3-text-muted)] e3-font-mono">
                                       {carrier.phone}
                                    </p>
                                 )}
                                 {carrier.email && (
                                    <p className="truncate text-xs text-[color:var(--e3-text-soft)] e3-font-mono">
                                       {carrier.email}
                                    </p>
                                 )}
                                 {!carrier.phone && !carrier.email && (
                                    <span className="text-sm text-[color:var(--e3-text-muted)]">—</span>
                                 )}
                              </div>
                           </SpacedTableCell>
                           <SpacedTableCell>
                              <div className="flex items-center gap-2 text-sm e3-font-mono">
                                 {carrier.totalCalls > 0 && (
                                    <span className="flex items-center gap-1 text-[color:var(--e3-text-strong)]" title="Calls">
                                       <PhoneIcon className="h-3.5 w-3.5 text-[color:var(--e3-text-soft)]" />
                                       {carrier.totalCalls}
                                    </span>
                                 )}
                                 {carrier.totalEmails > 0 && (
                                    <span className="flex items-center gap-1 text-[color:var(--e3-text-strong)]" title="Emails">
                                       <MailIcon className="h-3.5 w-3.5 text-[color:var(--e3-text-soft)]" />
                                       {carrier.totalEmails}
                                    </span>
                                 )}
                                 {carrier.totalCalls === 0 && carrier.totalEmails === 0 && (
                                    <span className="text-[color:var(--e3-text-muted)]">—</span>
                                 )}
                              </div>
                           </SpacedTableCell>
                           <SpacedTableCell>
                              {carrier.agreements > 0 ? (
                                 <StatusChip label={String(carrier.agreements)} tone="success" />
                              ) : (
                                 <span className="text-sm text-[color:var(--e3-text-muted)]">0</span>
                              )}
                           </SpacedTableCell>
                           <SpacedTableCell>
                              {carrier.bids > 0 ? (
                                 <StatusChip label={String(carrier.bids)} tone="violet" />
                              ) : (
                                 <span className="text-sm text-[color:var(--e3-text-muted)]">0</span>
                              )}
                           </SpacedTableCell>
                           <SpacedTableCell>
                              <span className="text-sm font-semibold text-[color:var(--e3-accent-lime)] e3-font-mono">
                                 {carrier.avgPrice > 0 ? formatCurrency(carrier.avgPrice) : "—"}
                              </span>
                           </SpacedTableCell>
                           <SpacedTableCell position="last">
                              <span className="text-xs text-[color:var(--e3-text-muted)] e3-font-mono" suppressHydrationWarning>
                                 {formatConsoleDateTime(carrier.lastActive)}
                              </span>
                           </SpacedTableCell>
                        </SpacedTableRow>
                     ))}
                  </SpacedTableBody>
               </SpacedTable>
            </div>
         )}
      </div>
   );
}
