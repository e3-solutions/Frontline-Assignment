"use client";

import { useState } from "react";
import { Button, DatePicker, FormField, Select } from "@e3-solutions/ui";
import { downloadCSV } from "@/src/utils/csv";
import type { CallRecord, EmailRecord, LoadRecord } from "@/src/types/dashboard";

type ExportsViewProps = {
   loads: LoadRecord[];
   calls: CallRecord[];
   emails: EmailRecord[];
};

type DataType = "loads" | "calls" | "emails" | "negotiations";

export function ExportsView({ loads, calls, emails }: ExportsViewProps) {
   const [dataType, setDataType] = useState<DataType>("loads");
   const [fromDate, setFromDate] = useState<Date | null>(null);
   const [toDate, setToDate] = useState<Date | null>(null);

   const filterByDate = <T extends { createdAt?: string; initiatedAt?: string }>(items: T[]): T[] => {
      return items.filter((item) => {
         const date = new Date(item.createdAt || item.initiatedAt || "");
         if (fromDate && date < fromDate) return false;
         if (toDate && date > new Date(toDate.getTime() + 86400000)) return false;
         return true;
      });
   };

   const handleExport = () => {
      const now = new Date().toISOString().slice(0, 10);

      switch (dataType) {
         case "loads": {
            const filtered = filterByDate(loads.map((l) => ({ ...l, createdAt: l.createdAt })));
            downloadCSV(
               `loads-export-${now}.csv`,
               ["Load ID", "Origin", "Destination", "Customer", "Target Rate", "Initial Rate", "Max Rate", "Calls", "Agreements", "Created"],
               filtered.map((load) => [
                  load.loadId,
                  load.data?.origin || "",
                  load.data?.destination || "",
                  load.data?.customer || "",
                  String(load.data?.pricing?.target || ""),
                  String(load.data?.pricing?.initial || ""),
                  String(load.data?.pricing?.ceiling || ""),
                  String(load.callCount),
                  String(load.negotiations.filter((n) => !n.aboveMax && n.agreedPrice).length),
                  load.createdAt,
               ])
            );
            break;
         }
         case "calls": {
            const filtered = filterByDate(calls.map((c) => ({ ...c, initiatedAt: c.initiatedAt })));
            downloadCSV(
               `calls-export-${now}.csv`,
               ["Caller", "Load ID", "Outcome", "Started", "Ended", "Duration (min)", "Recording URL"],
               filtered.map((call) => {
                  const duration = call.endedAt
                     ? Math.round((new Date(call.endedAt).getTime() - new Date(call.initiatedAt).getTime()) / 60000)
                     : 0;
                  return [
                     call.callerNumber,
                     call.loadId,
                     call.endReason ?? call.result.outcome,
                     call.initiatedAt,
                     call.endedAt || "",
                     String(duration),
                     call.result.audio_url || "",
                  ];
               })
            );
            break;
         }
         case "emails": {
            const filtered = filterByDate(emails.map((e) => ({ ...e, createdAt: e.createdAt })));
            downloadCSV(
               `emails-export-${now}.csv`,
               ["Subject", "Carrier Email", "Load ID", "Status", "Messages", "Created", "Updated"],
               filtered.map((email) => {
                  const status = email.negotiation && !email.negotiation.aboveMax && email.negotiation.agreedPrice
                     ? "Agreement"
                     : email.negotiation?.aboveMax
                        ? "Bid Placed"
                        : email.ended
                           ? "Ended"
                           : "Active";
                  return [
                     email.subject || "",
                     email.carrierEmail,
                     email.loadId || "",
                     status,
                     String(email.interactions.length),
                     email.createdAt,
                     email.updatedAt,
                  ];
               })
            );
            break;
         }
         case "negotiations": {
            const allNegs = loads.flatMap((load) =>
               load.negotiations.map((n) => ({ ...n, loadId: load.loadId, target: load.data?.pricing?.target }))
            );
            const filtered = filterByDate(allNegs);
            downloadCSV(
               `negotiations-export-${now}.csv`,
               ["Load ID", "Status", "Agreed Price", "Target Rate", "Above Max", "Contact Name", "Contact Phone", "Created"],
               filtered.map((n) => [
                  n.loadId,
                  n.aboveMax ? "Bid" : n.status,
                  String(n.agreedPrice || ""),
                  String(n.target || ""),
                  n.aboveMax ? "Yes" : "No",
                  n.carrierContactName || "",
                  n.carrierContactPhone || "",
                  n.createdAt,
               ])
            );
            break;
         }
      }
   };

   const allNegotiations = loads.flatMap((load) =>
      load.negotiations.map((n) => ({ ...n, loadId: load.loadId }))
   );

   const getFilteredCount = () => {
      switch (dataType) {
         case "loads": return filterByDate(loads.map((l) => ({ createdAt: l.createdAt }))).length;
         case "calls": return filterByDate(calls.map((c) => ({ initiatedAt: c.initiatedAt }))).length;
         case "emails": return filterByDate(emails.map((e) => ({ createdAt: e.createdAt }))).length;
         case "negotiations": return filterByDate(allNegotiations).length;
      }
   };

   const filteredCount = getFilteredCount();
   const totalCount = {
      loads: loads.length,
      calls: calls.length,
      emails: emails.length,
      negotiations: allNegotiations.length,
   }[dataType];

   return (
      <div className="space-y-6">
         <header>
            <h1 className="text-3xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
               Exports
            </h1>
            <p className="mt-1 text-sm text-[color:var(--e3-text-muted)] e3-font-body">
               Download your data as CSV files
            </p>
         </header>

         <div className="rounded-[22px] border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface)] p-6">
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
               <FormField label="Data Type">
                  <Select
                     value={dataType}
                     onChange={(e) => setDataType(e.target.value as DataType)}
                  >
                     <option value="loads">Loads ({loads.length})</option>
                     <option value="calls">Calls ({calls.length})</option>
                     <option value="emails">Emails ({emails.length})</option>
                     <option value="negotiations">Negotiations ({allNegotiations.length})</option>
                  </Select>
               </FormField>
               <FormField label="From Date">
                  <DatePicker value={fromDate} onChange={setFromDate} placeholder="Start date" />
               </FormField>
               <FormField label="To Date">
                  <DatePicker value={toDate} onChange={setToDate} placeholder="End date" />
               </FormField>
               <div className="flex items-end">
                  <Button onClick={handleExport} variant="primary" size="md">
                     Download CSV
                  </Button>
               </div>
            </div>
         </div>

         {/* Preview */}
         <div className="rounded-[22px] border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface)] p-6">
            <p className="text-sm text-[color:var(--e3-text-muted)] e3-font-body">
               {filteredCount} of {totalCount} {dataType} records will be exported
               {fromDate || toDate ? " (filtered by date range)" : ""}.
            </p>
         </div>
      </div>
   );
}
