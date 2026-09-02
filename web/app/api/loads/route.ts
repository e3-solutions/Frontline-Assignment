import { NextRequest, NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/src/db/server";
import { createLoadsService, validateLoadFormData } from "@/src/services/supabase/server/loads";
import type { NegotiationFormData } from "@/src/types/dashboard";

export const POST = async (request: NextRequest) => {
  try {
    const body = (await request.json()) as NegotiationFormData;

    const validationError = validateLoadFormData(body);
    if (validationError) {
      return NextResponse.json({ error: validationError }, { status: 400 });
    }

    const client = await createSupabaseServerClient();
    const loadsService = createLoadsService(client);

    const { data: { user }, error: authError } = await loadsService.getAuthenticatedUser();
    if (authError || !user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { data: userData, error: userError } = await loadsService.getUserOrgId(user.id);
    if (userError || !userData) {
      return NextResponse.json({ error: "User profile not found" }, { status: 403 });
    }

    const { data, error } = await loadsService.create({
      orgId: userData.org_id,
      formData: body,
    });

    if (error) {
      return NextResponse.json(
        { error: error.message || "Failed to create load" },
        { status: 500 }
      );
    }

    return NextResponse.json({ data, message: "Load created successfully" }, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Internal server error" },
      { status: 500 }
    );
  }
};
