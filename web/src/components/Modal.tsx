"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

type ModalProps = {
   isOpen: boolean;
   onClose: () => void;
   children: React.ReactNode;
};

export function Modal({ isOpen, onClose, children }: ModalProps) {
   const contentRef = useRef<HTMLDivElement>(null);

   // Auto-focus modal when it opens for keyboard navigation
   useEffect(() => {
      if (isOpen && contentRef.current) {
         contentRef.current.focus();
      }
   }, [isOpen]);

   if (!isOpen) return null;

   const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
         onClose();
      }
   };

   return createPortal(
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
         {/* Backdrop */}
         <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" onClick={onClose} />

         {/* Content */}
         <div
            ref={contentRef}
            tabIndex={-1}
            onKeyDown={handleKeyDown}
            className="relative w-full max-w-[95vw] xl:max-w-[85vw] 2xl:max-w-7xl max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-xl scrollbar-custom animate-in fade-in zoom-in-95 duration-200 outline-none"
         >
            {children}
         </div>
      </div>,
      document.body
   );
}
