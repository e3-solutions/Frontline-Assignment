-- Materialize the negotiated load contract directly on public.loads while
-- preserving the legacy data JSON for backwards compatibility.

ALTER TABLE public.loads
    ADD COLUMN IF NOT EXISTS origin_city TEXT,
    ADD COLUMN IF NOT EXISTS origin_state TEXT,
    ADD COLUMN IF NOT EXISTS origin_country TEXT,
    ADD COLUMN IF NOT EXISTS origin_timezone TEXT,
    ADD COLUMN IF NOT EXISTS destination_city TEXT,
    ADD COLUMN IF NOT EXISTS destination_state TEXT,
    ADD COLUMN IF NOT EXISTS destination_country TEXT,
    ADD COLUMN IF NOT EXISTS destination_timezone TEXT,
    ADD COLUMN IF NOT EXISTS pickup_time TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dropoff_time TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS equipment TEXT,
    ADD COLUMN IF NOT EXISTS commodity TEXT,
    ADD COLUMN IF NOT EXISTS weight TEXT,
    ADD COLUMN IF NOT EXISTS tracker_required BOOLEAN,
    ADD COLUMN IF NOT EXISTS special_instructions TEXT,
    ADD COLUMN IF NOT EXISTS start_rate NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS book_now_rate NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS max_rate NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS booked_rate NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS customer_name TEXT,
    ADD COLUMN IF NOT EXISTS transfer_call_to TEXT,
    ADD COLUMN IF NOT EXISTS transfer_country_code TEXT;

UPDATE public.loads
SET
    origin_city = COALESCE(
        origin_city,
        NULLIF(data #>> '{origin,city}', ''),
        NULLIF(BTRIM(SPLIT_PART(data ->> 'origin_location', ',', 1)), '')
    ),
    origin_state = COALESCE(
        origin_state,
        NULLIF(data #>> '{origin,state}', ''),
        NULLIF(BTRIM(SPLIT_PART(data ->> 'origin_location', ',', 2)), '')
    ),
    origin_country = COALESCE(
        origin_country,
        NULLIF(data #>> '{origin,country}', ''),
        NULLIF(BTRIM(SPLIT_PART(data ->> 'origin_location', ',', 3)), '')
    ),
    origin_timezone = COALESCE(
        origin_timezone,
        NULLIF(data #>> '{origin,timezone}', '')
    ),
    destination_city = COALESCE(
        destination_city,
        NULLIF(data #>> '{destination,city}', ''),
        NULLIF(BTRIM(SPLIT_PART(data ->> 'destination_location', ',', 1)), '')
    ),
    destination_state = COALESCE(
        destination_state,
        NULLIF(data #>> '{destination,state}', ''),
        NULLIF(BTRIM(SPLIT_PART(data ->> 'destination_location', ',', 2)), '')
    ),
    destination_country = COALESCE(
        destination_country,
        NULLIF(data #>> '{destination,country}', ''),
        NULLIF(BTRIM(SPLIT_PART(data ->> 'destination_location', ',', 3)), '')
    ),
    destination_timezone = COALESCE(
        destination_timezone,
        NULLIF(data #>> '{destination,timezone}', '')
    ),
    pickup_time = COALESCE(
        pickup_time,
        NULLIF(
            COALESCE(data ->> 'pickupTime', data ->> 'pickup_time', data ->> 'pickup_date'),
            ''
        )::timestamptz
    ),
    dropoff_time = COALESCE(
        dropoff_time,
        NULLIF(
            COALESCE(data ->> 'dropoffTime', data ->> 'delivery_time', data ->> 'dropoff_date'),
            ''
        )::timestamptz
    ),
    equipment = COALESCE(
        equipment,
        NULLIF(COALESCE(data ->> 'equipment', data ->> 'equipment_type'), '')
    ),
    commodity = COALESCE(
        commodity,
        NULLIF(data ->> 'commodity', '')
    ),
    weight = COALESCE(
        weight,
        NULLIF(data ->> 'weight', '')
    ),
    tracker_required = COALESCE(
        CASE
            WHEN data ? 'tracker_required' THEN NULLIF(data ->> 'tracker_required', '')::boolean
            WHEN data ? 'trackerRequired' THEN NULLIF(data ->> 'trackerRequired', '')::boolean
            ELSE NULL
        END,
        tracker_required
    ),
    special_instructions = COALESCE(
        special_instructions,
        NULLIF(COALESCE(data ->> 'specialInstructions', data ->> 'requirements'), '')
    ),
    start_rate = COALESCE(
        start_rate,
        NULLIF(COALESCE(data ->> 'startRate', data ->> 'broker_initial_offer'), '')::numeric(10, 2)
    ),
    book_now_rate = COALESCE(
        book_now_rate,
        NULLIF(COALESCE(data ->> 'bookNowRate', data ->> 'broker_target_rate'), '')::numeric(10, 2)
    ),
    max_rate = COALESCE(
        max_rate,
        NULLIF(COALESCE(data ->> 'maxRate', data ->> 'broker_max_rate'), '')::numeric(10, 2)
    ),
    booked_rate = COALESCE(
        booked_rate,
        NULLIF(data ->> 'bookedRate', '')::numeric(10, 2)
    ),
    customer_name = COALESCE(
        customer_name,
        NULLIF(COALESCE(data ->> 'customerName', data ->> 'customer_name'), '')
    ),
    transfer_call_to = COALESCE(
        transfer_call_to,
        NULLIF(COALESCE(data ->> 'transfer_call_to', data ->> 'transferCallTo'), '')
    ),
    transfer_country_code = COALESCE(
        transfer_country_code,
        NULLIF(COALESCE(data ->> 'transfer_country_code', data ->> 'transferCountryCode'), '')
    )
WHERE data IS NOT NULL;

UPDATE public.loads
SET tracker_required = FALSE
WHERE tracker_required IS NULL;

ALTER TABLE public.loads
    ALTER COLUMN tracker_required SET DEFAULT FALSE,
    ALTER COLUMN tracker_required SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.loads
        WHERE load_id IS NOT NULL
        GROUP BY org_id, load_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'Cannot create unique index on public.loads(org_id, load_id): duplicate values exist';
    END IF;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_loads_org_id_load_id_unique
    ON public.loads(org_id, load_id);
