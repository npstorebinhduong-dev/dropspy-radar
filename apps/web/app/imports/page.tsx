import Link from "next/link";
import DataWorkspace from "../../components/DataWorkspace";
export default function Page() {
  return (
    <main>
      <p>
        <Link href="/">← DROPSpy Radar dashboard</Link>
      </p>
      <DataWorkspace initialTab="import" />
    </main>
  );
}
