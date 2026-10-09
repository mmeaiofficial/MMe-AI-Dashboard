import type { ReactNode } from "react";
import { LogoMark } from "@/components/ui";

/** Shared frame for the signed-out pages: the sign-in card beside two flat tiles matching the dashboard. */
export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <div className="grid w-full max-w-4xl gap-4 md:grid-cols-[1fr_1fr]">
        <div className="card space-y-6 p-8 md:p-10">
          <div className="flex items-center gap-3">
            <LogoMark size={44} />
            <div className="leading-tight"><div className="font-semibold">MME OS</div><div className="text-sm text-ink-faint">Internal Business OS</div></div>
          </div>
          {children}
        </div>
        <div className="hidden grid-rows-[1.2fr_1fr] gap-4 md:grid" aria-hidden="true">
          <div className="flex flex-col justify-end rounded-4xl bg-brand-fill p-8 text-on-brand">
            <div className="text-3xl font-medium leading-tight tracking-tight">One place for<br />people, teams<br />and access.</div>
          </div>
          <div className="flex flex-col justify-end rounded-4xl bg-well p-8 ring-1 ring-border">
            <div className="text-sm text-ink-soft">Every sign-in and access change is recorded in the audit log.</div>
          </div>
        </div>
      </div>
    </main>
  );
}
