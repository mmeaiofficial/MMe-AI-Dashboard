"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { googleSignInUrl } from "@/lib/api";

function SignIn() {
  const params = useSearchParams();
  const error = params.get("error");
  const invite = params.get("invite");
  return (
    <main className="grid min-h-screen place-items-center px-4">
      <div className="card w-full max-w-sm space-y-5">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand font-bold text-white">M</span>
          <div><div className="font-semibold">MME OS</div><div className="text-xs text-slate-500">Internal Business OS</div></div>
        </div>
        <h1 className="text-2xl font-semibold">Sign in</h1>
        <p className="text-sm text-slate-600">
          {invite ? "You've been invited to MME OS. Sign in with the Google account the invitation was sent to." : "Use your MME Google account."}
        </p>
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {/* A full-page navigation: the API sets the session cookie on its callback. */}
        <a className="btn w-full justify-center py-2.5" href={googleSignInUrl("/", invite)}>Sign in with Google</a>
        <p className="text-xs text-slate-500">Access is by invitation. Admin accounts also need an authenticator app.</p>
      </div>
    </main>
  );
}

export default function Page() {
  return <Suspense><SignIn /></Suspense>;
}
