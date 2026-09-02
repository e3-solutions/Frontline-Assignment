import type { SupabaseClient } from "@supabase/supabase-js";
import type { NegotiationFormData } from "@/src/types/dashboard";

type LocationParts = {
  city?: string;
  state?: string;
  country?: string;
};

const cleanString = (value: unknown) => {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
};

const parseLocation = (value: unknown): LocationParts => {
  const parts = (cleanString(value) || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);

  if (parts.length === 0) {
    return {};
  }

  if (parts.length === 1) {
    return { city: parts[0] };
  }

  if (parts.length === 2) {
    return { city: parts[0], state: parts[1] };
  }

  return {
    city: parts[0],
    state: parts[1],
    country: parts.slice(2).join(", "),
  };
};

const parseNumeric = (value: unknown) => {
  const trimmed = cleanString(value);
  if (!trimmed) return null;

  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
};

const parseDatePart = (value: unknown) => {
  const cleaned = cleanString(value);
  if (!cleaned) return null;
  return cleaned.split("T")[0] || null;
};

const parseTimePart = (value: unknown) => {
  const cleaned = cleanString(value);
  if (!cleaned || !cleaned.includes("T")) return null;
  return cleaned.split("T")[1]?.slice(0, 5) || null;
};

const buildE164Phone = (countryCode: unknown, phone: unknown) => {
  const phoneDigits = cleanString(phone)?.replace(/\D/g, "");
  if (!phoneDigits) return null;

  const countryDigits = cleanString(countryCode)?.replace(/\D/g, "") || "1";
  return `+${countryDigits}${phoneDigits}`;
};

export const validateLoadFormData = (formData: NegotiationFormData) => {
  if (!cleanString(formData.load_id)) {
    return "Missing required field: load_id";
  }

  if (!cleanString(formData.broker_name)) {
    return "Missing required field: broker_name";
  }

  const origin = parseLocation(formData.origin_location);
  if (!origin.city) {
    return "Origin location must include a city";
  }

  const destination = parseLocation(formData.destination_location);
  if (!destination.city) {
    return "Destination location must include a city";
  }

  const startRate = parseNumeric(formData.broker_initial_offer);
  const bookNowRate = parseNumeric(formData.broker_target_rate);
  const maxRate = parseNumeric(formData.broker_max_rate);

  if (startRate === null) {
    return "Broker initial offer is required";
  }

  if (bookNowRate === null) {
    return "Broker target rate is required";
  }

  if (maxRate === null) {
    return "Broker max rate is required";
  }

  if (startRate < 0 || bookNowRate < 0 || maxRate < 0) {
    return "Rate fields must be non-negative";
  }

  if (bookNowRate < startRate) {
    return "Broker target rate must be greater than or equal to the initial offer";
  }

  if (maxRate < bookNowRate) {
    return "Broker max rate must be greater than or equal to the target rate";
  }

  if (!cleanString(formData.transfer_call_to)) {
    return "Missing required field: transfer_call_to";
  }

  if (!cleanString(formData.transfer_country_code)) {
    return "Missing required field: transfer_country_code";
  }

  return null;
};

const buildLoadColumns = (formData: NegotiationFormData) => {
  const requirements = cleanString(formData.requirements);
  const specialRequirements =
    formData.tracker_required && requirements?.toLowerCase().includes("tracker required") !== true
      ? [requirements, "Tracker required"].filter(Boolean).join("\n")
      : requirements;

  return {
    load_number: cleanString(formData.load_id),
    mode_name: "Van",
    equipment_type_name: "Dry Van 53'",
    kch_load_type: "Truckload",
    kch_service_level: "Standard",
    load_status: "Unassigned",
    load_priority: "3",
    ready_to_cover: true,
    load_posting_description: null,
    special_requirements: specialRequirements,
    hazardous_materials: false,
    customer_name: cleanString(formData.customer_name),
    customer_quote_total: parseNumeric(formData.broker_target_rate),
    customer_quote_status: "Won",
    max_pay_amount: parseNumeric(formData.broker_max_rate),
    offer_rate: parseNumeric(formData.broker_initial_offer),
    carrier_sales_rep_phone: buildE164Phone(
      formData.transfer_country_code,
      formData.transfer_call_to
    ),
  };
};

const buildStopRows = (formData: NegotiationFormData) => {
  const loadNumber = cleanString(formData.load_id);
  const origin = parseLocation(formData.origin_location);
  const destination = parseLocation(formData.destination_location);

  return [
    {
      load_number: loadNumber,
      stop_number: 1,
      expected_date: parseDatePart(formData.pickup_time),
      appointment_time: parseTimePart(formData.pickup_time),
      appointment_time_scheduled: Boolean(parseTimePart(formData.pickup_time)),
      stop_city: origin.city ?? null,
      state_code: origin.state ?? null,
      country_code: origin.country ?? "US",
      is_pickup: true,
      is_dropoff: false,
    },
    {
      load_number: loadNumber,
      stop_number: 2,
      expected_date: parseDatePart(formData.delivery_time),
      appointment_time: parseTimePart(formData.delivery_time),
      appointment_time_scheduled: Boolean(parseTimePart(formData.delivery_time)),
      stop_city: destination.city ?? null,
      state_code: destination.state ?? null,
      country_code: destination.country ?? "US",
      is_pickup: false,
      is_dropoff: true,
    },
  ];
};

export const createLoadsService = (client: SupabaseClient) => ({
  getAuthenticatedUser: () => client.auth.getUser(),

  getUserOrgId: (userId: string) =>
    client.from("users").select("org_id").eq("user_id", userId).single<{ org_id: string }>(),

  create: async (params: { orgId: string; formData: NegotiationFormData }) => {
    const loadResult = await client.from("loads").insert(buildLoadColumns(params.formData)).select().single();
    if (loadResult.error) return loadResult;

    const stopsResult = await client.from("stops").insert(buildStopRows(params.formData));
    if (stopsResult.error) {
      return { data: loadResult.data, error: stopsResult.error };
    }

    return loadResult;
  },
});
