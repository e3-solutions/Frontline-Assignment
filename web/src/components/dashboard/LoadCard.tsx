"use client";

import { Fragment } from "react";

import {
   ActionPill,
   cx,
   DisclosureButton,
   MailIcon,
   PhoneIcon,
   StatusChip,
   TableEmptyState,
   formatConsoleDateTime,
   formatCurrency,
   formatDate,
} from "@e3-solutions/ui";
import type { LoadNegotiation, LoadRecord } from "@/src/types/dashboard";

type LoadsTableProps = {
   loads: LoadRecord[];
   expandedLoadId: string | null;
   onExpandedLoadChange: (loadId: string | null) => void;
   onOpenLoadDetails: (load: LoadRecord) => void;
   emptyState: {
      title: string;
      description: string;
   };
};

const headerCellClasses =
   "px-4 pb-3 text-left text-[11px] uppercase tracking-[0.14em] text-[color:var(--e3-text-muted)] e3-font-mono";

const baseCellClasses =
   "border-y border-[color:var(--e3-row-border)] bg-[color:var(--e3-row-bg)] px-4 py-3 align-middle text-sm transition-all";

export function LoadsTable({
   loads,
   expandedLoadId,
   onExpandedLoadChange,
   onOpenLoadDetails,
   emptyState,
}: LoadsTableProps) {
   if (loads.length === 0) {
      return <TableEmptyState title={emptyState.title} description={emptyState.description} />;
   }

   return (
      <div className="rounded-[22px] border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface)] p-4">
         <div className="overflow-x-auto">
            <table className="min-w-[980px] w-full table-fixed border-separate border-spacing-y-2.5">
               <thead>
                  <tr>
                     <th className={headerCellClasses}>Load ID</th>
                     <th className={headerCellClasses}>Lane</th>
                     <th className={headerCellClasses}>Target</th>
                     <th className={headerCellClasses}>Activity</th>
                     <th className={headerCellClasses}>Summary</th>
                     <th className={cx(headerCellClasses, "text-right")}>Updated</th>
                  </tr>
               </thead>
               <tbody>
                  {loads.map((load) => {
                     const metrics = getLoadMetrics(load);
                     const isExpanded = expandedLoadId === load.id;
                     const rowClasses = isExpanded
                        ? "border-[color:var(--e3-row-border-open)] bg-[color:var(--e3-row-bg-open)]"
                        : "group-hover/row:border-[color:var(--e3-row-border-hover)] group-hover/row:bg-[color:var(--e3-row-bg-hover)] group-active/row:bg-[color:var(--e3-surface-pressed)]";

                     return (
                        <Fragment key={load.id}>
                           <tr
                              className="group/row cursor-pointer"
                              onClick={() => onExpandedLoadChange(isExpanded ? null : load.id)}
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
                                          onExpandedLoadChange(isExpanded ? null : load.id)
                                       }
                                       label={`${isExpanded ? "Collapse" : "Expand"} load ${load.loadId}`}
                                    />
                                    <button
                                       type="button"
                                       onClick={(e) => {
                                          e.stopPropagation();
                                          onOpenLoadDetails(load);
                                       }}
                                       className="truncate text-sm font-semibold text-[color:var(--e3-brand-lavender)] transition-colors hover:text-[color:var(--e3-text-strong)] e3-font-heading"
                                    >
                                       {load.loadId}
                                       <svg className="ml-1.5 inline-block h-3 w-3 align-middle opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                          <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                       </svg>
                                    </button>
                                 </div>
                              </td>
                              <td className={cx(baseCellClasses, rowClasses)}>
                                 <div className="min-w-0">
                                    <p
                                       className="truncate text-sm font-medium text-[color:var(--e3-text-strong)] e3-font-body"
                                       title={buildLaneLabel(load)}
                                    >
                                       {buildLaneLabel(load)}
                                    </p>
                                    <p
                                       className="truncate pt-1 text-xs text-[color:var(--e3-text-soft)] e3-font-body"
                                       title={load.data?.customer ?? "Customer unavailable"}
                                    >
                                       {load.data?.customer || "Customer unavailable"}
                                    </p>
                                 </div>
                              </td>
                              <td className={cx(baseCellClasses, rowClasses)}>
                                 <span className="text-sm text-[color:var(--e3-accent-lime)] e3-font-mono">
                                    {formatCurrency(load.data?.pricing?.target)}
                                 </span>
                              </td>
                              <td className={cx(baseCellClasses, rowClasses)}>
                                 {(() => {
                                    // Counts mirror what the drawer renders: only negotiations
                                    // (agreements + bids), not raw call/email attempts.
                                    const callBidCount = load.negotiations.filter((n) => n.callId).length;
                                    const emailBidCount = load.negotiations.filter((n) => !n.callId).length;
                                    return (
                                       <div className="flex items-center gap-3 text-sm e3-font-mono">
                                          <span className="flex items-center gap-1 text-[color:var(--e3-text-strong)]" title="Call bids">
                                             <PhoneIcon className="h-3.5 w-3.5 text-[color:var(--e3-text-soft)]" />
                                             {callBidCount}
                                          </span>
                                          {emailBidCount > 0 && (
                                             <span className="flex items-center gap-1 text-[color:var(--e3-text-strong)]" title="Email bids">
                                                <MailIcon className="h-3.5 w-3.5 text-[color:var(--e3-text-soft)]" />
                                                {emailBidCount}
                                             </span>
                                          )}
                                       </div>
                                    );
                                 })()}
                              </td>
                              <td className={cx(baseCellClasses, rowClasses)}>
                                 <div className="flex flex-wrap items-center gap-2">
                                    {metrics.agreementCount > 0 ? (
                                       <StatusChip
                                          label={`${metrics.agreementCount} agreed`}
                                          tone="success"
                                       />
                                    ) : null}
                                    {metrics.bidCount > 0 ? (
                                       <StatusChip
                                          label={`${metrics.bidCount} bid`}
                                          tone="violet"
                                       />
                                    ) : null}
                                    {metrics.agreementCount === 0 && metrics.bidCount === 0 ? (
                                       <span className="truncate text-xs text-[color:var(--e3-text-muted)] e3-font-body">
                                          {getSummaryCopy(load, metrics.latestNegotiation)}
                                       </span>
                                    ) : null}
                                 </div>
                              </td>
                              <td
                                 className={cx(
                                    baseCellClasses,
                                    rowClasses,
                                    "rounded-r-[18px] border-r text-right"
                                 )}
                              >
                                 <span className="text-xs text-[color:var(--e3-text-muted)] e3-font-mono" suppressHydrationWarning>
                                    {formatConsoleDateTime(load.updatedAt)}
                                 </span>
                              </td>
                           </tr>

                           {isExpanded ? (
                              <tr>
                                 <td colSpan={6} className="px-0 pt-0">
                                    <div className="mx-1 rounded-[18px] border border-[color:var(--e3-row-border-open)] bg-[color:var(--e3-surface-alt)] px-5 py-4">
                                       <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr_1.2fr]">
                                          <section className="border-b border-[color:var(--e3-divider)] pb-4 xl:border-b-0 xl:border-r xl:border-r-[color:var(--e3-border-strong)] xl:pr-4">
                                             <h3 className="text-base font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                                                Load details
                                             </h3>
                                             <div className="mt-4 space-y-2 text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                                                <p>
                                                   Customer: {load.data?.customer || "Unavailable"}
                                                </p>
                                                <p>Lane: {buildLaneLabel(load)}</p>
                                                <p>
                                                   Pickup:{" "}
                                                   {formatPickupLabel(
                                                      load.data?.pickupDate,
                                                      load.data?.pickupTime
                                                   )}
                                                </p>
                                                <p>
                                                   Delivery: {formatDate(load.data?.dropoffDate)}
                                                </p>
                                                <p>
                                                   Equipment: {load.data?.equipment || "—"} •{" "}
                                                   {load.data?.weight || "Weight unavailable"} •{" "}
                                                   {load.data?.trackerRequired
                                                      ? "Tracker required"
                                                      : "Tracker optional"}
                                                </p>
                                                {load.data?.requirements ? (
                                                   <p>Requirements: {load.data.requirements}</p>
                                                ) : null}
                                             </div>
                                          </section>

                                          <section className="border-b border-[color:var(--e3-divider)] pb-4 xl:border-b-0 xl:border-r xl:border-r-[color:var(--e3-border-strong)] xl:px-4">
                                             <h3 className="text-base font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                                                Pricing
                                             </h3>
                                             <dl className="mt-4 grid gap-3 text-sm">
                                                <PriceRow
                                                   label="Initial"
                                                   value={formatCurrency(
                                                      load.data?.pricing?.initial
                                                   )}
                                                />
                                                <PriceRow
                                                   label="Target"
                                                   value={formatCurrency(
                                                      load.data?.pricing?.target
                                                   )}
                                                   accent
                                                />
                                                <PriceRow
                                                   label="Ceiling"
                                                   value={formatCurrency(
                                                      load.data?.pricing?.ceiling
                                                   )}
                                                />
                                                <PriceRow
                                                   label="Avg win"
                                                   value={formatCurrency(
                                                      metrics.averageAgreedPrice,
                                                      {
                                                         minimumFractionDigits: 2,
                                                         maximumFractionDigits: 2,
                                                      }
                                                   )}
                                                />
                                             </dl>
                                          </section>

                                          <section className="border-b border-[color:var(--e3-divider)] pb-4 xl:border-b-0 xl:px-4">
                                             <h3 className="text-base font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                                                Negotiations
                                             </h3>
                                             <div className="mt-4 space-y-4">
                                                {metrics.latestNegotiation ? (
                                                   <>
                                                      <div className="flex flex-wrap gap-2">
                                                         {metrics.agreementCount > 0 ? (
                                                            <StatusChip
                                                               label={`${metrics.agreementCount} agreed`}
                                                               tone="success"
                                                            />
                                                         ) : null}
                                                         {metrics.bidCount > 0 ? (
                                                            <StatusChip
                                                               label={`${metrics.bidCount} bid`}
                                                               tone="violet"
                                                            />
                                                         ) : null}
                                                      </div>
                                                      <p className="text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                                                         Latest status:{" "}
                                                         {getSummaryCopy(
                                                            load,
                                                            metrics.latestNegotiation
                                                         )}
                                                      </p>
                                                      <p className="text-sm text-[color:var(--e3-text-strong)] e3-font-mono">
                                                         Latest price:{" "}
                                                         {formatCurrency(
                                                            metrics.latestNegotiation.agreedPrice
                                                         )}
                                                      </p>
                                                      <p className="text-xs text-[color:var(--e3-text-soft)] e3-font-mono" suppressHydrationWarning>
                                                         Updated{" "}
                                                         {formatConsoleDateTime(
                                                            metrics.latestNegotiation.createdAt
                                                         )}
                                                      </p>
                                                      {metrics.latestNegotiation.notes ? (
                                                         <p className="text-sm leading-6 text-[color:var(--e3-text-muted)] e3-font-body">
                                                            {metrics.latestNegotiation.notes}
                                                         </p>
                                                      ) : null}
                                                   </>
                                                ) : (
                                                   <p className="text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                                                      No negotiations recorded yet.
                                                   </p>
                                                )}
                                                <div className="flex flex-wrap gap-2 pt-1">
                                                   <ActionPill
                                                      label="View details"
                                                      onClick={() => onOpenLoadDetails(load)}
                                                   />
                                                </div>
                                             </div>
                                          </section>
                                       </div>
                                    </div>
                                 </td>
                              </tr>
                           ) : null}
                        </Fragment>
                     );
                  })}
               </tbody>
            </table>
         </div>
      </div>
   );
}

type PriceRowProps = {
   label: string;
   value: string;
   accent?: boolean;
};

function PriceRow({ label, value, accent = false }: PriceRowProps) {
   return (
      <div className="flex items-center justify-between gap-3">
         <dt className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--e3-text-soft)] e3-font-mono">
            {label}
         </dt>
         <dd
            className={cx(
               "text-sm e3-font-mono",
               accent ? "text-[color:var(--e3-accent-lime)]" : "text-[color:var(--e3-text-strong)]"
            )}
         >
            {value}
         </dd>
      </div>
   );
}

type LoadMetrics = {
   agreementCount: number;
   bidCount: number;
   averageAgreedPrice?: number;
   latestNegotiation?: LoadNegotiation;
};

function getLoadMetrics(load: LoadRecord): LoadMetrics {
   const sortedNegotiations = [...load.negotiations].sort(
      (left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
   );

   const latestNegotiation = sortedNegotiations[0];
   const agreementNegotiations = load.negotiations.filter(
      (negotiation) => negotiation.status === "success" && !negotiation.aboveMax
   );
   const bidNegotiations = load.negotiations.filter((negotiation) => negotiation.aboveMax);
   const prices = agreementNegotiations
      .map((negotiation) => negotiation.agreedPrice)
      .filter((value): value is number => typeof value === "number" && value > 0);

   const averageAgreedPrice =
      prices.length > 0
         ? Math.round((prices.reduce((sum, value) => sum + value, 0) / prices.length) * 100) / 100
         : undefined;

   return {
      agreementCount: agreementNegotiations.length,
      bidCount: bidNegotiations.length,
      averageAgreedPrice,
      latestNegotiation,
   };
}

function buildLaneLabel(load: LoadRecord) {
   return `${load.data?.origin || "Origin unavailable"} -> ${load.data?.destination || "Destination unavailable"}`;
}

function getSummaryCopy(load: LoadRecord, latestNegotiation?: LoadNegotiation) {
   if (load.negotiations.length === 0) {
      return "No negotiations";
   }

   if (!latestNegotiation) {
      return "Negotiations in progress";
   }

   if (latestNegotiation.aboveMax) {
      return "Bid placed";
   }

   switch (latestNegotiation.status) {
      case "success":
         return "Agreement reached";
      case "no_agreement":
         return "No agreement";
      case "error":
         return "Call error";
      default:
         return "Negotiation update";
   }
}

function formatPickupLabel(date?: string, pickupTime?: string) {
   if (pickupTime) {
      return formatConsoleDateTime(pickupTime);
   }

   return formatDate(date);
}
