"use client";

import { CloseIcon, Modal, cx, formatDateTime } from "@e3-solutions/ui";
import type { EmailRecord, EmailInteraction } from "@/src/types/dashboard";

type EmailThreadModalProps = {
   isOpen: boolean;
   onClose: () => void;
   email: EmailRecord | null;
};

function EmailBubble({ interaction }: { interaction: EmailInteraction }) {
   return (
      <div className="space-y-3">
         {interaction.clientResponse && (
            <div className="flex gap-3 flex-row-reverse">
               <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] text-[color:var(--e3-text-muted)] e3-font-heading">
                  C
               </div>
               <div className="max-w-[80%] rounded-[20px] border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] px-4 py-3 text-[color:var(--e3-text-strong)]">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] opacity-80 e3-font-heading">
                     Carrier
                  </p>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap text-[color:var(--e3-text-muted)] e3-font-body">
                     {interaction.clientResponse}
                  </p>
                  <p className="text-xs text-[color:var(--e3-text-soft)] mt-2 text-right e3-font-mono">
                     {formatDateTime(interaction.createdAt)}
                  </p>
               </div>
            </div>
         )}
         {interaction.botResponse && (
            <div className="flex gap-3 flex-row">
               <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold border border-[color:var(--e3-chip-amber-border)] bg-[color:var(--e3-chip-amber-bg)] text-[color:var(--e3-chip-amber-text)] e3-font-heading">
                  A
               </div>
               <div className="max-w-[80%] rounded-[20px] border border-[color:var(--e3-chip-amber-border)] bg-[color:var(--e3-chip-amber-bg)] px-4 py-3 text-[color:var(--e3-text-strong)]">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] opacity-80 e3-font-heading">
                     Arya (Bot)
                  </p>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap text-[color:var(--e3-text-muted)] e3-font-body">
                     {interaction.botResponse}
                  </p>
                  <p className="text-xs text-[color:var(--e3-text-soft)] mt-2 e3-font-mono">
                     {formatDateTime(interaction.createdAt)}
                  </p>
               </div>
            </div>
         )}
      </div>
   );
}

export function EmailThreadModal({ isOpen, onClose, email }: EmailThreadModalProps) {
   if (!email) return null;

   const totalMessages = email.interactions.reduce(
      (count, i) => count + (i.clientResponse ? 1 : 0) + (i.botResponse ? 1 : 0),
      0
   );

   return (
      <Modal isOpen={isOpen} onClose={onClose} className="max-w-3xl">
         <div className="flex max-h-[85vh] flex-col">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 border-b border-[color:var(--e3-divider)] px-6 py-5">
               <div className="min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                     <h2 className="text-xl font-semibold text-[color:var(--e3-text-strong)] truncate e3-font-heading">
                        {email.subject ?? "No subject"}
                     </h2>
                     <span
                        className={cx(
                           "shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-medium e3-font-body",
                           email.ended
                              ? "border-[color:var(--e3-chip-rose-border)] bg-[color:var(--e3-chip-rose-bg)] text-[color:var(--e3-chip-rose-text)]"
                              : "border-[color:var(--e3-chip-success-border)] bg-[color:var(--e3-chip-success-bg)] text-[color:var(--e3-chip-success-text)]"
                        )}
                     >
                        {email.ended ? "Ended" : "Active"}
                     </span>
                  </div>
                  <p className="text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                     {email.carrierEmail}
                  </p>
                  {email.loadId && (
                     <p className="text-xs text-[color:var(--e3-text-soft)] mt-0.5 e3-font-mono">
                        Load {email.loadId}
                     </p>
                  )}
               </div>
               <button
                  type="button"
                  onClick={onClose}
                  className="cursor-pointer rounded-2xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] p-2 text-[color:var(--e3-text-muted)] transition-all hover:border-[color:var(--e3-border-strong)] hover:bg-[color:var(--e3-surface-alt)] hover:text-[color:var(--e3-text-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--e3-brand-accent)]"
                  aria-label="Close email thread"
               >
                  <CloseIcon className="h-5 w-5" />
               </button>
            </div>

            {/* Negotiation outcome banner */}
            {email.negotiation && (
               <div
                  className={cx(
                     "flex items-center gap-3 px-6 py-3 text-sm border-b",
                     email.negotiation.aboveMax
                        ? "border-[color:var(--e3-chip-violet-border)] bg-[color:var(--e3-chip-violet-bg)] text-[color:var(--e3-chip-violet-text)]"
                        : "border-[color:var(--e3-chip-success-border)] bg-[color:var(--e3-chip-success-bg)] text-[color:var(--e3-chip-success-text)]"
                  )}
               >
                  <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                     <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="e3-font-body">
                     {email.negotiation.aboveMax ? "Bid placed" : "Agreement reached"} ·{" "}
                     <strong className="e3-font-heading">
                        {email.negotiation.agreedPrice != null
                           ? `$${email.negotiation.agreedPrice.toLocaleString()}`
                           : "—"}
                     </strong>
                     {email.negotiation.carrierContactName && ` · ${email.negotiation.carrierContactName}`}
                  </span>
               </div>
            )}

            {/* Thread */}
            <div className="scrollbar-custom flex-1 overflow-y-auto px-6 py-5">
               {email.interactions.length === 0 ? (
                  <div className="flex items-center justify-center h-32 text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                     No messages yet
                  </div>
               ) : (
                  <div className="space-y-6">
                     {email.interactions.map((interaction) => (
                        <EmailBubble key={interaction.id} interaction={interaction} />
                     ))}
                  </div>
               )}
            </div>

            {/* Footer */}
            <div className="border-t border-[color:var(--e3-divider)] px-6 py-4">
               <p className="text-center text-xs text-[color:var(--e3-text-soft)] e3-font-mono">
                  {totalMessages} messages · Started {formatDateTime(email.createdAt)}
               </p>
            </div>
         </div>
      </Modal>
   );
}
