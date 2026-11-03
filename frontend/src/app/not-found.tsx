import Link from "next/link";
export default function NotFound() {
  return (
    <div className="empty-state">
      <h1>Page not found</h1>
      <p>Open the company explorer to find an available report.</p>
      <Link className="btn" href="/companies">
        Open explorer
      </Link>
    </div>
  );
}
