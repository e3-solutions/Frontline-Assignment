"use client";

import { AudioPlayer, CloseIcon, Modal } from "@e3-solutions/ui";

type AudioPlayerModalProps = {
   isOpen: boolean;
   onClose: () => void;
   src: string;
   title?: string;
   description?: string;
};

export function AudioPlayerModal({
   isOpen,
   onClose,
   src,
   title,
   description,
}: AudioPlayerModalProps) {
   return (
      <Modal isOpen={isOpen} onClose={onClose} className="max-w-2xl">
         <div className="flex flex-col">
            <div className="flex items-center justify-between border-b border-[color:var(--e3-divider)] px-6 py-5">
               <div>
                  <h2 className="text-xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                     Call Recording
                  </h2>
                  {description && (
                     <p className="mt-1 text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                        {description}
                     </p>
                  )}
               </div>
               <button
                  type="button"
                  onClick={onClose}
                  className="cursor-pointer rounded-2xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] p-2 text-[color:var(--e3-text-muted)] transition-all hover:border-[color:var(--e3-border-strong)] hover:bg-[color:var(--e3-surface-alt)] hover:text-[color:var(--e3-text-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--e3-brand-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--e3-shell)]"
                  aria-label="Close audio player"
               >
                  <CloseIcon className="h-5 w-5" />
               </button>
            </div>

            <div className="p-6">
               <AudioPlayer src={src} title={title} autoPlay />
            </div>
         </div>
      </Modal>
   );
}
