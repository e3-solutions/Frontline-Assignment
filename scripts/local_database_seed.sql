-- Synthetic installation data only. The default 555 numbers cannot receive
-- calls; replace them through the setup command for a real development call.
INSERT INTO public.organizations (id, name)
VALUES ('00000000-0000-4000-8000-000000000001', 'Candidate Sandbox')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.phone_numbers (phone_number, org_id, label)
VALUES ('__PHONE_NUMBER__', '00000000-0000-4000-8000-000000000001', 'Candidate development line')
ON CONFLICT (phone_number) DO NOTHING;

INSERT INTO public.loads (
    load_number, mode_name, equipment_type_name, load_status, ready_to_cover,
    customer_name, offer_rate, max_pay_amount, total_weight, cargo_summary,
    hazardous_materials, carrier_sales_rep_phone
)
VALUES (
    'DEMO-1001', 'Van', 'Dry Van 53 ft', 'Unassigned', true,
    'Example Shipper', 1000, 1200, 10000, 'Packaged goods',
    false, '__TRANSFER_PHONE__'
)
ON CONFLICT (load_number) DO UPDATE
SET carrier_sales_rep_phone = COALESCE(__TRANSFER_UPDATE_PHONE__, public.loads.carrier_sales_rep_phone);

INSERT INTO public.stops (
    load_number, stop_number, expected_date, appointment_time, stop_city,
    state_code, country_code, is_pickup, is_dropoff, location_timezone
)
VALUES
    ('DEMO-1001', 1, CURRENT_DATE + 1, '09:00', 'Chicago', 'IL', 'US', true, false, 'America/Chicago'),
    ('DEMO-1001', 2, CURRENT_DATE + 2, '14:00', 'Indianapolis', 'IN', 'US', false, true, 'America/Indiana/Indianapolis')
ON CONFLICT (load_number, stop_number) DO NOTHING;
