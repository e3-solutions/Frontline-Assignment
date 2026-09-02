-- COR-1167: Align Supabase with the final KCH load/stops contract.
--
-- The runtime now treats public.loads.load_number as the canonical load key.
-- Related tables keep their existing text load_id columns, but those values are
-- expected to equal loads.load_number. Stops are linked by
-- stops(load_number, stop_number), with stop_city as the city field.

CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA extensions;
SET search_path TO public, extensions;

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS public.loads (
  load_number text NOT NULL,
  salesforce_load_id text NULL,
  is_ghost_load boolean NOT NULL DEFAULT false,
  mode_name text NULL,
  equipment_type_name text NULL,
  kch_load_type text NULL,
  kch_service_level text NULL,
  load_status text NULL,
  load_priority text NULL,
  ready_to_cover boolean NULL,
  distance_miles double precision NULL,
  total_weight double precision NULL,
  cargo_summary text NULL,
  commodity_description_posting text NULL,
  load_posting_description text NULL,
  special_requirements text NULL,
  hazardous_materials boolean NULL,
  temperature_setting_minimum double precision NULL,
  temperature_setting_maximum double precision NULL,
  command_center_branch text NULL,
  carrier_sales_rep_phone text NULL,
  carrier_sales_rep_email text NULL,
  customer_name text NULL,
  customer_quote_total numeric(18, 2) NULL,
  customer_quote_status text NULL,
  max_pay_amount numeric(18, 2) NULL,
  offer_rate numeric(18, 2) NULL,
  tender_accept_link text NULL,
  carrier_only_quote_total numeric(18, 2) NULL,
  carrier_mc_number text NULL,
  carrier_usdot_number text NULL,
  posted_to_dat boolean NULL,
  posted_to_highway boolean NULL,
  posted_to_truckstop boolean NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT loads_pkey PRIMARY KEY (load_number),
  CONSTRAINT loads_salesforce_load_id_key UNIQUE (salesforce_load_id),
  CONSTRAINT loads_load_number_check CHECK (btrim(load_number) <> '')
);

ALTER TABLE public.loads
  ADD COLUMN IF NOT EXISTS load_number text,
  ADD COLUMN IF NOT EXISTS salesforce_load_id text,
  ADD COLUMN IF NOT EXISTS is_ghost_load boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS mode_name text,
  ADD COLUMN IF NOT EXISTS equipment_type_name text,
  ADD COLUMN IF NOT EXISTS kch_load_type text,
  ADD COLUMN IF NOT EXISTS kch_service_level text,
  ADD COLUMN IF NOT EXISTS load_status text,
  ADD COLUMN IF NOT EXISTS load_priority text,
  ADD COLUMN IF NOT EXISTS ready_to_cover boolean,
  ADD COLUMN IF NOT EXISTS distance_miles double precision,
  ADD COLUMN IF NOT EXISTS total_weight double precision,
  ADD COLUMN IF NOT EXISTS cargo_summary text,
  ADD COLUMN IF NOT EXISTS commodity_description_posting text,
  ADD COLUMN IF NOT EXISTS load_posting_description text,
  ADD COLUMN IF NOT EXISTS special_requirements text,
  ADD COLUMN IF NOT EXISTS hazardous_materials boolean,
  ADD COLUMN IF NOT EXISTS temperature_setting_minimum double precision,
  ADD COLUMN IF NOT EXISTS temperature_setting_maximum double precision,
  ADD COLUMN IF NOT EXISTS command_center_branch text,
  ADD COLUMN IF NOT EXISTS carrier_sales_rep_phone text,
  ADD COLUMN IF NOT EXISTS carrier_sales_rep_email text,
  ADD COLUMN IF NOT EXISTS customer_name text,
  ADD COLUMN IF NOT EXISTS customer_quote_total numeric(18, 2),
  ADD COLUMN IF NOT EXISTS customer_quote_status text,
  ADD COLUMN IF NOT EXISTS max_pay_amount numeric(18, 2),
  ADD COLUMN IF NOT EXISTS offer_rate numeric(18, 2),
  ADD COLUMN IF NOT EXISTS tender_accept_link text,
  ADD COLUMN IF NOT EXISTS carrier_only_quote_total numeric(18, 2),
  ADD COLUMN IF NOT EXISTS carrier_mc_number text,
  ADD COLUMN IF NOT EXISTS carrier_usdot_number text,
  ADD COLUMN IF NOT EXISTS posted_to_dat boolean,
  ADD COLUMN IF NOT EXISTS posted_to_highway boolean,
  ADD COLUMN IF NOT EXISTS posted_to_truckstop boolean,
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

UPDATE public.loads
SET is_ghost_load = false
WHERE is_ghost_load IS NULL;

UPDATE public.loads
SET created_at = now()
WHERE created_at IS NULL;

UPDATE public.loads
SET updated_at = now()
WHERE updated_at IS NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM public.loads
    WHERE load_number IS NULL
       OR btrim(load_number) = ''
  ) THEN
    RAISE EXCEPTION 'public.loads.load_number must be populated before enforcing the KCH schema';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.loads
    GROUP BY load_number
    HAVING count(*) > 1
  ) THEN
    RAISE EXCEPTION 'public.loads.load_number must be unique before enforcing the KCH schema';
  END IF;
END;
$$;

ALTER TABLE public.loads
  ALTER COLUMN load_number SET NOT NULL,
  ALTER COLUMN is_ghost_load SET DEFAULT false,
  ALTER COLUMN is_ghost_load SET NOT NULL,
  ALTER COLUMN created_at SET DEFAULT now(),
  ALTER COLUMN created_at SET NOT NULL,
  ALTER COLUMN updated_at SET DEFAULT now(),
  ALTER COLUMN updated_at SET NOT NULL;

DO $$
BEGIN
  IF to_regclass('public.loads_legacy') IS NOT NULL
     AND EXISTS (
       SELECT 1
       FROM pg_constraint
       WHERE conrelid = 'public.loads_legacy'::regclass
         AND conname = 'loads_pkey'
     )
     AND to_regclass('public.loads_legacy_pkey') IS NULL THEN
    ALTER TABLE public.loads_legacy
      RENAME CONSTRAINT loads_pkey TO loads_legacy_pkey;
  END IF;
END;
$$;

DO $$
DECLARE
  current_pkey_name text;
  current_pkey_columns text[];
BEGIN
  SELECT c.conname, array_agg(a.attname ORDER BY ord.ordinality)
  INTO current_pkey_name, current_pkey_columns
  FROM pg_constraint c
  JOIN unnest(c.conkey) WITH ORDINALITY AS ord(attnum, ordinality) ON true
  JOIN pg_attribute a
    ON a.attrelid = c.conrelid
   AND a.attnum = ord.attnum
  WHERE c.conrelid = 'public.loads'::regclass
    AND c.contype = 'p'
  GROUP BY c.conname;

  IF current_pkey_columns IS NULL THEN
    ALTER TABLE public.loads
      ADD CONSTRAINT loads_pkey PRIMARY KEY (load_number);
  ELSIF current_pkey_columns <> ARRAY['load_number']::text[] THEN
    EXECUTE format('ALTER TABLE public.loads DROP CONSTRAINT %I', current_pkey_name);
    ALTER TABLE public.loads
      ADD CONSTRAINT loads_pkey PRIMARY KEY (load_number);
  ELSIF current_pkey_name <> 'loads_pkey'
    AND NOT EXISTS (
      SELECT 1
      FROM pg_constraint
      WHERE conrelid = 'public.loads'::regclass
        AND conname = 'loads_pkey'
    )
    AND to_regclass('public.loads_pkey') IS NULL THEN
    EXECUTE format(
      'ALTER TABLE public.loads RENAME CONSTRAINT %I TO loads_pkey',
      current_pkey_name
    );
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.loads'::regclass
      AND conname = 'loads_salesforce_load_id_key'
  )
  AND EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.loads'::regclass
      AND conname = 'load_new_salesforce_load_id_key'
  ) THEN
    ALTER TABLE public.loads
      RENAME CONSTRAINT load_new_salesforce_load_id_key
      TO loads_salesforce_load_id_key;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.loads'::regclass
      AND conname = 'loads_salesforce_load_id_key'
  ) THEN
    ALTER TABLE public.loads
      ADD CONSTRAINT loads_salesforce_load_id_key UNIQUE (salesforce_load_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.loads'::regclass
      AND conname = 'loads_load_number_check'
  )
  AND EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.loads'::regclass
      AND conname = 'load_new_load_number_check'
  ) THEN
    ALTER TABLE public.loads
      RENAME CONSTRAINT load_new_load_number_check
      TO loads_load_number_check;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.loads'::regclass
      AND conname = 'loads_load_number_check'
  ) THEN
    ALTER TABLE public.loads
      ADD CONSTRAINT loads_load_number_check CHECK (btrim(load_number) <> '');
  END IF;
END;
$$;

DROP TRIGGER IF EXISTS load_new_updated_at ON public.loads;
DROP TRIGGER IF EXISTS update_loads_updated_at ON public.loads;
DROP TRIGGER IF EXISTS loads_set_updated_at ON public.loads;

CREATE TRIGGER loads_set_updated_at
  BEFORE UPDATE ON public.loads
  FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS public.stops (
  load_number text NOT NULL,
  stop_number integer NOT NULL,
  salesforce_stop_id text NULL,
  expected_date date NULL,
  shipping_receiving_hours text NULL,
  appointment_time text NULL,
  appointment_time_scheduled boolean NULL,
  stop_city text NULL,
  state_code text NULL,
  postal_code text NULL,
  country_code text NULL,
  coordinates geography NULL,
  is_pickup boolean NULL,
  is_dropoff boolean NULL,
  location_timezone text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT stops_pkey PRIMARY KEY (load_number, stop_number),
  CONSTRAINT stops_salesforce_stop_id_key UNIQUE (salesforce_stop_id),
  CONSTRAINT stops_load_number_fkey
    FOREIGN KEY (load_number)
    REFERENCES public.loads (load_number)
    ON DELETE CASCADE
);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'stops'
      AND column_name = 'city'
  )
  AND NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'stops'
      AND column_name = 'stop_city'
  ) THEN
    ALTER TABLE public.stops RENAME COLUMN city TO stop_city;
  ELSIF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'stops'
      AND column_name = 'city'
  )
  AND EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'stops'
      AND column_name = 'stop_city'
  ) THEN
    UPDATE public.stops
    SET stop_city = city
    WHERE stop_city IS NULL
      AND city IS NOT NULL;
  END IF;
END;
$$;

ALTER TABLE public.stops DROP COLUMN IF EXISTS city;

ALTER TABLE public.stops
  ADD COLUMN IF NOT EXISTS load_number text,
  ADD COLUMN IF NOT EXISTS stop_number integer,
  ADD COLUMN IF NOT EXISTS salesforce_stop_id text,
  ADD COLUMN IF NOT EXISTS expected_date date,
  ADD COLUMN IF NOT EXISTS shipping_receiving_hours text,
  ADD COLUMN IF NOT EXISTS appointment_time text,
  ADD COLUMN IF NOT EXISTS appointment_time_scheduled boolean,
  ADD COLUMN IF NOT EXISTS stop_city text,
  ADD COLUMN IF NOT EXISTS state_code text,
  ADD COLUMN IF NOT EXISTS postal_code text,
  ADD COLUMN IF NOT EXISTS country_code text,
  ADD COLUMN IF NOT EXISTS coordinates geography,
  ADD COLUMN IF NOT EXISTS is_pickup boolean,
  ADD COLUMN IF NOT EXISTS is_dropoff boolean,
  ADD COLUMN IF NOT EXISTS location_timezone text,
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

UPDATE public.stops
SET created_at = now()
WHERE created_at IS NULL;

UPDATE public.stops
SET updated_at = now()
WHERE updated_at IS NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM public.stops
    WHERE load_number IS NULL
       OR btrim(load_number) = ''
       OR stop_number IS NULL
  ) THEN
    RAISE EXCEPTION 'public.stops.load_number and public.stops.stop_number must be populated before enforcing the KCH schema';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.stops
    GROUP BY load_number, stop_number
    HAVING count(*) > 1
  ) THEN
    RAISE EXCEPTION 'public.stops(load_number, stop_number) must be unique before enforcing the KCH schema';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public.stops s
    LEFT JOIN public.loads l
      ON l.load_number = s.load_number
    WHERE l.load_number IS NULL
  ) THEN
    RAISE EXCEPTION 'every public.stops.load_number must exist in public.loads.load_number before adding the KCH FK';
  END IF;
END;
$$;

ALTER TABLE public.stops
  ALTER COLUMN load_number SET NOT NULL,
  ALTER COLUMN stop_number SET NOT NULL,
  ALTER COLUMN created_at SET DEFAULT now(),
  ALTER COLUMN created_at SET NOT NULL,
  ALTER COLUMN updated_at SET DEFAULT now(),
  ALTER COLUMN updated_at SET NOT NULL;

DO $$
DECLARE
  current_pkey_name text;
  current_pkey_columns text[];
BEGIN
  SELECT c.conname, array_agg(a.attname ORDER BY ord.ordinality)
  INTO current_pkey_name, current_pkey_columns
  FROM pg_constraint c
  JOIN unnest(c.conkey) WITH ORDINALITY AS ord(attnum, ordinality) ON true
  JOIN pg_attribute a
    ON a.attrelid = c.conrelid
   AND a.attnum = ord.attnum
  WHERE c.conrelid = 'public.stops'::regclass
    AND c.contype = 'p'
  GROUP BY c.conname;

  IF current_pkey_columns IS NULL THEN
    ALTER TABLE public.stops
      ADD CONSTRAINT stops_pkey PRIMARY KEY (load_number, stop_number);
  ELSIF current_pkey_columns <> ARRAY['load_number', 'stop_number']::text[] THEN
    EXECUTE format('ALTER TABLE public.stops DROP CONSTRAINT %I', current_pkey_name);
    ALTER TABLE public.stops
      ADD CONSTRAINT stops_pkey PRIMARY KEY (load_number, stop_number);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.stops'::regclass
      AND conname = 'stops_salesforce_stop_id_key'
  ) THEN
    ALTER TABLE public.stops
      ADD CONSTRAINT stops_salesforce_stop_id_key UNIQUE (salesforce_stop_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.stops'::regclass
      AND conname = 'stops_load_number_fkey'
  ) THEN
    ALTER TABLE public.stops
      ADD CONSTRAINT stops_load_number_fkey
      FOREIGN KEY (load_number)
      REFERENCES public.loads (load_number)
      ON DELETE CASCADE;
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS stops_salesforce_stop_id_idx
  ON public.stops (salesforce_stop_id)
  WHERE salesforce_stop_id IS NOT NULL;

DROP TRIGGER IF EXISTS update_stops_updated_at ON public.stops;
DROP TRIGGER IF EXISTS stops_set_updated_at ON public.stops;

CREATE TRIGGER stops_set_updated_at
  BEFORE UPDATE ON public.stops
  FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

DO $$
BEGIN
  IF to_regclass('public.calls') IS NOT NULL
     AND EXISTS (
       SELECT 1
       FROM information_schema.columns
       WHERE table_schema = 'public'
         AND table_name = 'calls'
         AND column_name = 'load_id'
     ) THEN
    EXECUTE 'COMMENT ON COLUMN public.calls.load_id IS ''KCH loads.load_number text reference.''';
  END IF;

  IF to_regclass('public.negotiations') IS NOT NULL
     AND EXISTS (
       SELECT 1
       FROM information_schema.columns
       WHERE table_schema = 'public'
         AND table_name = 'negotiations'
         AND column_name = 'load_id'
     ) THEN
    EXECUTE 'COMMENT ON COLUMN public.negotiations.load_id IS ''KCH loads.load_number text reference.''';
  END IF;

  IF to_regclass('public.email_thread') IS NOT NULL
     AND EXISTS (
       SELECT 1
       FROM information_schema.columns
       WHERE table_schema = 'public'
         AND table_name = 'email_thread'
         AND column_name = 'load_id'
     ) THEN
    EXECUTE 'COMMENT ON COLUMN public.email_thread.load_id IS ''KCH loads.load_number text reference.''';
  END IF;
END;
$$;

ALTER TABLE public.loads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stops ENABLE ROW LEVEL SECURITY;

NOTIFY pgrst, 'reload schema';
