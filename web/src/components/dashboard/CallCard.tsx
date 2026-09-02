"use client";

import { Fragment, useState } from "react";

import {
   ActionPill,
   cx,
   DisclosureButton,
   DownloadIcon,
   PlayIcon,
   StatusChip,
   TableEmptyState,
   TranscriptDotIcon,
   formatConsoleDateTime,
   formatDuration,
   formatDurationShort,
} from "@e3-solutions/ui";
import { CallReviewModal } from "@/src/components/dashboard/CallReviewModal";
import type { CallOutcome, CallRecord } from "@/src/types/dashboard";

const outcomeConfig: Record<
   CallOutcome,
   {
      label: string;
      tone: "success" | "violet" | "sky" | "amber" | "rose";
   }
> = {
   agreement: { label: "Agreed", tone: "success" },
   no_agreement: { label: "No Agreement", tone: "amber" },
   bid_placed: { label: "Bid Placed", tone: "violet" },
   abrupt: { label: "Abrupt", tone: "rose" },
   error: { label: "Error", tone: "rose" },
   load_not_found: { label: "Load Not Found", tone: "sky" },
   mc_not_found: { label: "MC Not Found", tone: "sky" },
   call_transferred: { label: "Transferred", tone: "sky" },
};

type CallsTableProps = {
   calls: CallRecord[];
   expandedCallId: string | null;
   onExpandedCallChange: (callId: string | null) => void;
   onLoadClick?: (loadId: string) => void;
   sort: "started_desc" | "started_asc" | "duration_desc" | "ended_desc";
   onStartedSortToggle: () => void;
   emptyState: {
      title: string;
      description: string;
   };
};

const headerCellClasses =
   "px-4 pb-3 text-left text-[11px] uppercase tracking-[0.14em] text-[color:var(--e3-text-muted)] e3-font-mono";

const baseCellClasses =
   "border-y border-[color:var(--e3-row-border)] bg-[color:var(--e3-row-bg)] px-4 py-3 align-middle text-sm transition-all";

export function CallsTable({
   calls,
   expandedCallId,
   onExpandedCallChange,
   onLoadClick,
   sort,
   onStartedSortToggle,
   emptyState,
}: CallsTableProps) {
   const [reviewCall, setReviewCall] = useState<CallRecord | null>(null);

   if (calls.length === 0) {
      return <TableEmptyState title={emptyState.title} description={emptyState.description} />;
   }

   return (
      <>
         <div className="rounded-[22px] border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface)] p-4">
            <div className="overflow-x-auto">
               <table className="min-w-[1080px] w-full table-fixed border-separate border-spacing-y-2.5">
                  <thead>
                     <tr>
                        <th className={cx(headerCellClasses, "w-[16%]")}>Outcome</th>
                        <th className={cx(headerCellClasses, "w-[16%]")}>Caller</th>
                        <th className={cx(headerCellClasses, "w-[10%]")}>Load ID</th>
                        <th className={cx(headerCellClasses, "w-[14%]")}>
                           <button
                              type="button"
                              onClick={onStartedSortToggle}
                              className="inline-flex items-center gap-2 transition-colors hover:text-[color:var(--e3-text-strong)] focus-visible:outline-none focus-visible:text-[color:var(--e3-text-strong)]"
                              aria-label={`Sort by started ${sort === "started_asc" ? "descending" : "ascending"}`}
                           >
                              <span>Started</span>
                              <svg
                                 viewBox="0 0 20 20"
                                 className={cx(
                                    "size-3.5 transition-transform",
                                    sort === "started_asc" && "rotate-180"
                                 )}
                                 fill="none"
                                 stroke="currentColor"
                                 strokeWidth="1.8"
                                 strokeLinecap="round"
                                 strokeLinejoin="round"
                              >
                                 <path d="m5 7 5 6 5-6" />
                              </svg>
                           </button>
                        </th>
                        <th className={cx(headerCellClasses, "hidden w-[14%] 2xl:table-cell")}>
                           Ended
                        </th>
                        <th className={cx(headerCellClasses, "w-[8%]")}>Duration</th>
                        <th className={cx(headerCellClasses, "w-[14%]")}>Review</th>
                        <th className={cx(headerCellClasses, "w-[8%] text-center")}>Download</th>
                     </tr>
                  </thead>
                  <tbody>
                     {calls.map((call) => {
                        const currentOutcome = call.endReason ?? call.result.outcome;
                        const status = outcomeConfig[currentOutcome] ?? { label: currentOutcome, tone: "amber" as const };
                        const isExpanded = expandedCallId === call.id;
                        const hasTranscript = Boolean(call.result.transcription?.length);
                        const hasRecording = Boolean(call.result.audio_url);
                        const rowClasses = isExpanded
                           ? "border-[color:var(--e3-row-border-open)] bg-[color:var(--e3-row-bg-open)]"
                           : "group-hover/row:border-[color:var(--e3-row-border-hover)] group-hover/row:bg-[color:var(--e3-row-bg-hover)] group-active/row:bg-[color:var(--e3-surface-pressed)]";

                        return (
                           <Fragment key={call.id}>
                              <tr
                                 className="group/row cursor-pointer"
                                 onClick={() => onExpandedCallChange(isExpanded ? null : call.id)}
                              >
                                 <td
                                    className={cx(
                                       baseCellClasses,
                                       rowClasses,
                                       "rounded-l-[18px] border-l pl-3"
                                    )}
                                 >
                                    <div className="flex items-center gap-3">
                                       <DisclosureButton
                                          expanded={isExpanded}
                                          onToggle={() =>
                                             onExpandedCallChange(isExpanded ? null : call.id)
                                          }
                                          label={`${isExpanded ? "Collapse" : "Expand"} call ${call.dailyCallId}`}
                                       />
                                       <StatusChip label={status.label} tone={status.tone} />
                                    </div>
                                 </td>
                                 <td className={cx(baseCellClasses, rowClasses)}>
                                    <div className="max-w-[180px]">
                                       <p className="truncate text-sm font-medium text-[color:var(--e3-text-strong)] e3-font-mono">
                                          {call.callerNumber}
                                       </p>
                                       <p className="truncate pt-1 text-xs text-[color:var(--e3-text-soft)] e3-font-body">
                                          Daily {call.dailyCallId}
                                       </p>
                                    </div>
                                 </td>
                                 <td className={cx(baseCellClasses, rowClasses)}>
                                    {onLoadClick ? (
                                       <button
                                          type="button"
                                          onClick={(event) => {
                                             event.stopPropagation();
                                             onLoadClick(call.loadId);
                                          }}
                                          className="flex items-center gap-1.5 truncate text-sm font-semibold text-[color:var(--e3-brand-lavender)] transition-colors hover:text-[color:var(--e3-text-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--e3-brand-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--e3-surface)] e3-font-heading"
                                       >
                                          {call.loadId}
                                          <ExternalLinkIcon />
                                       </button>
                                    ) : (
                                       <span className="text-sm font-semibold text-[color:var(--e3-brand-lavender)] e3-font-heading">
                                          {call.loadId}
                                       </span>
                                    )}
                                 </td>
                                 <td className={cx(baseCellClasses, rowClasses)}>
                                    <span className="text-xs text-[color:var(--e3-text-muted)] e3-font-mono" suppressHydrationWarning>
                                       {formatConsoleDateTime(call.initiatedAt)}
                                    </span>
                                 </td>
                                 <td
                                    className={cx(
                                       baseCellClasses,
                                       rowClasses,
                                       "hidden 2xl:table-cell"
                                    )}
                                 >
                                    <span className="text-xs text-[color:var(--e3-text-muted)] e3-font-mono" suppressHydrationWarning>
                                       {call.endedAt
                                          ? formatConsoleDateTime(call.endedAt)
                                          : "In progress"}
                                    </span>
                                 </td>
                                 <td className={cx(baseCellClasses, rowClasses)}>
                                    <span className="text-sm text-[color:var(--e3-text-strong)] e3-font-mono">
                                       {formatDurationShort(call.initiatedAt, call.endedAt)}
                                    </span>
                                 </td>
                                 <td className={cx(baseCellClasses, rowClasses)}>
                                    <ActionPill
                                       label={hasRecording || hasTranscript ? "Review Audio" : "No media"}
                                       onClick={
                                          hasRecording || hasTranscript ? () => setReviewCall(call) : undefined
                                       }
                                       disabled={!hasRecording && !hasTranscript}
                                       tone="neutral"
                                       icon={<PlayIcon />}
                                    />
                                 </td>
                                 <td
                                    className={cx(
                                       baseCellClasses,
                                       rowClasses,
                                       "rounded-r-[18px] border-r"
                                    )}
                                 >
                                    <div className="flex justify-center">
                                       <button
                                          type="button"
                                          onClick={
                                             hasRecording
                                                ? () => {
                                                     const a = document.createElement("a");
                                                     a.href = call.result.audio_url!;
                                                     a.download = `call-${call.callerNumber || call.dailyCallId}.wav`;
                                                     a.target = "_blank";
                                                     document.body.appendChild(a);
                                                     a.click();
                                                     document.body.removeChild(a);
                                                  }
                                                : undefined
                                          }
                                          disabled={!hasRecording}
                                          className="flex h-7 w-7 items-center justify-center rounded-full text-[color:var(--e3-text-soft)] transition-colors hover:bg-[color:var(--e3-surface-alt)] hover:text-[color:var(--e3-text-strong)] disabled:opacity-50 disabled:cursor-not-allowed"
                                          title={hasRecording ? "Download Recording" : "No recording"}
                                       >
                                          <DownloadIcon className="h-4 w-4" />
                                       </button>
                                    </div>
                                 </td>
                              </tr>

                              {isExpanded ? (
                                 <>
                                    <ExpandedCallRow colSpan={7} className="2xl:hidden">
                                       <ExpandedCallDetails
                                          call={call}
                                          statusLabel={status.label}
                                          hasTranscript={hasTranscript}
                                          hasRecording={hasRecording}
                                          onLoadClick={onLoadClick}
                                          onReviewOpen={() => setReviewCall(call)}
                                       />
                                    </ExpandedCallRow>
                                    <ExpandedCallRow colSpan={8} className="hidden 2xl:table-row">
                                       <ExpandedCallDetails
                                          call={call}
                                          statusLabel={status.label}
                                          hasTranscript={hasTranscript}
                                          hasRecording={hasRecording}
                                          onLoadClick={onLoadClick}
                                          onReviewOpen={() => setReviewCall(call)}
                                       />
                                    </ExpandedCallRow>
                                 </>
                              ) : null}
                           </Fragment>
                        );
                     })}
                  </tbody>
               </table>
            </div>
         </div>

         {reviewCall ? (
            <CallReviewModal
               isOpen
               onClose={() => setReviewCall(null)}
               audioUrl={reviewCall.result.audio_url}
               transcription={reviewCall.result.transcription}
               callerNumber={reviewCall.callerNumber}
               agreedPrice={reviewCall.result.agreed_price}
            />
         ) : null}
      </>
   );
}

type ExpandedCallRowProps = {
   children: React.ReactNode;
   colSpan: number;
   className?: string;
};

function ExpandedCallRow({ children, colSpan, className }: ExpandedCallRowProps) {
   return (
      <tr className={className}>
         <td colSpan={colSpan} className="px-0 pt-0">
            {children}
         </td>
      </tr>
   );
}

type ExpandedCallDetailsProps = {
   call: CallRecord;
   statusLabel: string;
   hasTranscript: boolean;
   hasRecording: boolean;
   onLoadClick?: (loadId: string) => void;
   onReviewOpen: () => void;
};

function ExpandedCallDetails({
   call,
   statusLabel,
   hasTranscript,
   hasRecording,
   onLoadClick,
   onReviewOpen,
}: ExpandedCallDetailsProps) {
   return (
      <div className="mx-1 max-w-full overflow-hidden rounded-[18px] border border-[color:var(--e3-row-border-open)] bg-[color:var(--e3-surface-alt)] px-5 py-4">
         <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
            <section className="min-w-0 border-b border-[color:var(--e3-divider)] pb-4 xl:border-b-0 xl:border-r xl:border-r-[color:var(--e3-border-strong)] xl:pr-4">
               <h3 className="text-base font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                  Call details
               </h3>
               <div className="mt-4 space-y-2 text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                  <p className="break-words">Caller: {call.callerNumber}</p>
                  <p className="break-all">Daily Call ID: {call.dailyCallId}</p>
                  <p>Outcome: {statusLabel}</p>
                  <p>
                     Linked load:{" "}
                     {onLoadClick ? (
                        <button
                           type="button"
                           onClick={(event) => {
                              event.stopPropagation();
                              onLoadClick(call.loadId);
                           }}
                           className="inline-flex items-center gap-1 text-[color:var(--e3-brand-lavender)] transition-colors hover:text-[color:var(--e3-text-strong)] focus-visible:outline-none focus-visible:underline"
                        >
                           {call.loadId}
                           <ExternalLinkIcon />
                        </button>
                     ) : (
                        call.loadId
                     )}
                  </p>
                  <p className="break-all">Call ID: {call.id}</p>
               </div>
            </section>

            <section className="min-w-0 border-b border-[color:var(--e3-divider)] pb-4 xl:border-b-0 xl:border-r xl:border-r-[color:var(--e3-border-strong)] xl:px-4">
               <h3 className="text-base font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                  Timing
               </h3>
               <dl className="mt-4 grid gap-3 text-sm">
                  <div>
                     <dt className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--e3-text-soft)] e3-font-mono">
                        Started
                     </dt>
                     <dd className="mt-1 text-[color:var(--e3-text-strong)] e3-font-mono" suppressHydrationWarning>
                        {formatConsoleDateTime(call.initiatedAt)}
                     </dd>
                  </div>
                  <div>
                     <dt className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--e3-text-soft)] e3-font-mono">
                        Ended
                     </dt>
                     <dd className="mt-1 text-[color:var(--e3-text-strong)] e3-font-mono" suppressHydrationWarning>
                        {call.endedAt ? formatConsoleDateTime(call.endedAt) : "In progress"}
                     </dd>
                  </div>
                  <div>
                     <dt className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--e3-text-soft)] e3-font-mono">
                        Duration
                     </dt>
                     <dd className="mt-1 text-[color:var(--e3-text-strong)] e3-font-mono">
                        {formatDuration(call.initiatedAt, call.endedAt)}
                     </dd>
                  </div>
               </dl>
            </section>

            <section className="min-w-0 border-b border-[color:var(--e3-divider)] pb-4 xl:border-b-0 xl:border-r xl:border-r-[color:var(--e3-border-strong)] xl:px-4">
               <h3 className="text-base font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                  Notes
               </h3>
               <p className="mt-4 text-sm leading-6 text-[color:var(--e3-text-muted)] e3-font-body">
                  {call.result.notes?.trim() || "No notes captured for this call."}
               </p>
            </section>

            <section className="min-w-0 xl:pl-4">
               <h3 className="text-base font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                  Actions
               </h3>
               <div className="mt-4 flex flex-wrap gap-2">
                  <ActionPill
                     label={
                        hasTranscript || hasRecording
                           ? "Review Audio"
                           : "No media"
                     }
                     onClick={hasTranscript || hasRecording ? onReviewOpen : undefined}
                     disabled={!hasTranscript && !hasRecording}
                     icon={<PlayIcon />}
                  />
                  <ActionPill
                     label={hasRecording ? "Download Audio" : "No audio"}
                     onClick={
                        hasRecording
                           ? () => {
                                const a = document.createElement("a");
                                a.href = call.result.audio_url!;
                                a.download = `call-${call.callerNumber || call.dailyCallId}.wav`;
                                a.target = "_blank";
                                document.body.appendChild(a);
                                a.click();
                                document.body.removeChild(a);
                             }
                           : undefined
                     }
                     disabled={!hasRecording}
                     tone="neutral"
                     icon={<DownloadIcon />}
                  />
               </div>
            </section>
         </div>
      </div>
   );
}

function ExternalLinkIcon() {
   return (
      <svg className="h-3 w-3 shrink-0 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
         <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
      </svg>
   );
}
