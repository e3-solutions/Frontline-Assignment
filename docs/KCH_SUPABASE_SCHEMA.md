# Supabase load schema contract

The voice service reads load data from `public.loads` and linked `public.stops`. `shared/src/negotiation_db_service.py` defines the query shape, and `shared/src/load_normalization.py` maps these records into the voice prompt's load context.

## Load reads

- `public.loads.load_number` is the canonical key and customer-facing reference number.
- `public.loads.salesforce_load_id` is a fallback lookup identifier.
- `public.stops` links to loads with `stops.load_number -> loads.load_number`.
- Stop embedding uses the named foreign key `stops!stops_load_number_fkey`.
- Stop city is stored in `public.stops.stop_city`.
- Pricing reads use `public.loads.offer_rate` and `public.loads.max_pay_amount`.
- Human transfer routing reads `public.loads.carrier_sales_rep_phone`.
- Lane searches filter `ready_to_cover = true` and match pickup/dropoff stop locations.
- Internal call and negotiation records link by text `load_id = loads.load_number`.

## Application data

The remaining application also uses organization and phone-number mappings, call records, negotiations, and carrier phone lookups. The voice service accesses these using `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`; the dashboard uses its own Supabase configuration.

Historical migrations are stored under `web/supabase/migrations/` and `supabase/migrations/`. Their schema dependencies must remain intact when preparing a clean database. In particular, text load references are required by current call and negotiation writes. The current load schema must be available before making live calls.

This document describes the application contract. Database access policies and credentials must match the development database being used.
