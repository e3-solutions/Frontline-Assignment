import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// Routes that don't require authentication
const publicRoutes = ["/login", "/register"];

// Routes that are always accessible (API routes, static files, etc.)
const ignoredRoutes = ["/api", "/_next", "/favicon.ico"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip middleware for ignored routes
  if (ignoredRoutes.some((route) => pathname.startsWith(route))) {
    return NextResponse.next();
  }

  let supabaseResponse = NextResponse.next({
    request,
  });

  // Middleware runs on the server, so it can read runtime env. Prefer the
  // unprefixed Railway-side vars; fall back to the build-time-baked
  // NEXT_PUBLIC_* values for local dev or environments that haven't been
  // migrated to the runtime vars yet. `||` (not `??`) so an empty runtime
  // var still falls back to the baked value.
  const supabaseUrl =
    process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const supabaseAnonKey =
    process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

  const supabase = createServerClient(
    supabaseUrl,
    supabaseAnonKey,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          supabaseResponse = NextResponse.next({
            request,
          });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // Refresh session if expired
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const isPublicRoute = publicRoutes.some((route) => pathname.startsWith(route));

  // If user is not logged in and trying to access protected route
  if (!user && !isPublicRoute) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  // If user is logged in and trying to access auth pages, redirect to home
  if (user && isPublicRoute) {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * Feel free to modify this pattern to include more paths.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
