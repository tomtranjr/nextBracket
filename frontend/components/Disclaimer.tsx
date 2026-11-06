import { FULL_DISCLAIMER, shortDisclaimer } from "@/lib/disclaimer";

type Props = { variant: "short"; chartName: string; effectiveDate: string } | { variant: "full" };

/** The unofficial-tool notice: low weight, but zinc-600/400 stays readable in both modes. */
export function Disclaimer(props: Props) {
  if (props.variant === "full") {
    return <p className="text-xs text-zinc-600 dark:text-zinc-400">{FULL_DISCLAIMER}</p>;
  }
  return (
    <p className="text-sm text-zinc-600 dark:text-zinc-400">
      {shortDisclaimer(props.chartName, props.effectiveDate)}
    </p>
  );
}

/** The footer on every page. */
export function SiteFooter() {
  return (
    <footer className="mx-auto w-full max-w-xl border-t border-zinc-200 px-4 py-6 dark:border-zinc-800">
      <Disclaimer variant="full" />
    </footer>
  );
}
