"use client";

import { useMemo, useState } from "react";

import {
   ActionPill,
   CopyButton,
   Modal,
   PlayIcon,
   SpacedTable,
   SpacedTableBody,
   SpacedTableCell,
   SpacedTableHead,
   SpacedTableHeader,
   SpacedTableRow,
   StatusChip,
   cx,
   InfoCard,
   formatConsoleDateTime,
   formatCurrency,
   formatDate,
   formatDateTime,
} from "@e3-solutions/ui";
import { LoadAnalyticsSection } from "@/src/components/analytics/LoadAnalyticsSection";
import { AudioPlayerModal } from "@/src/components/dashboard/AudioPlayerModal";
import type { CallRecord, LoadRecord } from "@/src/types/dashboard";

type LoadModalProps = {
   load: LoadRecord | null;
   calls: CallRecord[];
   isOpen: boolean;
   onClose: () => void;
};

const negotiationStatusConfig = {
   success: {
      label: "Agreement",
      chipTone: "success" as const,
      accentText: "text-[color:var(--e3-chip-success-text)]",
   },
   bid: {
      label: "Bid",
      chipTone: "violet" as const,
      accentText: "text-[color:var(--e3-chip-violet-text)]",
   },
   no_agreement: {
      label: "No Agreement",
      chipTone: "amber" as const,
      accentText: "text-[color:var(--e3-chip-amber-text)]",
   },
   error: {
      label: "Error",
      chipTone: "rose" as const,
      accentText: "text-[color:var(--e3-chip-rose-text)]",
   },
};

export function LoadModal({ load, calls, isOpen, onClose }: LoadModalProps) {
   const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
   const [recordingTitle, setRecordingTitle] = useState<string>("");

   const callsMap = useMemo(() => {
      const map = new Map<string, CallRecord>();
      calls.forEach((call) => {
         map.set(call.id, call);
      });
      return map;
   }, [calls]);

   if (!load) return null;

   const hasLoadInfo = Boolean(
      load.data?.origin ||
         load.data?.destination ||
         load.data?.pickupDate ||
         load.data?.dropoffDate ||
         load.data?.pickupTime ||
         load.data?.equipment ||
         load.data?.weight ||
         load.data?.customer ||
         load.data?.requirements ||
         load.data?.trackerRequired !== undefined
   );

   const sortedNegotiations = [...load.negotiations].sort(
      (left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
   );

   const getRecordingUrl = (callId: string | undefined): string | null => {
      if (!callId) return null;
      const call = callsMap.get(callId);
      return call?.result?.audio_url || null;
   };

   return (
      <Modal isOpen={isOpen} onClose={onClose}>
         <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-[color:var(--e3-divider)] bg-[color:var(--e3-shell)] p-6 backdrop-blur-md">
            <div className="space-y-1">
               <p className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--e3-text-soft)] e3-font-mono">
                  Load Details
               </p>
               <h2 className="text-3xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                  {load.loadId}
               </h2>
               <p className="text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                  {load.data?.origin || "N/A"}
                  <span className="mx-2 text-[color:var(--e3-text-soft)]">→</span>
                  {load.data?.destination || "N/A"}
               </p>
            </div>
            <button
               type="button"
               onClick={onClose}
               className="rounded-2xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] p-2.5 text-[color:var(--e3-text-muted)] transition-all hover:border-[color:var(--e3-border-strong)] hover:bg-[color:var(--e3-surface-alt)] hover:text-[color:var(--e3-text-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--e3-brand-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--e3-shell)]"
               aria-label="Close modal"
            >
               <svg
                  viewBox="0 0 24 24"
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
               >
                  <path d="M18 6L6 18M6 6l12 12" />
               </svg>
            </button>
         </div>

         <div className="space-y-6 p-6">
            {hasLoadInfo ? (
               <div className="space-y-4 border-b border-[color:var(--e3-divider)] pb-6">
                  <h3 className="text-xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                     Load Information
                  </h3>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                     {load.data?.origin ? (
                        <InfoCard label="Pickup Address" value={load.data.origin} />
                     ) : null}
                     {load.data?.destination ? (
                        <InfoCard label="Delivery Address" value={load.data.destination} />
                     ) : null}
                     {load.data?.pickupDate ? (
                        <InfoCard label="Pickup Date" value={formatDate(load.data.pickupDate)} />
                     ) : null}
                     {load.data?.dropoffDate ? (
                        <InfoCard label="Delivery Date" value={formatDate(load.data.dropoffDate)} />
                     ) : null}
                     {load.data?.pickupTime ? (
                        <InfoCard
                           label="Pickup Time"
                           value={formatDateTime(load.data.pickupTime)}
                        />
                     ) : null}
                     {load.data?.equipment ? (
                        <InfoCard label="Equipment" value={load.data.equipment} />
                     ) : null}
                     {load.data?.weight ? (
                        <InfoCard label="Weight" value={load.data.weight} />
                     ) : null}
                     {load.data?.customer ? (
                        <InfoCard label="Customer" value={load.data.customer} />
                     ) : null}
                     {load.data?.trackerRequired !== undefined ? (
                        <InfoCard
                           label="Tracker"
                           value={
                              <span
                                 className={cx(
                                    "rounded-full border px-2.5 py-1 text-xs font-medium e3-font-body",
                                    load.data.trackerRequired
                                       ? "border-[color:var(--e3-chip-sky-border)] bg-[color:var(--e3-chip-sky-bg)] text-[color:var(--e3-chip-sky-text)]"
                                       : "border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] text-[color:var(--e3-text-muted)]"
                                 )}
                              >
                                 {load.data.trackerRequired ? "Required" : "Not Required"}
                              </span>
                           }
                        />
                     ) : null}
                     {load.data?.requirements ? (
                        <InfoCard label="Requirements" value={load.data.requirements} fullWidth />
                     ) : null}
                  </div>
               </div>
            ) : null}

            <LoadAnalyticsSection load={load} calls={calls} />

            <div className="space-y-4 border-t border-[color:var(--e3-divider)] pt-6">
               <div className="flex items-center justify-between">
                  <h3 className="text-xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                     Negotiations
                  </h3>
                  <span className="text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                     {load.negotiations.length} total
                  </span>
               </div>

               {load.negotiations.length === 0 ? (
                  <div className="flex min-h-[120px] items-center justify-center rounded-[22px] border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)]">
                     <p className="text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                        No negotiations recorded yet.
                     </p>
                  </div>
               ) : (
                  <div className="rounded-[22px] border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface)] p-4">
                     <SpacedTable spacing="sm">
                        <SpacedTableHeader>
                           <tr>
                              <SpacedTableHead className="w-[4%]">#</SpacedTableHead>
                              <SpacedTableHead className="w-[13%]">Status</SpacedTableHead>
                              <SpacedTableHead className="w-[11%]">Price</SpacedTableHead>
                              <SpacedTableHead className="w-[14%]">Contact</SpacedTableHead>
                              <SpacedTableHead className="w-[16%]">Date</SpacedTableHead>
                              <SpacedTableHead className="w-[20%]">Notes</SpacedTableHead>
                              <SpacedTableHead className="w-[22%] text-center">Actions</SpacedTableHead>
                           </tr>
                        </SpacedTableHeader>
                        <SpacedTableBody>
                           {sortedNegotiations.map((negotiation, index) => {
                              const negotiationRecordingUrl = getRecordingUrl(negotiation.callId);
                              const displayStatus = (
                                 negotiation.aboveMax ? "bid" : negotiation.status
                              ) as keyof typeof negotiationStatusConfig;
                              const statusConfig = negotiationStatusConfig[displayStatus] ?? { label: displayStatus, chipTone: "amber" as const, accentText: "text-[color:var(--e3-text-muted)]" };

                              return (
                                 <SpacedTableRow key={negotiation.id}>
                                    <SpacedTableCell position="first" className="pl-3">
                                       <span className="text-xs text-[color:var(--e3-text-soft)] e3-font-mono">
                                          {sortedNegotiations.length - index}
                                       </span>
                                    </SpacedTableCell>
                                    <SpacedTableCell>
                                       <StatusChip label={statusConfig.label} tone={statusConfig.chipTone} />
                                    </SpacedTableCell>
                                    <SpacedTableCell>
                                       <span className={cx(
                                          "text-sm font-semibold e3-font-heading",
                                          negotiation.agreedPrice
                                             ? statusConfig.accentText
                                             : "text-[color:var(--e3-text-muted)]"
                                       )}>
                                          {negotiation.agreedPrice
                                             ? formatCurrency(negotiation.agreedPrice)
                                             : "—"}
                                       </span>
                                    </SpacedTableCell>
                                    <SpacedTableCell>
                                       {negotiation.aboveMax && negotiation.carrierContactName ? (
                                          <div className="min-w-0">
                                             <p className="truncate text-sm text-[color:var(--e3-text-strong)] e3-font-body">
                                                {negotiation.carrierContactName}
                                             </p>
                                             {negotiation.carrierContactPhone ? (
                                                <p className="truncate pt-0.5 text-xs text-[color:var(--e3-text-muted)] e3-font-mono">
                                                   {negotiation.carrierContactPhone}
                                                </p>
                                             ) : null}
                                          </div>
                                       ) : (
                                          <span className="text-sm text-[color:var(--e3-text-muted)]">—</span>
                                       )}
                                    </SpacedTableCell>
                                    <SpacedTableCell>
                                       <span className="text-xs text-[color:var(--e3-text-muted)] e3-font-mono" suppressHydrationWarning>
                                          {formatConsoleDateTime(negotiation.createdAt)}
                                       </span>
                                    </SpacedTableCell>
                                    <SpacedTableCell>
                                       <p className="truncate text-sm text-[color:var(--e3-text-muted)] e3-font-body" title={negotiation.notes || undefined}>
                                          {negotiation.notes || "—"}
                                       </p>
                                    </SpacedTableCell>
                                    <SpacedTableCell position="last">
                                       <div className="flex items-center justify-center gap-2 whitespace-nowrap">
                                          {negotiationRecordingUrl ? (
                                             <ActionPill
                                                label="Play"
                                                icon={<PlayIcon />}
                                                tone="neutral"
                                                onClick={() => {
                                                   setRecordingUrl(negotiationRecordingUrl);
                                                   setRecordingTitle(`Negotiation #${sortedNegotiations.length - index}`);
                                                }}
                                             />
                                          ) : null}
                                          <CopyButton value={negotiation.id} label="Copy ID" />
                                       </div>
                                    </SpacedTableCell>
                                 </SpacedTableRow>
                              );
                           })}
                        </SpacedTableBody>
                     </SpacedTable>
                  </div>
               )}
            </div>
         </div>

         {recordingUrl ? (
            <AudioPlayerModal
               isOpen
               onClose={() => {
                  setRecordingUrl(null);
                  setRecordingTitle("");
               }}
               src={recordingUrl}
               title={recordingTitle}
               description={load.loadId ? `Load ${load.loadId}` : undefined}
            />
         ) : null}
      </Modal>
   );
}
