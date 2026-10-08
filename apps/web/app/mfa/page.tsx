"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SessionProvider, useSession } from "@/components/session";
import { api, ApiError } from "@/lib/api";

function Mfa() {
  const { me, refresh, signOut } = useSession();
  const router = useRouter();
  const [setup, setSetup] = useState<{ otpauth_uri: string; secret: string } | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!me) return null;
  const enrolling = !me.mfa.enrolled;

  async function begin() {
    setError(null);
    try { setSetup(await api.post("/auth/mfa/setup")); } catch (e) { setError((e as ApiError).message); }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await api.post(enrolling ? "/auth/mfa/confirm" : "/auth/mfa/verify", { code });
      await refresh();
      router.replace("/");
    } catch (err) { setError((err as ApiError).message); } finally { setBusy(false); }
  }

  return (
    <main className="grid min-h-screen place-items-center px-4">
      <div className="card w-full max-w-md space-y-4">
        <h1 className="text-xl font-semibold">{enrolling ? "Set up your authenticator" : "Enter your authenticator code"}</h1>
        {enrolling && !setup && (
          <>
            <p className="text-sm text-slate-600">Your account can change access or company settings, so it needs a second step. Use Google Authenticator, Microsoft Authenticator or 1Password.</p>
            <button className="btn-primary" onClick={begin}>Start setup</button>
          </>
        )}
        {enrolling && setup && (
          <div className="space-y-2 text-sm">
            <p>In your authenticator app, add an account with this key:</p>
            <code className="block break-all rounded-lg bg-slate-100 p-3 font-mono">{setup.secret}</code>
            <p className="text-slate-500">On a phone with the app installed, you can <a className="text-brand underline" href={setup.otpauth_uri}>open this link</a> instead.</p>
          </div>
        )}
        {(!enrolling || setup) && (
          <form onSubmit={submit} className="space-y-3">
            <label className="label" htmlFor="code">6-digit code</label>
            <input id="code" className="input font-mono tracking-widest" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
              value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} autoFocus />
            {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
            <button className="btn-primary" disabled={busy || code.length !== 6}>{enrolling ? "Confirm" : "Continue"}</button>
          </form>
        )}
        <button className="text-xs text-slate-500 underline" onClick={signOut}>Sign out</button>
      </div>
    </main>
  );
}

export default function Page() {
  return <SessionProvider requireMfa={false}><Mfa /></SessionProvider>;
}
