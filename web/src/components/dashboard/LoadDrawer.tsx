"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import {
   ActionPill,
   CloseIcon,
   CopyButton,
   DownloadIcon,
   MailIcon,
   PhoneIcon,
   PlayIcon,
   TranscriptDotIcon,
   SpacedTable,
   SpacedTableBody,
   SpacedTableCell,
   SpacedTableHead,
   SpacedTableHeader,
   SpacedTableRow,
   StatusChip,
   cx,
   formatConsoleDateTime,
   formatCurrency,
   formatDate,
   formatDateTime,
} from "@e3-solutions/ui";
import dynamic from "next/dynamic";
import { LoadAnalyticsSection } from "@/src/components/analytics/LoadAnalyticsSection";

const DynamicLoadMap = dynamic(() => import("@/src/components/dashboard/LoadMap"), {
   ssr: false,
});
import { CallReviewModal } from "@/src/components/dashboard/CallReviewModal";
import { EmailThreadModal } from "@/src/components/dashboard/EmailThreadModal";
import type { CallRecord, EmailRecord, LoadRecord, TranscriptMessage } from "@/src/types/dashboard";

type LoadDrawerProps = {
   load: LoadRecord | null;
   calls: CallRecord[];
   emails: EmailRecord[];
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

function KV({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
   return (
      <div>
         <p className="text-xs uppercase tracking-[0.12em] text-[color:var(--e3-text-soft)] e3-font-mono">{label}</p>
         <p className={cx("mt-1 text-base e3-font-body", bold ? "font-bold text-[color:var(--e3-text-strong)]" : "text-[color:var(--e3-text-strong)]")}>
            {value}
         </p>
      </div>
   );
}

type NegSort = "date_desc" | "date_asc" | "price_desc" | "price_asc";

export function LoadDrawer({ load, calls, emails, isOpen, onClose }: LoadDrawerProps) {
   const [reviewCallData, setReviewCallData] = useState<{
      audioUrl?: string;
      transcription?: TranscriptMessage[];
      callerNumber: string;
      agreedPrice?: number;
   } | null>(null);
   const [selectedEmail, setSelectedEmail] = useState<EmailRecord | null>(null);
   const [negSort, setNegSort] = useState<NegSort>("date_desc");
   const [mounted, setMounted] = useState(false);

   useEffect(() => {
      if (isOpen) {
         // Delay to trigger CSS transition
         requestAnimationFrame(() => setMounted(true));
         document.body.style.overflow = "hidden";
      } else {
         setMounted(false);
         document.body.style.overflow = "";
      }
      return () => {
         document.body.style.overflow = "";
      };
   }, [isOpen]);

   useEffect(() => {
      if (!isOpen) return;
      const handleKey = (e: KeyboardEvent) => {
         if (e.key === "Escape") onClose();
      };
      document.addEventListener("keydown", handleKey);
      return () => document.removeEventListener("keydown", handleKey);
   }, [isOpen, onClose]);

   const callsMap = useMemo(() => {
      const map = new Map<string, CallRecord>();
      calls.forEach((call) => map.set(call.id, call));
      return map;
   }, [calls]);

   if (!isOpen) return null;

   const getRecordingUrl = (callId: string | undefined): string | null => {
      if (!callId) return null;
      return callsMap.get(callId)?.result?.audio_url || null;
   };

   const getTranscript = (callId: string | undefined) => {
      if (!callId) return null;
      const call = callsMap.get(callId);
      if (!call?.result?.transcription?.length) return null;
      return { messages: call.result.transcription, caller: call.callerNumber };
   };

   // Build unified bids list: call negotiations + email negotiations
   type UnifiedBid = {
      id: string;
      source: "call" | "email";
      carrierName: string | null;
      carrierContact: string | null; // phone or email
      agreedPrice: number | null;
      aboveMax: boolean;
      status: "success" | "no_agreement" | "error";
      createdAt: string;
      // call-specific
      callId?: string;
      // email-specific
      email?: EmailRecord;
   };

   const loadEmails = load ? emails.filter((e) => e.loadId === load.loadId) : [];

   const unifiedBids: UnifiedBid[] = [];

   // Build a map of negotiation ID -> email thread for linking
   const negIdToEmail = new Map<string, EmailRecord>();
   for (const e of loadEmails) {
      if (e.negotiation) {
         // The email_thread.negotiations join uses the same negotiation IDs
         // Find which negotiation row belongs to this email thread
         for (const n of load?.negotiations ?? []) {
            if (!n.callId && n.carrierContactName === e.negotiation.carrierContactName
               && n.agreedPrice === e.negotiation.agreedPrice) {
               negIdToEmail.set(n.id, e);
            }
         }
      }
   }

   if (load) {
      for (const n of load.negotiations) {
         const isEmail = !n.callId;
         const linkedEmail = negIdToEmail.get(n.id);
         unifiedBids.push({
            id: n.id,
            source: isEmail ? "email" : "call",
            carrierName: n.carrierContactName ?? (linkedEmail?.carrierEmail ?? null),
            carrierContact: isEmail ? (linkedEmail?.carrierEmail ?? n.carrierContactPhone ?? null) : (n.carrierContactPhone ?? null),
            agreedPrice: n.agreedPrice ?? null,
            aboveMax: n.aboveMax ?? false,
            status: n.status,
            createdAt: n.createdAt,
            callId: n.callId,
            email: linkedEmail,
         });
      }
   }

   const sortedBids = [...unifiedBids].sort((left, right) => {
      switch (negSort) {
         case "price_desc":
            return (right.agreedPrice ?? 0) - (left.agreedPrice ?? 0);
         case "price_asc":
            return (left.agreedPrice ?? 0) - (right.agreedPrice ?? 0);
         case "date_asc":
            return new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime();
         case "date_desc":
         default:
            return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime();
      }
   });

   return createPortal(
      <div className="fixed inset-0 z-50 flex">
         {/* Backdrop */}
         <div
            className={cx(
               "absolute inset-0 bg-[color:rgba(4,2,10,0.5)] transition-opacity duration-300",
               mounted ? "opacity-100" : "opacity-0"
            )}
            onClick={onClose}
         />

         {/* Drawer panel */}
         <div
            className={cx(
               "scrollbar-custom ml-auto relative flex h-full w-full max-w-[572px] flex-col overflow-y-auto border-l border-[color:var(--e3-border-soft)] bg-[color:var(--e3-shell)] shadow-[0_0_60px_rgba(4,2,10,0.4)] transition-transform duration-300 ease-out",
               mounted ? "translate-x-0" : "translate-x-full"
            )}
         >
            {load && (
               <>
                  {/* Header */}
                  <div className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-[color:var(--e3-divider)] bg-[color:var(--e3-shell)] px-5 py-4">
                     <div className="flex items-center gap-3">
                        <div className="h-3 w-3 rounded-full bg-[color:var(--e3-chip-success-text)]" />
                        <h2 className="text-xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                           {load.loadId}
                        </h2>
                     </div>
                     <button
                        type="button"
                        onClick={onClose}
                        className="shrink-0 text-[color:var(--e3-text-muted)] transition-colors hover:text-[color:var(--e3-text-strong)]"
                        aria-label="Close drawer"
                     >
                        <CloseIcon className="h-5 w-5" />
                     </button>
                  </div>

                  {/* Content */}
                  <div className="p-5 space-y-5">
                     {/* Key-value grid — compact FleetWorks style */}
                     <div className="grid grid-cols-4 gap-x-4 gap-y-3 border-b border-[color:var(--e3-divider)] pb-5">
                        <KV label="Equipment" value={load.data?.equipment || "—"} />
                        <KV label="Weight" value={load.data?.weight || "—"} />
                        <KV label="Customer" value={load.data?.customer || "—"} />
                        <KV label="Tracker" value={load.data?.trackerRequired ? "Required" : "No"} />
                        {load.data?.requirements && (
                           <div className="col-span-4">
                              <KV label="Requirements" value={load.data.requirements} />
                           </div>
                        )}
                     </div>

                     {/* Route */}
                     {(load.data?.origin || load.data?.destination) && (
                        <div className="border-b border-[color:var(--e3-divider)] pb-5">
                           <p className="mb-3 text-xs uppercase tracking-[0.12em] text-[color:var(--e3-text-soft)] e3-font-mono">
                              Route
                           </p>
                           <div className="relative pl-6 space-y-6">
                              {/* Vertical Line */}
                              <div className="absolute left-[11px] top-6 bottom-6 w-0.5 bg-[color:var(--e3-border-soft)]" />
                              
                              {/* Origin */}
                              <div className="relative">
                                 <div className="absolute -left-[29px] top-1.5 h-3 w-3 rounded-full border-2 border-[color:var(--e3-shell)] bg-[color:var(--e3-chip-rose-text)] shadow-sm" />
                                 <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[color:var(--e3-chip-rose-text)] e3-font-mono mb-1">
                                    Pickup
                                 </p>
                                 <p className="text-[15px] font-medium text-[color:var(--e3-text-strong)] e3-font-body leading-snug max-w-[90%]">
                                    {load.data?.origin || "—"}
                                 </p>
                                 <p className="mt-1 text-sm text-[color:var(--e3-text-muted)] e3-font-mono">
                                    {load.data?.pickupDate ? formatDate(load.data.pickupDate) : "TBD"}
                                    {load.data?.pickupTime ? ` · ${formatDateTime(load.data.pickupTime)}` : ""}
                                 </p>
                              </div>

                              {/* Destination */}
                              <div className="relative">
                                 <div className="absolute -left-[29px] top-1.5 h-3 w-3 rounded-full border-2 border-[color:var(--e3-shell)] bg-[color:var(--e3-chip-success-text)] shadow-sm" />
                                 <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[color:var(--e3-chip-success-text)] e3-font-mono mb-1">
                                    Dropoff
                                 </p>
                                 <p className="text-[15px] font-medium text-[color:var(--e3-text-strong)] e3-font-body leading-snug max-w-[90%]">
                                    {load.data?.destination || "—"}
                                 </p>
                                 <p className="mt-1 text-sm text-[color:var(--e3-text-muted)] e3-font-mono">
                                    {load.data?.dropoffDate ? formatDate(load.data.dropoffDate) : "TBD"}
                                 </p>
                              </div>
                           </div>

                           <div className="mt-5">
                              <DynamicLoadMap origin={load.data?.origin ?? null} destination={load.data?.destination ?? null} />
                           </div>
                        </div>
                     )}

                     {/* Pricing — single row */}
                     {load.data?.pricing && (
                        <div className="grid grid-cols-4 gap-x-4 border-b border-[color:var(--e3-divider)] pb-5">
                           <KV label="Book Now" value={formatCurrency(load.data.pricing.target)} bold />
                           <KV label="Start" value={formatCurrency(load.data.pricing.initial)} />
                           <KV label="Max" value={formatCurrency(load.data.pricing.ceiling)} />
                           <KV label="Customer Rate" value={formatCurrency(load.data.pricing.target)} />
                        </div>
                     )}

                     {/* Analytics */}
                     <LoadAnalyticsSection load={load} calls={calls} emails={emails} />

                     {/* Bids — unified call + email negotiations */}
                     <div className="space-y-3 border-t border-[color:var(--e3-divider)] pt-5">
                        <div className="flex items-center justify-between">
                           <h3 className="text-base font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                              Bids
                           </h3>
                           <span className="text-xs text-[color:var(--e3-text-muted)] e3-font-mono">
                              {sortedBids.length} total
                           </span>
                        </div>

                        {sortedBids.length === 0 ? (
                           <p className="py-6 text-center text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                              No bids recorded yet.
                           </p>
                        ) : (
                           <div className="space-y-2">
                              {sortedBids.map((bid) => {
                                 const displayStatus = (
                                    bid.aboveMax ? "bid" : bid.status
                                 ) as keyof typeof negotiationStatusConfig;
                                 const statusConfig = negotiationStatusConfig[displayStatus] ?? {
                                    label: displayStatus,
                                    chipTone: "amber" as const,
                                    accentText: "text-[color:var(--e3-text-muted)]",
                                 };
                                 const recordingUrl = bid.source === "call" ? getRecordingUrl(bid.callId) : null;
                                 const transcript = bid.source === "call" ? getTranscript(bid.callId) : null;

                                 return (
                                    <div
                                       key={bid.id}
                                       className="flex items-center justify-between gap-3 rounded-xl border border-[color:var(--e3-border-subtle)] bg-[color:var(--e3-surface-soft)] px-4 py-3"
                                    >
                                       <div className="flex items-center gap-3 min-w-0">
                                          {/* Source icon */}
                                          {bid.source === "email" ? (
                                             <MailIcon className="h-4 w-4 shrink-0 text-[color:var(--e3-chip-amber-text)]" />
                                          ) : (
                                             <PhoneIcon className="h-4 w-4 shrink-0 text-[color:var(--e3-chip-violet-text)]" />
                                          )}
                                          {bid.carrierName ? (
                                             <div className="min-w-0">
                                                <p className="truncate text-sm font-medium text-[color:var(--e3-text-strong)] e3-font-body">
                                                   {bid.carrierName}
                                                </p>
                                                {bid.carrierContact && (
                                                   <p className="text-xs text-[color:var(--e3-text-muted)] e3-font-mono">
                                                      {bid.carrierContact}
                                                   </p>
                                                )}
                                             </div>
                                          ) : (
                                             <span className="text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                                                Unknown Carrier
                                             </span>
                                          )}
                                       </div>
                                       <div className="flex items-center gap-2 shrink-0">
                                          {/* Call: Call Review (Transcript + Audio) */}
                                          {(transcript || recordingUrl) && (
                                             <button
                                                type="button"
                                                onClick={() => setReviewCallData({
                                                   audioUrl: recordingUrl || undefined,
                                                   transcription: transcript?.messages,
                                                   callerNumber: bid.carrierName || bid.carrierContact || transcript?.caller || "Unknown",
                                                   agreedPrice: bid.agreedPrice || undefined
                                                })}
                                                className="flex h-5 w-5 items-center justify-center text-[color:var(--e3-text-soft)] hover:text-[color:var(--e3-text-strong)] transition-colors"
                                                title="View Recording/Transcript"
                                             >
                                                <PlayIcon />
                                             </button>
                                          )}
                                          {recordingUrl && (
                                             <button
                                                type="button"
                                                onClick={() => {
                                                   const a = document.createElement("a");
                                                   a.href = recordingUrl;
                                                   a.download = `call-${bid.carrierName || bid.carrierContact || "unknown"}.wav`;
                                                   a.target = "_blank";
                                                   document.body.appendChild(a);
                                                   a.click();
                                                   document.body.removeChild(a);
                                                }}
                                                className="flex h-5 w-5 items-center justify-center text-[color:var(--e3-text-soft)] hover:text-[color:var(--e3-text-strong)] transition-colors"
                                                title="Download Recording"
                                             >
                                                <DownloadIcon className="h-4 w-4" />
                                             </button>
                                          )}
                                          {/* Email: view thread */}
                                          {bid.email && (
                                             <button
                                                type="button"
                                                onClick={() => setSelectedEmail(bid.email!)}
                                                className="text-[color:var(--e3-text-soft)] hover:text-[color:var(--e3-text-strong)] transition-colors"
                                                title="View email thread"
                                             >
                                                <MailIcon className="h-4 w-4" />
                                             </button>
                                          )}
                                          <StatusChip label={statusConfig.label} tone={statusConfig.chipTone} />
                                          <span className={cx("text-sm font-semibold e3-font-mono", statusConfig.accentText)}>
                                             {bid.agreedPrice ? formatCurrency(bid.agreedPrice) : "—"}
                                          </span>
                                       </div>
                                    </div>
                                 );
                              })}
                           </div>
                        )}
                     </div>
                  </div>
               </>
            )}
         </div>

         {reviewCallData && (
            <CallReviewModal
               isOpen
               onClose={() => setReviewCallData(null)}
               audioUrl={reviewCallData.audioUrl}
               transcription={reviewCallData.transcription}
               callerNumber={reviewCallData.callerNumber}
               agreedPrice={reviewCallData.agreedPrice}
            />
         )}

         <EmailThreadModal
            isOpen={selectedEmail !== null}
            onClose={() => setSelectedEmail(null)}
            email={selectedEmail}
         />
      </div>,
      document.body
   );
}
