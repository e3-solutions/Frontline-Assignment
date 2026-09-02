import type { SupabaseClient } from "@supabase/supabase-js";

// Dashboard reads come from KCH Supabase `public.loads`. Calls/email_thread are
// queried directly because their `load_id` columns are text references that
// hold `loads.load_number` for post-migration records.
export const createDashboardService = (client: SupabaseClient) => ({
  loads: {
    getAll: () =>
      client
        .from("loads")
        .select(`
          load_number,
          mode_name,
          equipment_type_name,
          total_weight,
          load_posting_description,
          special_requirements,
          offer_rate,
          max_pay_amount,
          customer_name,
          created_at,
          updated_at,
          stops!stops_load_number_fkey (
            stop_number,
            expected_date,
            appointment_time,
            stop_city,
            state_code,
            country_code,
            is_pickup,
            is_dropoff
          )
        `)
        .order("created_at", { ascending: false }),
  },

  calls: {
    getByLoadIds: (loadIds: string[]) =>
      client
        .from("calls")
        .select("id, load_id, end_reason, result, initiated_at, negotiation_result, recording_url")
        .in("load_id", loadIds)
        .order("initiated_at", { ascending: false }),

    // No FK exists between calls.load_id and public.loads.load_number (the
    // legacy FK to loads.id was dropped in migration 20260415000000), so
    // we cannot use PostgREST's embedded select. The mapper at
    // services/dashboard.ts uses calls.load_id directly — it already holds
    // the load_number for any post-migration call.
    getAllWithLoads: () =>
      client
        .from("calls")
        .select(`
          id,
          load_id,
          daily_call_id,
          negotiation_result,
          caller_number,
          caller_country_code,
          initiated_at,
          updated_at,
          ended_at,
          end_reason,
          result,
          transcription,
          recording_url
        `)
        .order("initiated_at", { ascending: false }),
  },

  negotiations: {
    getByLoadIds: (loadIds: string[]) =>
      client
        .from("negotiations")
        .select("id, load_id, agreed_price, created_at, call_id, above_max, carrier_contact_name, carrier_contact_phone")
        .in("load_id", loadIds)
        .order("created_at", { ascending: false }),
  },

  // Same FK story for email_thread — load_id was decoupled from loads.id
  // in migration 20260415000000. The mapper uses email_thread.load_id
  // directly. negotiations is still joinable via thread_id FK.
  emailThreads: {
    getAll: () =>
      client
        .from("email_thread")
        .select(`
          id,
          thread_id,
          client_email,
          subject,
          load_id,
          ended,
          created_at,
          updated_at,
          email_interactions(id, client_response, bot_response, created_at),
          negotiations!left(id, agreed_price, above_max, carrier_contact_name, carrier_contact_phone, created_at)
        `)
        .order("created_at", { ascending: false }),
  },
});
