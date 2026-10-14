import { Calculator } from "@/components/Calculator";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Next Bracket</h1>
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          Score your PFA from the official charts. Enter results for each component.
        </p>
      </header>
      <Calculator />
    </main>
  );
}
