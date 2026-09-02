import { NextRequest, NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/src/db/server";
import { adminServices } from "@/src/services/supabase/admin";
import type { UserRole } from "@/src/types/auth";

interface CreateUserBody {
  email: string;
  password: string;
  fullName: string;
  role: UserRole;
  orgId: string;
}

export const POST = async (request: NextRequest) => {
  try {
    const client = await createSupabaseServerClient();
    const {
      data: { user: caller },
      error: authError,
    } = await client.auth.getUser();

    if (authError || !caller) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { data: callerProfile, error: profileError } = await client
      .from("users")
      .select("role, org_id")
      .eq("user_id", caller.id)
      .single();

    if (profileError || !callerProfile) {
      return NextResponse.json({ error: "User profile not found" }, { status: 403 });
    }

    if (callerProfile.role !== "admin") {
      return NextResponse.json({ error: "Admin access required" }, { status: 403 });
    }

    const body: CreateUserBody = await request.json();
    const { email, password, fullName, role, orgId } = body;

    if (!email || !password || !fullName || !role || !orgId) {
      return NextResponse.json({ error: "All fields are required" }, { status: 400 });
    }

    if (orgId !== callerProfile.org_id) {
      return NextResponse.json({ error: "Cannot create users for another organization" }, { status: 403 });
    }

    const { data: authData, error: createAuthError } = await adminServices.auth.createUser({
      email,
      password,
    });

    if (createAuthError || !authData.user) {
      return NextResponse.json(
        { error: createAuthError?.message || "Failed to create account" },
        { status: 400 }
      );
    }

    const { error: userError } = await adminServices.users.create({
      userId: authData.user.id,
      fullName,
      orgId,
      role,
    });

    if (userError) {
      await adminServices.auth.deleteUser(authData.user.id);
      return NextResponse.json(
        { error: userError.message || "Failed to create user profile" },
        { status: 400 }
      );
    }

    return NextResponse.json({ success: true });
  } catch {
    return NextResponse.json({ error: "Failed to create user account" }, { status: 500 });
  }
};
