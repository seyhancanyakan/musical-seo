"use client";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="tr">
      <body>
        <main
          style={{
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 16,
            padding: 32,
            textAlign: "center",
            background: "#f5f5f0",
            color: "#000",
            fontFamily: "Segoe UI, Arial, sans-serif",
          }}
        >
          <h1
            style={{
              fontFamily: "Arial Black, Segoe UI Black, Arial, sans-serif",
              textTransform: "uppercase",
              fontSize: 40,
            }}
          >
            Bir hata olustu
          </h1>
          <p>Beklenmeyen bir sorun oldu. Lutfen tekrar deneyin.</p>
          <button
            onClick={() => reset()}
            style={{
              display: "inline-block",
              border: "3px solid #000",
              boxShadow: "6px 6px 0 #000",
              background: "#2d6bff",
              color: "#fff",
              fontFamily: "Arial Black, Arial, sans-serif",
              textTransform: "uppercase",
              fontSize: 14,
              padding: "12px 22px",
              cursor: "pointer",
            }}
          >
            Tekrar dene
          </button>
        </main>
      </body>
    </html>
  );
}
