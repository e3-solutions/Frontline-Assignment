"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import WaveSurfer from "wavesurfer.js";
import { CloseIcon, Modal, PlayIcon, formatCurrency, cx } from "@e3-solutions/ui";
import type { TranscriptMessage } from "@/src/types/dashboard";

type MergedMessage = {
   id: string;
   role: "caller" | "agent";
   content: string[];
   timestamp: string;
   offsetSeconds: number;
   isAgreement?: boolean;
};

function processMessages(messages: TranscriptMessage[], agreedPrice?: number): MergedMessage[] {
   if (!messages || messages.length === 0) return [];

   const firstTime = new Date(messages[0].timestamp).getTime();
   const merged: MergedMessage[] = [];

   let agreedPriceStr = agreedPrice ? agreedPrice.toString() : null;

   for (const message of messages) {
      const last = merged[merged.length - 1];
      const time = new Date(message.timestamp).getTime();
      const offsetSeconds = Math.max(0, (time - firstTime) / 1000);

      let isAgreement = false;
      if (agreedPriceStr && message.role === "agent" && message.content.includes(agreedPriceStr)) {
         isAgreement = true;
      }

      if (last && last.role === message.role) {
         last.content.push(message.content);
         if (isAgreement) last.isAgreement = true;
      } else {
         merged.push({
            id: message.timestamp + message.content.substring(0, 5),
            role: message.role,
            content: [message.content],
            timestamp: message.timestamp,
            offsetSeconds,
            isAgreement,
         });
      }
   }

   return merged;
}

export type CallReviewModalProps = {
   isOpen: boolean;
   onClose: () => void;
   transcription?: TranscriptMessage[];
   audioUrl?: string;
   callerNumber: string;
   agreedPrice?: number;
};

export function CallReviewModal({
   isOpen,
   onClose,
   transcription = [],
   audioUrl,
   callerNumber,
   agreedPrice,
}: CallReviewModalProps) {
   const waveformRef = useRef<HTMLDivElement>(null);
   const wavesurfer = useRef<WaveSurfer | null>(null);
   const [isPlaying, setIsPlaying] = useState(false);
   const [currentTime, setCurrentTime] = useState(0);
   const [duration, setDuration] = useState(0);
   
   const messages = useMemo(() => processMessages(transcription, agreedPrice), [transcription, agreedPrice]);

   // Active message index based on current audio time
   const activeIndex = useMemo(() => {
      if (currentTime === 0) return -1;
      let active = -1;
      for (let i = 0; i < messages.length; i++) {
         if (currentTime >= messages[i].offsetSeconds) {
            active = i;
         } else {
            break;
         }
      }
      return active;
   }, [currentTime, messages]);

   // Auto-scroll to active message
   const transcriptContainerRef = useRef<HTMLDivElement>(null);
   const messageRefs = useRef<Map<string, HTMLDivElement>>(new Map());

   useEffect(() => {
      if (activeIndex >= 0) {
         const messageId = messages[activeIndex]?.id;
         const el = messageRefs.current.get(messageId);
         if (el && transcriptContainerRef.current) {
            // Smooth scroll into view
            el.scrollIntoView({ behavior: "smooth", block: "center" });
         }
      }
   }, [activeIndex, messages]);

   useEffect(() => {
      if (!isOpen || !audioUrl || !waveformRef.current) return;

      const ws = WaveSurfer.create({
         container: waveformRef.current,
         waveColor: "var(--e3-brand-lavender)",
         progressColor: "var(--e3-brand-accent)",
         cursorColor: "var(--e3-brand-accent)",
         barWidth: 2,
         barGap: 3,
         barRadius: 2,
         height: 64,
         normalize: true,
      });

      let destroyed = false;

      ws.load(audioUrl).catch(() => { /* ignore load abort */ });

      ws.on("ready", () => {
         setDuration(ws.getDuration());
      });

      ws.on("audioprocess", (time) => {
         setCurrentTime(time);
      });

      ws.on("seeking", () => {
         setCurrentTime(ws.getCurrentTime());
      });

      ws.on("play", () => setIsPlaying(true));
      ws.on("pause", () => setIsPlaying(false));

      wavesurfer.current = ws;

      return () => {
         destroyed = true;
         try { ws.destroy(); } catch { /* ignore abort during cleanup */ }
      };
   }, [isOpen, audioUrl]);

   const togglePlay = () => {
      if (wavesurfer.current) {
         wavesurfer.current.playPause();
      }
   };

   const handleMessageClick = (offsetSeconds: number) => {
      if (wavesurfer.current) {
         wavesurfer.current.setTime(offsetSeconds);
         wavesurfer.current.play();
      }
   };

   const formatTime = (seconds: number) => {
      const mins = Math.floor(seconds / 60);
      const secs = Math.floor(seconds % 60);
      return `${mins}:${secs.toString().padStart(2, "0")}`;
   };

   return (
      <Modal isOpen={isOpen} onClose={onClose} className="max-w-4xl h-[85vh]">
         <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b border-[color:var(--e3-divider)] px-6 py-5 shrink-0">
               <div>
                  <h2 className="text-xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                     Call Review
                  </h2>
                  <p className="mt-1 text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                     Call with {callerNumber}
                  </p>
               </div>
               <button
                  type="button"
                  onClick={onClose}
                  className="cursor-pointer rounded-2xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] p-2 text-[color:var(--e3-text-muted)] transition-all hover:border-[color:var(--e3-border-strong)] hover:bg-[color:var(--e3-surface-alt)] hover:text-[color:var(--e3-text-strong)] focus-visible:outline-none"
               >
                  <CloseIcon className="h-5 w-5" />
               </button>
            </div>

            {/* Audio Waveform Section */}
            {audioUrl ? (
               <div className="border-b border-[color:var(--e3-divider)] bg-[color:var(--e3-surface-alt)] px-6 py-5 shrink-0">
                  <div className="flex items-center gap-4">
                     <button
                        type="button"
                        onClick={togglePlay}
                        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[color:var(--e3-brand-accent)] text-white shadow-lg transition-transform hover:scale-105 active:scale-95 focus-visible:outline-none"
                     >
                        {isPlaying ? (
                           <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                              <rect x="6" y="4" width="4" height="16" />
                              <rect x="14" y="4" width="4" height="16" />
                           </svg>
                        ) : (
                           <PlayIcon className="h-6 w-6 ml-1" />
                        )}
                     </button>
                     <div className="flex-1">
                        <div ref={waveformRef} className="w-full" />
                     </div>
                     <div className="w-16 text-right text-xs text-[color:var(--e3-text-muted)] e3-font-mono shrink-0">
                        {formatTime(currentTime)} / {formatTime(duration)}
                     </div>
                  </div>
               </div>
            ) : (
               <div className="border-b border-[color:var(--e3-divider)] bg-[color:var(--e3-surface-soft)] px-6 py-3 text-sm text-[color:var(--e3-text-muted)] e3-font-body shrink-0 text-center">
                  No audio recording available for this call.
               </div>
            )}

            {/* Interactive Transcript */}
            <div 
               ref={transcriptContainerRef}
               className="scrollbar-custom flex-1 overflow-y-auto px-6 py-5 bg-[color:var(--e3-shell)]"
            >
               {messages.length === 0 ? (
                  <div className="text-center text-[color:var(--e3-text-muted)] e3-font-body mt-10">
                     No transcript available.
                  </div>
               ) : (
                  <div className="space-y-6">
                     {messages.map((block, index) => {
                        const isActive = index === activeIndex;
                        const isAgent = block.role === "agent";
                        
                        return (
                           <div
                              key={block.id}
                              ref={(el) => {
                                 if (el) messageRefs.current.set(block.id, el);
                              }}
                              className={cx(
                                 "flex gap-4 transition-all duration-300",
                                 isAgent ? "flex-row" : "flex-row-reverse",
                                 isActive ? "opacity-100 scale-[1.02]" : "opacity-70 hover:opacity-100"
                              )}
                              onClick={() => audioUrl && handleMessageClick(block.offsetSeconds)}
                              role={audioUrl ? "button" : "presentation"}
                              title={audioUrl ? "Click to jump to this point in the audio" : undefined}
                           >
                              <div
                                 className={cx(
                                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xs font-semibold e3-font-heading shadow-sm",
                                    isAgent
                                       ? "border border-[color:var(--e3-brand-accent)] bg-[color:var(--e3-brand-deep)] text-white"
                                       : "border border-[color:var(--e3-border-strong)] bg-[color:var(--e3-surface-alt)] text-[color:var(--e3-text-strong)]"
                                 )}
                              >
                                 {isAgent ? "A" : "C"}
                              </div>
                              <div
                                 className={cx(
                                    "max-w-[80%] rounded-[24px] px-5 py-4 cursor-pointer",
                                    isAgent
                                       ? "rounded-tl-sm border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface)]"
                                       : "rounded-tr-sm border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)]",
                                    isActive && "ring-2 ring-[color:var(--e3-brand-lavender)] ring-offset-2 ring-offset-[color:var(--e3-shell)] shadow-md",
                                    block.isAgreement && "border-[color:var(--e3-chip-success-border)] bg-[color:var(--e3-chip-success-bg)] ring-1 ring-[color:var(--e3-chip-success-border)]"
                                 )}
                              >
                                 <div className="mb-2 flex items-center justify-between gap-4">
                                    <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--e3-text-soft)] e3-font-heading">
                                       {isAgent ? "Agent" : "Caller"}
                                    </span>
                                    <span className="text-[11px] text-[color:var(--e3-text-muted)] e3-font-mono">
                                       {formatTime(block.offsetSeconds)}
                                    </span>
                                 </div>
                                 <div className="space-y-2 text-[15px] leading-relaxed text-[color:var(--e3-text-strong)] e3-font-body">
                                    {block.content.map((text, i) => (
                                       <p key={i}>
                                          {block.isAgreement && text.includes(agreedPrice?.toString() || "") ? (
                                             <span className="font-semibold text-[color:var(--e3-chip-success-text)] bg-[color:var(--e3-chip-success-bg)] px-1 py-0.5 rounded">
                                                {text}
                                             </span>
                                          ) : (
                                             text
                                          )}
                                       </p>
                                    ))}
                                 </div>
                                 {block.isAgreement && (
                                    <div className="mt-3 flex items-center gap-1.5 text-xs font-semibold text-[color:var(--e3-chip-success-text)] e3-font-heading">
                                       <div className="h-1.5 w-1.5 rounded-full bg-[color:var(--e3-chip-success-text)]" />
                                       Agreement Reached
                                    </div>
                                 )}
                              </div>
                           </div>
                        );
                     })}
                  </div>
               )}
            </div>
         </div>
      </Modal>
   );
}
