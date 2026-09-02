"use client";

import { useState } from "react";

import {
   ActionPill,
   cx,
   DisclosureButton,
   MailIcon,
   StatusChip,
   SpacedTable,
   SpacedTableBody,
   SpacedTableCell,
   SpacedTableHead,
   SpacedTableHeader,
   SpacedTableRow,
   TableEmptyState,
   formatConsoleDateTime,
   formatCurrency,
} from "@e3-solutions/ui";
import { EmailThreadModal } from "@/src/components/dashboard/EmailThreadModal";
import type { EmailRecord } from "@/src/types/dashboard";

function getEmailStatus(email: EmailRecord) {
   if (email.negotiation && !email.negotiation.aboveMax && email.negotiation.agreedPrice) {
      return { label: "Agreement", tone: "success" as const };
   }
   if (email.negotiation?.aboveMax) {
      return { label: "Bid Placed", tone: "violet" as const };
   }
   if (email.ended) {
      return { label: "Ended", tone: "rose" as const };
   }
   return { label: "Active", tone: "amber" as const };
}

type EmailsTableProps = {
   emails: EmailRecord[];
   onLoadClick?: (loadId: string) => void;
   emptyState: {
      title: string;
      description: string;
   };
};

const headerCellClasses =
   "px-4 pb-3 text-left text-[11px] uppercase tracking-[0.14em] text-[color:var(--e3-text-muted)] e3-font-mono";

const baseCellClasses =
   "border-y border-[color:var(--e3-row-border)] bg-[color:var(--e3-row-bg)] px-4 py-3 align-middle text-sm transition-all";

export function EmailsTable({
   emails,
   onLoadClick,
   emptyState,
}: EmailsTableProps) {
   const [threadEmail, setThreadEmail] = useState<EmailRecord | null>(null);

   if (emails.length === 0) {
      return <TableEmptyState title={emptyState.title} description={emptyState.description} />;
   }

   return (
      <>
         <div className="rounded-[22px] border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface)] p-4">
            <div className="overflow-x-auto">
               <table className="min-w-[900px] w-full table-fixed border-separate border-spacing-y-2.5">
                  <thead>
                     <tr>
                        <th className={cx(headerCellClasses, "w-[14%]")}>Status</th>
                        <th className={cx(headerCellClasses, "w-[24%]")}>Subject</th>
                        <th className={cx(headerCellClasses, "w-[18%]")}>Carrier</th>
                        <th className={cx(headerCellClasses, "w-[10%]")}>Load ID</th>
                        <th className={cx(headerCellClasses, "w-[10%]")}>Price</th>
                        <th className={cx(headerCellClasses, "w-[8%]")}>Msgs</th>
                        <th className={cx(headerCellClasses, "w-[16%]")}>Last Activity</th>
                     </tr>
                  </thead>
                  <tbody>
                     {emails.map((email) => {
                        const status = getEmailStatus(email);
                        const messageCount = email.interactions.length;
                        const lastActivity = email.interactions.at(-1)?.createdAt ?? email.updatedAt;
                        const rowClasses =
                           "group-hover/row:border-[color:var(--e3-row-border-hover)] group-hover/row:bg-[color:var(--e3-row-bg-hover)] group-active/row:bg-[color:var(--e3-surface-pressed)]";

                        return (
                           <tr
                              key={email.id}
                              className="group/row cursor-pointer"
                              onClick={() => setThreadEmail(email)}
                           >
                              <td
                                 className={cx(
                                    baseCellClasses,
                                    rowClasses,
                                    "rounded-l-[18px] border-l pl-3"
                                 )}
                              >
                                 <StatusChip label={status.label} tone={status.tone} />
                              </td>
                              <td className={cx(baseCellClasses, rowClasses)}>
                                 <div className="min-w-0">
                                    <p className="truncate text-sm font-medium text-[color:var(--e3-text-strong)] e3-font-body">
                                       {email.subject ?? "No subject"}
                                    </p>
                                 </div>
                              </td>
                              <td className={cx(baseCellClasses, rowClasses)}>
                                 <p className="truncate text-sm text-[color:var(--e3-text-muted)] e3-font-mono">
                                    {email.carrierEmail}
                                 </p>
                              </td>
                              <td className={cx(baseCellClasses, rowClasses)}>
                                 {onLoadClick && email.loadId ? (
                                    <button
                                       type="button"
                                       onClick={(event) => {
                                          event.stopPropagation();
                                          onLoadClick(email.loadId!);
                                       }}
                                       className="flex items-center gap-1.5 truncate text-sm font-semibold text-[color:var(--e3-brand-lavender)] transition-colors hover:text-[color:var(--e3-text-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--e3-brand-accent)] e3-font-heading"
                                    >
                                       {email.loadId}
                                       <svg className="h-3 w-3 shrink-0 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                          <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                       </svg>
                                    </button>
                                 ) : (
                                    <span className="text-sm text-[color:var(--e3-text-muted)]">
                                       {email.loadId ?? "—"}
                                    </span>
                                 )}
                              </td>
                              <td className={cx(baseCellClasses, rowClasses)}>
                                 <span
                                    className={cx(
                                       "text-sm font-semibold e3-font-heading",
                                       email.negotiation?.agreedPrice
                                          ? email.negotiation.aboveMax
                                             ? "text-[color:var(--e3-chip-violet-text)]"
                                             : "text-[color:var(--e3-chip-success-text)]"
                                          : "text-[color:var(--e3-text-muted)]"
                                    )}
                                 >
                                    {email.negotiation?.agreedPrice
                                       ? formatCurrency(email.negotiation.agreedPrice)
                                       : "—"}
                                 </span>
                              </td>
                              <td className={cx(baseCellClasses, rowClasses)}>
                                 <span className="text-sm text-[color:var(--e3-text-strong)] e3-font-heading">
                                    {String(messageCount).padStart(2, "0")}
                                 </span>
                              </td>
                              <td
                                 className={cx(
                                    baseCellClasses,
                                    rowClasses,
                                    "rounded-r-[18px] border-r"
                                 )}
                              >
                                 <span className="text-xs text-[color:var(--e3-text-muted)] e3-font-mono" suppressHydrationWarning>
                                    {formatConsoleDateTime(lastActivity)}
                                 </span>
                              </td>
                           </tr>
                        );
                     })}
                  </tbody>
               </table>
            </div>
         </div>

         {threadEmail ? (
            <EmailThreadModal
               isOpen
               onClose={() => setThreadEmail(null)}
               email={threadEmail}
            />
         ) : null}
      </>
   );
}
