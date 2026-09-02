-- Fix users RLS to allow viewing team members in same org

DROP POLICY IF EXISTS "select_same_org" ON users;

CREATE OR REPLACE FUNCTION auth_user_org_id() RETURNS UUID AS $$
  SELECT org_id FROM users WHERE user_id = auth.uid()
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

CREATE POLICY "select_same_org" ON users
  FOR SELECT USING (org_id = auth_user_org_id());
