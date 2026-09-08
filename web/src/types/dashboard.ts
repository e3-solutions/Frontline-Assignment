export type LoadPricing = {
   initial: number;
   target: number;
   ceiling: number;
};

export type LoadNegotiation = {
   id: string;
   loadId: string;
   callId?: string;
   createdAt: string;
   agreedPrice?: number;
   status: "success" | "no_agreement" | "error";
   notes?: string;
   aboveMax?: boolean;
   carrierContactName?: string;
   carrierContactPhone?: string;
};

// Base load data structure (camelCase for database storage)
export type LoadFormData = {
   origin?: string;
   destination?: string;
   equipment?: string;
   weight?: string;
   pickupDate?: string;
   dropoffDate?: string;
   pickupTime?: string;
   requirements?: string;
   trackerRequired?: boolean;
   pricing?: LoadPricing;
   broker?: string;
   customer?: string;
};

// API request format (snake_case matching backend expectations)
export type LoadApiRequest = {
   load_id: string;
   contact_phone: string;
   country_code: string;
   transfer_call_to: string;
   transfer_country_code: string;
   broker_name: string;
   company_name: string;
   customer_name: string;
   origin_location: string;
   destination_location: string;
   pickup_time: string;
   delivery_time: string;
   requirements: string;
   tracker_required: boolean;
   broker_initial_offer: string;
   broker_target_rate: string;
   broker_max_rate: string;
};

// Legacy export for backwards compatibility (deprecated - use LoadApiRequest instead)
export type { LoadApiRequest as NegotiationFormData };

export type LoadRecord = {
   id: string;
   loadId: string;
   orgId: string;
   createdAt: string;
   updatedAt: string;
   data?: LoadFormData;
   callCount: number;
   negotiations: LoadNegotiation[];
};

export type CallOutcome = "abrupt" | "agreement" | "no_agreement" | "error" | "load_not_found" | "mc_not_found" | "bid_placed" | "call_transferred";

export type TranscriptMessage = {
   role: "caller" | "agent";
   content: string;
   timestamp: string;
};

export type CallResult = {
   outcome: CallOutcome;
   agreed_price?: number;
   transcription?: TranscriptMessage[];
   notes?: string;
   audio_url?: string;
};

export type CallRecord = {
   id: string;
   loadId: string;
   dailyCallId: string;
   telephonyProvider: "daily" | "livekit";
   providerCallId: string;
   negotiationResult?: string;
   callerNumber: string;
   callerCountryCode: string;
   initiatedAt: string;
   updatedAt: string;
   endedAt?: string;
   endReason?: CallOutcome;
   result: CallResult;
};

export type DashboardSummary = {
   totalLoads: number;
   totalCalls: number;
   totalEmails: number;
   agreements: number;
   averageRate: string;
};

export type EmailInteraction = {
   id: string;
   clientResponse: string | null;
   botResponse: string | null;
   createdAt: string;
};

export type EmailNegotiation = {
   agreedPrice: number | null;
   aboveMax: boolean;
   carrierContactName: string | null;
   carrierContactPhone: string | null;
};

export type EmailRecord = {
   id: string;
   threadId: string;
   subject: string | null;
   carrierEmail: string;
   loadId: string | null;
   ended: boolean;
   createdAt: string;
   updatedAt: string;
   interactions: EmailInteraction[];
   negotiation: EmailNegotiation | null;
};
