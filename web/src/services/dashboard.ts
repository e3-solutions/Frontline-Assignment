import type { SupabaseClient } from "@supabase/supabase-js";
import { createDashboardService } from "@/src/services/supabase/server/dashboard";
import type {
  LoadRecord,
  CallRecord,
  EmailRecord,
  EmailInteraction,
  DashboardSummary,
  LoadNegotiation,
  LoadFormData,
  CallOutcome,
  TranscriptMessage,
} from "@/src/types/dashboard";

const getString = (value: unknown) => (typeof value === "string" && value.trim() ? value : undefined);

const getNumber = (value: unknown) => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
};

type StopRecord = {
  stop_number?: number | null;
  expected_date?: string | null;
  appointment_time?: string | null;
  stop_city?: string | null;
  city?: string | null;
  state_code?: string | null;
  country_code?: string | null;
  is_pickup?: boolean | null;
  is_dropoff?: boolean | null;
};

const buildLocationLabel = (city?: string, state?: string, country?: string) =>
  [city, state, country].filter(Boolean).join(", ") || undefined;

const getOrderedStops = (load: Record<string, unknown>): StopRecord[] => {
  const stops = load.stops;
  if (!Array.isArray(stops)) return [];
  return stops
    .filter((stop): stop is StopRecord => Boolean(stop) && typeof stop === "object")
    .sort((left, right) => (left.stop_number ?? Number.MAX_SAFE_INTEGER) - (right.stop_number ?? Number.MAX_SAFE_INTEGER));
};

const findStop = (stops: StopRecord[], actionKey: "is_pickup" | "is_dropoff", reverse = false) => {
  const ordered = reverse ? [...stops].reverse() : stops;
  return ordered.find((stop) => stop[actionKey] === true) ?? ordered[0];
};

const getStopDateTime = (stop?: StopRecord) => {
  const appointmentTime = getString(stop?.appointment_time);
  if (!appointmentTime) return undefined;
  if (appointmentTime.includes("T")) return appointmentTime;

  const expectedDate = getString(stop?.expected_date);
  if (/^\d{2}:\d{2}/.test(appointmentTime) && expectedDate) {
    return `${expectedDate}T${appointmentTime.slice(0, 5)}:00`;
  }

  return undefined;
};

const joinText = (...values: unknown[]) => {
  const seen = new Set<string>();
  const parts: string[] = [];
  values.forEach((value) => {
    const cleaned = getString(value);
    if (!cleaned) return;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    parts.push(cleaned);
  });
  return parts.length ? parts.join("\n") : undefined;
};

const mapDatabaseDataToLoadFormData = (load: Record<string, unknown>): LoadFormData => {
  const offerRate = getNumber(load.offer_rate) ?? 0;
  const totalWeight = load.total_weight;
  const weightString =
    typeof totalWeight === "number"
      ? String(totalWeight)
      : typeof totalWeight === "string" && totalWeight.trim()
      ? totalWeight
      : undefined;
  const stops = getOrderedStops(load);
  const pickupStop = findStop(stops, "is_pickup");
  const dropoffStop = findStop(stops, "is_dropoff", true);
  const requirements = joinText(load.special_requirements, load.load_posting_description);

  return {
    origin: buildLocationLabel(
      getString(pickupStop?.stop_city) ?? getString(pickupStop?.city),
      getString(pickupStop?.state_code),
      getString(pickupStop?.country_code)
    ),
    destination: buildLocationLabel(
      getString(dropoffStop?.stop_city) ?? getString(dropoffStop?.city),
      getString(dropoffStop?.state_code),
      getString(dropoffStop?.country_code)
    ),
    equipment: getString(load.equipment_type_name) ?? getString(load.mode_name),
    weight: weightString,
    pickupDate: getString(pickupStop?.expected_date),
    dropoffDate: getString(dropoffStop?.expected_date),
    pickupTime: getStopDateTime(pickupStop),
    requirements,
    trackerRequired: requirements?.toLowerCase().includes("tracker required") ?? false,
    pricing: {
      initial: offerRate,
      target: offerRate,
      ceiling: getNumber(load.max_pay_amount) ?? 0,
    },
    customer: getString(load.customer_name),
  };
};

const aggregateCallCounts = (calls: { load_id: string }[]): Record<string, number> =>
  calls.reduce((acc, call) => {
    acc[call.load_id] = (acc[call.load_id] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

const groupNegotiationsByLoadId = (
  negotiations: { id: string; load_id: string; call_id?: string | null; created_at: string; agreed_price: number; above_max?: boolean; carrier_contact_name?: string; carrier_contact_phone?: string }[]
): Record<string, LoadNegotiation[]> =>
  negotiations.reduce((acc, neg) => {
    if (!acc[neg.load_id]) acc[neg.load_id] = [];
    const isAboveMax = neg.above_max === true;
    const hasPrice = neg.agreed_price != null && neg.agreed_price > 0;
    const status: "success" | "no_agreement" | "error" =
      isAboveMax ? "no_agreement" : hasPrice ? "success" : "no_agreement";

    acc[neg.load_id].push({
      id: neg.id,
      loadId: neg.load_id,
      callId: neg.call_id ?? undefined,
      createdAt: neg.created_at,
      agreedPrice: neg.agreed_price,
      status,
      aboveMax: isAboveMax,
      carrierContactName: neg.carrier_contact_name,
      carrierContactPhone: neg.carrier_contact_phone,
    });
    return acc;
  }, {} as Record<string, LoadNegotiation[]>);

const mapCallRowToRecord = (call: {
  id: string;
  load_id?: string | null;
  daily_call_id?: string | null;
  negotiation_result?: string | null;
  caller_number?: string | null;
  caller_country_code?: string | null;
  initiated_at: string;
  updated_at: string;
  ended_at?: string | null;
  end_reason?: CallOutcome | null;
  result?: {
    outcome?: CallOutcome;
    agreed_price?: number;
    notes?: string;
    audio_url?: string;
  } | null;
  transcription?: TranscriptMessage[] | null;
  recording_url?: string | null;
}): CallRecord => {
  const outcome = call.end_reason || call.result?.outcome || "error";

  return {
    id: call.id,
    // calls.load_id holds the load_number for post-migration calls;
    // historical orphans (Salesforce-shaped IDs) display as-is.
    loadId: call.load_id || "N/A",
    dailyCallId: call.daily_call_id || "",
    negotiationResult: call.negotiation_result || undefined,
    callerNumber: call.caller_number || "N/A",
    callerCountryCode: call.caller_country_code || "+1",
    initiatedAt: call.initiated_at,
    updatedAt: call.updated_at,
    endedAt: call.ended_at || undefined,
    endReason: call.end_reason || undefined,
    result: {
      outcome,
      agreed_price: call.result?.agreed_price,
      transcription: call.transcription ?? undefined,
      notes: call.result?.notes,
      audio_url: call.recording_url || call.result?.audio_url,
    },
  };
};

const calculateSummary = (loads: LoadRecord[], calls: CallRecord[], emails: EmailRecord[]): DashboardSummary => {
  const agreements = loads.reduce((total, load) => total + load.negotiations.length, 0);

  const targetPrices = loads
    .map((load) => load.data?.pricing?.target)
    .filter((price): price is number => typeof price === "number" && !isNaN(price));

  const averageRate =
    targetPrices.length > 0
      ? `$${(targetPrices.reduce((sum, price) => sum + price, 0) / targetPrices.length).toFixed(0)}`
      : "$0";

  return {
    totalLoads: loads.length,
    totalCalls: calls.length,
    totalEmails: emails.length,
    agreements,
    averageRate,
  };
};

export const createDashboardBusinessService = (client: SupabaseClient) => {
  const dbService = createDashboardService(client);

  const fetchLoadsWithDetails = async (): Promise<LoadRecord[]> => {
    const { data: loads, error: loadsError } = await dbService.loads.getAll();
    if (loadsError) throw new Error(`Failed to fetch loads: ${loadsError.message}`);
    if (!loads?.length) return [];

    // `loads.load_number` is the primary key and the value stored in
    // `calls.load_id` / `negotiations.load_id` going forward.
    const loadNumbers = loads
      .map((load) => load.load_number)
      .filter((value): value is string => typeof value === "string" && value.length > 0);

    const [callsResult, negotiationsResult] = await Promise.all([
      dbService.calls.getByLoadIds(loadNumbers),
      dbService.negotiations.getByLoadIds(loadNumbers),
    ]);

    if (callsResult.error) throw new Error(`Failed to fetch calls: ${callsResult.error.message}`);
    if (negotiationsResult.error) throw new Error(`Failed to fetch negotiations: ${negotiationsResult.error.message}`);

    const callCounts = aggregateCallCounts(callsResult.data || []);
    const negotiationsByLoad = groupNegotiationsByLoadId(negotiationsResult.data || []);

    return loads.map((load) => {
      const loadNumber = (load.load_number as string) || "N/A";
      const negotiations = negotiationsByLoad[loadNumber] || [];
      return {
        id: loadNumber,
        loadId: loadNumber,
        orgId: "",
        createdAt: load.created_at as string,
        updatedAt: load.updated_at as string,
        data: mapDatabaseDataToLoadFormData(load),
        callCount: callCounts[loadNumber] || 0,
        negotiations,
      };
    });
  };

  const fetchCallsWithDetails = async (): Promise<CallRecord[]> => {
    const { data: calls, error } = await dbService.calls.getAllWithLoads();
    if (error) throw new Error(`Failed to fetch calls: ${error.message}`);
    if (!calls) return [];

    // KNOWN BUG: Some calls have result stored as '{}' in Supabase,
    // which causes them to show as "Error" outcome. Filter these out
    // until the upstream data issue is fixed.
    const validCalls = calls.filter((call) => {
      const result = call.result;
      if (!result || (typeof result === "object" && !call.end_reason && !result.outcome)) {
        return false;
      }
      return true;
    });

    return validCalls.map(mapCallRowToRecord);
  };

  const fetchEmailThreads = async (): Promise<EmailRecord[]> => {
    const { data, error } = await dbService.emailThreads.getAll();
    if (error) throw new Error(`Failed to fetch email threads: ${error.message}`);
    if (!data) return [];

    return data.map((row) => {
      const negs = (Array.isArray(row.negotiations) ? row.negotiations : row.negotiations ? [row.negotiations] : [])
        .sort((a: { created_at?: string }, b: { created_at?: string }) =>
          new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime()
        );
      const latestNeg = negs[0] ?? null;

      const interactions: EmailInteraction[] = (
        Array.isArray(row.email_interactions) ? row.email_interactions : []
      )
        .sort((a: { created_at: string }, b: { created_at: string }) =>
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        )
        .map((i: { id: string; client_response: string | null; bot_response: string | null; created_at: string }) => ({
          id: i.id,
          clientResponse: i.client_response,
          botResponse: i.bot_response,
          createdAt: i.created_at,
        }));

      return {
        id: row.id,
        threadId: row.thread_id,
        subject: row.subject ?? null,
        carrierEmail: row.client_email,
        // email_thread.load_id holds the load_number for post-migration threads.
        loadId: row.load_id ?? null,
        ended: row.ended ?? false,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
        interactions,
        negotiation: latestNeg
          ? {
              agreedPrice: latestNeg.agreed_price ?? null,
              aboveMax: latestNeg.above_max ?? false,
              carrierContactName: latestNeg.carrier_contact_name ?? null,
              carrierContactPhone: latestNeg.carrier_contact_phone ?? null,
            }
          : null,
      };
    });
  };

  const fetchAll = async () => {
    const [loads, calls, emails] = await Promise.all([
      fetchLoadsWithDetails(),
      fetchCallsWithDetails(),
      fetchEmailThreads(),
    ]);

    return {
      loads,
      calls,
      emails,
      summary: calculateSummary(loads, calls, emails),
    };
  };

  return { fetchLoadsWithDetails, fetchCallsWithDetails, fetchEmailThreads, fetchAll };
};
