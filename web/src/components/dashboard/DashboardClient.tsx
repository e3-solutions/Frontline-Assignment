"use client";

import { useDeferredValue, useMemo, useState } from "react";

import {
   BarChartIcon,
   DashboardFilters,
   DashboardLayout,
   DownloadIcon,
   MailIcon,
   Modal,
   TruckIcon,
   PhoneIcon,
   SettingsIcon,
   UserIcon,
   type DashboardNavGroup,
   type FilterOption,
} from "@e3-solutions/ui";
import NegotiationForm from "@/src/components/NegotiationForm";
import { ThemedLogo } from "@/src/components/ThemedLogo";
import { AgentPhone } from "@/src/components/AgentPhone";
import { ThemeToggle } from "@/src/components/ThemeToggle";
import { UserMenu } from "@/src/components/auth/UserMenu";
import { useAuth } from "@/src/contexts/AuthContext";
import { CallsTable } from "@/src/components/dashboard/CallCard";
import { CarriersView } from "@/src/components/dashboard/CarriersView";
import { DashboardHome } from "@/src/components/dashboard/DashboardHome";
import { EmailsTable } from "@/src/components/dashboard/EmailCard";
import { ExportsView } from "@/src/components/dashboard/ExportsView";
import { LoadsTable } from "@/src/components/dashboard/LoadCard";
import { LoadDrawer } from "@/src/components/dashboard/LoadDrawer";
import type {
   CallOutcome,
   CallRecord,
   DashboardSummary,
   EmailRecord,
   LoadRecord,
} from "@/src/types/dashboard";
import { fuzzySearch } from "@/src/utils/search";

type DashboardClientProps = {
   loads: LoadRecord[];
   calls: CallRecord[];
   emails: EmailRecord[];
   // TODO: summary is computed server-side but metrics are derived client-side in DashboardHome.
   // Remove server-side calculateSummary once client-side metrics are validated.
   summary?: DashboardSummary;
};

type DashboardView = "home" | "loads" | "calls" | "emails" | "carriers" | "exports";
type LoadSearchField = "loadId" | "lane" | "customer";
type LoadSort = "updated_desc" | "target_desc" | "calls_desc";
type CallSearchField = "caller" | "loadId" | "callId";
type CallSort = "started_desc" | "started_asc" | "duration_desc" | "ended_desc";
type EmailSearchField = "subject" | "carrier" | "loadId";
type EmailSort = "newest" | "oldest" | "most_messages";
type EmailStatus = "all" | "active" | "ended" | "agreed" | "bid";

const loadSearchOptions: FilterOption[] = [
   { value: "loadId", label: "Load ID" },
   { value: "lane", label: "Lane" },
   { value: "customer", label: "Customer" },
];

const loadSortOptions: FilterOption[] = [
   { value: "updated_desc", label: "Updated" },
   { value: "target_desc", label: "Target" },
   { value: "calls_desc", label: "Calls" },
];

const callSearchOptions: FilterOption[] = [
   { value: "caller", label: "Caller" },
   { value: "loadId", label: "Load ID" },
   { value: "callId", label: "Call ID" },
];

const callSortOptions: FilterOption[] = [
   { value: "started_desc", label: "Started (Newest)" },
   { value: "started_asc", label: "Started (Oldest)" },
   { value: "duration_desc", label: "Duration" },
   { value: "ended_desc", label: "Ended" },
];

const emailSearchOptions: FilterOption[] = [
   { value: "subject", label: "Subject" },
   { value: "carrier", label: "Carrier" },
   { value: "loadId", label: "Load ID" },
];

const emailSortOptions: FilterOption[] = [
   { value: "newest", label: "Newest" },
   { value: "oldest", label: "Oldest" },
   { value: "most_messages", label: "Most Messages" },
];

const emailStatusOptions: FilterOption[] = [
   { value: "all", label: "All statuses" },
   { value: "active", label: "Active" },
   { value: "ended", label: "Ended" },
   { value: "agreed", label: "Agreement" },
   { value: "bid", label: "Bid Placed" },
];

const callOutcomeLabel: Record<CallOutcome, string> = {
   agreement: "Agreed",
   bid_placed: "Bid Placed",
   no_agreement: "No Agreement",
   load_not_found: "Load Not Found",
   mc_not_found: "MC Not Found",
   abrupt: "Abrupt",
   error: "Error",
   call_transferred: "Transferred",
};

export function DashboardClient({ loads, calls, emails, summary: _summary }: DashboardClientProps) {
   const { user } = useAuth();
   const [view, setView] = useState<DashboardView>("home");
   const [expandedLoadId, setExpandedLoadId] = useState<string | null>(null);
   const [expandedCallId, setExpandedCallId] = useState<string | null>(null);
   const [selectedLoad, setSelectedLoad] = useState<LoadRecord | null>(null);
   const [isLoadModalOpen, setIsLoadModalOpen] = useState(false);
   const [isCreateLoadOpen, setIsCreateLoadOpen] = useState(false);
   const [loadFilters, setLoadFilters] = useState<{
      query: string;
      searchField: LoadSearchField;
      sort: LoadSort;
      customer: string;
   }>({
      query: "",
      searchField: "loadId",
      sort: "updated_desc",
      customer: "all",
   });
   const [callFilters, setCallFilters] = useState<{
      query: string;
      searchField: CallSearchField;
      sort: CallSort;
      outcome: string;
   }>({
      query: "",
      searchField: "caller",
      sort: "started_desc",
      outcome: "all",
   });
   const [emailFilters, setEmailFilters] = useState<{
      query: string;
      searchField: EmailSearchField;
      sort: EmailSort;
      status: EmailStatus;
   }>({
      query: "",
      searchField: "subject",
      sort: "newest",
      status: "all",
   });

   const deferredLoadQuery = useDeferredValue(loadFilters.query);
   const deferredCallQuery = useDeferredValue(callFilters.query);
   const deferredEmailQuery = useDeferredValue(emailFilters.query);

   const loadCustomerOptions = useMemo<FilterOption[]>(() => {
      const customers = Array.from(
         new Set(
            loads
               .map((load) => load.data?.customer)
               .filter((customer): customer is string => Boolean(customer))
         )
      ).sort((left, right) => left.localeCompare(right));

      return [
         { value: "all", label: "All customers" },
         ...customers.map((customer) => ({ value: customer, label: customer })),
      ];
   }, [loads]);

   const callOutcomeOptions = useMemo<FilterOption[]>(() => {
      const outcomes = Array.from(
         new Set(calls.map((call) => call.endReason ?? call.result.outcome))
      );

      const ordered = Object.keys(callOutcomeLabel).filter((outcome) =>
         outcomes.includes(outcome as CallOutcome)
      ) as CallOutcome[];

      return [
         { value: "all", label: "All outcomes" },
         ...ordered.map((outcome) => ({
            value: outcome,
            label: callOutcomeLabel[outcome],
         })),
      ];
   }, [calls]);

   const filteredLoads = useMemo(() => {
      let result = [...loads];

      if (loadFilters.customer !== "all") {
         result = result.filter((load) => load.data?.customer === loadFilters.customer);
      }

      if (deferredLoadQuery.trim()) {
         result = fuzzySearch(result, deferredLoadQuery, (load) => {
            switch (loadFilters.searchField) {
               case "lane":
                  return `${load.data?.origin || ""} ${load.data?.destination || ""}`;
               case "customer":
                  return load.data?.customer;
               case "loadId":
               default:
                  return load.loadId;
            }
         });
      }

      return result.sort((left, right) => {
         switch (loadFilters.sort) {
            case "target_desc":
               return (right.data?.pricing?.target || 0) - (left.data?.pricing?.target || 0);
            case "calls_desc":
               return right.callCount - left.callCount;
            case "updated_desc":
            default:
               return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
         }
      });
   }, [deferredLoadQuery, loadFilters.customer, loadFilters.searchField, loadFilters.sort, loads]);

   const filteredCalls = useMemo(() => {
      let result = [...calls];

      if (callFilters.outcome !== "all") {
         result = result.filter(
            (call) => (call.endReason ?? call.result.outcome) === callFilters.outcome
         );
      }

      if (deferredCallQuery.trim()) {
         result = fuzzySearch(result, deferredCallQuery, (call) => {
            switch (callFilters.searchField) {
               case "loadId":
                  return call.loadId;
               case "callId":
                  return `${call.id} ${call.dailyCallId}`;
               case "caller":
               default:
                  return call.callerNumber;
            }
         });
      }

      return result.sort((left, right) => {
         switch (callFilters.sort) {
            case "duration_desc":
               return getCallDurationMinutes(right) - getCallDurationMinutes(left);
            case "ended_desc":
               return getOptionalDateValue(right.endedAt) - getOptionalDateValue(left.endedAt);
            case "started_asc":
               return new Date(left.initiatedAt).getTime() - new Date(right.initiatedAt).getTime();
            case "started_desc":
            default:
               return new Date(right.initiatedAt).getTime() - new Date(left.initiatedAt).getTime();
         }
      });
   }, [callFilters.outcome, callFilters.searchField, callFilters.sort, calls, deferredCallQuery]);

   const filteredEmails = useMemo(() => {
      let result = [...emails];

      if (emailFilters.status !== "all") {
         result = result.filter((email) => {
            const isAgreed = email.negotiation && !email.negotiation.aboveMax && email.negotiation.agreedPrice;
            const isBid = email.negotiation?.aboveMax;
            switch (emailFilters.status) {
               case "active": return !email.ended;
               case "ended": return email.ended;
               case "agreed": return isAgreed;
               case "bid": return isBid;
               default: return true;
            }
         });
      }

      if (deferredEmailQuery.trim()) {
         result = fuzzySearch(result, deferredEmailQuery, (email) => {
            switch (emailFilters.searchField) {
               case "carrier": return email.carrierEmail;
               case "loadId": return email.loadId;
               case "subject":
               default: return email.subject;
            }
         });
      }

      return result.sort((left, right) => {
         switch (emailFilters.sort) {
            case "oldest":
               return new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime();
            case "most_messages":
               return right.interactions.length - left.interactions.length;
            case "newest":
            default:
               return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime();
         }
      });
   }, [deferredEmailQuery, emailFilters.searchField, emailFilters.sort, emailFilters.status, emails]);

   const visibleExpandedLoadId =
      expandedLoadId && filteredLoads.some((load) => load.id === expandedLoadId)
         ? expandedLoadId
         : null;

   const visibleExpandedCallId =
      expandedCallId && filteredCalls.some((call) => call.id === expandedCallId)
         ? expandedCallId
         : null;

   const hasActiveLoadFilters = Boolean(loadFilters.query.trim()) || loadFilters.customer !== "all";
   const hasActiveCallFilters = Boolean(callFilters.query.trim()) || callFilters.outcome !== "all";

   const handleOpenLoadDetails = (load: LoadRecord) => {
      setSelectedLoad(load);
      setIsLoadModalOpen(true);
   };

   const handleOpenLoadFromCall = (loadId: string) => {
      const match = loads.find((load) => load.loadId === loadId);
      if (!match) {
         return;
      }

      handleOpenLoadDetails(match);
   };

   const handleCloseLoadModal = () => {
      setIsLoadModalOpen(false);
      setSelectedLoad(null);
   };

   const viewTitles: Record<DashboardView, string> = {
      home: "Overview", loads: "Loads", calls: "Calls", emails: "Emails",
      carriers: "Carriers", exports: "Exports",
   };
   const currentTitle = viewTitles[view];
   const currentTable =
      view === "carriers" ? (
         <CarriersView loads={loads} calls={calls} emails={emails} />
      ) : view === "exports" ? (
         <ExportsView loads={loads} calls={calls} emails={emails} />
      ) : view === "loads" ? (
         <LoadsTable
            loads={filteredLoads}
            expandedLoadId={visibleExpandedLoadId}
            onExpandedLoadChange={setExpandedLoadId}
            onOpenLoadDetails={handleOpenLoadDetails}
            emptyState={{
               title: loads.length === 0 ? "No loads found" : "No loads match your search",
               description:
                  loads.length === 0
                     ? "Create your first load to start tracking negotiations here."
                     : hasActiveLoadFilters
                       ? "Try a different search or clear an active filter."
                       : "No loads are available right now.",
            }}
         />
      ) : view === "calls" ? (
         <CallsTable
            calls={filteredCalls}
            expandedCallId={visibleExpandedCallId}
            onExpandedCallChange={setExpandedCallId}
            onLoadClick={handleOpenLoadFromCall}
            sort={callFilters.sort}
            onStartedSortToggle={() =>
               setCallFilters((current) => ({
                  ...current,
                  sort: current.sort === "started_desc" ? "started_asc" : "started_desc",
               }))
            }
            emptyState={{
               title: calls.length === 0 ? "No calls found" : "No calls match your search",
               description:
                  calls.length === 0
                     ? "Calls will appear here after negotiations begin."
                     : hasActiveCallFilters
                       ? "Try a different search or clear an active filter."
                       : "No calls are available right now.",
            }}
         />
      ) : (
         <EmailsTable
            emails={filteredEmails}
            onLoadClick={handleOpenLoadFromCall}
            emptyState={{
               title: emails.length === 0 ? "No email threads found" : "No emails match your search",
               description:
                  emails.length === 0
                     ? "Email negotiations will appear here once threads are started."
                     : "Try a different search or clear an active filter.",
            }}
         />
      );

   const navGroups: DashboardNavGroup[] = [
      {
         label: "Main",
         items: [
            {
               id: "home",
               label: "Overview",
               icon: <BarChartIcon className="h-4 w-4" />,
            },
            {
               id: "loads",
               label: "Loads",
               icon: <TruckIcon className="h-4 w-4" />,
               badge: loads.length > 0 ? String(loads.length) : undefined,
            },
            {
               id: "calls",
               label: "Calls",
               icon: <PhoneIcon className="h-4 w-4" />,
               badge: calls.length > 0 ? String(calls.length) : undefined,
            },
            {
               id: "emails",
               label: "Emails",
               icon: <MailIcon className="h-4 w-4" />,
               badge: emails.length > 0 ? String(emails.length) : undefined,
            },
            {
               id: "carriers",
               label: "Carriers",
               icon: <UserIcon className="h-4 w-4" />,
            },
         ],
      },
      {
         label: "Data",
         items: [
            {
               id: "exports",
               label: "Exports",
               icon: <DownloadIcon className="h-4 w-4" />,
            },
         ],
      },
      {
         label: "System",
         items: [
            {
               id: "settings",
               label: "Settings",
               icon: <SettingsIcon className="h-4 w-4" />,
            },
         ],
      },
   ];

   const handleNavSelect = (id: string) => {
      if (id === "settings") {
         window.location.href = "/settings/team";
         return;
      }
      setView(id as DashboardView);
      window.scrollTo(0, 0);
   };

   return (
      <>
         <DashboardLayout
            nav={navGroups}
            activeId={view}
            onSelect={handleNavSelect}
            sidebarWidth={260}
            contentMaxWidth={1400}
            sidebarHeader={
               <div className="flex flex-col items-center gap-1">
                  <ThemedLogo
                     width={80}
                     height={16}
                     priority
                     className="h-auto max-w-[70px] object-contain"
                  />
                  <span className="text-2xl font-semibold tracking-[0.25em] text-[color:var(--e3-text-strong)] font-[family-name:var(--font-oxanium)]">
                     FRONTLINE
                  </span>
               </div>
            }
            sidebarFooter={
               <div className="flex items-center justify-between border-t border-[color:var(--e3-border-subtle)] pt-4">
                  <div className="flex items-center gap-3">
                     <UserMenu />
                     <AgentPhone variant="dark" />
                  </div>
                  <ThemeToggle />
               </div>
            }
         >
            {view === "home" ? (
               <DashboardHome
                  userName={user?.full_name ?? "there"}
                  loads={loads}
                  calls={calls}
                  emails={emails}
                  onNavigate={(v) => { setView(v as DashboardView); window.scrollTo(0, 0); }}
                  onCreateLoad={() => setIsCreateLoadOpen(true)}
                  onOpenLoadDetails={handleOpenLoadDetails}
               />
            ) : view === "carriers" || view === "exports" ? (
               currentTable
            ) : (
               <>
                  <header className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                     <h1 className="text-3xl font-semibold tracking-tight text-[color:var(--e3-text-strong)] e3-font-heading">
                        {currentTitle}
                     </h1>
                     <div className="flex flex-wrap items-center gap-3">
                        <button
                           type="button"
                           onClick={() => setIsCreateLoadOpen(true)}
                           className="inline-flex h-10 items-center rounded-xl bg-[color:var(--e3-brand-accent)] px-5 text-sm font-semibold text-white transition-all hover:bg-[color:var(--e3-brand-deep)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--e3-brand-accent)] focus-visible:ring-offset-2 active:scale-[0.98] e3-font-heading"
                        >
                           Create Load
                        </button>
                     </div>
                  </header>

                  <div className="mb-4">
                     {view === "loads" && (
                        <DashboardFilters
                           query={loadFilters.query}
                           onQueryChange={(value) =>
                              setLoadFilters((current) => ({ ...current, query: value }))
                           }
                           searchPlaceholder="Search loads"
                           searchField={loadFilters.searchField}
                           onSearchFieldChange={(value) =>
                              setLoadFilters((current) => ({
                                 ...current,
                                 searchField: value as LoadSearchField,
                              }))
                           }
                           searchFieldOptions={loadSearchOptions}
                           sortValue={loadFilters.sort}
                           onSortChange={(value) =>
                              setLoadFilters((current) => ({
                                 ...current,
                                 sort: value as LoadSort,
                              }))
                           }
                           sortOptions={loadSortOptions}
                           filterValue={loadFilters.customer}
                           onFilterChange={(value) =>
                              setLoadFilters((current) => ({ ...current, customer: value }))
                           }
                           filterOptions={loadCustomerOptions}
                        />
                     )}
                     {view === "calls" && (
                        <DashboardFilters
                           query={callFilters.query}
                           onQueryChange={(value) =>
                              setCallFilters((current) => ({ ...current, query: value }))
                           }
                           searchPlaceholder="Search calls"
                           searchField={callFilters.searchField}
                           onSearchFieldChange={(value) =>
                              setCallFilters((current) => ({
                                 ...current,
                                 searchField: value as CallSearchField,
                              }))
                           }
                           searchFieldOptions={callSearchOptions}
                           sortValue={callFilters.sort}
                           onSortChange={(value) =>
                              setCallFilters((current) => ({
                                 ...current,
                                 sort: value as CallSort,
                              }))
                           }
                           sortOptions={callSortOptions}
                           filterValue={callFilters.outcome}
                           onFilterChange={(value) =>
                              setCallFilters((current) => ({ ...current, outcome: value }))
                           }
                           filterOptions={callOutcomeOptions}
                        />
                     )}
                     {view === "emails" && (
                        <DashboardFilters
                           query={emailFilters.query}
                           onQueryChange={(value) =>
                              setEmailFilters((current) => ({ ...current, query: value }))
                           }
                           searchPlaceholder="Search emails"
                           searchField={emailFilters.searchField}
                           onSearchFieldChange={(value) =>
                              setEmailFilters((current) => ({
                                 ...current,
                                 searchField: value as EmailSearchField,
                              }))
                           }
                           searchFieldOptions={emailSearchOptions}
                           sortValue={emailFilters.sort}
                           onSortChange={(value) =>
                              setEmailFilters((current) => ({
                                 ...current,
                                 sort: value as EmailSort,
                              }))
                           }
                           sortOptions={emailSortOptions}
                           filterValue={emailFilters.status}
                           onFilterChange={(value) =>
                              setEmailFilters((current) => ({ ...current, status: value as EmailStatus }))
                           }
                           filterOptions={emailStatusOptions}
                        />
                     )}
                  </div>

                  {currentTable}
               </>
            )}
         </DashboardLayout>

         <LoadDrawer
            load={selectedLoad}
            calls={calls}
            emails={emails}
            isOpen={isLoadModalOpen}
            onClose={handleCloseLoadModal}
         />

         <Modal isOpen={isCreateLoadOpen} onClose={() => setIsCreateLoadOpen(false)} className="max-w-5xl">
            <NegotiationForm onClose={() => setIsCreateLoadOpen(false)} />
         </Modal>
      </>
   );
}

function getCallDurationMinutes(call: CallRecord) {
   if (!call.endedAt) {
      return 0;
   }

   return Math.max(
      1,
      Math.round((new Date(call.endedAt).getTime() - new Date(call.initiatedAt).getTime()) / 60000)
   );
}

function getOptionalDateValue(value?: string) {
   if (!value) {
      return 0;
   }

   return new Date(value).getTime();
}
