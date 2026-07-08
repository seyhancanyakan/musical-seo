import Link from "next/link";

export default function NotFound() {
  return (
    <main
      style={{
        minHeight: "60vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
        padding: 32,
        textAlign: "center",
      }}
    >
      <h1 className="nb-h" style={{ fontSize: 48 }}>
        404
      </h1>
      <p>Bu sayfa bulunamadi.</p>
      <Link href="/" className="nb-btn">
        Ana sayfaya don
      </Link>
    </main>
  );
}
