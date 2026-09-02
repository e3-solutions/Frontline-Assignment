-- Access for a disposable candidate Supabase instance only.
-- The current load catalog has no org_id. Users with an application profile
-- share this synthetic catalog; use a separate local stack per candidate.

CREATE POLICY local_candidate_catalog_select ON public.loads
    FOR SELECT TO authenticated USING ((SELECT auth_user_org_id()) IS NOT NULL);
CREATE POLICY local_candidate_catalog_insert ON public.loads
    FOR INSERT TO authenticated WITH CHECK ((SELECT auth_user_org_id()) IS NOT NULL);
CREATE POLICY local_candidate_catalog_update ON public.loads
    FOR UPDATE TO authenticated USING ((SELECT auth_user_org_id()) IS NOT NULL)
    WITH CHECK ((SELECT auth_user_org_id()) IS NOT NULL);
CREATE POLICY local_candidate_stops_select ON public.stops
    FOR SELECT TO authenticated USING ((SELECT auth_user_org_id()) IS NOT NULL);
CREATE POLICY local_candidate_stops_insert ON public.stops
    FOR INSERT TO authenticated WITH CHECK ((SELECT auth_user_org_id()) IS NOT NULL);
CREATE POLICY local_candidate_stops_update ON public.stops
    FOR UPDATE TO authenticated USING ((SELECT auth_user_org_id()) IS NOT NULL)
    WITH CHECK ((SELECT auth_user_org_id()) IS NOT NULL);

-- Replace the SELECT policies removed before the historical UUID-to-text
-- load_id conversion. Call ownership no longer depends on a legacy load FK.
CREATE POLICY org_isolation_select ON public.calls
    FOR SELECT TO authenticated USING (org_id = (SELECT auth_user_org_id()));
CREATE POLICY org_isolation_select ON public.negotiations
    FOR SELECT TO authenticated USING (
        call_id IN (SELECT id FROM public.calls WHERE org_id = (SELECT auth_user_org_id()))
    );

-- Make Data API access explicit instead of relying on project defaults.
-- Historical email schema remains available to the backend. Only the existing
-- read-only dashboard thread/interaction views receive authenticated access.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.auth_user_org_id() TO authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT SELECT ON public.users, public.organizations, public.phone_numbers,
    public.calls, public.negotiations, public.email_thread,
    public.email_interactions TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.loads, public.stops, public.invites TO authenticated;
GRANT DELETE ON public.invites TO authenticated;
GRANT UPDATE (full_name) ON public.users TO authenticated;
GRANT UPDATE (name) ON public.organizations TO authenticated;
NOTIFY pgrst, 'reload schema';
