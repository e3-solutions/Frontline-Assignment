"use client";

import { CloseIcon, Modal } from "@e3-solutions/ui";
import type { TranscriptMessage } from "@/src/types/dashboard";

type MergedMessage = {
   role: "caller" | "agent";
   content: string[];
};

function mergeSequentialMessages(messages: TranscriptMessage[]): MergedMessage[] {
   const merged: MergedMessage[] = [];

   for (const message of messages) {
      const last = merged[merged.length - 1];
      if (last && last.role === message.role) {
         last.content.push(message.content);
      } else {
         merged.push({ role: message.role, content: [message.content] });
      }
   }

   return merged;
}

type TranscriptModalProps = {
   isOpen: boolean;
   onClose: () => void;
   transcription: TranscriptMessage[];
   callerNumber: string;
};

export function TranscriptModal({
   isOpen,
   onClose,
   transcription,
   callerNumber,
}: TranscriptModalProps) {
   const merged = mergeSequentialMessages(transcription);

   return (
      <Modal
         isOpen={isOpen}
         onClose={onClose}
         className="max-w-3xl"
      >
         <div className="flex max-h-[85vh] flex-col">
            <div className="flex items-center justify-between border-b border-[color:var(--e3-divider)] px-6 py-5">
               <div>
                  <h2 className="text-xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                     Conversation Transcript
                  </h2>
                  <p className="mt-1 text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                     Call with {callerNumber}
                  </p>
               </div>
               <button
                  type="button"
                  onClick={onClose}
                  className="cursor-pointer rounded-2xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] p-2 text-[color:var(--e3-text-muted)] transition-all hover:border-[color:var(--e3-border-strong)] hover:bg-[color:var(--e3-surface-alt)] hover:text-[color:var(--e3-text-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--e3-brand-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--e3-shell)]"
                  aria-label="Close transcript"
               >
                  <CloseIcon className="h-5 w-5" />
               </button>
            </div>

            <div className="scrollbar-custom flex-1 overflow-y-auto px-6 py-5">
               <div className="space-y-4">
                  {merged.map((block, index) => (
                     <div
                        key={index}
                        className={`flex gap-3 ${block.role === "agent" ? "flex-row" : "flex-row-reverse"}`}
                     >
                        <div
                           className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold e3-font-heading ${
                              block.role === "agent"
                                 ? "border border-[color:var(--e3-chip-violet-border)] bg-[color:var(--e3-chip-violet-bg)] text-[color:var(--e3-chip-violet-text)]"
                                 : "border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] text-[color:var(--e3-text-muted)]"
                           }`}
                        >
                           {block.role === "agent" ? "A" : "C"}
                        </div>
                        <div
                           className={`max-w-[80%] rounded-[20px] border px-4 py-3 ${
                              block.role === "agent"
                                 ? "border-[color:var(--e3-chip-violet-border)] bg-[color:var(--e3-chip-violet-bg)] text-[color:var(--e3-text-strong)]"
                                 : "border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] text-[color:var(--e3-text-strong)]"
                           }`}
                        >
                           <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] opacity-80 e3-font-heading">
                              {block.role === "agent" ? "Agent" : "Caller"}
                           </p>
                           <p className="text-sm leading-relaxed text-[color:var(--e3-text-muted)] e3-font-body">
                              {block.content.join(" ")}
                           </p>
                        </div>
                     </div>
                  ))}
               </div>
            </div>

            <div className="border-t border-[color:var(--e3-divider)] px-6 py-4">
               <p className="text-center text-xs text-[color:var(--e3-text-soft)] e3-font-mono">
                  {transcription.length} messages in conversation
               </p>
            </div>
         </div>
      </Modal>
   );
}
